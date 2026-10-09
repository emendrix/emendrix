"""How Alembic connects: asynchronously, over psycopg, to the three schemas only.

Alembic runs this module for every command. The URL and the version table's schema come from the
configuration `db/migrate.py` builds (or, for a developer, from `alembic.ini`). Autogenerate
compares against `Base.metadata` and looks only at `app`, `content` and `notify`, so an object in
`public` is never proposed for removal.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema

from emendrix_service.db import tables
from emendrix_service.db.migrate import VERSION_SCHEMA, include_name

config = context.config
target_metadata = tables.Base.metadata
version_table_schema = config.get_main_option("version_table_schema", VERSION_SCHEMA)


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("no database URL is configured for the migration")
    return url


def _configure(**options: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema=version_table_schema,
        compare_type=True,
        **options,  # type: ignore[arg-type]
    )


def run_migrations_offline() -> None:
    """Write the SQL of the migrations instead of running them."""
    _configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # Alembic writes its version table before the first revision runs, so the schema that
    # holds it has to exist first.
    connection.execute(CreateSchema(version_table_schema, if_not_exists=True))
    connection.commit()
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_url(), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
