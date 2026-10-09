"""The Account tab: who is signed in, signing out, the reader's data and the way to delete.

The test shell carries a script of its own, standing in for the site's search, so "no script"
is read off the page's own content; "no inline style" holds for the whole response.
"""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence, ItemKind, UserStatus
from emendrix_service.db.tables import User, WatchItem, Watchlist
from emendrix_service.web.frame import SUSPENDED_SENTENCE
from tests.conftest import NOW
from tests.test_svc_watch_fixtures import sign_in

pytestmark = pytest.mark.anyio

READER = "reader@example.org"

HEADER = re.compile(r'<div id="search" data-root="/"></div>(.*?)</header>', re.DOTALL)
CONTENT = re.compile(r'<main id="content">(.*?)</main>', re.DOTALL)

ACTIONS = (
    'action="/account/signout"',
    'action="/account/signout-everywhere"',
    'href="/account/export"',
    'href="/account/privacy"',
    'href="/account/delete"',
)


def part(pattern: re.Pattern[str], page: str) -> str:
    found = pattern.search(page)
    assert found is not None, page
    return found.group(1)


async def watching(db: Db, user_id: UUID, *locations: str) -> None:
    """One list for the reader holding a provision item at each of `locations`."""
    async with db.transaction() as tx:
        watchlist = Watchlist(
            user_id=user_id,
            name="Flat rules",
            cadence=Cadence.WEEKLY,
            date_alerts=True,
            created_at=NOW,
        )
        tx.add(watchlist)
        await tx.flush()
        for location in locations:
            tx.add(
                WatchItem(
                    watchlist_id=watchlist.id,
                    kind=ItemKind.PROVISION,
                    corpus="toy",
                    act_key="house-rules",
                    location=location,
                    created_at=NOW,
                )
            )


async def test_svc_leave_the_account_tab_names_the_reader_and_every_action(
    client: AsyncClient, db: Db
) -> None:
    await sign_in(db, client, READER)
    page = await client.get("/account/settings")
    assert page.status_code == 200
    text = page.text
    header, content = part(HEADER, text), part(CONTENT, text)
    assert "You and your data" in content
    assert "Your sign-in, and everything the service holds about you." in content
    assert content.replace("<wbr>", "").count(READER) == 1
    assert READER in header and 'aria-current="page"' in header
    assert '<a href="/account/settings" aria-current="page">Account</a>' in content
    for action in ACTIONS:
        assert action in content, action
    assert content.count('name="csrf"') == 2, "each sign-out form carries the token"
    assert 'role="alert"' not in content
    assert "style=" not in text
    assert "<script" not in content
    assert "<title>Your account</title>" in text


async def test_svc_leave_the_account_tab_needs_a_session(client: AsyncClient) -> None:
    response = await client.get("/account/settings")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/account/signin?next=")


async def test_svc_leave_a_suspended_reader_keeps_every_action_on_the_account_tab(
    client: AsyncClient, db: Db
) -> None:
    await sign_in(db, client, READER)
    async with db.transaction() as tx:
        await tx.execute(update(User).values(status=UserStatus.SUSPENDED))
    page = await client.get("/account/settings")
    assert page.status_code == 200
    content = part(CONTENT, page.text)
    banner = re.search(r'<div class="banner banner--alert" role="alert">(.*?)</div>', content, re.S)
    assert banner is not None
    sentence = re.sub(r"<[^>]+>", "", banner.group(1)).strip()
    assert sentence == SUSPENDED_SENTENCE.format(email=READER)
    for action in ACTIONS:
        assert action in content, action
    assert "Resume email" not in content and "/resume" not in content


async def test_svc_leave_the_watching_tab_counts_every_item_from_the_account_tab(
    client: AsyncClient, db: Db
) -> None:
    user_id = await sign_in(db, client, READER)
    await watching(db, user_id, "AR 1", "AR 2", "AR 3")
    content = part(CONTENT, (await client.get("/account/settings")).text)
    assert '<a href="/account/">Watching <span class="count">3</span>' in content
    assert '<a href="/account/delivery">Delivery</a>' in content


async def test_svc_leave_the_delete_page_leads_back_to_the_account_tab(
    client: AsyncClient, db: Db
) -> None:
    await sign_in(db, client, READER)
    content = part(CONTENT, (await client.get("/account/delete")).text)
    assert '<a class="back" href="/account/settings">Back to your account</a>' in content
    assert '<a class="button secondary" href="/account/settings">Keep it</a>' in content
    assert '<div class="panel danger-zone">' in content
    assert "style=" not in content and "<script" not in content


async def test_svc_leave_the_deleted_page_names_nobody_in_the_header(
    client: AsyncClient, db: Db
) -> None:
    await sign_in(db, client, READER)
    page = await client.get("/account/delete")
    token = re.findall(r'name="csrf" value="([^"]+)"', page.text)[0]
    response = await client.post("/account/delete", data={"csrf": token})
    assert response.status_code == 200
    assert part(HEADER, response.text) == '<a class="account" href="/account/">Account</a>'
    content = part(CONTENT, response.text)
    assert '<a class="back" href="/">Back to the site</a>' in content
    assert READER not in response.text
