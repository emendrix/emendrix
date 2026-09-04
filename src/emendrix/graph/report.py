"""The EMIT stage: what the loop produces, as a typed document. Byte-stable, disclaimed.

This document is deliberately the *whole* answer rather than a summary: every change, its
verbatim before/after (inside the `Change`), the sentences that survived the gate, and a
rendered citation per key. `emendrix run` prints it as JSON, and `output/` renders it into the
Markdown changelog and the per-change JSON committed to the output repository.

Two things worth noticing about the shape.

**Citation keys become citations here and nowhere earlier.** The model saw opaque tokens
(`explain/context.py`); the gate checked those tokens; only now, on the way out, does a key
become a URL, and only through the adapter, because only a corpus knows what resolves.
Nothing upstream can invent a link, because nothing upstream can render one.

**Nothing is dropped.** A change whose explanation failed carries the reason; an act whose
version could not be fetched appears in `skipped` with its first-class state. A report where
some entries are thin is the correct output of a loop that had a thin day.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix import DISCLAIMER
from emendrix.core import (
    ActId,
    Change,
    Citation,
    Delta,
    DeltaSummary,
    ProvisionRef,
    VersionId,
)
from emendrix.corroborate import CorroborationReport
from emendrix.explain import ExplainContext, RunStats
from emendrix.gate import GatedChange, GatedDelta, GatedSentence, GateOutcome, GateStats
from emendrix.watch.events import PollStats

__all__ = [
    "ActSummary",
    "EmittedChange",
    "EmittedDelta",
    "EmittedSentence",
    "RunReport",
    "RunSummary",
    "SkippedAct",
    "build_delta_report",
    "summarise_run",
]

CitationRenderer = Callable[[ProvisionRef], Citation]
"""`CorpusAdapter.render_citation`, passed as a function so this module stays corpus-free."""


class EmittedSentence(BaseModel):
    """One sentence that shipped, with its citations resolved to clickable references."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    fallback: bool = Field(
        default=False, description="Written by the gate as a verbatim quotation, not by the model."
    )
    citations: tuple[Citation, ...] = ()


class EmittedChange(BaseModel):
    """One change as a reader receives it: the facts, then whatever prose survived the gate."""

    model_config = ConfigDict(frozen=True)

    change: Change
    outcome: GateOutcome
    sentences: tuple[EmittedSentence, ...] = ()
    applicability_note: EmittedSentence | None = None
    unexplained: str = Field(
        default="", description="Why there are no sentences, when there are none."
    )
    unexplained_kind: str = Field(
        default="",
        description="Which counted kind that reason was, empty when there are sentences.",
    )


class EmittedDelta(BaseModel):
    """One act's transition, complete: the changes, the corroboration and both stages' counts."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    from_version: VersionId
    to_version: VersionId
    summary: DeltaSummary
    changes: tuple[EmittedChange, ...] = ()
    corroboration: CorroborationReport | None = None
    explain: RunStats | None = None
    gate: GateStats = GateStats()


class SkippedAct(BaseModel):
    """A watched act the loop could not diff, and the stated reason — never an exception."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    target_version: VersionId | None = None
    reason: str = Field(min_length=1)


class RunReport(BaseModel):
    """One run of the loop, whole. The disclaimer is a field so it cannot be forgotten."""

    model_config = ConfigDict(frozen=True)

    disclaimer: str = DISCLAIMER
    observed_on: date
    poll: PollStats | None = None
    deltas: tuple[EmittedDelta, ...] = ()
    skipped: tuple[SkippedAct, ...] = ()
    gate: GateStats = GateStats()


