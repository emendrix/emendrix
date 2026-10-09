"""Signing up: the link a watch landing sends, what confirming it makes, and what it may not do.

Every email is checked for the disclaimer here, and every log line for an address or a token.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from emendrix_service import DISCLAIMER
from emendrix_service.app import create_app
from emendrix_service.auth.logic import Silent, WatchIntent
from emendrix_service.auth.ratelimit import SlidingWindow
from emendrix_service.auth.service import request_link
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence, ConsentKind, ItemKind, TokenPurpose
from emendrix_service.db.tables import Act, Consent, User, WatchItem, Watchlist
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ServiceSettings
from tests.conftest import SITE_URL
from tests.test_svc_auth_flow import TOKEN, ask, count, link_of, press

# Two fixtures, imported so pytest finds them in this module too.
from tests.test_svc_auth_flow import known as known
from tests.test_svc_auth_flow import settings as settings

pytestmark = pytest.mark.anyio


async def link_request(
    app: FastAPI, email: str, purpose: TokenPurpose, intent: WatchIntent | None
) -> TokenPurpose | Silent:
    """What a watch landing does with a typed address: one link request from one client."""
    state = app.state
    return await request_link(
        state.db,
        state.mailer,
        state.settings,
        state.clock,
        email=email,
        purpose=purpose,
        intent=intent,
        ip="203.0.113.1",
        window=SlidingWindow(20, 3600, state.clock),
    )


async def test_svc_auth_sign_up_with_an_intent_makes_everything_once(
    service_app: FastAPI, client: AsyncClient, mailer: RecordingMailer, db: Db
) -> None:
    async with db.transaction() as tx:
        tx.add(
            Act(
                corpus="eu",
                act_key="32017R0745",
                label="MDR",
                long_name="Medical Devices Regulation",
                domain="health",
                aliases=[],
                url="acts/32017R0745/",
                title="Regulation (EU) 2017/745",
                waiting=[],
            )
        )
    newcomer = "newcomer@example.org"
    outcome = await link_request(
        service_app,
        newcomer,
        TokenPurpose.SIGNUP,
        WatchIntent(corpus="eu", act_key="32017R0745", location="AN I"),
    )
    assert outcome is TokenPurpose.SIGNUP
    (mail,) = mailer.sent
    assert mail.subject == "Confirm your address to start watching Annex I of MDR"
    assert "privacy" not in mail.subject
    path = link_of(mail)
    assert await count(db, User) == 0, "no account before the link is opened"
    confirmed = await press(client, path)
    assert confirmed.status_code == 303
    assert confirmed.headers["location"] == "/account/"
    async with db.transaction() as tx:
        user = (await tx.scalars(select(User))).one()
        assert user.email == newcomer
        consents = (await tx.scalars(select(Consent))).all()
        assert sorted(c.kind for c in consents) == [
            ConsentKind.PRIVACY_NOTICE,
            ConsentKind.SERVICE_EMAIL,
        ]
        watchlist = (await tx.scalars(select(Watchlist))).one()
        assert (watchlist.name, watchlist.cadence) == ("My watchlist", Cadence.WEEKLY)
        assert (watchlist.date_alerts, watchlist.heartbeat, watchlist.paused) == (
            True,
            True,
            False,
        )
        item = (await tx.scalars(select(WatchItem))).one()
        assert (item.kind, item.corpus, item.act_key, item.location) == (
            ItemKind.PROVISION,
            "eu",
            "32017R0745",
            "AN I",
        )
    again = await client.post(path, data={"csrf": TOKEN.findall((await client.get(path)).text)[0]})
    assert again.status_code == 410
    assert await count(db, User) == 1


async def test_svc_auth_a_known_address_asking_to_sign_up_gets_a_signin_link(
    service_app: FastAPI, client: AsyncClient, mailer: RecordingMailer, known: str
) -> None:
    intent = WatchIntent(corpus="eu", act_key="32017R0745")
    outcome = await link_request(service_app, known, TokenPurpose.SIGNUP, intent)
    assert outcome is TokenPurpose.SIGNIN
    assert mailer.sent[0].subject == "Sign in to Emendrix"
    confirmed = await press(client, link_of(mailer.sent[0]))
    assert confirmed.headers["location"] == intent.landing()


async def test_svc_auth_closed_signup_admits_only_the_allowlist(
    settings: ServiceSettings, clock: FixedClock, db: Db, known: str
) -> None:
    closed = settings.model_copy(
        update={"signup_open": False, "signup_allowlist": ("invited@example.org",)}
    )
    mailer = RecordingMailer()
    window = SlidingWindow(20, 3600, clock)

    async def sign_up(email: str, purpose: TokenPurpose) -> TokenPurpose | Silent:
        return await request_link(
            db,
            mailer,
            closed,
            clock,
            email=email,
            purpose=purpose,
            intent=None,
            ip="203.0.113.1",
            window=window,
        )

    assert await sign_up("stranger@example.org", TokenPurpose.SIGNUP) is Silent.SIGNUP_CLOSED
    assert mailer.sent == []
    assert await sign_up(known, TokenPurpose.SIGNIN) is TokenPurpose.SIGNIN
    assert await sign_up("Invited@example.org", TokenPurpose.SIGNUP) is TokenPurpose.SIGNUP
    assert [mail.to for mail in mailer.sent] == [known, "Invited@example.org"]

    app = create_app(closed, clock=clock, mailer=mailer, db=db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=SITE_URL) as http:
        await press(http, link_of(mailer.sent[1]))
    assert await count(db, User) == 2


async def test_svc_auth_every_email_carries_the_disclaimer_and_no_log_line_a_secret(
    service_app: FastAPI,
    client: AsyncClient,
    mailer: RecordingMailer,
    known: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        await ask(client, known)
        await ask(client, "stranger@example.org")
        await link_request(
            service_app,
            "newcomer@example.org",
            TokenPurpose.SIGNUP,
            WatchIntent(corpus="eu", act_key="32017R0745"),
        )
        paths = [link_of(mail) for mail in mailer.sent]
        for path in paths:
            await press(client, path)
    assert len(mailer.sent) == 2
    for mail in mailer.sent:
        assert DISCLAIMER in mail.text
        assert DISCLAIMER in mail.html
        assert f"{SITE_URL}/account/" in mail.text
    secrets = [known, "stranger@example.org", "newcomer@example.org"]
    secrets += [path.rsplit("/", 1)[1] for path in paths]
    # The test's own client logs every URL it fetches; only the service's records are judged.
    records = [r for r in caplog.records if not r.name.startswith(("httpx", "httpcore"))]
    assert records
    for record in records:
        line = f"{record.getMessage()} {record.args!r}"
        for secret in secrets:
            assert secret not in line, record.name
