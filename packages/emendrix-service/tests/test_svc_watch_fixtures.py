"""What the watch tests share: the record fixture loaded into `content`, and signed-in browsers.

A reader is signed in by writing an account and a session through `db/accounts` and handing the
browser the session's cookie, exactly what confirming a link leaves behind.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from emendrix_record.record import Record
from emendrix_service.auth.logic import new_token, session_expiry
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.accounts import create_session, create_user_with_consents
from emendrix_service.db.tables import Watchlist
from emendrix_service.load.run import load
from emendrix_service.web.csrf import SESSION_COOKIE
from tests.conftest import NOW

FIXTURE = Path(__file__).resolve().parents[2] / "emendrix-record" / "tests" / "fixtures"
TOKEN = re.compile(r'name="csrf" value="([^"]+)"')

HOUSE = "house-rules"
GARDEN = "garden-rules"


async def load_record(db: Db) -> None:
    counts = await load(
        db, Record(FIXTURE / "changelogs", FIXTURE / "catalogue.json"), clock=FixedClock(NOW)
    )
    assert counts.status == "complete"


@pytest.fixture
async def loaded(db: Db) -> Db:
    """`content` holding the record fixture: two toy acts, House Rules and Garden Rules."""
    await load_record(db)
    return db


async def sign_in(db: Db, http: AsyncClient, email: str) -> UUID:
    """A new account for `email`, with `http` holding one of its sessions; its id."""
    token, token_hash = new_token()
    async with db.transaction() as tx:
        user = await create_user_with_consents(tx, email, "000000000000", NOW)
        assert user is not None
        await create_session(
            tx, id_hash=token_hash, user_id=user.id, now=NOW, expires_at=session_expiry(NOW)
        )
    http.cookies.set(SESSION_COOKIE, token, domain="example.org")
    return user.id


async def csrf(http: AsyncClient, path: str = "/account/") -> str:
    """The token a form on `path` carries for this browser."""
    page = await http.get(path)
    assert page.status_code == 200, page.text
    token: str = TOKEN.findall(page.text)[0]
    return token


async def watchlist_ids(db: Db, user_id: UUID) -> list[UUID]:
    async with db.transaction() as tx:
        rows = await tx.scalars(
            select(Watchlist.id).where(Watchlist.user_id == user_id).order_by(Watchlist.created_at)
        )
        return list(rows)
