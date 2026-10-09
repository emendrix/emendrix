"""The account page: every watchlist and item, the acts' coverage, the suspended banner."""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from emendrix_service import DISCLAIMER
from emendrix_service.db import Db
from emendrix_service.db.enums import ItemKind, UserStatus
from emendrix_service.db.tables import User, Watchlist
from emendrix_service.db.watchlists import add_item, create_watchlist
from tests.conftest import NOW
from tests.test_svc_watch_fixtures import GARDEN, HOUSE, csrf, sign_in
from tests.test_svc_watch_fixtures import loaded as loaded

pytestmark = pytest.mark.anyio


async def test_svc_watch_account_lists_everything_with_coverage(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "owner@example.org")
    async with loaded.transaction() as tx:
        first = await create_watchlist(tx, user, "Flat rules", NOW)
        second = await create_watchlist(tx, user, "Garden only", NOW + timedelta(seconds=1))
        for watchlist, act, location in (
            (first, HOUSE, "AR 4"),
            (first, HOUSE, "AR 2 PA 1"),
            (first, HOUSE, None),
            (second, GARDEN, "AN III"),
            (second, "32099R9999", "AR 1"),
        ):
            kind = ItemKind.ACT if location is None else ItemKind.PROVISION
            assert await add_item(tx, user, watchlist, kind, "toy", act, location, NOW)
    page = await client.get("/account/")
    assert page.status_code == 200
    text = page.text
    assert "Signed in as <strong>owner@example.org</strong>" in text
    for watchlist in (first, second):
        assert f'<section id="wl-{watchlist}">' in text
    assert text.index("Flat rules") < text.index("Garden only")
    assert text.index("The whole act") < text.index("Article 2(1)") < text.index("Article 4")
    assert "Article 2: Bins" in text, "a sub-provision shows its unit's heading"
    assert "Parcels" in text
    assert text.count("no change recorded yet") == 2
    assert "Weekly digest (Monday 07:00 Brussels time, only when something changed)" in text
    assert "Checked for changes published up to 2026-08-12. 1 consolidation has been" in text
    assert "1 version is not offered in English." in text
    assert "32099R9999: The site&#39;s catalogue does not list this act." in text
    assert DISCLAIMER.split("'")[0] in text
    assert "{% block" not in text and "No email is being sent" not in text


async def test_svc_watch_account_shows_a_notice_only_from_the_known_codes(
    client: AsyncClient, loaded: Db
) -> None:
    await sign_in(loaded, client, "owner@example.org")
    assert "Watchlist created." in (await client.get("/account/?notice=created")).text
    odd = await client.get("/account/?notice=<script>")
    assert odd.status_code == 200 and "<script>" not in odd.text


async def test_svc_watch_account_needs_a_session(client: AsyncClient, loaded: Db) -> None:
    page = await client.get("/account/")
    assert page.status_code == 303
    assert page.headers["location"] == "/account/signin?next=/account/"


async def test_svc_watch_account_suspended_sees_a_banner_and_no_editing(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "bounced@example.org")
    async with loaded.transaction() as tx:
        watchlist = await create_watchlist(tx, user, "Kept list", NOW)
        await add_item(tx, user, watchlist, ItemKind.PROVISION, "toy", HOUSE, "AR 3", NOW)
    token = await csrf(client)
    async with loaded.transaction() as tx:
        await tx.execute(update(User).values(status=UserStatus.SUSPENDED))
    page = await client.get("/account/")
    assert page.status_code == 200
    assert "No email is being sent to this address." in page.text
    assert "Kept list" in page.text and "Guests" in page.text
    assert 'action="/account/signout"' in page.text
    assert f'action="/account/watchlists/{watchlist}"' not in page.text
    assert 'action="/account/watchlists"' not in page.text
    refused = await client.post(
        f"/account/watchlists/{watchlist}", data={"csrf": token, "name": "x", "cadence": "none"}
    )
    assert refused.status_code == 303
    assert refused.headers["location"].startswith("/account/signin")
    async with loaded.transaction() as tx:
        assert (await tx.get_one(Watchlist, watchlist)).name == "Kept list"
