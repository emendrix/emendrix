"""The personal feed over the record fixture: minted once, served without a session, rotated."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID
from xml.etree.ElementTree import fromstring

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from emendrix_service import DISCLAIMER
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import AuditAction, Cadence, ItemKind
from emendrix_service.db.tables import AuditLog, Change, Event, User, Watchlist
from emendrix_service.db.watchlists import add_item, create_watchlist
from tests.conftest import NOW, SITE_URL
from tests.test_svc_watch_fixtures import HOUSE, csrf, sign_in
from tests.test_svc_watch_fixtures import loaded as loaded

pytestmark = pytest.mark.anyio

NS = "{http://www.w3.org/2005/Atom}"
FEED = re.compile(r"<code>https://example\.org(/u/feed/([A-Za-z0-9_-]{22})\.xml)</code>")


@pytest.fixture
async def reader(service_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A feed reader: a client of the same app that never holds a cookie."""
    async with AsyncClient(transport=ASGITransport(app=service_app), base_url=SITE_URL) as http:
        yield http


async def a_watchlist(db: Db, client: AsyncClient, email: str = "owner@example.org") -> UUID:
    user = await sign_in(db, client, email)
    async with db.transaction() as tx:
        watchlist = await create_watchlist(tx, user, "Flat rules", NOW)
        assert await add_item(tx, user, watchlist, ItemKind.ACT, "toy", HOUSE, None, NOW)
    return watchlist


async def rotate(client: AsyncClient, watchlist: UUID) -> str:
    token = await csrf(client)
    page = await client.post(
        "/account/feed/rotate", data={"csrf": token, "watchlist_id": str(watchlist)}
    )
    assert page.status_code == 200, page.text
    assert "Copy it now; it is not shown again. Rotating it again turns this address off." in (
        page.text
    )
    found = FEED.search(page.text)
    assert found is not None
    return found.group(1)


async def test_svc_feed_is_served_by_token_with_the_public_entry_ids(
    client: AsyncClient, reader: AsyncClient, loaded: Db, caplog: pytest.LogCaptureFixture
) -> None:
    watchlist = await a_watchlist(loaded, client)
    assert "Create a personal feed" in (await client.get("/account/")).text
    path = await rotate(client, watchlist)
    assert "Replace the feed address" in (await client.get("/account/")).text
    with caplog.at_level(logging.INFO):
        response = await reader.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/atom+xml; charset=utf-8"
    assert response.headers["cache-control"] == "private, no-store"
    assert "set-cookie" not in response.headers and not reader.cookies
    root = fromstring(response.content)
    assert root.findtext(f"{NS}id") == f"{SITE_URL}/u/feed/{watchlist}.xml"
    assert root.findtext(f"{NS}subtitle") == DISCLAIMER
    async with loaded.transaction() as tx:
        expected = {
            f"{url}#{anchor}"
            for url, anchor in await tx.execute(
                select(Event.url, Change.anchor)
                .join(Change, Change.event_key == Event.event_key)
                .where(Event.act_key == HOUSE)
            )
        }
    ids = [entry.findtext(f"{NS}id") for entry in root.findall(f"{NS}entry")]
    assert ids and set(ids) == expected and len(ids) == len(expected)
    ours = "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith("emendrix_service")
    )
    assert "/u/feed/- 200" in ours and path.split("/")[-1] not in ours


async def test_svc_feed_rotating_turns_the_old_address_off(
    client: AsyncClient, reader: AsyncClient, loaded: Db
) -> None:
    watchlist = await a_watchlist(loaded, client)
    first = await rotate(client, watchlist)
    second = await rotate(client, watchlist)
    assert first != second
    assert (await reader.get(first)).status_code == 410
    assert (await reader.get(second)).status_code == 200
    assert (await reader.get("/u/feed/never-issued-AAAAAAAAAA.xml")).status_code == 410
    async with loaded.transaction() as tx:
        rotations = await tx.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == AuditAction.FEED_ROTATE)
        )
    assert rotations == 2


async def test_svc_feed_another_readers_watchlist_cannot_be_given_a_feed(
    client: AsyncClient, reader: AsyncClient, loaded: Db
) -> None:
    theirs = await a_watchlist(loaded, reader, "other@example.org")
    reader.cookies.clear()
    await a_watchlist(loaded, client)
    token = await csrf(client)
    for wanted in (str(theirs), "not-an-id"):
        refused = await client.post(
            "/account/feed/rotate", data={"csrf": token, "watchlist_id": wanted}
        )
        assert refused.status_code == 404
    async with loaded.transaction() as tx:
        assert (
            await tx.scalar(select(Watchlist.feed_token_hash).where(Watchlist.id == theirs)) is None
        )


async def test_svc_feed_a_paused_or_unmailed_watchlist_keeps_its_feed(
    client: AsyncClient, reader: AsyncClient, loaded: Db
) -> None:
    watchlist = await a_watchlist(loaded, client)
    path = await rotate(client, watchlist)
    async with loaded.transaction() as tx:
        row = await tx.get_one(Watchlist, watchlist)
        row.paused, row.cadence = True, Cadence.NONE
    assert (await reader.get(path)).status_code == 200


async def test_svc_feed_a_fetch_moves_last_seen_at_most_daily(
    client: AsyncClient, reader: AsyncClient, loaded: Db, clock: FixedClock
) -> None:
    watchlist = await a_watchlist(loaded, client)
    path = await rotate(client, watchlist)

    async def seen() -> object:
        async with loaded.transaction() as tx:
            return await tx.scalar(select(User.last_seen_at))

    await reader.get(path)
    assert await seen() == NOW
    clock.advance(timedelta(days=2))
    await reader.get(path)
    assert await seen() == NOW + timedelta(days=2)
    clock.advance(timedelta(hours=20))
    await reader.get(path)
    assert await seen() == NOW + timedelta(days=2)
