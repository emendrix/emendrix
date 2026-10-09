"""The watchlist editor: every change works for its owner, and for nobody else."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence
from emendrix_service.db.tables import WatchItem, Watchlist
from tests.conftest import SITE_URL
from tests.test_svc_watch_fixtures import GARDEN, HOUSE, csrf, sign_in, watchlist_ids
from tests.test_svc_watch_fixtures import loaded as loaded

pytestmark = pytest.mark.anyio


async def state(db: Db) -> list[tuple[object, ...]]:
    """Every watchlist and item, as plain values, to compare before and after."""
    async with db.transaction() as tx:
        lists = await tx.scalars(select(Watchlist).order_by(Watchlist.id))
        rows: list[tuple[object, ...]] = [
            (wl.id, wl.name, wl.cadence, wl.date_alerts, wl.heartbeat, wl.paused) for wl in lists
        ]
        found = await tx.scalars(select(WatchItem).order_by(WatchItem.id))
        rows += [(i.id, i.watchlist_id, i.act_key, i.location) for i in found]
        return rows


async def item_locations(db: Db, watchlist: UUID) -> list[tuple[str, str | None]]:
    async with db.transaction() as tx:
        found = await tx.scalars(
            select(WatchItem)
            .where(WatchItem.watchlist_id == watchlist)
            .order_by(WatchItem.act_key, WatchItem.location)
        )
        return [(i.act_key, i.location) for i in found]


async def make_list(http: AsyncClient, db: Db, user: UUID, name: str) -> UUID:
    made = await http.post("/account/watchlists", data={"csrf": await csrf(http), "name": name})
    assert made.status_code == 303
    newest = (await watchlist_ids(db, user))[-1]
    assert made.headers["location"] == f"/account/?notice=created#wl-{newest}"
    return newest


@pytest.fixture
async def other(service_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A second browser, for a second account."""
    transport = ASGITransport(app=service_app)
    async with AsyncClient(transport=transport, base_url=SITE_URL) as http:
        yield http


async def test_svc_watch_editor_create_change_and_delete(client: AsyncClient, loaded: Db) -> None:
    user = await sign_in(loaded, client, "owner@example.org")
    wl = await make_list(client, loaded, user, "  Devices  ")
    token = await csrf(client)
    settings = {"csrf": token, "name": "Notified bodies", "cadence": "daily", "paused": "yes"}
    saved = await client.post(f"/account/watchlists/{wl}", data=settings)
    assert saved.headers["location"] == f"/account/?notice=saved#wl-{wl}"
    async with loaded.transaction() as tx:
        row = await tx.get_one(Watchlist, wl)
        assert (row.name, row.cadence, row.date_alerts, row.heartbeat, row.paused) == (
            "Notified bodies",
            Cadence.DAILY,
            False,
            False,
            True,
        )
    page = await client.get(saved.headers["location"])
    assert "Settings saved." in page.text
    assert "no email is sent for this watchlist" in page.text
    for bad in ({**settings, "cadence": "hourly"}, {**settings, "name": " "}):
        refused = await client.post(f"/account/watchlists/{wl}", data=bad)
        assert refused.status_code == 400
    long = await client.post("/account/watchlists", data={"csrf": token, "name": "x" * 81})
    assert "1 to 80 characters" in long.text and long.status_code == 400
    confirm = await client.get(f"/account/watchlists/{wl}/delete")
    assert confirm.status_code == 200 and "Notified bodies" in confirm.text
    gone = await client.post(f"/account/watchlists/{wl}/delete", data={"csrf": token})
    assert gone.headers["location"] == "/account/?notice=deleted"
    assert await watchlist_ids(loaded, user) == []


async def test_svc_watch_editor_adds_and_removes_items(client: AsyncClient, loaded: Db) -> None:
    user = await sign_in(loaded, client, "owner@example.org")
    wl = await make_list(client, loaded, user, "Rules")
    picker = await client.get(f"/account/watchlists/{wl}/add?act={HOUSE}")
    assert picker.status_code == 200
    assert "Article 2: Bins (2 changes recorded)" in picker.text
    assert picker.text.index("Article 9") < picker.text.index("Annex I")
    token = await csrf(client)
    items = f"/account/watchlists/{wl}/items"
    pick = {"csrf": token, "act": HOUSE, "mode": "pick", "whole": "yes", "location": "AR 3"}
    assert (await client.post(items, data=pick)).headers["location"].endswith(f"added#wl-{wl}")
    typed = {"csrf": token, "act": GARDEN, "mode": "text", "location": "Article 9a"}
    assert (await client.post(items, data=typed)).status_code == 303
    unread = await client.post(items, data={**typed, "location": "the bins"})
    assert unread.status_code == 400
    assert "“the bins” is not a location this page can read" in unread.text
    assert 'value="the bins"' in unread.text
    paste = {"csrf": token, "act": GARDEN, "mode": "paste", "lines": "Annex 2\nnonsense\nAR 2"}
    pasted = await client.post(items, data=paste)
    assert pasted.status_code == 200
    assert "Now watched: Annex II, Article 2." in pasted.text
    assert "“nonsense” is not a location this page can read" in pasted.text
    assert ">nonsense</textarea>" in pasted.text
    assert await item_locations(loaded, wl) == [
        (GARDEN, "AN II"),
        (GARDEN, "AR 2"),
        (GARDEN, "AR 9a"),
        (HOUSE, "AR 3"),
        (HOUSE, None),
    ]
    account = await client.get("/account/")
    assert account.text.count("no change recorded yet") == 2, "AR 9a and AN II"
    async with loaded.transaction() as tx:
        first = await tx.scalar(select(WatchItem.id).where(WatchItem.location.is_(None)))
    removed = await client.post(f"{items}/{first}/delete", data={"csrf": token})
    assert removed.headers["location"] == f"/account/?notice=removed#wl-{wl}"
    assert (HOUSE, None) not in await item_locations(loaded, wl)


