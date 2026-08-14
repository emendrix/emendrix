"""The gate's three questions, on toy data: offered? resolvable? and nothing else.

Everything here runs on `tests/toy_corpus.py`, a flat's house rules that is not law, and on
`Explanation` objects written in this file rather than produced by a model. That is deliberate
twice over. The gate is corpus-agnostic, so proving it on the alien corpus proves the seam; and
every committed cassette passes the gate on its first answer, so a crafted explanation is the
*only* way to state precisely which citation is being rejected and why.

What is not tested here, because it is not the gate's job: whether a sentence is true, useful
or well written. A factually wrong sentence with a valid citation passes, and there is a test
below that says so out loud: blurring citation grounding into explanation quality is the one
line this project draws hardest.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import (
    Change,
    ChangeType,
    ProvisionLocation,
    ProvisionRef,
    ProvisionText,
    ProvisionTree,
)
from emendrix.explain import (
    CitedSentence,
    ExplainContext,
    ExplainSettings,
    Explanation,
    OfferedCitation,
    build_context,
)
from emendrix.gate import (
    APPLICABILITY_NOTE,
    FailureReason,
    Resolution,
    TreeResolver,
    check_explanation,
    note_is_verbatim,
)
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED = date(2026, 8, 6)


@pytest.fixture
def trees() -> tuple[ProvisionTree, ProvisionTree]:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before, after = adapter.fetch_version(HOUSE_RULES, V1), adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return before, after


@pytest.fixture
def resolver(trees: tuple[ProvisionTree, ProvisionTree]) -> TreeResolver:
    return TreeResolver(trees)


def modified(location: str = "AR 2") -> Change:
    """A change with both sides, so both its keys are offered."""
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(
            act=HOUSE_RULES, version=V2, location=ProvisionLocation.parse(location)
        ),
        before=ProvisionText("The bins go out on Tuesday evening."),
        after=ProvisionText("The bins go out on Tuesday evening, and the recycling too."),
    )


def context(change: Change) -> ExplainContext:
    return build_context(change, from_version=V1, to_version=V2)


def says(text: str, *keys: str) -> CitedSentence:
    return CitedSentence(text=text, citations=tuple(keys))


# ------------------------------------------------------------------ the resolver


def test_the_resolver_answers_present_absent_and_uncheckable_differently(
    resolver: TreeResolver,
) -> None:
    """Three answers, not two: "no such provision" and "no such text on hand" are not the same.

    Only one of them is the model's fault, and a gate that collapsed them would report a
    missing fixture as a hallucination.
    """
    here = ProvisionRef(act=HOUSE_RULES, version=V2, location=ProvisionLocation.parse("AR 2"))
    gone = ProvisionRef(act=HOUSE_RULES, version=V2, location=ProvisionLocation.parse("AR 3"))
    unfetched = ProvisionRef(act=HOUSE_RULES, version=V1, location=ProvisionLocation.parse("AR 2"))

    assert resolver.resolves(here) is Resolution.PRESENT
    assert resolver.resolves(gone) is Resolution.ABSENT, "AR 3 was deleted in v2"
    assert TreeResolver(()).resolves(unfetched) is Resolution.UNCHECKABLE


def test_the_resolver_never_reaches_for_a_version_nobody_handed_it(
    trees: tuple[ProvisionTree, ProvisionTree],
) -> None:
    """No network and no adapter: the gate resolves against text already in memory."""
    only_v2 = TreeResolver((trees[1],))
    in_v1 = ProvisionRef(act=HOUSE_RULES, version=V1, location=ProvisionLocation.parse("AR 1"))
    assert only_v2.resolves(in_v1) is Resolution.UNCHECKABLE


# ------------------------------------------------------------------ the check


def test_a_well_cited_explanation_passes_and_the_volumes_are_counted(
    resolver: TreeResolver,
) -> None:
    change = modified()
    offered = context(change)
    keys = sorted(offered.keys)
    result = check_explanation(
        Explanation(
            sentences=(
                says("The rule gained a clause.", *keys),
                says("Nothing else moved.", keys[0]),
            )
        ),
        offered,
        resolver,
    )
    assert result.passed
    assert result.failures == ()
    assert result.sentences == 2
    assert result.citations == 3
    assert result.rejected_citations == 0


def test_an_unoffered_key_is_rejected_without_anyone_judging_the_sentence(
    resolver: TreeResolver,
) -> None:
    """The anti-hallucination invariant: citing outside the offered set is structurally wrong."""
    change = modified()
    offered = context(change)
    assert "AR 9@v2" not in offered.keys

    result = check_explanation(
        Explanation(sentences=(says("An impeccable sentence about nothing.", "AR 9@v2"),)),
        offered,
        resolver,
    )
    assert not result.passed
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.index == 0
    assert failure.citations[0].reason is FailureReason.UNKNOWN_KEY
    assert "AR 9@v2" in failure.citations[0].detail
    assert "not offered" in failure.citations[0].detail


def test_a_key_that_is_offered_but_names_nothing_fails_for_a_different_reason(
    resolver: TreeResolver,
) -> None:
    """Offered and resolvable are two checks, and the report says which one failed.

    A caller that mints its own offered set can offer a provision the version does not have.
    That is the caller's bug, not a hallucination, and the gate names it as such.
    """
    change = modified()
    ghost = ProvisionRef(act=HOUSE_RULES, version=V2, location=ProvisionLocation.parse("AR 3"))
    widened = ExplainContext(offered=(*context(change).offered, OfferedCitation.for_ref(ghost)))

    result = check_explanation(
        Explanation(sentences=(says("It says so.", "AR 3@v2"),)), widened, resolver
    )
    assert not result.passed
    assert result.failures[0].citations[0].reason is FailureReason.UNRESOLVED
    assert "names no provision in v2" in result.failures[0].citations[0].detail


def test_an_unfetched_version_is_unchecked_rather_than_quietly_passed() -> None:
    """The gate does not pass what it cannot check, and it says which of the two it was."""
    change = modified()
    result = check_explanation(
        Explanation(sentences=(says("Something changed.", sorted(context(change).keys)[0]),)),
        context(change),
        TreeResolver(()),
    )
    assert not result.passed
    assert result.failures[0].citations[0].reason is FailureReason.UNCHECKABLE
    assert "never fetched" in result.failures[0].citations[0].detail


def test_only_the_failing_sentences_are_flagged(resolver: TreeResolver) -> None:
    """Partial failure is the common case; a gate that condemned the whole answer would
    throw away good sentences and make the retry harder than it needs to be."""
    change = modified()
    offered = context(change)
    good = sorted(offered.keys)[0]
    result = check_explanation(
        Explanation(
            sentences=(
                says("First, grounded.", good),
                says("Second, invented.", "AR 42@v2"),
                says("Third, grounded.", good),
            )
        ),
        offered,
        resolver,
    )
    assert [failure.index for failure in result.failures] == [1]
    assert result.failures[0].text == "Second, invented."
    assert result.sentences == 3
    assert result.citations == 3
    assert result.rejected_citations == 1


def test_one_bad_key_condemns_its_whole_sentence(resolver: TreeResolver) -> None:
    """A sentence stands on all of its citations: half-accepting it would ship a claim
    pointing at something that is not there."""
    change = modified()
    offered = context(change)
    result = check_explanation(
        Explanation(sentences=(says("Half right.", sorted(offered.keys)[0], "AR 42@v2"),)),
        offered,
        resolver,
    )
    assert len(result.failures) == 1
    assert [item.key for item in result.failures[0].citations] == ["AR 42@v2"]


def test_the_applicability_note_is_checked_and_reported_under_its_own_slot(
    resolver: TreeResolver,
) -> None:
    """It has no ordinal of its own, so it gets a named one and a readable label."""
    change = modified()
    offered = context(change)
    good = sorted(offered.keys)[0]
    result = check_explanation(
        Explanation(
            sentences=(says("Grounded.", good),),
            applicability_note=says("It applies from some date.", "AR 99@v2"),
        ),
        offered,
        resolver,
    )
    assert [failure.index for failure in result.failures] == [APPLICABILITY_NOTE]
    assert result.failures[0].label == "the applicability note"
    assert result.sentences == 2, "the note is a citing slot like any other"


# ------------------------------------------------------- the note is quoted or it is nothing

AFTER = "The bins go out on Tuesday evening.\nThis Article applies from 1 June 2026."

CAP = ExplainSettings().text_char_cap
"""The shipped default, not a literal: the cap has exactly one definition, in the settings."""


def test_a_note_is_verbatim_when_only_its_whitespace_differs() -> None:
    """Containment under the project's one normaliser, because a quotation lifted out of an
    XML document arrives with the source's line breaks rather than the reader's."""
    note = says("This  Article\n   applies from 1 June 2026.", "AR 2@v2")
    assert note_is_verbatim(note, AFTER, CAP)


def test_a_quotation_spaced_the_way_a_person_writes_it_is_still_a_quotation() -> None:
    """The normaliser collapses a run of whitespace and cannot insert one, so a text whose
    blocks were joined with nothing turned a correct quotation into a false negative: it failed
    containment and was counted ungrounded. Since extraction started separating those blocks on
    2026-08-12, the note and the stored text collapse to the same string. The AFTER side here
    carries no separator at all, which is the case that must keep working: a quotation with the
    separator in it still has to fail against a text that genuinely runs the two sentences
    together.
    """
    note = says("The bins go out on Tuesday evening. This Article applies", "AR 2@v2")
    assert note_is_verbatim(note, AFTER, CAP)
    assert not note_is_verbatim(note, AFTER.replace("\n", ""), CAP)


def test_a_paraphrase_that_agrees_with_the_date_is_still_not_a_quotation() -> None:
    """Agreement is not quotation. This one names the right date and says nothing the text
    says, which is exactly the case a reader cannot tell apart from a real quotation."""
    note = says("The provision applies from 1 June 2026.", "AR 2@v2")
    assert not note_is_verbatim(note, AFTER, CAP)


def test_a_note_quoting_only_what_lies_past_the_truncation_marker_is_not_a_quotation() -> None:
    """The model never saw those characters, so a match against them is coincidence. The same
    note passes once the cap is wide enough to have shown it."""
    padded = "x" * 200 + " " + AFTER
    note = says("This Article applies from 1 June 2026.", "AR 2@v2")
    assert not note_is_verbatim(note, padded, 40)
    assert note_is_verbatim(note, padded, CAP)


def test_a_deletion_has_no_after_text_and_so_nothing_to_quote() -> None:
    """An empty side answers `False` rather than matching everything, which is what a
    containment test on an empty string would otherwise do to an empty note."""
    assert not note_is_verbatim(says("It applies from 1 June 2026.", "AR 2@v2"), "", CAP)


def test_the_complaint_names_every_bad_key_and_is_byte_stable(resolver: TreeResolver) -> None:
    """It is what `revise` is handed, so it has to be specific, and identical across runs."""
    change = modified()
    offered = context(change)
    explanation = Explanation(
        sentences=(says("One.", "AR 42@v2"), says("Two.", sorted(offered.keys)[0], "AR 43@v2"))
    )
    first = check_explanation(explanation, offered, resolver).complaint
    second = check_explanation(explanation, offered, resolver).complaint
    assert first == second
    assert "sentence 1" in first and "sentence 2" in first
    assert "AR 42@v2" in first and "AR 43@v2" in first


def test_the_gate_has_no_opinion_about_whether_a_sentence_is_true(
    resolver: TreeResolver,
) -> None:
    """Nonsense with a valid citation passes. That is not a hole but the division of labour:
    faithfulness is measured separately, against a different reference, and folding it in here
    would make the grounding number mean nothing."""
    change = modified()
    offered = context(change)
    result = check_explanation(
        Explanation(
            sentences=(says("The bins were abolished by royal decree.", sorted(offered.keys)[0]),)
        ),
        offered,
        resolver,
    )
    assert result.passed
