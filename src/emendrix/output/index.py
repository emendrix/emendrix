"""The change index, built from the payloads a changelogs repository has committed.

Two rules a reader needs. Every value is copied off a committed payload read through
`ChangelogEntry`, never off its raw JSON keys, and the payload's hash is taken over the bytes
as committed rather than over a re-serialisation, which would differ from the file a consumer
downloads wherever the model now writes a field the document predates. And the index carries
no provision text and no timestamp: the text is what the payload is for, and a timestamp would
make two builds of one record differ.

Nothing here writes a file, reads a clock or decides anything. Given one directory of payloads
the builders return the same model, and `render` the same bytes, whatever order the files are
listed in, because every sequence is put in an explicit order before it is stored.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import NamedTuple

from emendrix.graph.report import EmittedChange
from emendrix.output.index_model import (
    INDEX_FILE,
    ActIndex,
    ActRow,
    EventRow,
    ProvisionRow,
    RepairRow,
    RootIndex,
    SignalRow,
    TextSides,
)
from emendrix.output.json_out import ChangelogEntry

__all__ = ["act_index", "index_files", "render", "root_index"]

_CHANGES = "changes"


def render(model: RootIndex | ActIndex) -> str:
    """The index file's text: indented and newline-terminated, as the payloads are."""
    return model.model_dump_json(indent=2) + "\n"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> tuple[bytes, ChangelogEntry]:
    raw = path.read_bytes()
    try:
        return raw, ChangelogEntry.model_validate_json(raw)
    except ValueError as error:
        raise ValueError(f"{path} is not a changelog document emendrix wrote: {error}") from error


def _text_sides(emitted: EmittedChange) -> TextSides:
    before = emitted.change.before is not None
    after = emitted.change.after is not None
    if before and after:
        return "both"
    if before:
        return "before"
    return "after" if after else "none"


def _provision_row(entry: ChangelogEntry, emitted: EmittedChange, occurrence: int) -> ProvisionRow:
    change = emitted.change
    signals = change.signals
    reason = change.dispute_reason
    applies = change.applies_from
    return ProvisionRow(
        version=str(entry.to_version),
        change_type=change.change_type.value,
        previous_location=None
        if change.previous_location is None
        else change.previous_location.canonical,
        disputed=change.disputed,
        dispute_reason=None if reason is None else reason.value,
        signals=SignalRow(
            structural_diff=signals.structural_diff.status.value,
            corpus_metadata=signals.corpus_metadata.status.value,
            instruction_parse=signals.instruction_parse.status.value,
        ),
        text=_text_sides(emitted),
        in_force=change.in_force,
        applies_from=applies.isoformat() if isinstance(applies, date) else applies.kind,
        dates_added=change.dates_added,
        dates_removed=change.dates_removed,
        outcome=emitted.outcome.value,
        unexplained_kind=emitted.unexplained_kind,
        amending_acts=tuple(act.key for act in change.amending_acts),
        changed_within=tuple(location.canonical for location in change.changed_within),
        occurrence=occurrence,
    )


def _provision_rows(entry: ChangelogEntry) -> tuple[tuple[str, ProvisionRow], ...]:
    """One `(unit, row)` per change, in payload order.

    The occurrence is counted over the change's own location, which is what the site's anchor
    counter is handed, so a permalink built from a row lands on the fragment the page carries.
    """
    seen: dict[str, int] = {}
    rows: list[tuple[str, ProvisionRow]] = []
    for emitted in entry.changes:
        location = emitted.change.location.canonical
        seen[location] = seen.get(location, 0) + 1
        rows.append((emitted.change.unit.canonical, _provision_row(entry, emitted, seen[location])))
    return tuple(rows)


def _event_row(entry: ChangelogEntry, path: str, raw: bytes) -> EventRow:
    report = entry.corroboration
    return EventRow(
        to_version=str(entry.to_version),
        from_version=str(entry.from_version),
        detected_on=entry.detected_on,
        in_force=entry.in_force,
        updated_on=max((entry.detected_on, *(repair.repaired_on for repair in entry.repairs))),
        schema_version=entry.schema_version,
        path=path,
        sha256=_sha256(raw),
        diff_only=entry.diff_only,
        counts=entry.counts,
        repairs=tuple(
            RepairRow(kind=repair.kind, repaired_on=repair.repaired_on) for repair in entry.repairs
        ),
        evidence=bool(entry.evidence),
        metadata_only_units=()
        if report is None
        else tuple(unit.canonical for unit in report.metadata_only_units),
        instruction_only_units=()
        if report is None
        else tuple(unit.canonical for unit in report.instruction_only_units),
    )


