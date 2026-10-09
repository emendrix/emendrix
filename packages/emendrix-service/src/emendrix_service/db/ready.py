"""What `/readyz` asks of the database before the web process is sent traffic.

A check returns `None` when ready and a reason when not. The reason is shown on the probe's own
answer, which nothing outside the cluster reaches, so it names the problem plainly and never the
address or credentials of the server.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.exc import SQLAlchemyError

from emendrix_service.db.engine import Db
from emendrix_service.db.migrate import current_matches_head

__all__ = ["NOT_ANSWERING", "NOT_MIGRATED", "ReadyCheck", "ready_checks"]

ReadyCheck = Callable[[], Awaitable[str | None]]
"""One readiness check: `None` when ready, else the reason it is not."""

NOT_ANSWERING = "the database does not answer"
NOT_MIGRATED = "the database is not at the newest migration; run emendrix-service migrate"


def ready_checks(db: Db) -> list[ReadyCheck]:
    """The database's checks, in the order they are asked: reachable, then migrated."""

    async def answers() -> str | None:
        return None if await db.answers() else NOT_ANSWERING

    async def migrated() -> str | None:
        try:
            current = await current_matches_head(db)
        except (SQLAlchemyError, OSError):
            return NOT_ANSWERING
        return None if current else NOT_MIGRATED

    return [answers, migrated]
