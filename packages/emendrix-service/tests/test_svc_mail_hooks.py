"""The provider's webhook: authenticated by its path secret, read without fetching anything, and
turning bounces and complaints into suppressions.

The event payloads below follow the examples of Scaleway's "Understanding webhook event
payloads" (https://www.scaleway.com/en/docs/transactional-email/reference-content/webhook-events-payloads/,
read 2026-10-09), with placeholder values where the page shows a type name. The envelopes
around them are the SNS shapes the provider's Topics and Events service posts, as "Use webhooks
with SNS topics"
(https://www.scaleway.com/en/docs/transactional-email/api-cli/use-webhooks-with-sns-topics/,
read 2026-10-09) describes: a `SubscriptionConfirmation` first, then `Notification`s whose
`Message` is the event as a JSON string.
"""

from __future__ import annotations

import json
import logging
import socket
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from emendrix_service.app import create_app
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import MailEventKind, SuppressionReason, UserStatus
from emendrix_service.db.suppressions import email_sha256
from emendrix_service.db.tables import MailEvent, Suppression, User
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.mail.scaleway import (
    Confirmation,
    Notification,
    ProviderEvent,
    parse_envelope,
)
from emendrix_service.settings import ServiceSettings
from tests.conftest import NOW, SITE_URL

pytestmark = pytest.mark.anyio

SECRET = "hook-secret-0123456789abcdef"
PATH = f"/u/hooks/scaleway/{SECRET}"
ADDRESS = "Reader@Example.org"
SUBSCRIBE_URL = (
    "https://sns.example.org/?Action=ConfirmSubscription&TopicArn=arn:scw:sns:fr-par:x:t"
    "&Token=2336412f37fb687f5d51e6e2425dacbbb4b1d2b4"
)


def event(kind: str, to: str = ADDRESS, *, field: str = "email_to") -> dict[str, object]:
    """One event in the documented shape."""
    return {
        "id": "8f6b3c2e-1d4a-4a8e-9f00-000000000001",
        "type": kind,
        "organization_id": "00000000-0000-4000-8000-0000000000aa",
        "project_id": "00000000-0000-4000-8000-0000000000bb",
        "domain_id": "00000000-0000-4000-8000-0000000000cc",
        "domain_name": "example.org",
        "created_at": "2026-10-12T04:59:00Z",
        "email_sent_at": "2026-10-12T04:58:00Z",
        "email_id": "00000000-0000-4000-8000-0000000000dd",
        "email_from": "alerts@example.org",
        field: to,
        "email_headers": [{"key": "Subject", "value": "Article 6 changed"}],
        "email_response_code": 550,
        "email_response_message": "5.1.1 mailbox unavailable",
    }


def notification(*events: dict[str, object]) -> bytes:
    message = events[0] if len(events) == 1 else list(events)
    return json.dumps(
        {
            "Type": "Notification",
            "MessageId": "da41e39f-ea4d-435a-b922-c6aae3915ebe",
            "TopicArn": "arn:scw:sns:fr-par:project-x:emendrix-mail",
            "Message": json.dumps(message),
            "Timestamp": "2026-10-12T04:59:01.000Z",
        }
    ).encode()


CONFIRMATION = json.dumps(
    {
        "Type": "SubscriptionConfirmation",
        "MessageId": "165545c9-2a5c-472c-8df2-7ff2be2b3b1b",
        "Token": "2336412f37fb687f5d51e6e2425dacbbb4b1d2b4",
        "TopicArn": "arn:scw:sns:fr-par:project-x:emendrix-mail",
        "Message": "You have chosen to subscribe to the topic. To confirm, visit SubscribeURL.",
        "SubscribeURL": SUBSCRIBE_URL,
        "Timestamp": "2026-10-12T04:58:00.000Z",
    }
).encode()


@pytest.fixture
async def hook_client(
    settings: ServiceSettings,
    clock: FixedClock,
    mailer: RecordingMailer,
    db: Db,
    worker_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """A client of an app with a webhook secret, in which opening any socket fails the test."""
    configured = settings.model_copy(
        update={"database_url": SecretStr(worker_url), "webhook_secret": SecretStr(SECRET)}
    )
    app: FastAPI = create_app(configured, clock=clock, mailer=mailer, db=db)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the webhook made an outbound connection")

    async with app.router.lifespan_context(app):
        monkeypatch.setattr(socket, "create_connection", refuse)
        monkeypatch.setattr(socket.socket, "connect", refuse)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=SITE_URL) as http:
            yield http


async def add_user(db: Db, email: str = ADDRESS) -> None:
    async with db.transaction() as tx:
        tx.add(
            User(
                email=email,
                created_at=NOW,
                verified_at=NOW,
                last_signin_at=NOW,
                last_seen_at=NOW,
            )
        )


async def state(db: Db) -> tuple[SuppressionReason | None, UserStatus]:
    async with db.transaction() as tx:
        reason = await tx.scalar(
            select(Suppression.reason).where(Suppression.email_sha256 == email_sha256(ADDRESS))
        )
        status = await tx.scalar(select(User.status))
    assert status is not None
    return reason, status


async def test_svc_mail_hooks_a_wrong_or_missing_secret_is_not_found(
    hook_client: AsyncClient, client: AsyncClient
) -> None:
    wrong = await hook_client.post("/u/hooks/scaleway/not-the-secret", content=CONFIRMATION)
    assert wrong.status_code == 404
    unset = await client.post(PATH, content=CONFIRMATION)
    assert unset.status_code == 404


