"""The unsupported-coordinate count: a counted outcome, never a dropped sentence.

A hand review of the shipped prose (2026-08-08) found a sentence naming a paragraph that
exists nowhere in the model's evidence, and the pipeline held everything needed to notice
deterministically. These tests pin that check end to end on synthetic house rules: support
comes from `Change.changed_within` or from text visibly inside the capped evidence, the count
reaches `GateStats`, and nothing about the shipped explanation moves because of it.
"""

from __future__ import annotations

from emendrix.core import (
    Change,
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionNode,
    ProvisionRef,
    ProvisionText,
    ProvisionTree,
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
    RunStats,
    build_context,
)
from emendrix.gate import (
    GatedExplanation,
    GatedSentence,
    GateOutcome,
    TreeResolver,
    first_round,
    second_round,
    unsupported_coordinates,
)
from toy_corpus import HOUSE_RULES, V1, V2

CAP = ExplainSettings().text_char_cap
UNIT = ProvisionLocation.parse("AR 7")

PARA_ONE = "First synthetic paragraph, about the notice board."
PARA_TWO_V1 = "Second synthetic paragraph, about the stairwell."
PARA_TWO_V2 = "Second synthetic paragraph, about the stairwell and the cellar."


def _tree(version: VersionId, para_two: str) -> ProvisionTree:
    """One article of two paragraphs; the unit's text contains its children's, as a parser's
    would, because `shown` is verbatim containment of the child text in the capped unit text."""
    return ProvisionTree(
        act=HOUSE_RULES,
        version=version,
        roots=(
            ProvisionNode.from_plain_text(
                "AR 7",
                f"{PARA_ONE} {para_two}",
                heading="Synthetic",
                children=(
                    ProvisionNode.from_plain_text("AR 7 PA 1", PARA_ONE),
                    ProvisionNode.from_plain_text("AR 7 PA 2", para_two),
                ),
            ),
        ),
    )


BEFORE_TREE = _tree(V1, PARA_TWO_V1)
AFTER_TREE = _tree(V2, PARA_TWO_V2)


def modified(*changed_within: str) -> Change:
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(act=HOUSE_RULES, version=V2, location=UNIT),
        before=ProvisionText(f"{PARA_ONE} {PARA_TWO_V1}"),
        after=ProvisionText(f"{PARA_ONE} {PARA_TWO_V2}"),
        changed_within=tuple(ProvisionLocation.parse(raw) for raw in changed_within),
    )


def checked_context(change: Change, *, cap: int = CAP) -> ExplainContext:
    return build_context(
        change,
        from_version=V1,
        to_version=V2,
        before_tree=BEFORE_TREE,
        after_tree=AFTER_TREE,
        text_char_cap=cap,
    )


def says(context: ExplainContext, *texts: str) -> Explanation:
    key = sorted(context.keys)[0]
    return Explanation(
        sentences=tuple(CitedSentence(text=text, citations=(key,)) for text in texts)
    )


def gated(explanation: Explanation) -> GatedExplanation:
    return GatedExplanation.accepted(explanation)


# ------------------------------------------------------------------ support, both legs


def test_a_localised_and_a_shown_coordinate_are_both_supported() -> None:
    """The sameness-claim case is the reason `shown` is a leg of support at all: an unchanged
    paragraph is correctly absent from `changed_within`, and a sentence saying it did not
    change is grounded by the text being visibly on the page."""
    change = modified("AR 7 PA 2")
    context = checked_context(change)
    explanation = says(
        context,
        "Paragraph 1 remains worded as it was.",
        "Paragraph 2 now also names the cellar.",
    )
    assert unsupported_coordinates(gated(explanation), context, UNIT) == ()


def test_an_invented_coordinate_is_counted_by_its_canonical_string() -> None:
    change = modified("AR 7 PA 2")
    context = checked_context(change)
    explanation = says(context, "Paragraph 2 changes and paragraph 12 is repealed.")
    assert unsupported_coordinates(gated(explanation), context, UNIT) == ("AR 7 PA 12",)


def test_the_flagged_review_shape_a_point_inside_a_localised_paragraph() -> None:
    """The shape the 2026-08-08 review flagged: `9(e)` is supported when the diff localised
    paragraph 9, and adding an unlocalised, unshown `12` yields exactly one count."""
    change = modified("AR 7 PA 9", "AR 7 PA 10")
    context = checked_context(change)
    fine = says(context, "Paragraphs 9(e) and 10 add references.")
    assert unsupported_coordinates(gated(fine), context, UNIT) == ()
    wider = says(context, "Paragraphs 9(e), 10 and 12 add references.")
    assert unsupported_coordinates(gated(wider), context, UNIT) == ("AR 7 PA 12",)


