"""The connection pool, and the one way a feature reaches the database: a transaction.

A feature holds a `Db` and writes `async with db.transaction() as tx:`; the block commits when it
ends and rolls back when it raises, so no code path can leave a half-written change behind or
forget to commit. Sessions never expire what they loaded on commit, because repository functions
copy rows into frozen models before the block ends and nothing reads an ORM object after it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from emendrix_service.settings import ServiceSettings

__all__ = ["COMMAND_POOL", "WEB_POOL", "Db", "Tx", "make_engine"]

WEB_POOL: Final = 5
"""Connections the web process keeps: one node's worth of concurrent pages."""

COMMAND_POOL: Final = 2
"""Connections a command keeps; every command works through one transaction at a time."""

CONNECT_TIMEOUT: Final = 5
"""Seconds a new connection may take, so `/readyz` answers rather than hangs on a dead server."""

Tx = AsyncSession
"""An open transaction, as `Db.transaction` yields it."""


def make_engine(settings: ServiceSettings, *, pool_size: int = WEB_POOL) -> AsyncEngine:
    """A pool over the configured database; nothing connects until the first query."""
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=0,
        connect_args={"connect_timeout": CONNECT_TIMEOUT},
    )


class Db:
    """The database of one process: an engine and the sessions made over it."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def connect(cls, settings: ServiceSettings, *, pool_size: int = WEB_POOL) -> Db:
        """A `Db` over the configured database."""
        return cls(make_engine(settings, pool_size=pool_size))

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Tx]:
        """One transaction: committed when the block ends, rolled back when it raises."""
        async with self._sessions() as session, session.begin():
            yield session

    async def answers(self) -> bool:
        """Whether the server answers a trivial query."""
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):
            return False
        return True

    async def dispose(self) -> None:
        """Close every pooled connection."""
        await self.engine.dispose()