async def test_svc_mail_hooks_a_confirmation_is_logged_and_never_fetched(
    hook_client: AsyncClient, mailer: RecordingMailer, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="emendrix_service.mail.hooks"):
        response = await hook_client.post(
            PATH, content=CONFIRMATION, headers={"content-type": "text/plain"}
        )
    assert response.status_code == 200
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert SUBSCRIBE_URL in warnings[0].getMessage()
    assert mailer.attempts == []


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("email_dropped", SuppressionReason.HARD_BOUNCE),
        ("email_mailbox_not_found", SuppressionReason.HARD_BOUNCE),
        ("email_spam", SuppressionReason.COMPLAINT),
    ],
)
async def test_svc_mail_hooks_a_hard_bounce_or_complaint_suppresses_and_suspends(
    hook_client: AsyncClient,
    db: Db,
    caplog: pytest.LogCaptureFixture,
    kind: str,
    reason: SuppressionReason,
) -> None:
    await add_user(db)
    with caplog.at_level(logging.DEBUG):
        response = await hook_client.post(PATH, content=notification(event(kind)))
    assert response.status_code == 200
    assert await state(db) == (reason, UserStatus.SUSPENDED)
    logged = " ".join(record.getMessage() for record in caplog.records).lower()
    assert ADDRESS.lower() not in logged


async def test_svc_mail_hooks_three_soft_bounces_in_a_week_suppress(
    hook_client: AsyncClient, db: Db, clock: FixedClock
) -> None:
    await add_user(db)
    deferred = event("email_deferred", field="email_rcpt_to")
    for _ in range(2):
        deferred["created_at"] = clock.now().isoformat()
        assert (await hook_client.post(PATH, content=notification(deferred))).status_code == 200
        clock.advance(timedelta(days=3))
        assert await state(db) == (None, UserStatus.ACTIVE)
    deferred["created_at"] = clock.now().isoformat()
    assert (await hook_client.post(PATH, content=notification(deferred))).status_code == 200
    assert await state(db) == (SuppressionReason.SOFT_BOUNCES, UserStatus.SUSPENDED)


async def test_svc_mail_hooks_soft_bounces_spread_over_more_than_a_week_do_not(
    hook_client: AsyncClient, db: Db, clock: FixedClock
) -> None:
    await add_user(db)
    deferred = event("email_deferred")
    for _ in range(3):
        deferred["created_at"] = clock.now().isoformat()
        assert (await hook_client.post(PATH, content=notification(deferred))).status_code == 200
        clock.advance(timedelta(days=4))
    assert await state(db) == (None, UserStatus.ACTIVE)


async def test_svc_mail_hooks_two_soft_bounces_do_not_suppress(
    hook_client: AsyncClient, db: Db
) -> None:
    await add_user(db)
    body = notification(event("email_deferred"), event("email_deferred"))
    assert (await hook_client.post(PATH, content=body)).status_code == 200
    assert await state(db) == (None, UserStatus.ACTIVE)
    async with db.transaction() as tx:
        kinds = (await tx.execute(select(MailEvent.kind))).scalars().all()
    assert kinds == [MailEventKind.SOFT_BOUNCE, MailEventKind.SOFT_BOUNCE]


async def test_svc_mail_hooks_delivered_and_ignored_types_suppress_nothing(
    hook_client: AsyncClient, db: Db
) -> None:
    await add_user(db)
    body = notification(event("email_delivered"), event("email_queued"), event("unknown_type"))
    assert (await hook_client.post(PATH, content=body)).status_code == 200
    assert await state(db) == (None, UserStatus.ACTIVE)
    async with db.transaction() as tx:
        rows = (await tx.execute(select(MailEvent))).scalars().all()
    assert [(row.kind, row.provider_message_id) for row in rows] == [
        (MailEventKind.DELIVERED, "00000000-0000-4000-8000-0000000000dd")
    ]
    assert rows[0].at == NOW - timedelta(minutes=1)


@pytest.mark.parametrize(
    "body",
    [b"", b"not json", b"[]", b'{"Type": "Something"}', b'{"Type": "Notification"}'],
)
async def test_svc_mail_hooks_garbage_is_a_bad_request(
    hook_client: AsyncClient, body: bytes
) -> None:
    assert (await hook_client.post(PATH, content=body)).status_code == 400


async def test_svc_mail_hooks_a_body_over_the_limit_is_refused(hook_client: AsyncClient) -> None:
    body = notification(event("email_delivered", to="x" * 70_000 + "@example.org"))
    assert (await hook_client.post(PATH, content=body)).status_code == 413


def test_svc_mail_hooks_parses_the_documented_envelopes() -> None:
    assert parse_envelope(CONFIRMATION) == Confirmation(subscribe_url=SUBSCRIBE_URL)
    parsed = parse_envelope(notification(event("email_dropped", field="email_rcpt_to")))
    assert parsed == Notification(
        events=(
            ProviderEvent(
                kind=MailEventKind.HARD_BOUNCE,
                recipient=ADDRESS,
                provider_message_id="00000000-0000-4000-8000-0000000000dd",
                at=NOW - timedelta(minutes=1),
            ),
        )
    )
    blocklisted = parse_envelope(notification(event("email_blocklisted")))
    assert isinstance(blocklisted, Notification)
    assert blocklisted.events[0].kind is None
    assert parse_envelope(b'{"Type": "UnsubscribeConfirmation"}') == Notification(events=())


@pytest.mark.parametrize("body", [b'{"Type": []}', b'{"Type": {"a": 1}}', b'{"Type": 1}'])
def test_svc_mail_hooks_a_type_that_is_not_text_is_not_an_envelope(body: bytes) -> None:
    assert parse_envelope(body) is None
