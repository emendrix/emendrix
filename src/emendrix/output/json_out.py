"""The structured artifact: one amendment event as a versioned JSON document.

The second output of the loop: structured JSON for the same content, so other tools can
consume it. Because other tools consume it, it carries `schema_version` from the first byte
and is documented rather than left for a reader to infer from an example.

**A `ChangelogEntry` is the unit both renderers consume.** The Markdown renderer
(`markdown.py`) and this schema are two views of one object, so they cannot drift: a count
printed in the changelog is the same field a consumer reads out of the JSON. The entry is built
from `graph.report.EmittedDelta`, the EMIT stage's typed document, plus the one thing that
document holds at run level rather than per act: the date the run observed.

**Nothing here re-derives anything.** The per-change signal provenance is `Change.signals` as
corroboration left it, the gate flags are `EmittedChange.outcome` and
`EmittedSentence.fallback` as the gate left them, and the citations were rendered by the
adapter at emit time. This module counts, wraps and serialises; it does not decide.

No clock, no network, no corpus: `detected_on` is passed in from the CLI boundary, which is
what makes two runs of one event produce identical bytes.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, ChangeType, Delta, DeltaSummary, VersionId
from emendrix.corroborate import CorroborationReport
from emendrix.explain import CallUsage, RunStats
from emendrix.gate import GateOutcome, GateStats
from emendrix.graph.report import EmittedChange, EmittedDelta, EmittedSentence, RunReport
from emendrix.output.disclaimer import DISCLAIMER

__all__ = [
    "DIFF_ONLY_NOTE",
    "SCHEMA_VERSION",
    "ChangelogEntry",
    "EntryCounts",
    "RepairRecord",
    "act_dir_for",
    "diff_only_entry",
    "entries_for",
    "payload_for",
    "slug",
]

SCHEMA_VERSION: Final = "1.0"
"""Bumped whenever a consumer would have to change to keep reading these documents.

