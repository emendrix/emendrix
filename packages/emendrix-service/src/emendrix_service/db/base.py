"""The declarative base every table is declared on, and how Python types become column types.

Constraint and index names follow one convention, so a migration written today and the metadata
of a later version name the same object the same way, and `compare_metadata` can hold them equal.
Every timestamp is `timestamptz` and is written aware, in UTC, from the injected clock; no column
takes its time from the database's own `now()`, so a test standing at a fixed instant sees that
instant stored. Text is `text`, never `varchar(n)`: a length limit belongs to validation, where
it can be named.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Final

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, LargeBinary, MetaData, Text, Uuid
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeEngine

from emendrix_service.db import enums

__all__ = ["NAMING", "SCHEMAS", "Base", "enum_type"]

SCHEMAS: Final = ("app", "content", "notify")
"""The three schemas the service owns: user data, the derived record, the notifier's ledger."""

NAMING: Final = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def enum_type(kind: type[StrEnum], *, schema: str = "app") -> Enum:
    """The named Postgres enum holding the values (not the member names) of `kind`."""
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", kind.__name__).lower()
    return Enum(
        kind,
        name=name,
        schema=schema,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


TYPES: Final[dict[Any, TypeEngine[Any]]] = {
    datetime: DateTime(timezone=True),
    date: Date(),
    uuid.UUID: Uuid(),
    bytes: LargeBinary(),
    str: Text(),
    int: Integer(),
    bool: Boolean(),
    **{
        kind: enum_type(kind)
        for kind in (
            enums.UserStatus,
            enums.ConsentKind,
            enums.TokenPurpose,
            enums.Cadence,
            enums.ItemKind,
            enums.DeliveryKind,
            enums.OutboxPurpose,
            enums.OutboxStatus,
            enums.SuppressionReason,
            enums.MailEventKind,
            enums.AuditAction,
        )
    },
}
"""The column type of each annotation a table uses; an enum class becomes its named enum."""


class Base(DeclarativeBase):
    """The base of every table in the three schemas."""

    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = TYPES
