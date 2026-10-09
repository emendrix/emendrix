"""The database: the engine, the tables of the `app`, `content` and `notify` schemas, the
migrations, and one query module per feature. The only package that imports SQLAlchemy, Alembic
or psycopg.

A feature reaches the database through `Db.transaction()` and the query functions of its own
module here (`db/<feature>.py`), and never imports SQLAlchemy itself. **Repository functions
return frozen pydantic models, never ORM instances**: a row is copied into a value before the
transaction ends, so no lazy load, expired attribute or open session can leak into a page, an
email or a command's output.
"""

from __future__ import annotations

from emendrix_service.db.engine import COMMAND_POOL, WEB_POOL, Db, Tx
from emendrix_service.db.guards import insert_once

__all__ = ["COMMAND_POOL", "WEB_POOL", "Db", "Tx", "insert_once"]
