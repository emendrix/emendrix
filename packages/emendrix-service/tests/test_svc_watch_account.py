"""The Watching tab: first visit, one list, several lists, and a suspended reader."""

from __future__ import annotations

import re
from datetime import timedelta
from uuid import UUID

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


async def watch(db: Db, user: UUID, watchlist: UUID, act: str, location: str | None) -> None:
    kind = ItemKind.ACT if location is None else ItemKind.PROVISION
    async with db.transaction() as tx:
        assert await add_item(tx, user, watchlist, kind, "toy", act, location, NOW)


async def a_list(db: Db, user: UUID, name: str = "My watchlist", offset: int = 0) -> UUID:
    async with db.transaction() as tx:
        return await create_watchlist(tx, user, name, NOW + timedelta(seconds=offset))


def body(text: str) -> str:
    """The page between the header and the footer: what the tab itself wrote."""
    return text.split("</header>", 1)[1].split("<footer", 1)[0]


def assert_clean(text: str) -> None:
    assert "style=" not in body(text) and "<script" not in body(text)
    assert "{% block" not in text and "{{" not in text
    assert DISCLAIMER.split("'")[0] in text


async def test_svc_watch_account_first_visit_offers_every_act(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "new@example.org")
    for _ in range(2):
        page = await client.get("/account/")
        assert page.status_code == 200
        text = page.text
        assert "Hear when EU law you rely on changes" in text
        assert '<p class="account-eyebrow">Welcome</p>' in text
        assert body(text).count('<li class="panel step">') == 3
        assert 'href="/acts/"' in text
        for act in (HOUSE, GARDEN):
            assert f'href="/account/watch?act={act}"' in text
        assert text.index("Garden Rules of Flat 3B") < text.index("House Rules of Flat 3B")
        assert 'class="panel strip"' not in text and "act-group" not in text
        assert 'class="account account--in"' in text
        assert_clean(text)
        await a_list(loaded, user)


async def test_svc_watch_account_one_list_groups_by_act_with_the_latest_change(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "owner@example.org")
    wl = await a_list(loaded, user)
    for act, location in (
        (HOUSE, "AR 4"),
        (HOUSE, "AR 2 PA 1"),
        (HOUSE, None),
        (GARDEN, "AN III"),
        ("32099R9999", "AR 1"),
    ):
        await watch(loaded, user, wl, act, location)
    page = await client.get("/account/")
    assert page.status_code == 200
    text = page.text
    assert (
        "<h1>What you watch</h1>" in text and '<p class="account-eyebrow">Your account</p>' in text
    )
    assert "5 items across 3 acts" in text
    assert 'href="/account/delivery">Change delivery</a>' in text
    assert "Weekly digest, Mondays 07:00 Brussels time" in text and "Flagged" in text
    assert text.index("32099R9999") < text.index("Garden Rules") < text.index("House Rules")
    assert text.index("The whole act") < text.index("Article 2(1)") < text.index("Article 4")
    assert "Article 2: Bins" in text, "a sub-provision shows its unit's heading"
    assert "Checked to 2026-08-12" in text
    assert "Checked for changes published up to 2026-08-12. 1 consolidation has been" in text
    assert "1 version is not offered in English." in text
    assert "The site&#39;s catalogue does not list this act." in text
    assert text.count("No change recorded yet") == 2, "Annex III of Garden Rules, and AR 1"
    assert text.count("Latest change recorded 2026-08-09") == 3, "the act, Article 2(1), 4"
    assert re.search(
        r'<a href="https://example.org/acts/house-rules/v3/#[^"]+">'
        r"Latest change recorded 2026-08-09</a>",
        text,
    )
    assert "Emails repeat what the record says." in text
    for absent in ("My watchlist", 'class="lists"', "Rename", "watchlist</", "Watchlist"):
        assert absent not in body(text), absent
    assert '<details id="new-list">' in text and "Start a second list" in text
    assert f'action="/account/watchlists/{wl}/items/' in text
    assert 'aria-label="Stop watching Article 4 of House Rules of Flat 3B"' in text
    assert 'class="button quiet"' in text
    assert_clean(text)
    opened = await client.get("/account/?new=1")
    assert '<details id="new-list" open>' in opened.text
    long = await client.post(
        "/account/watchlists", data={"csrf": await csrf(client), "name": "x" * 81}
    )
    assert long.status_code == 400 and "1 to 80 characters" in long.text
    assert '<details id="new-list" open>' in long.text


