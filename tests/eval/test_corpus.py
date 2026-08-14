"""The committed corpus: is it the set the rules ask for, and is its selection reproducible?

The corpus is generated, so these tests do not check taste. They check that the generated file
still satisfies the decision it implements, that the sampling rule is a pure function of two
integers, and that nothing in it was quietly curated.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.eu.cache import read_manifest
from emendrix.eval_.build import ACTS, MAX_INSTRUCTION_BYTES
from emendrix.eval_.corpus import REACH_SAMPLE, EvalCorpus, load_corpus, sample_indices
from eu_pins import FIXTURE_DIR

MINIMUM_CASES = 15
"""The minimum the corpus must contain. The committed corpus has more; this is the floor."""


@pytest.fixture(scope="module")
def corpus() -> EvalCorpus:
    return load_corpus()


def test_the_sample_is_evenly_spread_and_keeps_both_endpoints() -> None:
    assert sample_indices(62, 10) == (0, 7, 14, 20, 27, 34, 41, 47, 54, 61)
    assert sample_indices(3, 10) == (0, 1, 2)
    assert sample_indices(0, 10) == ()
    assert sample_indices(10, 1) == (0,)


def test_the_sample_depends_on_nothing_but_two_integers() -> None:
    """No seed, no dict order, no clock: the same two numbers, always the same indices."""
    assert sample_indices(62, 10) == sample_indices(62, 10)
    assert all(0 <= index < 62 for index in sample_indices(62, 10))


def test_the_corpus_carries_at_least_the_required_transitions(corpus: EvalCorpus) -> None:
    assert len(corpus.cases) >= MINIMUM_CASES
    assert {case.id for case in corpus.cases} == {case.id for case in corpus.cases}
    assert corpus.built_on == date(2026, 8, 6)


def test_every_required_act_is_a_corpus_member(corpus: EvalCorpus) -> None:
    """The DSA has no second readable version and is still a member, stated as such."""
    assert {act.celex for act in corpus.acts} == {celex for celex, _ in ACTS}
    dsa = next(act for act in corpus.acts if act.celex == "32022R2065")
    assert dsa.transitions_possible == 0
    assert "corpus member for future amendments" in dsa.note


def test_reach_contributes_exactly_the_documented_sample(corpus: EvalCorpus) -> None:
    reach = next(act for act in corpus.acts if act.celex == "32006R1907")
    assert reach.transitions_selected == REACH_SAMPLE
    assert reach.transitions_possible > REACH_SAMPLE
    assert len(corpus.cases_of("32006R1907")) == REACH_SAMPLE


def test_the_other_acts_contribute_every_transition_they_have(corpus: EvalCorpus) -> None:
    for act in corpus.acts:
        if act.celex == "32006R1907":
            continue
        assert act.transitions_selected == act.transitions_possible, act.celex
        assert act.coverage == 1.0


def test_the_flagship_transition_is_in_the_corpus(corpus: EvalCorpus) -> None:
    """It only exists because a version with no English text is bridged, not chained through."""
    case = corpus.case("32024R1689@20260727")
    assert case is not None
    assert (case.from_version, case.to_version) == ("32024R1689", "02024R1689-20260727")
    assert case.from_original and case.annotations == 88
    assert case.bridged == ("02024R1689-20240712",)
    assert case.instruction_source == "32026R1744"


def test_every_skip_names_a_first_class_state_and_a_reason(corpus: EvalCorpus) -> None:
    assert corpus.skips
    for skip in corpus.skips:
        assert skip.reason in {"structured_text_unavailable", "version_date_unknown"}
        assert skip.detail
    bridged = {version for case in corpus.cases for version in case.bridged}
    assert bridged <= {skip.version for skip in corpus.skips}


def test_coverage_is_published_as_a_fraction(corpus: EvalCorpus) -> None:
    """Honesty rule 5: a documented sample of a stated whole, never an implied census."""
    assert 0.0 < corpus.coverage < 1.0
    assert corpus.transitions_possible > len(corpus.cases)


def test_every_case_pins_the_documents_it_is_computed_from(corpus: EvalCorpus) -> None:
    for case in corpus.cases:
        roles = {item.role for item in case.inputs}
        assert {"from", "to", "metadata", "routing"} <= roles, case.id
        if case.instruction_source is not None:
            assert "instructions" in roles, case.id
        assert all(len(item.sha256) == 64 and item.size > 0 for item in case.inputs)


def test_every_pinned_input_is_the_document_the_fixture_set_still_holds(
    corpus: EvalCorpus,
) -> None:
    """`CaseInput`'s promise, checked: a case whose inputs hash differently is a different case.

    `FixtureResponseCache.get` checks a fixture body against its manifest entry on every read,
    which keeps manifest and bytes honest. This closes the other half of the chain, that the
    digests `corpus.json` was generated against are still the digests the manifest pins, so a
    fixture re-trimmed on both sides at once cannot rescore silently under the same case id.
    """
    pinned = {entry.sha256 for entry in read_manifest(FIXTURE_DIR / "manifest.json")}
    assert pinned
    for case in corpus.cases:
        for item in case.inputs:
            assert item.sha256 in pinned, f"{case.id}: {item.role} {item.url} was re-pinned"


def test_a_case_without_a_third_signal_says_why(corpus: EvalCorpus) -> None:
    silent = [case for case in corpus.cases if case.instruction_source is None]
    assert silent, "the corpus is expected to contain windows with several amending acts"
    for case in silent:
        assert case.instruction_note, case.id


def test_no_pinned_instruction_document_exceeds_the_committed_cap(corpus: EvalCorpus) -> None:
    """The cap is what keeps the CLP Regulation's 3.3 MB of Formex out of the repository."""
    for case in corpus.cases:
        for item in case.inputs:
            if item.role == "instructions":
                assert item.size <= MAX_INSTRUCTION_BYTES, case.id