`1.0` is the first published shape. A field added with a default is *not* a bump; a field
removed, renamed or re-meant is.
"""

DIFF_ONLY_NOTE: Final = "diff-only mode: the explain stage did not run for this entry"
"""Why a `--markdown` diff carries no prose. Recorded on the change, not implied by silence."""

_UNSAFE: Final = re.compile(r"[^A-Za-z0-9._-]+")


def slug(value: str) -> str:
    """A filesystem-safe form of a corpus identifier, for a path segment.

    Version tags and act keys are already safe in the EU corpus (`02024R1689-20260727`), but
    they are *opaque*: the core never reads them, so nothing guarantees the next corpus keeps to
    that alphabet, and a `/` in one would silently write outside the act's directory.
    """
    cleaned = _UNSAFE.sub("_", value).strip("._-")
    return cleaned or "unnamed"


def act_dir_for(act: ActId) -> str:
    """`eu/32017R0745` — one directory per act, namespaced by its corpus.

    A function as well as a property on the entry, because the layout is also the answer to
    "has this transition already been written?", and that question is asked *before* there is
    an entry to ask it of: a backfill consults it to decide what it need not pay for again.
    """
    return f"{slug(act.corpus)}/{slug(act.key)}"


def payload_for(act: ActId, version: VersionId | str) -> str:
    """`eu/32017R0745/changes/02017R0745-20200424.json`, relative to the repository root.

    The one place the output layout is spelled out, so that the writer and the reader of that
    layout cannot drift: `OutputRepo.write` puts a transition here and `OutputRepo.holds` looks
    for it here.
    """
    return f"{act_dir_for(act)}/changes/{slug(str(version))}.json"


class EntryCounts(BaseModel):
    """The counts a reader is shown first, at the unit of change.

    `substantive` and `date_only` split the touched units by whether *anything but a date*
    moved: a unit whose every change is `DEFERRED` is a date-only unit. The split is
    the one the Markdown header prints ("Provisions touched: 14 · Substantive: 9 ·
    Date-only: 5") and it is computed, never asserted.
    """

    model_config = ConfigDict(frozen=True)

    touched: int = Field(default=0, ge=0, description="Top-level units this event touched.")
    substantive: int = Field(default=0, ge=0, description="Touched units that are not date-only.")
    date_only: int = Field(default=0, ge=0, description="Units whose every change is DEFERRED.")
    disputed: int = Field(default=0, ge=0, description="Changes the signals disagree about.")
    quoted: int = Field(
        default=0, ge=0, description="Sentences the citation gate wrote as verbatim quotations."
    )
    unexplained: int = Field(
        default=0, ge=0, description="Changes that ship with no prose at all, and say why."
    )


class RepairRecord(BaseModel):
    """One repair applied to this entry after it was first written.

    The `explain` and `gate` blocks record the run that produced the entry and stay as that run
    left them: no repair retracts a call that was made, and summing them would turn a record of
    one run into a lifetime total. What a later pass did is recorded here instead.
    """

    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1, description="Which repair this was.")
    repaired_on: date = Field(description="Passed in from the CLI boundary; never clock-read here.")
    addressed: int = Field(default=0, ge=0, description="Changes this repair looked at.")
    repaired: int = Field(default=0, ge=0, description="Changes it actually changed.")
    remaining: int = Field(default=0, ge=0, description="Changes it addressed and could not fix.")
    usage: CallUsage = CallUsage()
    coordinates_checked: bool = Field(
        default=False,
        description="Whether a coordinate check ran; False suppresses the count rather than "
        "letting an unrun check read as a pass.",
    )


def _sentences(change: EmittedChange) -> tuple[EmittedSentence, ...]:
    note = change.applicability_note
    return change.sentences if note is None else (*change.sentences, note)


def _counts(delta: EmittedDelta, *, diff_only: bool) -> EntryCounts:
    units: dict[str, list[ChangeType]] = {}
    for emitted in delta.changes:
        units.setdefault(emitted.change.unit.canonical, []).append(emitted.change.change_type)
    date_only = sum(
        1 for kinds in units.values() if all(kind is ChangeType.DEFERRED for kind in kinds)
    )
    quoted = sum(
        1 for emitted in delta.changes for sentence in _sentences(emitted) if sentence.fallback
    )
    return EntryCounts(
        touched=len(units),
        substantive=len(units) - date_only,
        date_only=date_only,
        disputed=sum(1 for emitted in delta.changes if emitted.change.disputed),
        # In diff-only mode nothing was asked of a model, so nothing is missing: reporting
        # 45 "unexplained" changes there would be a defect count for a stage that never ran.
        quoted=0 if diff_only else quoted,
        unexplained=0 if diff_only else sum(1 for e in delta.changes if not e.sentences),
    )


class ChangelogEntry(BaseModel):
    """One amendment event of one act: the JSON document, and the Markdown renderer's input."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    disclaimer: str = DISCLAIMER
    act: ActId
    from_version: VersionId
    to_version: VersionId
    detected_on: date = Field(description="Observation date, passed in; never clock-read here.")
    in_force: tuple[date, ...] = Field(
        default=(), description="Clock 1, as the changes report it — usually exactly one."
    )
    diff_only: bool = Field(
        default=False, description="Rendered from a bare `Delta`; no model stage ran."
    )
    summary: DeltaSummary
    counts: EntryCounts
    changes: tuple[EmittedChange, ...] = ()
    corroboration: CorroborationReport | None = None
    explain: RunStats | None = None
    gate: GateStats = GateStats()
    repairs: tuple[RepairRecord, ...] = Field(
        default=(), description="Repairs applied after this entry was first written, oldest first."
    )

    @classmethod
    def of(cls, delta: EmittedDelta, *, detected_on: date, diff_only: bool = False) -> Self:
        """Wrap one emitted delta. The only computation is the counts; everything else rides."""
        return cls(
            act=delta.act,
            from_version=delta.from_version,
            to_version=delta.to_version,
            detected_on=detected_on,
            in_force=tuple(
                sorted(
                    {
                        emitted.change.in_force
                        for emitted in delta.changes
                        if emitted.change.in_force is not None
                    }
                )
            ),
            diff_only=diff_only,
            summary=delta.summary,
            counts=_counts(delta, diff_only=diff_only),
            changes=delta.changes,
            corroboration=delta.corroboration,
            explain=delta.explain,
            gate=delta.gate,
        )

    @property
    def key(self) -> str:
        """The event's identity in the output repository: the version it produced.

        The version tag, and neither the amending act nor a date read from a clock. No stage of
        this loop resolves the amending act's identifier, because an event names the
        *consolidation* rather than what caused it; and a clock-read date would make a re-run on
        a later day write a second file for the same event, which is the opposite of the
        idempotency the output repository is built on. The version tag is the identity of the
        event, it already carries the date for a consolidated version, and it is stable forever.
        """
        return slug(self.to_version)

    @property
    def act_dir(self) -> str:
        """`eu/32017R0745` — one directory per act, namespaced by its corpus.

        Two corpora may key an act the same way; `ActId` identity is `(corpus, key)` and the
        layout says so, rather than trusting that a collision will not happen.
        """
        return act_dir_for(self.act)

    @property
    def title(self) -> str:
        """What a reader calls this act: its display name if the watchlist gave it one."""
        return self.act.display_name or self.act.key

    def to_json(self) -> str:
        """The document as committed bytes. Indented and newline-terminated, so git diffs it."""
        return self.model_dump_json(indent=2) + "\n"


def entries_for(report: RunReport) -> tuple[ChangelogEntry, ...]:
    """Every act's transition in one run of the loop, in the report's order."""
    return tuple(
        ChangelogEntry.of(delta, detected_on=report.observed_on) for delta in report.deltas
    )


def diff_only_entry(delta: Delta, *, detected_on: date) -> ChangelogEntry:
    """An entry for `emendrix diff --markdown`: the structural facts, and no prose.

    Diff-only is a first-class product mode rather than an eval mode: the deterministic half of
    the loop is the half with the measured numbers behind it, and it is useful on its own. The
    changes are wrapped as `UNEXPLAINED` because that is exactly what they are, and each one
    carries the reason rather than leaving a reader to wonder where the sentences went.
    """
    return ChangelogEntry.of(
        EmittedDelta(
            act=delta.act,
            from_version=delta.from_version,
            to_version=delta.to_version,
            summary=delta.summary,
            changes=tuple(
                EmittedChange(
                    change=change, outcome=GateOutcome.UNEXPLAINED, unexplained=DIFF_ONLY_NOTE
                )
                for change in delta.changes
            ),
        ),
        detected_on=detected_on,
        diff_only=True,
    )