async def test_svc_watch_editor_every_change_needs_the_form_token(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "owner@example.org")
    wl = await make_list(client, loaded, user, "Rules")
    token = await csrf(client)
    await client.post(
        f"/account/watchlists/{wl}/items",
        data={"csrf": token, "act": HOUSE, "mode": "text", "location": "AR 2"},
    )
    assert await item_locations(loaded, wl) == [(HOUSE, "AR 2")]
    async with loaded.transaction() as tx:
        item_id = await tx.scalar(select(WatchItem.id))
    before = await state(loaded)
    posts = {
        "/account/watchlists": {"name": "Another"},
        f"/account/watchlists/{wl}": {"name": "Renamed", "cadence": "none"},
        f"/account/watchlists/{wl}/items": {"act": HOUSE, "mode": "text", "location": "AR 3"},
        f"/account/watchlists/{wl}/items/{item_id}/delete": {},
        f"/account/watchlists/{wl}/delete": {},
        "/account/watch": {"act": HOUSE, "watchlist": str(wl)},
    }
    for path, data in posts.items():
        for forged in ({}, {"csrf": "forged"}):
            refused = await client.post(path, data={**data, **forged})
            assert refused.status_code == 403, path
    assert await state(loaded) == before


async def test_svc_watch_editor_one_account_cannot_touch_another(
    client: AsyncClient, other: AsyncClient, loaded: Db
) -> None:
    owner = await sign_in(loaded, client, "owner@example.org")
    wl = await make_list(client, loaded, owner, "Private list")
    token = await csrf(client)
    await client.post(
        f"/account/watchlists/{wl}/items",
        data={"csrf": token, "act": HOUSE, "mode": "text", "location": "AR 2"},
    )
    async with loaded.transaction() as tx:
        item_id = await tx.scalar(select(WatchItem.id))
    intruder = await sign_in(loaded, other, "intruder@example.org")
    own = await make_list(other, loaded, intruder, "Mine")
    before = await state(loaded)
    theirs = await csrf(other)
    assert "Private list" not in (await other.get("/account/")).text
    for path in (f"/account/watchlists/{wl}/add?act={HOUSE}", f"/account/watchlists/{wl}/delete"):
        assert (await other.get(path)).status_code == 404, path
    posts = [
        (f"/account/watchlists/{wl}", {"name": "Mine now", "cadence": "instant"}),
        (f"/account/watchlists/{wl}/items", {"act": HOUSE, "mode": "text", "location": "AR 3"}),
        (f"/account/watchlists/{wl}/items", {"act": HOUSE, "mode": "text", "location": "x"}),
        (f"/account/watchlists/{wl}/items/{item_id}/delete", {}),
        (f"/account/watchlists/{own}/items/{item_id}/delete", {}),
        (f"/account/watchlists/{wl}/delete", {}),
        ("/account/watch", {"act": HOUSE, "watchlist": str(wl)}),
        ("/account/watchlists/not-a-uuid/delete", {}),
    ]
    for path, data in posts:
        answered = await other.post(path, data={"csrf": theirs, **data})
        assert answered.status_code == 404, path
        assert "Private list" not in answered.text
    assert await state(loaded) == before


async def test_svc_watch_editor_refuses_oversized_and_control_input(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "owner@example.org")
    wl = await make_list(client, loaded, user, "Rules")
    token = await csrf(client)
    items = f"/account/watchlists/{wl}/items"
    for location in ("AR " + "1" * 5000, "AR 1\x00"):
        typed = {"csrf": token, "act": HOUSE, "mode": "text", "location": location}
        assert (await client.post(items, data=typed)).status_code == 400
    many = "\n".join(f"Article {n}" for n in range(1, 102))
    pasted = await client.post(
        items, data={"csrf": token, "act": HOUSE, "mode": "paste", "lines": many}
    )
    assert pasted.status_code == 400 and "Paste 1 to 100 locations" in pasted.text
    assert (await client.post(items, data={"csrf": token, "act": "x\x00"})).status_code == 404
    named = await client.post("/account/watchlists", data={"csrf": token, "name": "a\x00b"})
    assert named.status_code == 400
    assert await item_locations(loaded, wl) == []
    assert (await client.get("/account/")).status_code == 200
