"""The substitution of last resort, and the two properties the gate exists to have.

The gate's promise has two halves: **a change is never dropped, and an ungrounded sentence
never ships.** Both are stated below as properties over generated inputs rather than as
examples, because an example proves a case and the promise is about every case, including the
ones nobody thought to write down.

The generator is a small deterministic one rather than Hypothesis. A fixed grid over the
explanation's shape, whether the first answer cites garbage, and whether the revision fixes it
is exhaustive at this size, and a fixed grid keeps the suite byte-stable, which is the same
reason the rest of the pipeline avoids randomness.
"""

from __future__ import annotations

from datetime import date
from itertools import product

import pytest

from emendrix.core import (
    Change,
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionRef,
    ProvisionText,
    ProvisionTree,
    Signal,
    SignalObservation,
    SignalSet,
    SignalStatus,
    VersionId,
)
from emendrix.explain import (
    CallUsage,
    CitedSentence,
    ExplainContext,
    ExplainedChange,
    ExplainRun,
    ExplainSettings,
    Explanation,
    ExplanationUnavailable,
    RunStats,
    build_context,
    contexts_for_delta,
)
from emendrix.gate import (
    QUOTE_CHAR_CAP,
    GatedDelta,
    GateOutcome,
    GateStats,
    TreeResolver,
    apply_fallback,
    check_explanation,
    fallback_key,
    first_round,
    second_round,
    verbatim_quote,
)
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED = date(2026, 8, 6)
MODEL = "test:stub"
CAP = ExplainSettings().text_char_cap
"""The shipped per-side cap, taken from the settings rather than written down twice."""

_LONG = "Residents shall not leave anything at all in the hallway, ever, for any reason. "


@pytest.fixture
def resolver() -> TreeResolver:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    trees = [adapter.fetch_version(HOUSE_RULES, version) for version in (V1, V2)]
    return TreeResolver(tree for tree in trees if isinstance(tree, ProvisionTree))


def change(
    location: str, *, before: str | None = "old text", after: str | None = "new text"
) -> Change:
    """A change of whichever type its two sides imply; `core` validates the pairing."""
    if before is not None and after is not None:
        kind = ChangeType.MODIFIED
    elif after is not None:
        kind = ChangeType.INSERTED
    else:
        kind = ChangeType.DELETED
    return Change(
        change_type=kind,
        provision=ProvisionRef(
            act=HOUSE_RULES, version=V2, location=ProvisionLocation.parse(location)
        ),
        before=None if before is None else ProvisionText(before),
        after=None if after is None else ProvisionText(after),
    )


def context(item: Change) -> ExplainContext:
    return build_context(item, from_version=V1, to_version=V2)


def says(text: str, *keys: str) -> CitedSentence:
    return CitedSentence(text=text, citations=tuple(keys))


def explained(item: Change, explanation: Explanation | None) -> ExplainedChange:
    return ExplainedChange(
        provision=item.provision,
        explanation=explanation,
        unavailable=None
        if explanation
        else ExplanationUnavailable(kind="model_failed", reason="the provider said no"),
        usage=CallUsage(input_tokens=10, output_tokens=2, requests=1),
        synthetic=True,
    )


def run_of(changes: tuple[Change, ...], answers: tuple[Explanation | None, ...]) -> ExplainRun:
    results = tuple(explained(c, a) for c, a in zip(changes, answers, strict=True))
    return ExplainRun(results=results, stats=RunStats.over(MODEL, results))


def delta_of(*changes: Change) -> Delta:
    return Delta(act=HOUSE_RULES, from_version=V1, to_version=V2, changes=changes)


# ------------------------------------------------------------------ the quotation


def test_the_quotation_is_the_provisions_own_text(resolver: TreeResolver) -> None:
    """Correct by construction: the only sentence about a provision that cannot be wrong."""
    item = change("AR 2", after="The bins go out on Tuesday evening.")
    quote = verbatim_quote(item)
    assert "The bins go out on Tuesday evening." in quote
    assert "The new text of Art. 2" in quote


