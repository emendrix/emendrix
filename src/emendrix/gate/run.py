"""The gate over a whole delta, in the two rounds the retry policy allows. Still no model.

The policy is one sentence long and the code is arranged so it stays that way: **check; on
failure ask once more with the specific complaint; on a second failure quote the provision.**
`first_round` performs the check and hands back which changes want the revision; `second_round`
takes the revised answers and settles every one of them. Nothing here calls a model — the
revision itself is the orchestrator's job (`graph/`), because the gate may not be the place a
model call hides.

Two properties are asserted as properties in `tests/gate/`, not as examples:

- **Input changes == output changes, always.** A gated delta is positionally aligned with the
  delta it came from, including the changes that had nothing to explain.
- **No ungrounded sentence ships.** Every sentence in a settled `GatedDelta` either passed the
  check or was written by the gate as a verbatim quotation.

The applicability note is checked twice over and the order is deliberate. Its citations go
through the same check as any other slot, and *then* `note_is_verbatim` asks whether the note
quotes the AFTER text the model was shown. Running the second check afterwards leaves every
citation count, and so the published grounding rate, exactly where it was: a note the gate
drops is counted in `GateStats.notes_dropped` and nowhere else. It is never a reason to ask the
model again either, because a paraphrase is prose the reader is better off without rather than
a claim pointing at nothing, and the one retry exists for the second kind.

The unsupported-coordinate count follows the same shape: taken on the settled explanation only
(`_counted_coordinates`), summed into `GateStats.coordinates_unsupported`, and never a reason
to drop, rewrite or retry a sentence. Counted-only is deliberate, and the single instance the
check has ever produced is the argument for it. Read 2026-08-09: one sentence named "point (30)
of Article 2(1)", the conventional legal citation of a path the source markup spells
`AR 2 ALN 1 PO 30`, so the named paragraph exists in neither tree and the mention counts by the
check's definition while the sentence itself reads as sound. The check graduates to dropping
only when every counted instance of a recording has been read and confirmed a genuine
unsupported coordinate with no false positive of that kind, and the entries losing a sentence
still say something. Until then, a dropped true sentence is a worse trade than a counted false
one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from emendrix.core import Change, Delta
from emendrix.explain import ExplainContext, ExplainedChange, ExplainRun
from emendrix.gate.check import (
    ProvisionResolver,
    check_explanation,
    note_is_verbatim,
    unsupported_coordinates,
)
from emendrix.gate.fallback import apply_fallback, fallback_sentence
from emendrix.gate.results import (
    GatedChange,
    GatedDelta,
    GatedExplanation,
    GateOutcome,
    GateResult,
    GateStats,
)

__all__ = ["first_round", "second_round"]


def _unexplained(result: ExplainedChange) -> GatedChange:
    """No explanation to check — a model failure, or a change with nothing to explain.

    The change still ships: its verbatim before/after come from the `Change` itself and never
    from the model, so an entry with no sentences is thinner, not absent. The gate does not
    invent a quotation here, because there was no ungrounded claim to replace.

    That asymmetry is deliberate, decided 2026-08-31: the verbatim fallback exists to replace
    a claim the gate rejected, and a change that never got an explanation made no claim. The
    texts a quotation would repeat already ship with the entry, and counting a failed call
    into `fallback` would fold provider availability into `fallback_rate`, which measures
    citation failures. So the change ships its stated reason instead, counted `unexplained`.
    """
    return GatedChange(
        provision=result.provision, outcome=GateOutcome.UNEXPLAINED, unavailable=result.unavailable
    )


def _tally(
    gated: Sequence[GatedChange],
    results: Sequence[GateResult],
    notes_dropped: int,
    coordinates_unsupported: int,
) -> GateStats:
    outcomes = [change.outcome for change in gated]
    return GateStats(
        changes=len(gated),
        passed_first=outcomes.count(GateOutcome.PASSED),
        passed_on_retry=outcomes.count(GateOutcome.PASSED_ON_RETRY),
        fallback=outcomes.count(GateOutcome.FALLBACK),
        unexplained=outcomes.count(GateOutcome.UNEXPLAINED),
        retries=outcomes.count(GateOutcome.RETRY_REQUESTED),
        sentences=sum(result.sentences for result in results),
        citations=sum(result.citations for result in results),
        citations_rejected=sum(result.rejected_citations for result in results),
        notes_dropped=notes_dropped,
        coordinates_unsupported=coordinates_unsupported,
    )


def _counted_coordinates(resolved: GatedChange, change: Change, context: ExplainContext) -> int:
    """The unsupported-coordinate count for one change that just settled.

    Called exactly where an explanation becomes final — passed, passed on retry, or fallen
    back — and never on a first attempt awaiting revision, so a sentence that was retried and
    replaced is counted once, in the form that ships.
    """
    if resolved.explanation is None:
        return 0
    return len(unsupported_coordinates(resolved.explanation, context, change.location))


def _checked_note(
    explanation: GatedExplanation, change: Change, text_char_cap: int
) -> tuple[GatedExplanation, int]:
    """Drop an applicability note the AFTER text does not contain, and say so as a count.

    The one place the decision is made, so every explanation leaving this module has been asked
    the same question however it got here: passed first time, passed on retry, or assembled
    around the gate's own quotation. A dropped note is a counted outcome and never an exception,
    and the entry it came from still ships: the headline already carries `applies from:`, so a
    reader who never sees the note is not missing anything the pipeline knows.
    """
    note = explanation.applicability_note
    if note is None or note_is_verbatim(note.sentence, change.after or "", text_char_cap):
        return explanation, 0
    return explanation.model_copy(update={"applicability_note": None}), 1


def first_round(
    delta: Delta,
    run: ExplainRun,
    contexts: Sequence[ExplainContext | None],
    resolver: ProvisionResolver,
    *,
    text_char_cap: int,
) -> GatedDelta:
    """Check every explained change once. Failures come back as `RETRY_REQUESTED`.

    The three sequences are paired positionally and must be the same length — the same contract
    `explain_delta` enforces, and for the same reason: a slipped index would gate one change's
    sentences against another change's offered keys.

    `text_char_cap` is the explain settings' own cap, passed in rather than read: the gate holds
    no settings and may not grow any, and the number has to be the one that built the prompt or
    the note is checked against a text nobody was shown.
    """
    if not len(delta.changes) == len(run.results) == len(contexts):
        raise ValueError(
            f"{len(delta.changes)} changes, {len(run.results)} explanations and "
            f"{len(contexts)} contexts; the three are paired positionally"
        )
    gated: list[GatedChange] = []
    results: list[GateResult] = []
    dropped = 0
    unsupported = 0
    for change, result, context in zip(delta.changes, run.results, contexts, strict=True):
        explanation = result.explanation
        if explanation is None or context is None:
            gated.append(_unexplained(result))
            continue
        verdict = check_explanation(explanation, context, resolver)
        results.append(verdict)
        accepted: GatedExplanation | None = None
        if verdict.passed:
            accepted, lost = _checked_note(
                GatedExplanation.accepted(explanation), change, text_char_cap
            )
            dropped += lost
        ruling = GatedChange(
            provision=result.provision,
            outcome=GateOutcome.PASSED if verdict.passed else GateOutcome.RETRY_REQUESTED,
            explanation=accepted,
            failures=verdict.failures,
            complaint="" if verdict.passed else verdict.complaint,
        )
        if verdict.passed:
            unsupported += _counted_coordinates(ruling, change, context)
        gated.append(ruling)
    return GatedDelta(changes=tuple(gated), stats=_tally(gated, results, dropped, unsupported))


def second_round(
    gated: GatedDelta,
    delta: Delta,
    revised: Mapping[int, ExplainedChange],
    contexts: Sequence[ExplainContext | None],
    resolver: ProvisionResolver,
    *,
    text_char_cap: int,
) -> GatedDelta:
    """Settle every pending change with the revised answer. After this, nothing is pending.

    A revision that passes is `PASSED_ON_RETRY`. A revision that fails, or that the model could
    not produce at all, is `FALLBACK`: the answer it revises was already rejected, so there is a
    claim to replace and the quotation replaces it. There is no third round by design.
    """
    settled: list[GatedChange] = []
    results: list[GateResult] = []
    dropped = 0
    unsupported = 0
    for index, change in enumerate(gated.changes):
        if change.outcome is not GateOutcome.RETRY_REQUESTED:
            settled.append(change)
            continue
        answer = revised.get(index)
        context = contexts[index]
        if answer is None or context is None:
            raise ValueError(
                f"change {index} ({change.provision.location.canonical}) was sent for revision "
                f"and no revised answer came back; the retry cycle did not run to completion"
            )
        verdict, resolved, lost = _settle(
            delta.changes[index], change, answer, context, resolver, text_char_cap
        )
        results.append(verdict)
        dropped += lost
        unsupported += _counted_coordinates(resolved, delta.changes[index], context)
        settled.append(resolved)
    merged = _tally(settled, results, dropped, unsupported)
    return GatedDelta(changes=tuple(settled), stats=_carry(gated.stats, merged))


def _settle(
    change: Change,
    prior: GatedChange,
    answer: ExplainedChange,
    context: ExplainContext,
    resolver: ProvisionResolver,
    text_char_cap: int,
) -> tuple[GateResult, GatedChange, int]:
    """One pending change, after its revision: passed on retry, or quoted."""
    explanation = answer.explanation
    if explanation is None:
        return GateResult(), _fell_back(change, prior, context), 0
    verdict = check_explanation(explanation, context, resolver)
    if verdict.passed:
        accepted, dropped = _checked_note(
            GatedExplanation.accepted(explanation), change, text_char_cap
        )
        return (
            verdict,
            prior.model_copy(
                update={"outcome": GateOutcome.PASSED_ON_RETRY, "explanation": accepted}
            ),
            dropped,
        )
    quoted, dropped = _checked_note(
        apply_fallback(change, explanation, verdict, context), change, text_char_cap
    )
    return (
        verdict,
        prior.model_copy(
            update={
                "outcome": GateOutcome.FALLBACK,
                "explanation": quoted,
                "failures": prior.failures + verdict.failures,
            }
        ),
        dropped,
    )


def _fell_back(change: Change, prior: GatedChange, context: ExplainContext) -> GatedChange:
    """The revision produced no explanation, and the rejected answer still needs replacing."""
    return prior.model_copy(
        update={
            "outcome": GateOutcome.FALLBACK,
            "explanation": GatedExplanation(sentences=(fallback_sentence(change, context),)),
        }
    )


def _carry(before: GateStats, after: GateStats) -> GateStats:
    """Merge the two rounds' counts: outcomes from the second, volumes from both.

    `retries` is kept from the first round, because that is the number the report means by "how
    often did the gate have to ask again" — and it is zero in the settled round by definition.
    """
    return after.model_copy(
        update={
            "retries": before.retries,
            "sentences": before.sentences + after.sentences,
            "citations": before.citations + after.citations,
            "citations_rejected": before.citations_rejected + after.citations_rejected,
            "notes_dropped": before.notes_dropped + after.notes_dropped,
            "coordinates_unsupported": (
                before.coordinates_unsupported + after.coordinates_unsupported
            ),
        }
    )