async def test_svc_watch_account_several_lists_show_the_switcher(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "owner@example.org")
    first = await a_list(loaded, user, "Flat rules")
    second = await a_list(loaded, user, "Garden only", offset=1)
    await watch(loaded, user, first, HOUSE, "AR 3")
    await watch(loaded, user, second, GARDEN, "AR 9")
    oldest = (await client.get("/account/")).text
    assert '<ul class="lists" aria-label="Your lists">' in oldest
    assert "<h2>Flat rules</h2>" in oldest and "Guests" in oldest
    assert "Each list has its own email and feed." in oldest
    assert "Rename or delete this list" in oldest
    assert f'action="/account/watchlists/{first}/name"' in oldest
    assert f'href="/account/watchlists/{first}/delete"' in oldest
    assert f'href="/account/delivery?list={first}">Change delivery for this list' in oldest
    assert "Start a second list" not in oldest and 'id="new-list"' not in oldest
    chosen = (await client.get(f"/account/?list={second}")).text
    assert "<h2>Garden only</h2>" in chosen and "Article 9" in chosen
    assert "Article 3" not in body(chosen)
    assert f'href="/account/?list={second}" aria-current="true"' in chosen
    stale = await client.get("/account/?list=not-a-list")
    assert stale.status_code == 200 and "<h2>Flat rules</h2>" in stale.text
    opened = (await client.get(f"/account/?list={second}&new=1")).text
    assert '<details id="new-list" open>' in opened
    assert_clean(chosen)


async def test_svc_watch_account_shows_a_notice_only_from_the_known_codes(
    client: AsyncClient, loaded: Db
) -> None:
    await sign_in(loaded, client, "owner@example.org")
    assert "List created." in (await client.get("/account/?notice=created")).text
    assert "Email resumed." in (await client.get("/account/?notice=resumed")).text
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
    watchlist = await a_list(loaded, user, "Kept list")
    await watch(loaded, user, watchlist, HOUSE, "AR 3")
    token = await csrf(client)
    async with loaded.transaction() as tx:
        await tx.execute(update(User).values(status=UserStatus.SUSPENDED))
    page = await client.get("/account/")
    assert page.status_code == 200
    text = page.text
    assert "No email is reaching bounced@example.org." in text
    assert "Guests" in text and "Article 3" in text
    assert '<span class="account-email">bounced@example.org</span>' in text
    assert "<form" not in body(text) and "<button" not in body(text)
    assert "Remove" not in body(text) and "Watch an act or provision" not in text
    assert_clean(text)
    refused = await client.post(
        f"/account/watchlists/{watchlist}/name", data={"csrf": token, "name": "x"}
    )
    assert refused.status_code == 303
    assert refused.headers["location"].startswith("/account/signin")
    async with loaded.transaction() as tx:
        assert (await tx.get_one(Watchlist, watchlist)).name == "Kept list"


async def test_svc_watch_account_suspended_first_visit_offers_no_watch_button(
    client: AsyncClient, loaded: Db
) -> None:
    await sign_in(loaded, client, "bounced@example.org")
    async with loaded.transaction() as tx:
        await tx.execute(update(User).values(status=UserStatus.SUSPENDED))
    text = (await client.get("/account/")).text
    assert "Hear when EU law you rely on changes" in text and "House Rules" in text
    assert "/account/watch?" not in text and "No email is reaching" in text
