"""Toy entries written as committed payload files, for the change index to read back.

Every file is `entry.to_json()`, the committed form, at the path `OutputRepo.write` uses, so the
index is tested against the bytes a changelogs repository holds and never against a model
handed over in memory. The variants below are the shapes the hosted record carries: a later
event, a repaired one, a document written under schema `1.0`, one written before
`dispute_reason` was stored, and one whose corroboration report names units by name only.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from toy_entries import OBSERVED_ON

from emendrix.core import ProvisionLocation, VersionId
from emendrix.corroborate import CorroborationReport
from emendrix.output import ChangelogEntry
from emendrix.output.json_out import RepairRecord, payload_for

SECOND_EVENT_ON = OBSERVED_ON + timedelta(days=3)
"""When the later toy event was observed; any date after the first will do."""

DISTINCTIVE_TEXT = "and the recycling on the first Tuesday"
"""A phrase of one toy provision's `after` text, which no index file may carry."""


def write_payload(repo: Path, entry: ChangelogEntry, text: str | None = None) -> Path:
    """Write `entry` where the writer would, as `text` when given, else as its committed form."""
    path = repo / payload_for(entry.act, entry.to_version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(entry.to_json() if text is None else text, encoding="utf-8")
    return path


def at_version(entry: ChangelogEntry, version: str, detected_on: date) -> ChangelogEntry:
    """The same changes as a later event of the same act."""
    return entry.model_copy(update={"to_version": VersionId(version), "detected_on": detected_on})


def repaired(entry: ChangelogEntry, kind: str, repaired_on: date) -> ChangelogEntry:
    return entry.model_copy(
        update={"repairs": (*entry.repairs, RepairRecord(kind=kind, repaired_on=repaired_on))}
    )


def with_units(
    entry: ChangelogEntry, *, metadata_only: tuple[str, ...], instruction_only: tuple[str, ...]
) -> ChangelogEntry:
    report = CorroborationReport(
        act=entry.act,
        from_version=entry.from_version,
        to_version=entry.to_version,
        metadata_only_units=tuple(ProvisionLocation.parse(unit) for unit in metadata_only),
        instruction_only_units=tuple(ProvisionLocation.parse(unit) for unit in instruction_only),
    )
    return entry.model_copy(update={"corroboration": report})


def _edited(entry: ChangelogEntry, edit: Any) -> str:
    payload = json.loads(entry.to_json())
    edit(payload)
    return json.dumps(payload, indent=2) + "\n"


def without_dispute_reason(entry: ChangelogEntry) -> str:
    """The payload as written before `dispute_reason` was stored on each change."""

    def drop(payload: dict[str, Any]) -> None:
        for emitted in payload["changes"]:
            del emitted["change"]["dispute_reason"]

    return _edited(entry, drop)


def as_schema_1_0(entry: ChangelogEntry) -> str:
    """The payload as schema `1.0` wrote it: the older version string and no `evidence` key."""

    def downgrade(payload: dict[str, Any]) -> None:
        payload["schema_version"] = "1.0"
        del payload["evidence"]

    return _edited(entry, downgrade)
