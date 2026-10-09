"""The Delivery tab: one list or several, saving, pausing and resuming, and a suspended reader."""

from __future__ import annotations

import re
from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from emendrix_service.db import Db
from emendrix_service.db.accounts import create_user_with_consents
from emendrix_service.db.enums import Cadence, ItemKind, UserStatus
from emendrix_service.db.tables import User, Watchlist
from emendrix_service.db.watchlists import add_item, create_watchlist
from tests.conftest import NOW
from tests.test_svc_watch_fixtures import GARDEN, HOUSE, csrf, sign_in
from tests.test_svc_watch_fixtures import loaded as loaded

pytestmark = pytest.mark.anyio

PAGE = "/account/delivery"
CHECKED = re.compile(r'name="cadence" value="([a-z]+)" checked')


async def one_list(db: Db, http: AsyncClient, email: str = "owner@example.org") -> UUID:
    user = await sign_in(db, http, email)
    async with db.transaction() as tx:
        watchlist = await create_watchlist(tx, user, "Flat rules", NOW)
        assert await add_item(tx, user, watchlist, ItemKind.ACT, "toy", HOUSE, None, NOW)
    return watchlist


async def two_lists(db: Db, http: AsyncClient) -> tuple[UUID, UUID]:
    user = await sign_in(db, http, "owner@example.org")
    async with db.transaction() as tx:
        first = await create_watchlist(tx, user, "Flat rules", NOW)
        second = await create_watchlist(tx, user, "Garden only", NOW + timedelta(seconds=1))
        assert await add_item(tx, user, second, ItemKind.ACT, "toy", GARDEN, None, NOW)
        await tx.execute(update(Watchlist).where(Watchlist.id == second).values(cadence="daily"))
    return first, second


async def stored(db: Db, watchlist: UUID) -> tuple[str, Cadence, bool, bool, bool]:
    async with db.transaction() as tx:
        row = await tx.get_one(Watchlist, watchlist)
        return row.name, row.cadence, row.date_alerts, row.heartbeat, row.paused


async def test_svc_watch_delivery_one_list_shows_no_list_at_all(
    client: AsyncClient, loaded: Db
) -> None:
    watchlist = await one_list(loaded, client)
    page = await client.get(PAGE)
    assert page.status_code == 200
    text = page.text
    assert "<h1>How you hear about changes</h1>" in text
    assert text.count('class="choice"') == 4
    assert CHECKED.findall(text) == ["weekly"]
    assert '<span class="tag">Default</span>' in text
    assert 'class="lists"' not in text and "Flat rules" not in text
    assert '<a href="/account/delivery" aria-current="page">Delivery</a>' in text
    assert f'action="/account/watchlists/{watchlist}/delivery"' in text
    assert "Create a personal feed" in text and 'class="state-off"' in text
    assert "style=" not in text and "<script" not in text


async def test_svc_watch_delivery_two_lists_pick_one_by_the_query(
    client: AsyncClient, loaded: Db
) -> None:
    first, second = await two_lists(loaded, client)
    text = (await client.get(f"{PAGE}?list={second}")).text
    switcher = text.split('<ul class="lists"', 1)[1].split("</ul>", 1)[0]
    assert switcher.count(f'href="{PAGE}?list=') == 2
    assert f'href="{PAGE}?list={second}" aria-current="true"' in text
    assert "<h2>Garden only</h2>" in text and CHECKED.findall(text) == ["daily"]
    for odd in ("not-an-id", "00000000-0000-0000-0000-000000000000"):
        fallback = (await client.get(f"{PAGE}?list={odd}")).text
        assert "<h2>Flat rules</h2>" in fallback and CHECKED.findall(fallback) == ["weekly"]
    assert f'action="/account/watchlists/{first}/delivery"' in fallback


