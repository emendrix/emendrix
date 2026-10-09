"""The migration and the models describe one schema, and it has everything the models name."""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, text

from emendrix_service.db import Db
from emendrix_service.db.base import SCHEMAS
from emendrix_service.db.migrate import (
    VERSION_SCHEMA,
    current_matches_head,
    head_revisions,
    include_name,
)
from emendrix_service.db.tables import Base

pytestmark = pytest.mark.anyio

ENUMS = {
    "audit_action",
    "cadence",
    "consent_kind",
    "delivery_kind",
    "item_kind",
    "mail_event_kind",
    "outbox_purpose",
    "outbox_status",
    "suppression_reason",
    "token_purpose",
    "user_status",
}


def differences(connection: Connection) -> list[object]:
    context = MigrationContext.configure(
        connection,
        opts={
            "include_schemas": True,
            "include_name": include_name,
            "version_table_schema": VERSION_SCHEMA,
            "compare_type": True,
            "compare_server_default": True,
        },
    )
    return list(compare_metadata(context, Base.metadata))


async def test_svc_the_migration_and_the_models_agree(db: Db) -> None:
    async with db.engine.connect() as connection:
        assert await connection.run_sync(differences) == []


async def test_svc_the_schemas_the_extension_and_every_enum_exist(db: Db) -> None:
    async with db.transaction() as tx:
        schemas: set[str] = set(
            (
                await tx.execute(text("SELECT schema_name FROM information_schema.schemata"))
            ).scalars()
        )
        extensions: set[str] = set(
            (await tx.execute(text("SELECT extname FROM pg_extension"))).scalars()
        )
        enums = (
            await tx.execute(
                text(
                    "SELECT t.typname, n.nspname FROM pg_type t "
                    "JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typtype = 'e'"
                )
            )
        ).all()
    assert set(SCHEMAS) <= schemas
    assert "citext" in extensions
    assert {(name, "app") for name in ENUMS} == {(name, schema) for name, schema in enums}


async def test_svc_the_database_is_stamped_at_0001(db: Db) -> None:
    async with db.transaction() as tx:
        versions = (await tx.execute(text("SELECT version_num FROM notify.alembic_version"))).all()
    assert [tuple(row) for row in versions] == [("0001",)]
    assert head_revisions() == {"0001"}
    assert await current_matches_head(db)


async def test_svc_every_table_is_in_one_of_the_three_schemas() -> None:
    assert {table.schema for table in Base.metadata.sorted_tables} == set(SCHEMAS)
    assert len(Base.metadata.sorted_tables) == 18
