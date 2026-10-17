"""Substance watch items and the table hits they match. Revision ID: 0002.

`app.item_kind` gains `substance`; a watch item gains `identifier` (`cas:50-00-0`), and its
`corpus` and `act_key` become nullable, for that kind only, as a check constraint states. The
unique key over an item gains `identifier`. `content.table_hits` holds, per stored change, every
CAS and EC number a moved table row carries on either side, so matching reads no text.

Postgres refuses to use an enum value in the transaction that added it, so the value is added
in an autocommit block of its own before the constraint that names it.

There is no downgrade: Postgres cannot drop a value from an enum type, and the service's
migrations only move forward. Going back means restoring a backup taken before this revision.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEXT = sa.Text()
OLD_ITEM_KEY = "uq_watch_items_watchlist_id_kind_corpus_act_key_location"
ITEM_KEY = ("watchlist_id", "kind", "corpus", "act_key", "location", "identifier")
ITEM_SHAPE = (
    "(kind = 'substance' AND identifier IS NOT NULL AND corpus IS NULL AND act_key IS NULL "
    "AND location IS NULL) OR (kind <> 'substance' AND identifier IS NULL "
    "AND corpus IS NOT NULL AND act_key IS NOT NULL)"
)
CHANGE_KEY = ("event_key", "location", "occurrence")
HIT_KEY = (
    *CHANGE_KEY,
    "container",
    "table_ordinal",
    "row_key",
    "row_occurrence",
    "side",
    "identifier",
)
INTEGERS = {"occurrence", "table_ordinal", "row_occurrence"}


def col(name: str, type_: sa.types.TypeEngine[Any], *, null: bool = False) -> sa.Column[Any]:
    return sa.Column(name, type_, nullable=null)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE app.item_kind ADD VALUE IF NOT EXISTS 'substance'")
    op.add_column("watch_items", col("identifier", TEXT, null=True), schema="app")
    for name in ("corpus", "act_key"):
        op.alter_column("watch_items", name, nullable=True, schema="app")
    op.drop_constraint(OLD_ITEM_KEY, "watch_items", type_="unique", schema="app")
    op.create_unique_constraint(
        "uq_watch_items_item",
        "watch_items",
        list(ITEM_KEY),
        schema="app",
        postgresql_nulls_not_distinct=True,
    )
    op.create_check_constraint(
        "ck_watch_items_item_shape", "watch_items", sa.text(ITEM_SHAPE), schema="app"
    )
    op.create_table(
        "table_hits",
        *(col(name, sa.Integer() if name in INTEGERS else TEXT) for name in HIT_KEY),
        col("kind", TEXT),
        col("typography_only", sa.Boolean()),
        col("unit", TEXT),
        col("key_label", TEXT, null=True),
        col("name", TEXT, null=True),
        sa.ForeignKeyConstraint(
            list(CHANGE_KEY),
            [f"content.changes.{name}" for name in CHANGE_KEY],
            name="fk_table_hits_event_key_changes",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(*HIT_KEY, name="pk_table_hits"),
        schema="content",
    )
    op.create_index("ix_table_hits_identifier", "table_hits", ["identifier"], schema="content")


def downgrade() -> None:
    raise NotImplementedError("forward only: Postgres cannot drop a value from an enum type")
