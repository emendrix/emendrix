"""The structured artifact: one amendment event as a versioned JSON document.

The second output of the loop: structured JSON for the same content, so other tools can
consume it. Because other tools consume it, it carries `schema_version` from the first byte
and is documented rather than left for a reader to infer from an example.

The counts it carries are derived next door in `counts.py`, and the evidence digests beside
them in `provenance.py`; those are the module's two real seams. This one holds the document
and asks each of them once.

**A `ChangelogEntry` is the unit both renderers consume.** The Markdown renderer
(`markdown.py`) and this schema are two views of one object, so they cannot drift: a count
printed in the changelog is the same field a consumer reads out of the JSON. The entry is built
from `graph.report.EmittedDelta`, the EMIT stage's typed document, plus the one thing that
document holds at run level rather than per act: the date the run observed.

**Nothing here re-derives anything.** The per-change signal provenance is `Change.signals` as
corroboration left it, the gate flags are `EmittedChange.outcome` and
`EmittedSentence.fallback` as the gate left them, and the citations were rendered by the
adapter at emit time. This module counts, wraps and serialises; it does not decide. The one
thing it computes besides the counts is the evidence digest, and only for a run that has just
made the calls: `ChangelogEntry.of` is told what to record and never works it out for itself,
which is what keeps a repair from inventing provenance for an entry that has none.

No clock, no network, no corpus: `detected_on` is passed in from the CLI boundary, which is
what makes two runs of one event produce identical bytes.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, Delta, DeltaSummary, VersionId
from emendrix.corroborate import CorroborationReport
from emendrix.explain import CallUsage, RunStats
from emendrix.gate import GateOutcome, GateStats
from emendrix.graph.report import EmittedChange, EmittedDelta, RunReport
from emendrix.output.counts import EntryCounts, counts_of
from emendrix.output.disclaimer import DISCLAIMER
from emendrix.output.provenance import EvidenceDigest, evidence_for

__all__ = [
    "DIFF_ONLY_NOTE",
    "SCHEMA_VERSION",
    "ChangelogEntry",
    "RepairRecord",
    "act_dir_for",
    "diff_only_entry",
    "entries_for",
    "payload_for",
    "slug",
]

SCHEMA_VERSION: Final = "1.2"
"""Bumped whenever a consumer would have to change to keep reading these documents.

`1.0` is the first published shape. A field added with a default is *not* a bump; a field
removed, renamed or re-meant is. `1.1` re-means one: `substantive` stopped covering a unit
that carries no text on either side, so summing `substantive + date_only` no longer gives
`touched`. The new `textless` count is the third term of that sum.

`1.2` says a document may carry `evidence`, and that an entry without it is one whose
provenance is unknown rather than one whose evidence is unchanged. Adding the field alone
would not have been a bump, since it has a default; the reading of its absence is one, because
a consumer that took a missing digest for an unmoved text would be wrong about every document
published before 2026-09-05.

Documents already published say `1.0` and stay readable, which is why the field's type is a
union of the three. An entry written under `1.0` reads back with `textless` at 0, the
`substantive` its own run computed and no evidence at all; it is corrected when something
rewrites it, not in bulk, and no rewrite ever invents a digest for it.
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


class ChangelogEntry(BaseModel):
    """One amendment event of one act: the JSON document, and the Markdown renderer's input."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0", "1.1", "1.2"] = SCHEMA_VERSION
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
    evidence: tuple[EvidenceDigest, ...] = Field(
        default=(),
        description="What each change's explanation was written about, digested by the run "
        "that made the call. Empty means provenance unknown, never evidence unchanged.",
    )

    @classmethod
    def of(
        cls,
        delta: EmittedDelta,
        *,
        detected_on: date,
        diff_only: bool = False,
        evidence: tuple[EvidenceDigest, ...] = (),
    ) -> Self:
        """Wrap one emitted delta. The only computation is the counts; everything else rides.

        `evidence` is passed in rather than derived here, and that is the whole safeguard: this
        constructor is also how a repair puts a committed entry back together, and an entry
        whose digests it derived from its own stored texts would claim a fact about a call
        nobody witnessed. A caller that watched the calls supplies them; every other caller
        leaves the entry saying its provenance is unknown, which is true.
        """
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
            counts=counts_of(delta, diff_only=diff_only),
            changes=delta.changes,
            corroboration=delta.corroboration,
            explain=delta.explain,
            gate=delta.gate,
            evidence=evidence,
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
    """Every act's transition in one run of the loop, in the report's order.

    This is the one place an evidence digest is written, because it is the one place holding
    the changes the explain stage was handed in the run that handed them over: the `Change`
    objects here are the objects the prompt was built from, not text read back off a document.
    A delta with no `explain` block had no model stage at all, so there is nothing whose
    provenance to record and the entry says so by carrying none.
    """
    return tuple(
        ChangelogEntry.of(
            delta,
            detected_on=report.observed_on,
            evidence=()
            if delta.explain is None
            else evidence_for(emitted.change for emitted in delta.changes),
        )
        for delta in report.deltas
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
