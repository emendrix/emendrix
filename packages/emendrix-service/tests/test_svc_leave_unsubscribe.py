"""One-click unsubscribe: a GET only shows the button, a POST with no cookie stops the email."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from emendrix_service.db import Db
from emendrix_service.db.enums import AuditAction, Cadence
from emendrix_service.db.tables import AuditLog, User, Watchlist
from emendrix_service.notify.digest_run import DigestCounts, digest
from emendrix_service.notify.render import unsubscribe_url
from emendrix_service.notify.run import notify
from emendrix_service.settings import ServiceSettings
from tests.conftest import NOW, SITE_URL
from tests.test_svc_load_run import copy_record
from tests.test_svc_notify_run import add_watchlist, count, go_live, notify_settings

pytestmark = pytest.mark.anyio

ONE_CLICK = {"List-Unsubscribe": "One-Click"}


def path_of(watchlist_id: UUID, settings: ServiceSettings) -> str:
    url = unsubscribe_url(SITE_URL, watchlist_id, secret=settings.secret_key)
    return url.removeprefix(SITE_URL)


async def state(db: Db, watchlist_id: UUID) -> tuple[Cadence, int]:
    async with db.transaction() as tx:
        cadence = await tx.scalar(select(Watchlist.cadence).where(Watchlist.id == watchlist_id))
    assert cadence is not None
    audits = await count(db, AuditLog, AuditLog.action == AuditAction.UNSUBSCRIBE)
    return cadence, audits


async def test_svc_leave_a_get_shows_the_button_and_changes_nothing(
    client: AsyncClient, db: Db, settings: ServiceSettings
) -> None:
    watchlist = await add_watchlist(db, "reader@example.org")
    for _ in range(2):
        page = await client.get(path_of(watchlist, settings))
        assert page.status_code == 200
        assert "weekly list" in page.text and '<form class="stack" method="post">' in page.text
        assert "reader@example.org" not in page.text
        assert "set-cookie" not in page.headers
    assert await state(db, watchlist) == (Cadence.WEEKLY, 0)


async def test_svc_leave_a_one_click_post_with_no_cookie_stops_the_email_once(
    client: AsyncClient, db: Db, settings: ServiceSettings
) -> None:
    watchlist = await add_watchlist(db, "reader@example.org")
    assert not client.cookies
    first = await client.post(path_of(watchlist, settings), data=ONE_CLICK)
    assert first.status_code == 200, first.text
    assert "Email stopped" in first.text
    assert "set-cookie" not in first.headers
    assert await state(db, watchlist) == (Cadence.NONE, 1)
    again = await client.post(path_of(watchlist, settings), files={"List-Unsubscribe": "One-Click"})
    assert again.status_code == 200
    assert await state(db, watchlist) == (Cadence.NONE, 1)
    async with db.transaction() as tx:
        seen = await tx.scalar(select(User.last_seen_at))
    assert seen == NOW


async def test_svc_leave_the_page_button_posts_with_an_empty_body(
    client: AsyncClient, db: Db, settings: ServiceSettings
) -> None:
    watchlist = await add_watchlist(db, "reader@example.org", cadence=Cadence.DAILY)
    page = await client.post(path_of(watchlist, settings))
    assert page.status_code == 200
    assert await state(db, watchlist) == (Cadence.NONE, 1)
    shown = await client.get(path_of(watchlist, settings))
    assert "already sends no email" in shown.text and "<form" not in shown.text


async def test_svc_leave_a_tampered_token_is_404_and_a_deleted_watchlist_410(
    client: AsyncClient, db: Db, settings: ServiceSettings
) -> None:
    watchlist = await add_watchlist(db, "reader@example.org")
    path = path_of(watchlist, settings)
    tampered = path[:-2] + ("AA" if not path.endswith("AA") else "BB")
    for method in ("GET", "POST"):
        assert (await client.request(method, tampered)).status_code == 404
        assert (await client.request(method, "/u/unsubscribe/not-a-token")).status_code == 404
    async with db.transaction() as tx:
        await tx.execute(delete(Watchlist).where(Watchlist.id == watchlist))
    for method in ("GET", "POST"):
        gone = await client.request(method, path, data=ONE_CLICK)
        assert gone.status_code == 410
        assert "This watchlist has been deleted; no email will be sent for it." in gone.text
    assert await count(db, AuditLog) == 0


async def test_svc_leave_after_unsubscribing_digest_mails_nothing(
    client: AsyncClient, db: Db, settings: ServiceSettings, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    watchlist = await add_watchlist(db, "weekly@example.org")
    await go_live(db, record)
    notified = notify_settings(record)
    await notify(db, notified, NOW - timedelta(days=1))
    assert (await client.post(path_of(watchlist, settings), data=ONE_CLICK)).status_code == 200
    assert await digest(db, notified, NOW) == DigestCounts()


async def test_svc_leave_the_token_never_reaches_the_log(
    client: AsyncClient, db: Db, settings: ServiceSettings, caplog: pytest.LogCaptureFixture
) -> None:
    watchlist = await add_watchlist(db, "reader@example.org")
    path = path_of(watchlist, settings)
    token = path.rsplit("/", 1)[1]
    with caplog.at_level(logging.INFO):
        await client.get(path)
        await client.post(path, data=ONE_CLICK)
    ours = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("emendrix_service")
    )
    assert "/u/unsubscribe/-" in ours
    assert token not in ours
