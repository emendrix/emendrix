"""The `content` schema: the published record, loaded for querying, and nothing else.

Every row is derived from the changelogs repository and the site's catalogue, so the whole schema
may be truncated and reloaded at any time; a migration may change it freely. Hashes are stored as
the hex text the record publishes, so a stored hash compares with a published one as written.
Arrays of dates and keys are kept as arrays, in the record's order, rather than as child tables:
nothing joins on them, and the loader writes each change in one row. Table hits are the one
child table, because matching looks a number up across every act.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from emendrix_service.db.base import Base

__all__ = ["Act", "Change", "Event", "Load", "Provision", "TableHit"]

CONTENT = {"schema": "content"}


class Act(Base):
    """One watched act, as the catalogue names it."""

    __tablename__ = "acts"
    __table_args__ = CONTENT

    corpus: Mapped[str] = mapped_column(primary_key=True)
    act_key: Mapped[str] = mapped_column(primary_key=True)
    label: Mapped[str]
    long_name: Mapped[str]
    domain: Mapped[str]
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text))
    url: Mapped[str]
    feed: Mapped[str | None]
    title: Mapped[str]
    index_sha256: Mapped[str | None]
    checked_through: Mapped[date | None]
    waiting: Mapped[list[dict[str, object]]] = mapped_column(JSONB)


class Event(Base):
    """One amendment event of one act: one payload of the record."""

    __tablename__ = "events"
    __table_args__ = (Index(None, "corpus", "act_key"), CONTENT)

    event_key: Mapped[str] = mapped_column(primary_key=True)
    corpus: Mapped[str]
    act_key: Mapped[str]
    entry_key: Mapped[str]
    from_version: Mapped[str]
    to_version: Mapped[str]
    detected_on: Mapped[date]
    in_force: Mapped[list[date]] = mapped_column(ARRAY(Date))
    updated_on: Mapped[date]
    path: Mapped[str]
    sha256: Mapped[str]
    url: Mapped[str | None]


class Change(Base):
    """One change of one event, keyed as the record keys it: location and its occurrence."""

    __tablename__ = "changes"
    __table_args__ = (Index(None, "unit"), CONTENT)

    event_key: Mapped[str] = mapped_column(
        ForeignKey("content.events.event_key", ondelete="CASCADE"), primary_key=True
    )
    location: Mapped[str] = mapped_column(primary_key=True)
    occurrence: Mapped[int] = mapped_column(primary_key=True)
    unit: Mapped[str]
    change_type: Mapped[str]
    heading: Mapped[str | None]
    previous_location: Mapped[str | None]
    disputed: Mapped[bool]
    dispute_reason: Mapped[str | None]
    signals: Mapped[dict[str, object]] = mapped_column(JSONB)
    in_force: Mapped[date | None]
    applies_from: Mapped[str]
    dates_added: Mapped[list[date]] = mapped_column(ARRAY(Date))
    dates_removed: Mapped[list[date]] = mapped_column(ARRAY(Date))
    amending_acts: Mapped[list[str]] = mapped_column(ARRAY(Text))
    changed_within: Mapped[list[str]] = mapped_column(ARRAY(Text))
    outcome: Mapped[str]
    unexplained_kind: Mapped[str]
    unexplained: Mapped[str]
    sentences: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    anchor: Mapped[str]


class TableHit(Base):
    """One identifier one side of one moved table row carries, so matching never reads text.

    A change's table-entry diff is flattened to one row per (row change, side, identifier):
    `side` is `before` or `after`, `identifier` is `scheme:value` (`cas:50-00-0`), and only CAS
    and EC numbers are kept, the two schemes a watch item may name. `row_key` and
    `row_occurrence` are the table row's key and its repeat, never the changelog entry's key.
    """

    __tablename__ = "table_hits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["event_key", "location", "occurrence"],
            ["content.changes.event_key", "content.changes.location", "content.changes.occurrence"],
            ondelete="CASCADE",
        ),
        Index(None, "identifier"),
        CONTENT,
    )

    event_key: Mapped[str] = mapped_column(primary_key=True)
    location: Mapped[str] = mapped_column(primary_key=True)
    occurrence: Mapped[int] = mapped_column(primary_key=True)
    container: Mapped[str] = mapped_column(primary_key=True)
    table_ordinal: Mapped[int] = mapped_column(primary_key=True)
    row_key: Mapped[str] = mapped_column(primary_key=True)
    row_occurrence: Mapped[int] = mapped_column(primary_key=True)
    side: Mapped[str] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str]
    typography_only: Mapped[bool]
    unit: Mapped[str]
    key_label: Mapped[str | None]
    name: Mapped[str | None]


class Provision(Base):
    """One top-level unit of an act the record has recorded a change to."""

    __tablename__ = "provisions"
    __table_args__ = CONTENT

    corpus: Mapped[str] = mapped_column(primary_key=True)
    act_key: Mapped[str] = mapped_column(primary_key=True)
    unit: Mapped[str] = mapped_column(primary_key=True)
    heading: Mapped[str | None]
    newest_version: Mapped[str]
    changes: Mapped[int]


class Load(Base):
    """One run of the loader; `finished_at` is null while it runs or after it failed."""

    __tablename__ = "loads"
    __table_args__ = CONTENT

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    root_sha256: Mapped[str]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    events_upserted: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    events_removed: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    events_skipped: Mapped[int] = mapped_column(default=0, server_default=text("0"))