async def test_svc_watch_delivery_save_keeps_the_name_and_reads_absent_boxes_as_off(
    client: AsyncClient, loaded: Db
) -> None:
    watchlist = await one_list(loaded, client)
    token = await csrf(client, PAGE)
    saved = await client.post(
        f"/account/watchlists/{watchlist}/delivery",
        data={"csrf": token, "cadence": "daily", "heartbeat": "yes"},
    )
    assert saved.status_code == 303
    assert saved.headers["location"] == f"{PAGE}?list={watchlist}&notice=saved"
    assert await stored(loaded, watchlist) == ("Flat rules", Cadence.DAILY, False, True, False)
    page = (await client.get(saved.headers["location"])).text
    assert "Delivery settings saved." in page and CHECKED.findall(page) == ["daily"]
    refused = await client.post(
        f"/account/watchlists/{watchlist}/delivery", data={"csrf": token, "cadence": "hourly"}
    )
    assert refused.status_code == 400
    assert "Choose one of the four email choices." in refused.text
    assert await stored(loaded, watchlist) == ("Flat rules", Cadence.DAILY, False, True, False)


async def test_svc_watch_delivery_another_readers_list_is_not_found(
    client: AsyncClient, loaded: Db
) -> None:
    async with loaded.transaction() as tx:
        other = await create_user_with_consents(tx, "other@example.org", "000000000000", NOW)
        assert other is not None
        theirs = await create_watchlist(tx, other.id, "Theirs", NOW)
    await one_list(loaded, client)
    token = await csrf(client, PAGE)
    for wanted in (str(theirs), "not-an-id"):
        for action, data in (("delivery", {"cadence": "none"}), ("resume", {})):
            refused = await client.post(
                f"/account/watchlists/{wanted}/{action}", data={"csrf": token, **data}
            )
            assert refused.status_code == 404
    assert await stored(loaded, theirs) == ("Theirs", Cadence.WEEKLY, True, True, False)


async def test_svc_watch_delivery_needs_a_session(client: AsyncClient, loaded: Db) -> None:
    page = await client.get(PAGE)
    assert page.status_code == 303 and page.headers["location"].startswith("/account/signin")


async def test_svc_watch_delivery_pause_shows_the_banner_and_resume_goes_back(
    client: AsyncClient, loaded: Db
) -> None:
    watchlist = await one_list(loaded, client)
    token = await csrf(client, PAGE)
    paused = await client.post(
        f"/account/watchlists/{watchlist}/delivery",
        data={"csrf": token, "cadence": "instant", "date_alerts": "yes", "paused": "yes"},
    )
    page = (await client.get(paused.headers["location"])).text
    assert "Email is paused." in page
    assert f'action="/account/watchlists/{watchlist}/resume"' in page
    assert '<input type="hidden" name="back" value="delivery">' in page
    expected = {
        "watching": f"/account/?list={watchlist}&notice=resumed",
        "delivery": f"{PAGE}?list={watchlist}&notice=resumed",
        "account": "/account/settings?notice=resumed",
        "": f"{PAGE}?list={watchlist}&notice=resumed",
    }
    for back, location in expected.items():
        resumed = await client.post(
            f"/account/watchlists/{watchlist}/resume", data={"csrf": token, "back": back}
        )
        assert resumed.status_code == 303 and resumed.headers["location"] == location
        assert await stored(loaded, watchlist) == (
            "Flat rules",
            Cadence.INSTANT,
            True,
            False,
            False,
        )
    page = (await client.get(expected["delivery"])).text
    assert "Email resumed." in page and "Email is paused." not in page


async def test_svc_watch_delivery_suspended_sees_what_is_set_and_nothing_to_change(
    client: AsyncClient, loaded: Db
) -> None:
    watchlist = await one_list(loaded, client, "bounced@example.org")
    token = await csrf(client, PAGE)
    async with loaded.transaction() as tx:
        await tx.execute(update(User).values(status=UserStatus.SUSPENDED))
    page = await client.get(PAGE)
    assert page.status_code == 200
    text = page.text
    assert "No email is reaching bounced@example.org." in text
    assert "<form" not in text.split("</header>", 1)[1].split("<footer", 1)[0]
    assert "<button" not in text and "Weekly digest" in text
    refused = await client.post(
        f"/account/watchlists/{watchlist}/delivery", data={"csrf": token, "cadence": "none"}
    )
    assert refused.status_code == 303 and refused.headers["location"].startswith("/account/signin")


async def test_svc_watch_delivery_without_a_list_goes_to_watching(
    client: AsyncClient, loaded: Db
) -> None:
    await sign_in(loaded, client, "new@example.org")
    page = await client.get(PAGE)
    assert page.status_code == 303 and page.headers["location"] == "/account/"
