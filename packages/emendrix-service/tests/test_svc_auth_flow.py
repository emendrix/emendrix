"""Signing in through the pages, over a real database, a fixed clock and recorded mail.

The helpers and fixtures here are shared with the sign-up tests, which import them.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.accounts import create_user_with_consents
from emendrix_service.db.enums import AuditAction, OutboxStatus
from emendrix_service.db.tables import AuditLog, Outbox, UserSession
from emendrix_service.mail.port import OutgoingMail, RecordingMailer
from emendrix_service.settings import ServiceSettings
from emendrix_service.web.csrf import SESSION_COOKIE
from tests.conftest import NOW, SITE_URL, settings_values

pytestmark = pytest.mark.anyio

KNOWN = "known@example.org"
TOKEN = re.compile(r'name="csrf" value="([^"]+)"')
LINK = re.compile(r"https://example\.org(/account/confirm/[A-Za-z0-9_-]+)")


@pytest.fixture
def settings(shell_file: Path, tmp_path: Path) -> ServiceSettings:
    notice = tmp_path / "privacy-notice.html"
    notice.write_text("<p>The operator's notice.</p>", encoding="utf-8")
    return ServiceSettings.model_validate(
        {
            **settings_values(),
            "shell": shell_file,
            "privacy_notice": notice,
            "mail_from": "Emendrix <alerts@example.org>",
        }
    )


@pytest.fixture
async def known(db: Db) -> str:
    async with db.transaction() as tx:
        await create_user_with_consents(tx, KNOWN, "000000000000", NOW - timedelta(days=9))
    return KNOWN


async def ask(http: AsyncClient, email: str) -> Response:
    token = TOKEN.findall((await http.get("/account/signin")).text)[0]
    return await http.post("/account/signin", data={"email": email, "csrf": token})


def link_of(mail: OutgoingMail) -> str:
    found = LINK.search(mail.text)
    assert found is not None
    assert f'href="{SITE_URL}{found.group(1)}"' in mail.html
    return found.group(1)


async def press(http: AsyncClient, path: str) -> Response:
    page = await http.get(path)
    assert page.status_code == 200
    return await http.post(path, data={"csrf": TOKEN.findall(page.text)[0]})


async def count(db: Db, table: type[object]) -> int:
    async with db.transaction() as tx:
        return int(await tx.scalar(select(func.count()).select_from(table)) or 0)


async def test_svc_auth_signin_sends_a_link_only_the_post_consumes(
    client: AsyncClient, mailer: RecordingMailer, known: str, db: Db
) -> None:
    page = await ask(client, known)
    assert page.status_code == 200
    assert "Check your inbox" in page.text
    assert len(mailer.sent) == 1
    mail = mailer.sent[0]
    assert (mail.to, mail.subject) == (known, "Sign in to Emendrix")
    path = link_of(mail)
    for _ in range(2):
        shown = await client.get(path)
        assert shown.status_code == 200
        assert "Confirm and sign in" in shown.text
    async with db.transaction() as tx:
        assert (await tx.scalar(select(Outbox.status))) is OutboxStatus.SENT
    confirmed = await press(client, path)
    assert confirmed.status_code == 303
    assert confirmed.headers["location"] == "/account/"
    cookie = next(
        c for c in confirmed.headers.get_list("set-cookie") if c.startswith(f"{SESSION_COOKIE}=")
    )
    for attribute in ("Secure", "HttpOnly", "SameSite=lax", "Path=/", "Max-Age=2592000"):
        assert attribute in cookie
    assert "Domain" not in cookie
    assert await count(db, UserSession) == 1
    assert (await client.get("/account/signin")).status_code == 303, "signed in now"


async def test_svc_auth_an_unknown_address_gets_the_same_page_and_nothing(
    client: AsyncClient, mailer: RecordingMailer, known: str
) -> None:
    for_known = await ask(client, known)
    for_unknown = await ask(client, "stranger@example.org")
    assert len(mailer.sent) == 1
    assert for_unknown.status_code == for_known.status_code
    assert for_unknown.content == for_known.content
    assert for_unknown.headers.get_list("set-cookie") == for_known.headers.get_list("set-cookie")


async def test_svc_auth_a_link_expires_after_thirty_minutes(
    client: AsyncClient, mailer: RecordingMailer, known: str, clock: FixedClock
) -> None:
    await ask(client, known)
    clock.advance(timedelta(minutes=31))
    refused = await press(client, link_of(mailer.sent[0]))
    assert refused.status_code == 410
    assert "This link has been used or has expired" in refused.text


async def test_svc_auth_the_fourth_link_for_one_address_is_not_sent(
    client: AsyncClient, mailer: RecordingMailer, known: str
) -> None:
    pages = [await ask(client, known) for _ in range(4)]
    assert len(mailer.sent) == 3
    assert pages[3].content == pages[0].content


async def test_svc_auth_the_twenty_first_link_from_one_address_is_not_sent(
    client: AsyncClient, mailer: RecordingMailer, db: Db
) -> None:
    addresses = [f"user{n}@example.org" for n in range(7)]
    async with db.transaction() as tx:
        for address in addresses:
            await create_user_with_consents(tx, address, "000000000000", NOW)
    pages = [await ask(client, address) for address in addresses for _ in range(3)]
    assert len(pages) == 21
    assert len(mailer.sent) == 20
    assert pages[20].content == pages[0].content


async def test_svc_auth_sign_out_ends_one_session_and_everywhere_ends_all(
    service_app: FastAPI, client: AsyncClient, mailer: RecordingMailer, known: str, db: Db
) -> None:
    transport = ASGITransport(app=service_app)
    browsers = [client, AsyncClient(transport=transport, base_url=SITE_URL)]
    others = AsyncClient(transport=transport, base_url=SITE_URL)
    async with browsers[1], others:
        for browser in [*browsers, others]:
            await ask(browser, known)
            await press(browser, link_of(mailer.sent[-1]))
        assert await count(db, UserSession) == 3

        form = TOKEN.findall((await others.get("/account/confirm/x")).text)[0]
        out = await others.post("/account/signout", data={"csrf": form})
        assert (out.status_code, out.headers["location"]) == (303, "/account/signin")
        assert await count(db, UserSession) == 2

        form = TOKEN.findall((await client.get("/account/confirm/x")).text)[0]
        everywhere = await client.post("/account/signout-everywhere", data={"csrf": form})
        assert everywhere.status_code == 303
        assert await count(db, UserSession) == 0
        async with db.transaction() as tx:
            assert (await tx.scalars(select(AuditLog.action))).all() == [AuditAction.SIGNOUT_ALL]
        assert (await browsers[1].get("/account/signin")).status_code == 200


async def test_svc_auth_a_session_slides_and_expires(
    client: AsyncClient, mailer: RecordingMailer, known: str, clock: FixedClock
) -> None:
    await ask(client, known)
    await press(client, link_of(mailer.sent[0]))
    clock.advance(timedelta(days=20))
    slid = await client.get("/account/signin")
    assert slid.status_code == 303
    assert any(c.startswith(f"{SESSION_COOKIE}=") for c in slid.headers.get_list("set-cookie"))
    clock.advance(timedelta(days=20))
    assert (await client.get("/account/signin")).status_code == 303
    clock.advance(timedelta(days=31))
    assert (await client.get("/account/signin")).status_code == 200