def test_a_coarse_mention_of_a_deeply_localised_paragraph_is_supported() -> None:
    """The diff may localise below the paragraph; naming the paragraph is still grounded."""
    change = modified("AR 7 PA 2 ALN 1 PTA (e)")
    context = checked_context(change)
    explanation = says(context, "Paragraph 2 is reworded.")
    assert unsupported_coordinates(gated(explanation), context, UNIT) == ()


def test_a_coordinate_the_cap_hid_is_not_supported_by_text_nobody_saw() -> None:
    change = modified("AR 7 PA 2")
    context = checked_context(change, cap=10)
    assert context.coordinates_checked and context.shown == frozenset()
    explanation = says(context, "Paragraph 1 remains worded as it was.")
    assert unsupported_coordinates(gated(explanation), context, UNIT) == ("AR 7 PA 1",)


def test_an_unchecked_context_counts_nothing_rather_than_everything() -> None:
    """Built without the trees, the sets are meaningless, and the honest count is none."""
    change = modified("AR 7 PA 2")
    bare = build_context(change, from_version=V1, to_version=V2)
    assert not bare.coordinates_checked
    explanation = says(bare, "Paragraph 12 is repealed.")
    assert unsupported_coordinates(gated(explanation), bare, UNIT) == ()


def test_a_gate_written_quotation_is_never_pattern_matched() -> None:
    """A fallback sentence is quoted provision text, and provision text is never read by the
    recogniser; only the model's own sentences are."""
    change = modified("AR 7 PA 2")
    context = checked_context(change)
    key = sorted(context.keys)[0]
    quoted = GatedExplanation(
        sentences=(
            GatedSentence(
                sentence=CitedSentence(
                    text="Paragraph 12 would count, were this model prose.", citations=(key,)
                ),
                fallback=True,
            ),
        )
    )
    assert unsupported_coordinates(quoted, context, UNIT) == ()


# ------------------------------------------------------------------ through the gate rounds


def explained(change: Change, explanation: Explanation | None) -> ExplainedChange:
    return ExplainedChange(
        provision=change.provision,
        explanation=explanation,
        usage=CallUsage(input_tokens=10, output_tokens=2, requests=1),
        synthetic=True,
    )


def run_of(changes: tuple[Change, ...], answers: tuple[Explanation | None, ...]) -> ExplainRun:
    results = tuple(explained(c, a) for c, a in zip(changes, answers, strict=True))
    return ExplainRun(results=results, stats=RunStats.over("test:stub", results))


def delta_of(*changes: Change) -> Delta:
    return Delta(act=HOUSE_RULES, from_version=V1, to_version=V2, changes=changes)


RESOLVER = TreeResolver((BEFORE_TREE, AFTER_TREE))


def test_the_count_reaches_the_stats_and_the_sentence_still_ships() -> None:
    change = modified("AR 7 PA 2")
    context = checked_context(change)
    explanation = says(context, "Paragraph 12 is repealed.")
    result = first_round(
        delta_of(change),
        run_of((change,), (explanation,)),
        (context,),
        RESOLVER,
        text_char_cap=CAP,
    )
    assert result.stats.coordinates_unsupported == 1
    ruled = result.changes[0]
    assert ruled.outcome is GateOutcome.PASSED, "counted, never a failure"
    assert ruled.explanation is not None
    assert [item.text for item in ruled.explanation.sentences] == ["Paragraph 12 is repealed."]


def test_the_count_is_taken_on_the_settled_explanation_only() -> None:
    """A retried change is counted once, in the form that ships: the first round counts the
    passed changes, the second counts the newly settled ones, and `_carry` sums the rounds."""
    passed = modified("AR 7 PA 2")
    retried = modified("AR 7 PA 2")
    delta = delta_of(passed, retried)
    contexts = (checked_context(passed), checked_context(retried))
    good = says(contexts[0], "Paragraph 12 is repealed.")
    bad = Explanation(
        sentences=(CitedSentence(text="Paragraph 13 is repealed.", citations=("AR 404@v2",)),)
    )
    first = first_round(
        delta, run_of((passed, retried), (good, bad)), contexts, RESOLVER, text_char_cap=CAP
    )
    assert first.stats.coordinates_unsupported == 1, "the pending change is not counted yet"
    assert first.pending == (1,)

    revised = {1: explained(retried, says(contexts[1], "Paragraph 13 is repealed."))}
    settled = second_round(first, delta, revised, contexts, RESOLVER, text_char_cap=CAP)
    assert settled.stats.coordinates_unsupported == 2
    assert settled.stats.settled == settled.stats.changes