def test_a_deletion_quotes_what_it_said_before() -> None:
    """There is no `after`, so the removed text is all there is to quote."""
    quote = verbatim_quote(change("AR 3", before="Guests are announced.", after=None))
    assert "Guests are announced." in quote
    assert quote.startswith("The removed text")


def test_a_long_provision_is_cut_and_the_cut_says_so() -> None:
    """Verbatim means verbatim, so a cap that bit has to be visible in the sentence itself."""
    body = _LONG * 40
    assert len(body) > QUOTE_CHAR_CAP
    quote = verbatim_quote(change("AR 4", after=body))
    assert "truncated by emendrix" in quote
    assert "characters omitted" in quote
    assert len(quote) < len(body)


def test_the_fallback_cites_the_changes_own_provision(resolver: TreeResolver) -> None:
    """The sentence the gate writes passes the gate for the same reason every other one does."""
    item = change("AR 2")
    offered = context(item)
    key = fallback_key(item, offered)
    assert key in offered.keys

    result = check_explanation(
        Explanation(sentences=(says(verbatim_quote(item), key),)), offered, resolver
    )
    assert result.passed, "a gate that rejected its own fallback would loop forever"


def test_the_quotation_is_byte_stable_across_calls() -> None:
    item = change("AR 2", after=_LONG * 40)
    assert verbatim_quote(item) == verbatim_quote(item)


# ------------------------------------------------------------------ substitution


def test_substitution_keeps_what_passed_and_replaces_what_did_not(resolver: TreeResolver) -> None:
    item = change("AR 2")
    offered = context(item)
    good = sorted(offered.keys)[0]
    explanation = Explanation(
        sentences=(says("Kept.", good), says("Invented.", "AR 99@v2"), says("Also kept.", good))
    )
    verdict = check_explanation(explanation, offered, resolver)
    gated = apply_fallback(item, explanation, verdict, offered)

    kept = [item.text for item in gated.sentences]
    assert kept[0] == "Kept."
    assert kept[2] == "Also kept."
    assert gated.sentences[1].fallback
    assert not gated.sentences[0].fallback
    assert gated.fallbacks == 1


def test_three_rejected_sentences_become_one_quotation_not_three(resolver: TreeResolver) -> None:
    """Otherwise the entry repeats the same provision three times and reads like a bug."""
    item = change("AR 2")
    offered = context(item)
    explanation = Explanation(
        sentences=(says("A.", "AR 91@v2"), says("B.", "AR 92@v2"), says("C.", "AR 93@v2"))
    )
    verdict = check_explanation(explanation, offered, resolver)
    gated = apply_fallback(item, explanation, verdict, offered)
    assert len(gated.sentences) == 1
    assert gated.fallbacks == 1


def test_a_failing_applicability_note_is_dropped_rather_than_quoted(
    resolver: TreeResolver,
) -> None:
    """The note exists only to quote the act's own application prose; replacing it with
    the whole provision would answer a question nobody asked. Its rejection is still counted."""
    item = change("AR 2")
    offered = context(item)
    good = sorted(offered.keys)[0]
    explanation = Explanation(
        sentences=(says("Grounded.", good),),
        applicability_note=says("It applies from a date.", "AR 99@v2"),
    )
    verdict = check_explanation(explanation, offered, resolver)
    gated = apply_fallback(item, explanation, verdict, offered)
    assert gated.applicability_note is None
    assert [sentence.text for sentence in gated.sentences] == ["Grounded."]
    assert verdict.rejected_citations == 1


# --------------------------------------------------------- the note is quoted or it is dropped

AFTER_WITH_NOTE = "The bins go out on Tuesday evening.\nThis Article applies from 1 June 2026."


