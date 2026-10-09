"""Export and delete: one file of everything a reader owns, and a deletion that forgets them."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from emendrix_service import DISCLAIMER
from emendrix_service.db import Db, Tx
from emendrix_service.db.enums import (
    AuditAction,
    Cadence,
    DeliveryKind,
    ItemKind,
    MailEventKind,
    OutboxPurpose,
    SuppressionReason,
    TokenPurpose,
    UserStatus,
)
from emendrix_service.db.outbox import enqueue
from emendrix_service.db.suppressions import email_sha256
from emendrix_service.db.tables import (
    AuditLog,
    Base,
    Delivery,
    LoginToken,
    MailEvent,
    Match,
    Outbox,
    Suppression,
    User,
    WatchItem,
    Watchlist,
)
from emendrix_service.leave.routes import export_bytes
from emendrix_service.mail.message import OutgoingMail
from emendrix_service.web.csrf import SESSION_COOKIE
from tests.conftest import NOW
from tests.test_svc_db_cascade import a_person, counts
from tests.test_svc_watch_fixtures import TOKEN, sign_in

pytestmark = pytest.mark.anyio

OWNER = "owner@example.org"
OTHER = "other@example.org"
FEED_HASH = bytes(range(32))
BODY = "the body of a weekly email"
SECTIONS = {
    "format",
    "disclaimer",
    "user",
    "consents",
    "watchlists",
    "items",
    "matches",
    "deliveries",
    "outbox",
    "sessions",
    "audit_log",
}


async def furnish(tx: Tx, user_id: UUID, email: str, reason: SuppressionReason) -> None:
    """A row in every table that names the reader, by id, address or digest."""
    watchlist = Watchlist(
        user_id=user_id,
        name="Flat rules",
        cadence=Cadence.WEEKLY,
        date_alerts=True,
        feed_token_hash=FEED_HASH,
        created_at=NOW,
    )
    tx.add(watchlist)
    await tx.flush()
    tx.add(
        WatchItem(
            watchlist_id=watchlist.id,
            kind=ItemKind.PROVISION,
            corpus="toy",
            act_key="house-rules",
            location="AR 2",
            created_at=NOW,
        )
    )
    mail = OutgoingMail(to=email, subject="Weekly", text=BODY, html=f"<p>{BODY}</p>")
    outbox_id = await enqueue(
        tx, purpose=OutboxPurpose.WEEKLY, to=email, mail=mail, user_id=user_id, now=NOW
    )
    await enqueue(tx, purpose=OutboxPurpose.SIGNUP, to=email, mail=mail, user_id=None, now=NOW)
    delivery = Delivery(
        watchlist_id=watchlist.id,
        kind=DeliveryKind.WEEKLY,
        period_key="2026-W42",
        outbox_id=outbox_id,
        created_at=NOW,
    )
    tx.add(delivery)
    await tx.flush()
    tx.add(
        Match(
            watchlist_id=watchlist.id,
            event_key="toy/house-rules@v3",
            location="AR 2",
            occurrence=1,
            date_alert=False,
            matched_at=NOW,
            delivery_id=delivery.id,
        )
    )
    tx.add(
        LoginToken(
            token_hash=b"login" + bytes(27),
            email=email,
            purpose=TokenPurpose.SIGNIN,
            created_at=NOW,
            expires_at=NOW,
        )
    )
    digest = email_sha256(email)
    tx.add(MailEvent(email_sha256=digest, kind=MailEventKind.HARD_BOUNCE, at=NOW))
    tx.add(Suppression(email_sha256=digest, reason=reason, created_at=NOW))
    tx.add(AuditLog(user_id=user_id, action=AuditAction.SIGNOUT_ALL, at=NOW))
    await tx.flush()


async def a_reader(db: Db, client: AsyncClient, reason: SuppressionReason) -> UUID:
    user_id = await sign_in(db, client, OWNER)
    async with db.transaction() as tx:
        await furnish(tx, user_id, OWNER, reason)
        await a_person(tx, OTHER)
    return user_id


async def test_svc_leave_the_export_holds_every_section_and_only_the_reader(
    client: AsyncClient, db: Db
) -> None:
    user_id = await a_reader(db, client, SuppressionReason.HARD_BOUNCE)
    response = await client.get("/account/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == (
        'attachment; filename="emendrix-export-2026-10-12.json"'
    )
    document = json.loads(response.content)
    assert set(document) == SECTIONS
    assert document["format"] == "emendrix-account-export/1"
    assert document["disclaimer"] == DISCLAIMER
    assert document["user"]["id"] == str(user_id)
    assert document["user"]["email"] == OWNER
    for section, size in (
        ("consents", 2),
        ("watchlists", 1),
        ("items", 1),
        ("matches", 1),
        ("deliveries", 1),
        ("outbox", 1),
        ("sessions", 1),
        ("audit_log", 1),
    ):
        assert len(document[section]) == size, section
    assert document["watchlists"][0]["has_feed"] is True
    assert set(document["sessions"][0]) == {"created_at", "expires_at"}
    text = response.text
    assert OTHER not in text
    for secret in ("token_hash", "id_hash", "feed_token_hash", FEED_HASH.hex(), BODY, "headers"):
        assert secret not in text, secret
    assert response.content == export_bytes(document), "keys sorted, indented, one newline"
    async with db.transaction() as tx:
        actions = (
            await tx.scalars(select(AuditLog.action).where(AuditLog.user_id == user_id))
        ).all()
    assert sorted(actions) == sorted([AuditAction.SIGNOUT_ALL, AuditAction.EXPORT])


async def test_svc_leave_the_export_needs_a_session(client: AsyncClient, db: Db) -> None:
    response = await client.get("/account/export")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/account/signin")


async def owned_rows(tx: Tx, user_id: UUID, email: str) -> dict[str, int]:
    """Every row naming the reader, table by table, the audit log and suppressions aside."""
    found: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        if table.schema != "app" or table.name in {"audit_log", "suppressions"}:
            continue
        columns = table.c
        if "user_id" in columns:
            where = columns.user_id == user_id
        elif "watchlist_id" in columns:
            where = columns.watchlist_id.in_(
                select(Watchlist.id).where(Watchlist.user_id == user_id)
            )
        elif "email" in columns:
            where = columns.email == email
        elif "email_sha256" in columns:
            where = columns.email_sha256 == email_sha256(email)
        else:
            where = columns.id == user_id
        query = select(func.count()).select_from(table).where(where)
        found[table.fullname] = int(await tx.scalar(query) or 0)
    found["app.outbox (by address)"] = int(
        await tx.scalar(select(func.count()).select_from(Outbox).where(Outbox.to_email == email))
        or 0
    )
    return found


@pytest.mark.parametrize(
    ("reason", "kept"),
    [(SuppressionReason.COMPLAINT, 1), (SuppressionReason.HARD_BOUNCE, 0)],
)
async def test_svc_leave_deleting_forgets_the_reader_but_a_complaint(
    client: AsyncClient, db: Db, reason: SuppressionReason, kept: int
) -> None:
    user_id = await a_reader(db, client, reason)
    session = client.cookies[SESSION_COOKIE]
    async with db.transaction() as tx:
        before = await counts(tx)
        assert all((await owned_rows(tx, user_id, OWNER)).values())
    page = await client.get("/account/delete")
    assert page.status_code == 200 and "Delete my account" in page.text
    assert '<a class="button secondary" href="/account/settings">Keep it</a>' in page.text
    response = await client.post("/account/delete", data={"csrf": TOKEN.findall(page.text)[0]})
    assert response.status_code == 200
    assert "Your account is deleted" in response.text and "35 days" in response.text
    cleared = response.headers["set-cookie"]
    assert cleared.startswith(f"{SESSION_COOKIE}=") and "Max-Age=0" in cleared
    async with db.transaction() as tx:
        assert set((await owned_rows(tx, user_id, OWNER)).values()) == {0}
        after = await counts(tx)
        suppressed = await tx.scalar(
            select(func.count())
            .select_from(Suppression)
            .where(Suppression.email_sha256 == email_sha256(OWNER))
        )
        logged = (
            await tx.scalars(select(AuditLog.action).where(AuditLog.user_id == user_id))
        ).all()
    assert suppressed == kept
    assert AuditAction.DELETE in logged
    for name in ("app.users", "app.watchlists", "app.sessions", "app.matches"):
        assert after[name] == 1, f"{name} keeps the other reader's row"
    assert after["app.users"] == before["app.users"] - 1
    client.cookies.set(SESSION_COOKIE, session, domain="example.org")
    signed_out = await client.get("/account/")
    assert signed_out.status_code == 303


async def test_svc_leave_a_suspended_reader_may_still_export_and_delete(
    client: AsyncClient, db: Db
) -> None:
    user_id = await sign_in(db, client, OWNER)
    async with db.transaction() as tx:
        await tx.execute(update(User).values(status=UserStatus.SUSPENDED))
    account = await client.get("/account/settings")
    assert 'href="/account/export"' in account.text and 'href="/account/delete"' in account.text
    assert (await client.get("/account/export")).status_code == 200
    page = await client.get("/account/delete")
    response = await client.post("/account/delete", data={"csrf": TOKEN.findall(page.text)[0]})
    assert response.status_code == 200
    async with db.transaction() as tx:
        assert await tx.get(User, user_id) is None


async def test_svc_leave_the_privacy_page_says_when_none_is_configured(client: AsyncClient) -> None:
    page = await client.get("/account/privacy")
    assert page.status_code == 404
    assert "No privacy notice is configured for this service." in page.text
    assert DISCLAIMER.split("'")[0] in page.text