class ActSummary(BaseModel):
    """One act's transition as counts alone: `EmittedDelta` with the prose taken out."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    from_version: VersionId
    to_version: VersionId
    summary: DeltaSummary
    explain: RunStats | None = None
    gate: GateStats = GateStats()


class RunSummary(BaseModel):
    """One run as counts alone, for a log stream rather than for a reader.

    The report is the whole answer and is the wrong thing to log: nine changes serialise to
    roughly 180 kB, so pretty-printed it reaches a collector as dozens of unparseable fragments,
    and compacted onto one line it exceeds the line caps collectors impose and is dropped
    entire. Neither failure is loud. This is the shape that survives the trip, and its size is
    bounded by how many acts are watched rather than by how much changed in them.

    Every field here is a count, an identifier or a stated reason. Nothing the model wrote
    reaches it, which is what keeps the bound true rather than merely usual.

    Measured on 2026-08-09 over the pinned MDR transition: 1,252 bytes for one amended act
    against 206,101 for the same run's report. The per-act cost is dominated by the act's
    display name, so the 32 kB line cap is not reached until roughly twenty-five acts are
    amended in one run, which is not a shape the watchlist can produce in practice.
    """

    model_config = ConfigDict(frozen=True)

    observed_on: date
    poll: PollStats | None = None
    acts: tuple[ActSummary, ...] = ()
    skipped: tuple[SkippedAct, ...] = ()
    gate: GateStats = GateStats()


def summarise_run(report: RunReport) -> RunSummary:
    """Project a report onto its counts. Deterministic, and never a clock read."""
    return RunSummary(
        observed_on=report.observed_on,
        poll=report.poll,
        acts=tuple(
            ActSummary(
                act=delta.act,
                from_version=delta.from_version,
                to_version=delta.to_version,
                summary=delta.summary,
                explain=delta.explain,
                gate=delta.gate,
            )
            for delta in report.deltas
        ),
        skipped=report.skipped,
        gate=report.gate,
    )


def _citations(
    keys: Sequence[str], context: ExplainContext, render: CitationRenderer
) -> tuple[Citation, ...]:
    """Resolve the keys a sentence carries. Every one of them passed the gate, so every one
    is in the offered set; an unknown key can only mean a caller assembled this by hand."""
    resolved = [context.resolve(key) for key in keys]
    return tuple(render(offered.ref) for offered in resolved if offered is not None)


def _sentence(
    sentence: GatedSentence, context: ExplainContext, render: CitationRenderer
) -> EmittedSentence:
    return EmittedSentence(
        text=sentence.text,
        fallback=sentence.fallback,
        citations=_citations(sentence.citations, context, render),
    )


def _change(
    change: Change,
    gated: GatedChange,
    context: ExplainContext | None,
    render: CitationRenderer,
) -> EmittedChange:
    explanation = gated.explanation
    if explanation is None or context is None:
        reason = gated.unavailable.reason if gated.unavailable is not None else "no explanation"
        # The kind rides along because the payload is also read back: `OutputRepo.holds_finished`
        # tells an entry a re-run would add nothing to from one written while the provider was
        # refusing calls, and the reason sentence alone cannot carry that.
        kind = gated.unavailable.kind if gated.unavailable is not None else ""
        return EmittedChange(
            change=change, outcome=gated.outcome, unexplained=reason, unexplained_kind=kind
        )
    note = explanation.applicability_note
    return EmittedChange(
        change=change,
        outcome=gated.outcome,
        sentences=tuple(_sentence(item, context, render) for item in explanation.sentences),
        applicability_note=None if note is None else _sentence(note, context, render),
    )


def build_delta_report(
    delta: Delta,
    gated: GatedDelta,
    contexts: Sequence[ExplainContext | None],
    render: CitationRenderer,
    *,
    corroboration: CorroborationReport | None = None,
    explain: RunStats | None = None,
) -> EmittedDelta:
    """Assemble one act's emitted delta. Pure, ordered, and free of any clock or network."""
    if not len(delta.changes) == len(gated.changes) == len(contexts):
        raise ValueError(
            f"{len(delta.changes)} changes, {len(gated.changes)} gated and {len(contexts)} "
            f"contexts; the three are paired positionally"
        )
    return EmittedDelta(
        act=delta.act,
        from_version=delta.from_version,
        to_version=delta.to_version,
        summary=delta.summary,
        changes=tuple(
            _change(change, verdict, context, render)
            for change, verdict, context in zip(delta.changes, gated.changes, contexts, strict=True)
        ),
        corroboration=corroboration,
        explain=explain,
        gate=gated.stats,
    )