def _one_round(item: Change, explanation: Explanation, resolver: TreeResolver) -> GatedDelta:
    """One change through the first round, which is where an accepted note is decided."""
    delta = delta_of(item)
    return first_round(
        delta,
        run_of((item,), (explanation,)),
        contexts_for_delta(delta),
        resolver,
        text_char_cap=CAP,
    )


def _with_note(item: Change, note: str) -> Explanation:
    good = sorted(context(item).keys)[0]
    return Explanation(
        sentences=(says("The collection day moved.", good),),
        applicability_note=says(note, good),
    )


def test_a_note_that_quotes_the_after_text_ships(resolver: TreeResolver) -> None:
    """Rule 7 asks for a quotation of the act's own application prose, and this is one, down to
    arriving with the source's line breaks rather than the reader's."""
    item = change("AR 2", after=AFTER_WITH_NOTE)
    quotation = "This  Article\napplies from 1 June 2026."
    gated = _one_round(item, _with_note(item, quotation), resolver)

    shipped = gated.changes[0].explanation
    assert shipped is not None and shipped.applicability_note is not None
    assert shipped.applicability_note.text == quotation, "verbatim means the model's own bytes"
    assert gated.stats.notes_dropped == 0


def test_a_paraphrased_note_is_dropped_and_counted(resolver: TreeResolver) -> None:
    """It names the same date the deterministic clock computed, and it is still dropped: the
    reader cannot tell a lucky paraphrase from a quotation, so neither does the gate."""
    item = change("AR 2", after=AFTER_WITH_NOTE)
    gated = _one_round(item, _with_note(item, "The provision applies from 1 June 2026."), resolver)

    shipped = gated.changes[0].explanation
    assert shipped is not None and shipped.applicability_note is None
    assert [sentence.text for sentence in shipped.sentences] == ["The collection day moved."]
    assert gated.stats.notes_dropped == 1
    assert gated.changes[0].outcome is GateOutcome.PASSED, "a dropped note is not a retry"


def test_dropping_a_note_moves_no_citation_count(resolver: TreeResolver) -> None:
    """The property that keeps the published grounding rate comparable across this change: the
    citation check runs first and is untouched by what happens to the note afterwards."""
    item = change("AR 2", after=AFTER_WITH_NOTE)
    kept = _one_round(item, _with_note(item, "This Article applies from 1 June 2026."), resolver)
    dropped = _one_round(item, _with_note(item, "It applies from June."), resolver)

    assert dropped.stats.notes_dropped == 1 and kept.stats.notes_dropped == 0
    for field in ("sentences", "citations", "citations_rejected", "passed_first"):
        assert getattr(dropped.stats, field) == getattr(kept.stats, field), field


def test_a_note_dropped_in_the_first_round_is_still_counted_after_the_second(
    resolver: TreeResolver,
) -> None:
    """`_carry` merges the two rounds, and a count it forgets to sum is a silent undercount."""
    kept = change("AR 2", after=AFTER_WITH_NOTE)
    pending = change("AR 1")
    delta = delta_of(kept, pending)
    contexts = contexts_for_delta(delta)
    firsts = (
        _with_note(kept, "The provision applies from 1 June 2026."),
        attempt(_require(contexts[1]), 1, grounded=False),
    )
    gated = first_round(
        delta, run_of((kept, pending), firsts), contexts, resolver, text_char_cap=CAP
    )
    assert gated.pending == (1,) and gated.stats.notes_dropped == 1

    revised = {1: explained(pending, attempt(_require(contexts[1]), 1, grounded=True))}
    settled = second_round(gated, delta, revised, contexts, resolver, text_char_cap=CAP)
    assert settled.stats.notes_dropped == 1
    assert settled.stats.passed_on_retry == 1


def test_gate_stats_plus_sums_every_field_it_holds() -> None:
    """Written generically on purpose: `plus` is a pairwise sum written out by hand, so a field
    added to the model and not to it would go missing with nothing else to notice."""
    left = GateStats(**dict.fromkeys(GateStats.model_fields, 1))
    right = GateStats(**dict.fromkeys(GateStats.model_fields, 2))
    total = left.plus(right)
    for field in GateStats.model_fields:
        assert getattr(total, field) == 3, field


