"""What a read of the record returns: the thing asked for with its provenance, or why not.

Kept apart from `record.py`, which does the reading, because these are the shapes a reader
hands on: a caller imports them to say what it returns without touching the disk.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.models import EventRow, ProvisionRow
from emendrix_record.payload import ChangeRecord, Payload

__all__ = ["PERMALINK_UNAVAILABLE", "ChangeRead", "PayloadRead", "Unavailable"]

PERMALINK_UNAVAILABLE: Final = "permalink unavailable: this server was given no site catalogue"


class Unavailable(BaseModel):
    """What could not be read, and why, said so that it can be repeated to a reader."""

    model_config = ConfigDict(frozen=True)

    reason: str = Field(description="One sentence naming what was asked for and why it failed.")


class PayloadRead(BaseModel):
    """One payload as read now, with the hash of the bytes read and whether the index agrees."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description="The payload's path relative to the repository root.")
    sha256: str = Field(description="Hex sha256 of the bytes this read found.")
    indexed_sha256: str = Field(description="The hash the index row states for the payload.")
    matches_index: bool = Field(
        description="False when the bytes differ from what the index states: the repository "
        "is being rewritten, and the index and the payload describe different moments."
    )
    payload: Payload = Field(description="The payload, read through this server's model.")


class ChangeRead(BaseModel):
    """One change of one event, with the index rows that describe it."""

    model_config = ConfigDict(frozen=True)

    event: EventRow = Field(description="The event's row in the act index.")
    location: str = Field(description="The change's own canonical location.")
    occurrence: int = Field(ge=1, description="Which repeat of that location, from 1.")
    row: ProvisionRow | None = Field(
        description="The index row of this change, the source of its `dispute_reason`; null "
        "when the act index files no row under this location for the event."
    )
    sha256: str = Field(description="Hex sha256 of the payload bytes this read found.")
    matches_index: bool = Field(description="Whether those bytes are the ones the index states.")
    change: ChangeRecord = Field(description="The change as the payload stores it.")
