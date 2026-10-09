"""Alembic, configured in code: where the migrations are, which database, and which schemas.

The configuration is built from the settings rather than read from an ini file, so the image runs
`emendrix-service migrate` with nothing beside the package; `alembic.ini` at the member's root is
for a developer generating the next revision. Migrations only move forward. A revision may change
`content` freely, because it is reloaded from the record, but never drops an `app` column without
a release in which nothing reads it.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from typing import Final

import anyio.to_thread
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

from emendrix_service.db.base import SCHEMAS
from emendrix_service.db.engine import Db
from emendrix_service.settings import ServiceSettings

__all__ = [
    "VERSION_SCHEMA",
    "alembic_config",
    "current_heads",
    "current_matches_head",
    "head_revisions",
    "include_name",
    "script_location",
    "upgrade_head",
]

VERSION_SCHEMA: Final = "notify"
"""Where `alembic_version` lives: beside the ledger that, like it, must survive a reload."""


def script_location() -> str:
    """The on-disk directory of the migrations, inside the installed package."""
    return str(files("emendrix_service.db").joinpath("migrations"))


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """Whether autogenerate looks at an object: only the three schemas, never `public`."""
    if type_ == "schema":
        return name in SCHEMAS
    return True


def alembic_config(settings: ServiceSettings) -> Config:
    """The configuration every Alembic command of the service runs with."""
    config = Config()
    config.set_main_option("script_location", script_location())
    # The ini parser behind `Config` treats `%` as interpolation, which a password may contain.
    url = settings.database_url.get_secret_value().replace("%", "%%")
    config.set_main_option("sqlalchemy.url", url)
    config.set_main_option("version_table_schema", VERSION_SCHEMA)
    return config


def _upgrade(settings: ServiceSettings) -> None:
    command.upgrade(alembic_config(settings), "head")


async def upgrade_head(settings: ServiceSettings) -> None:
    """Apply every migration the database has not had.

    Alembic's commands are synchronous and run their own event loop inside `env.py`, so the
    upgrade runs in a worker thread rather than inside the caller's loop.
    """
    await anyio.to_thread.run_sync(_upgrade, settings)


@cache
def head_revisions() -> frozenset[str]:
    """The newest revision of every branch of the migration tree this package carries."""
    return frozenset(ScriptDirectory(script_location()).get_heads())


def current_heads(connection: Connection) -> frozenset[str]:
    """The revisions the database is stamped at; empty when it has never been migrated."""
    context = MigrationContext.configure(connection, opts={"version_table_schema": VERSION_SCHEMA})
    return frozenset(context.get_current_heads())


async def current_matches_head(db: Db) -> bool:
    """Whether the database stands at exactly the newest migration this package carries."""
    async with db.engine.connect() as connection:
        current = await connection.run_sync(current_heads)
    return current == head_revisions()