# ------------------------------------------------------------------ the properties


GRID = tuple(product((1, 2, 3), (True, False), (True, False)))
"""(sentence count, does the first answer cite garbage, does the revision fix it)."""


def attempt(offered: ExplainContext, count: int, *, grounded: bool) -> Explanation:
    key = sorted(offered.keys)[0] if grounded else "AR 404@v2"
    return Explanation(sentences=tuple(says(f"Sentence {n}.", key) for n in range(count)))


@pytest.mark.parametrize(("count", "bad_first", "fixed_on_retry"), GRID)
def test_a_change_is_never_dropped_and_no_ungrounded_sentence_ships(
    resolver: TreeResolver, count: int, bad_first: bool, fixed_on_retry: bool
) -> None:
    """The property, over the whole grid: same changes out as in, every sentence grounded."""
    changes = (change("AR 1"), change("AR 2"), change("AR 4", before=None))
    delta = delta_of(*changes)
    contexts = contexts_for_delta(delta)
    firsts = tuple(
        attempt(ctx, count, grounded=not bad_first) for ctx in contexts if ctx is not None
    )
    gated = first_round(delta, run_of(changes, firsts), contexts, resolver, text_char_cap=CAP)

    assert len(gated.changes) == len(delta.changes), "input changes == output changes"

    revised = {
        index: explained(
            delta.changes[index],
            attempt(_require(contexts[index]), count, grounded=fixed_on_retry),
        )
        for index in gated.pending
    }
    settled = second_round(gated, delta, revised, contexts, resolver, text_char_cap=CAP)

    assert len(settled.changes) == len(delta.changes), "input changes == output changes"
    assert settled.pending == (), "nothing may be left waiting after the one retry"
    assert settled.stats.settled == settled.stats.changes

    for index, verdict in enumerate(settled.changes):
        explanation = verdict.explanation
        assert explanation is not None, f"change {index} lost its explanation"
        for sentence in explanation.sentences:
            if sentence.fallback:
                continue  # written by the gate: grounded by construction
            check = check_explanation(
                Explanation(sentences=(sentence.sentence,)), _require(contexts[index]), resolver
            )
            assert check.passed, f"an ungrounded sentence shipped: {sentence.text!r}"


@pytest.mark.parametrize(("count", "bad_first", "fixed_on_retry"), GRID)
def test_the_outcome_counts_add_up_to_the_number_of_changes(
    resolver: TreeResolver, count: int, bad_first: bool, fixed_on_retry: bool
) -> None:
    """Counts are published as measured, so they have to be arithmetic rather than vibes."""
    changes = (change("AR 1"), change("AR 2"))
    delta = delta_of(*changes)
    contexts = contexts_for_delta(delta)
    firsts = tuple(attempt(_require(ctx), count, grounded=not bad_first) for ctx in contexts)
    gated = first_round(delta, run_of(changes, firsts), contexts, resolver, text_char_cap=CAP)
    revised = {
        index: explained(
            delta.changes[index],
            attempt(_require(contexts[index]), count, grounded=fixed_on_retry),
        )
        for index in gated.pending
    }
    settled = second_round(gated, delta, revised, contexts, resolver, text_char_cap=CAP)
    stats = settled.stats

    assert stats.changes == 2
    assert stats.settled == 2
    if not bad_first:
        assert stats.passed_first == 2 and stats.retries == 0
    elif fixed_on_retry:
        assert stats.passed_on_retry == 2 and stats.retries == 2 and stats.fallback == 0
    else:
        assert stats.fallback == 2 and stats.retries == 2
        assert all(v.outcome is GateOutcome.FALLBACK for v in settled.changes)


