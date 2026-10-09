"""The rows the loader writes, built from the record's own models and nothing else.

Every field is read off the catalogue, an index row or a payload. The only values computed here
are the ones whose rule is stated where they are built: the event key, a change's occurrence and
anchor (the site's counting rule, through `emendrix_record.links`), the flattening of
`applies_from` exactly as the act index flattens it, and a provision's summary of the changes
stored for it. Nothing here reads a file, the database or the clock.

Where a payload and its index row both state a fact, the payload is read, except for `disputed`
and `dispute_reason`: payloads written before the reason existed do not store it, and the index
row always carries both.
"""

from __future__ import annotations

from datetime import date

from emendrix_record.links import entry_anchors
from emendrix_record.models import ActIndex, ActRow, CatalogueAct, EventRow
from emendrix_record.payload import ChangeRecord, Payload, Sentence
from emendrix_record.record import entry_key, row_for
from emendrix_service.load.models import (
    ActLoad,
    ChangeLoad,
    EventLoad,
    FiledRow,
    Json,
    ProvisionLoad,
    StoredUnitChange,
)

__all__ = [
    "act_load",
    "applies_from",
    "change_loads",
    "event_key",
    "event_load",
    "filed_rows",
    "provision_loads",
    "sentences_json",
]


def event_key(corpus: str, act_key: str, to_version: str) -> str:
    """An event's identity: a repair never changes `to_version`, so it never changes this."""
    return f"{corpus}/{act_key}@{to_version}"


def act_load(
    row: CatalogueAct,
    index_row: ActRow | None,
    checked_through: date | None,
    *,
    index_sha256: str | None,
) -> ActLoad:
    """The act as the catalogue lists it; `index_sha256` is what the loader may vouch for."""
    return ActLoad(
        corpus=row.corpus,
        act_key=row.key,
        label=row.label,
        long_name=row.long_name,
        domain=row.domain,
        aliases=row.aliases,
        url=row.url,
        feed=row.feed,
        title=row.label if index_row is None else index_row.title,
        index_sha256=index_sha256,
        checked_through=checked_through,
        waiting=tuple(waiting.model_dump(mode="json") for waiting in row.waiting),
    )


def event_load(
    corpus: str, act_key: str, event: EventRow, catalogue_act: CatalogueAct
) -> EventLoad:
    """The event as its act index row states it, with its page from the catalogue."""
    entry = entry_key(event)
    return EventLoad(
        event_key=event_key(corpus, act_key, event.to_version),
        corpus=corpus,
        act_key=act_key,
        entry_key=entry,
        from_version=event.from_version,
        to_version=event.to_version,
        detected_on=event.detected_on,
        in_force=event.in_force,
        updated_on=event.updated_on,
        path=event.path,
        sha256=event.sha256,
        url=catalogue_act.events.get(entry),
    )


def _unit(index: ActIndex, location: str) -> str | None:
    """The act index's key for `location`: the shortest one it extends word by word."""
    words = location.split(" ")
    for size in range(1, len(words) + 1):
        candidate = " ".join(words[:size])
        if candidate in index.provisions:
            return candidate
    return None


def filed_rows(index: ActIndex, event: EventRow, payload: Payload) -> tuple[FiledRow | None, ...]:
    """The index row of every payload change, in payload order; null where the index has none."""
    changes = payload.changes
    filed: list[FiledRow | None] = []
    for position, change in enumerate(changes):
        row = row_for(index, event, changes, position)
        unit = _unit(index, change.change.provision.location)
        filed.append(None if row is None or unit is None else FiledRow(unit=unit, row=row))
    return tuple(filed)


def _sentence(sentence: Sentence) -> Json:
    return {
        "text": sentence.text,
        "fallback": sentence.fallback,
        "citations": [
            {"label": citation.label, "url": citation.url} for citation in sentence.citations
        ],
    }


def sentences_json(record: ChangeRecord) -> tuple[Json, ...]:
    """The stored sentences, then the applicability note, if any, marked as the note."""
    sentences = [_sentence(sentence) for sentence in record.sentences]
    if record.applicability_note is not None:
        sentences.append({**_sentence(record.applicability_note), "note": True})
    return tuple(sentences)


def applies_from(record: ChangeRecord) -> str:
    """`applies_from` flattened as the act index flattens it: a date, `unknown`, `unchanged`."""
    value = record.change.applies_from
    return value.isoformat() if isinstance(value, date) else value.kind


def change_loads(
    event_key: str, entry_key: str, payload: Payload, rows: tuple[FiledRow | None, ...]
) -> tuple[ChangeLoad, ...]:
    """Every change of one payload, in payload order, paired with `rows` by position.

    A change the act index files no row for keeps its own location as its unit and the
    payload's `disputed` and `dispute_reason`; the index files every change, so this is a
    record that contradicts itself, kept rather than dropped.
    """
    if len(rows) != len(payload.changes):
        raise ValueError("one index row, or None, is needed per payload change")
    locations = [record.change.provision.location for record in payload.changes]
    anchors = entry_anchors(entry_key, locations)
    seen: dict[str, int] = {}
    loads: list[ChangeLoad] = []
    for record, filed, anchor in zip(payload.changes, rows, anchors, strict=True):
        change = record.change
        location = change.provision.location
        seen[location] = seen.get(location, 0) + 1
        loads.append(
            ChangeLoad(
                event_key=event_key,
                location=location,
                occurrence=seen[location],
                unit=location if filed is None else filed.unit,
                change_type=change.change_type,
                heading=change.heading,
                previous_location=change.previous_location,
                disputed=change.disputed if filed is None else filed.row.disputed,
                dispute_reason=change.dispute_reason if filed is None else filed.row.dispute_reason,
                signals=change.signals.model_dump(mode="json"),
                in_force=change.in_force,
                applies_from=applies_from(record),
                dates_added=change.dates_added,
                dates_removed=change.dates_removed,
                amending_acts=tuple(act.key for act in change.amending_acts),
                changed_within=change.changed_within,
                outcome=record.outcome,
                unexplained_kind=record.unexplained_kind,
                unexplained=record.unexplained,
                sentences=sentences_json(record),
                anchor=anchor,
            )
        )
    return tuple(loads)


def provision_loads(
    corpus: str, act_key: str, changes: tuple[StoredUnitChange, ...]
) -> tuple[ProvisionLoad, ...]:
    """One row per unit the stored changes of one act are filed under, sorted by unit.

    The newest change is the one of the greatest `to_version`, the order the act index lists
    events in; within one event the unit's own location, then the lowest occurrence, comes
    first, because stored changes keep no payload order.
    """
    by_unit: dict[str, list[StoredUnitChange]] = {}
    for change in changes:
        by_unit.setdefault(change.unit, []).append(change)
    loads: list[ProvisionLoad] = []
    for unit in sorted(by_unit):
        stored = by_unit[unit]
        newest_version = max(change.to_version for change in stored)
        newest = min(
            (change for change in stored if change.to_version == newest_version),
            key=lambda change: (change.location, change.occurrence),
        )
        loads.append(
            ProvisionLoad(
                corpus=corpus,
                act_key=act_key,
                unit=unit,
                heading=newest.heading,
                newest_version=newest_version,
                changes=len(stored),
            )
        )
    return tuple(loads)