class _Read(NamedTuple):
    """What one payload contributes, kept so the payload itself can be dropped once read."""

    key: str
    event: EventRow
    rows: tuple[tuple[str, ProvisionRow], ...]
    corpus: str
    act_key: str
    title: str


def act_index(repo: Path, act_dir: str) -> ActIndex:
    """The index of one act directory, from every payload under its `changes/`.

    A payload that does not validate raises `ValueError` naming it: an index that silently
    skipped a document would be wrong in a way nobody sees. A directory with no payloads raises
    too, because there is no act to name.
    """
    found: list[_Read] = []
    for path in sorted((repo / act_dir / _CHANGES).glob("*.json")):
        raw, entry = _read(path)
        relative = f"{act_dir}/{_CHANGES}/{path.name}"
        found.append(
            _Read(
                key=entry.key,
                event=_event_row(entry, relative, raw),
                rows=_provision_rows(entry),
                corpus=entry.act.corpus,
                act_key=entry.act.key,
                title=entry.title,
            )
        )
    if not found:
        raise ValueError(f"{repo / act_dir / _CHANGES} holds no changelog documents")
    # Newest event first; within one event rows keep payload order, so occurrences ascend.
    found.sort(key=lambda read: read.key, reverse=True)
    provisions: dict[str, list[ProvisionRow]] = {}
    for read in found:
        for unit, row in read.rows:
            provisions.setdefault(unit, []).append(row)
    newest = found[0]
    return ActIndex(
        corpus=newest.corpus,
        key=newest.act_key,
        title=newest.title,
        events=tuple(read.event for read in found),
        provisions={unit: tuple(rows) for unit, rows in sorted(provisions.items())},
    )


def _act_row(act: ActIndex, act_dir: str) -> ActRow:
    newest = act.events[0]
    rows = [row for rows in act.provisions.values() for row in rows]
    return ActRow(
        corpus=act.corpus,
        key=act.key,
        title=act.title,
        index=f"{act_dir}/{INDEX_FILE}",
        index_sha256=_sha256(render(act).encode("utf-8")),
        events=len(act.events),
        changes=len(rows),
        provisions=len(act.provisions),
        disputed=sum(1 for row in rows if row.disputed),
        newest_version=newest.to_version,
        newest_in_force=max(newest.in_force, default=None),
        first_detected_on=min(event.detected_on for event in act.events),
        updated_on=max(event.updated_on for event in act.events),
    )


def _act_dir(act: ActIndex) -> str:
    """Where this act's index sits: the directory its payloads were read from."""
    return act.events[0].path.rsplit(f"/{_CHANGES}/", 1)[0]


def root_index(acts: Sequence[ActIndex]) -> RootIndex:
    """The root index over the given act indexes, sorted by `(corpus, key)`."""
    ordered = sorted(acts, key=lambda act: (act.corpus, act.key))
    return RootIndex(acts=tuple(_act_row(act, _act_dir(act)) for act in ordered))


def index_files(repo: Path) -> dict[str, str]:
    """Every index file the repository should hold, by path relative to it, never written.

    Act directories are `<corpus>/<act>/` holding a `changes/` directory with at least one
    payload; they are read one at a time, in sorted order.
    """
    files: dict[str, str] = {}
    acts: list[ActIndex] = []
    for changes in sorted(repo.glob(f"*/*/{_CHANGES}")):
        if not changes.is_dir() or not any(changes.glob("*.json")):
            continue
        act_dir = changes.parent.relative_to(repo).as_posix()
        act = act_index(repo, act_dir)
        acts.append(act)
        files[f"{act_dir}/{INDEX_FILE}"] = render(act)
    files[INDEX_FILE] = render(root_index(acts))
    return dict(sorted(files.items()))
