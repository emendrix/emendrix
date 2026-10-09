"""Exactly-once writes: an insert that a unique key refuses is an answer, not an error.

A delivery, a match or an announcement is written once whatever retries or overlapping runs do,
because a unique key refuses the second copy. The refusal is the expected outcome of a race, so
it comes back as `False` and the caller's transaction carries on. Only a unique violation is
answered this way; any other integrity error (a missing parent, a NULL where none is allowed) is
a bug and still raises.
"""

from __future__ import annotations

from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError

from emendrix_service.db.base import Base
from emendrix_service.db.engine import Tx

__all__ = ["insert_once"]


async def insert_once(tx: Tx, row: Base) -> bool:
    """Insert `row` unless a unique key already holds its twin; `True` when it was written.

    The insert runs in a savepoint, so a refusal rolls back only the insert and leaves the rest
    of the transaction as it was.
    """
    try:
        async with tx.begin_nested():
            tx.add(row)
            await tx.flush()
    except IntegrityError as error:
        if not isinstance(error.orig, UniqueViolation):
            raise
        if row in tx:
            tx.expunge(row)
        return False
    return True