def test_a_textless_change_keeps_its_slot_and_is_counted_unexplained(
    resolver: TreeResolver,
) -> None:
    """Corroboration appends these routinely; `contexts_for_delta` answers `None` for them.

    They have nothing to quote, so the gate writes no fallback, but they still ship, and the
    delta they came from is still the same length as the one that leaves.
    """
    textless = Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(
            act=HOUSE_RULES, version=V2, location=ProvisionLocation.parse("AR 7")
        ),
        signals=SignalSet(
            structural_diff=SignalObservation(
                status=SignalStatus.ABSENT, detail=Signal.STRUCTURAL_DIFF.value
            ),
            corpus_metadata=SignalObservation(
                status=SignalStatus.OBSERVED, detail=Signal.CORPUS_METADATA.value
            ),
        ),
    )
    delta = delta_of(change("AR 1"), textless)
    contexts = contexts_for_delta(delta)
    assert contexts[1] is None

    offered = _require(contexts[0])
    gated = first_round(
        delta,
        run_of(
            (delta.changes[0], textless),
            (attempt(offered, 1, grounded=True), None),
        ),
        contexts,
        resolver,
        text_char_cap=CAP,
    )
    assert len(gated.changes) == 2
    assert gated.changes[1].outcome is GateOutcome.UNEXPLAINED
    assert gated.stats.unexplained == 1
    assert gated.stats.settled == 2


def test_a_revision_that_never_came_back_is_a_build_fault_not_a_silent_pass(
    resolver: TreeResolver,
) -> None:
    """`second_round` refuses to settle a pending change with no answer: dropping it quietly
    is the exact failure the whole package exists to prevent."""
    changes = (change("AR 1"),)
    delta = delta_of(*changes)
    contexts = contexts_for_delta(delta)
    firsts = (attempt(_require(contexts[0]), 1, grounded=False),)
    gated = first_round(delta, run_of(changes, firsts), contexts, resolver, text_char_cap=CAP)
    assert gated.pending == (0,)

    with pytest.raises(ValueError, match="did not run to completion"):
        second_round(gated, delta, {}, contexts, resolver, text_char_cap=CAP)


def test_a_revision_the_model_could_not_produce_still_falls_back(resolver: TreeResolver) -> None:
    """A provider failure on the retry is not a reason to ship the rejected sentence."""
    changes = (change("AR 1"),)
    delta = delta_of(*changes)
    contexts = contexts_for_delta(delta)
    gated = first_round(
        delta,
        run_of(changes, (attempt(_require(contexts[0]), 1, grounded=False),)),
        contexts,
        resolver,
        text_char_cap=CAP,
    )
    settled = second_round(
        gated, delta, {0: explained(changes[0], None)}, contexts, resolver, text_char_cap=CAP
    )
    verdict = settled.changes[0]
    assert verdict.outcome is GateOutcome.FALLBACK
    assert verdict.explanation is not None
    assert verdict.explanation.sentences[0].fallback
    assert "old text" in verdict.explanation.sentences[0].text or "new text" in (
        verdict.explanation.sentences[0].text
    )


def test_the_three_sequences_must_be_the_same_length() -> None:
    """A slipped index would gate one change's sentences against another's offered keys."""
    changes = (change("AR 1"), change("AR 2"))
    delta = delta_of(*changes)
    contexts = contexts_for_delta(delta)
    short = run_of(changes[:1], (attempt(_require(contexts[0]), 1, grounded=True),))
    with pytest.raises(ValueError, match="paired positionally"):
        first_round(delta, short, contexts, TreeResolver(()), text_char_cap=CAP)


def _require(context: ExplainContext | None) -> ExplainContext:
    assert context is not None
    return context


def test_the_versions_the_toy_corpus_uses_are_the_ones_these_tests_assume() -> None:
    """A guard, not an assertion about law: if the toy renames its versions, say so here."""
    assert VersionId("v1") == V1
    assert VersionId("v2") == V2
