"""The whole committed corpus, scored offline: the run CI does on every push.

**If one of these numbers moves, that is a finding to explain, not a test to update.** The
committed report under `reports/eval/` is the record of what was measured; this file
asserts the same figures through the same code, so a regression fails the build rather than
appearing quietly in the next report.

Two transitions in it are hard cases and stay in:

- the MDR's first consolidation carries only a corrigendum, so no amending act annotated its
  window and the metadata has no reference set to offer. It is scored, its 15 changes ship, and
  it contributes nothing to the localisation pairing. Until 2026-08-12 the empty reference set
  was read as a claim that nothing changed, which scored the pairing at zero precision over
  those 15 units and shipped every one of them `disputed`;
- REACH's 2007 → 2008 pair is where the two location vocabularies spell an annex differently
  (`AN 4` against `AN IV`), so neither signal shares a unit with the other. That one is a real
  disagreement and still ships as one.

Both are in the corpus on purpose. Curating them out is the one unrecoverable failure of this
project.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

from emendrix.core import Signal
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eval_.corpus import EvalCorpus, load_corpus
from emendrix.eval_.judge import Triple, sample
from emendrix.eval_.model_metrics import SUBSET_CASSETTE_DIR
from emendrix.eval_.model_run import SubsetRun, attach_model_layer, replay_engine, run_subset
from emendrix.eval_.runner import CorpusReader, EvalRun, run_corpus
from emendrix.eval_.signoff import PENDING, latest_signoff, review_status, sample_digest
from emendrix.eval_.thresholds import FLOORS, check
from emendrix.explain import DEFAULT_MODEL, Cassette, model_slug
from eu_pins import FIXTURE_DIR, OBSERVED_ON

RUN_DATE = date(2026, 8, 6)


@pytest.fixture(scope="module")
def corpus() -> EvalCorpus:
    return load_corpus()


@pytest.fixture(scope="module")
def run(corpus: EvalCorpus) -> EvalRun:
    """The full corpus, from committed fixtures. `FixtureResponseCache` has no path to a socket."""
    http = CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR))
    reader = CorpusReader(CellarClient(http, observed_on=OBSERVED_ON))
    return run_corpus(reader, corpus, run_date=RUN_DATE, revision="test")


@pytest.fixture(scope="module")
def subset(corpus: EvalCorpus) -> SubsetRun:
    """The pinned explanation subset, replayed from committed cassettes. No provider, no key."""
    http = CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR))
    with http:
        client = CellarClient(http, observed_on=OBSERVED_ON)
        return asyncio.run(
            run_subset(
                CorpusReader(client),
                corpus,
                engine=replay_engine(),
                adapter=EuCorpusAdapter(client),
                observed_on=OBSERVED_ON,
            )
        )


@pytest.fixture(scope="module")
def sampled(subset: SubsetRun) -> tuple[Triple, ...]:
    return sample(subset.triples)


def test_every_transition_in_the_corpus_scores(run: EvalRun) -> None:
    unscored = [case.case_id for case in run.cases if not case.scored]
    assert unscored == []
    assert run.metrics.cases == run.metrics.cases_scored == 18


def test_the_headline_numbers_are_the_ones_the_committed_report_publishes(run: EvalRun) -> None:
    """17 transitions, not 18: a pairing needs two signals, and one window has only one.

    Until 2026-08-12 this read 18 transitions, 98 diff units, P 0.806 / F1 0.883 / macro 0.864.
    The transition that left is `32017R0745@20170505`, whose window no amending act annotated:
    its metadata signal is `UNAVAILABLE`, so there is nothing to pair the diff's 15 units with
    and they are left out of the denominator rather than counted as 15 misses. **These figures
    and the earlier ones are not the same measurement improved.** Recall is the one number
    computed over the same right-hand side either way, and it did not move.
    """
    pair = run.metrics.localisation
    assert pair is not None
    assert (pair.cases, pair.left_units, pair.right_units, pair.shared) == (17, 83, 81, 79)
    assert round(pair.micro_precision, 3) == 0.952
    assert round(pair.micro_recall, 3) == 0.975
    assert round(pair.micro_f1, 3) == 0.963
    assert round(pair.macro_f1, 3) == 0.915


def test_classification_agrees_on_every_shared_unit(run: EvalRun) -> None:
    """79 units both signals named, and not one kind disagreement among them."""
    assert run.metrics.classification_accuracy == 1.0
    assert run.metrics.classification_units == 79
    assert {(cell.diff, cell.metadata): cell.count for cell in run.metrics.confusion} == {
        ("INSERTED", "INSERTED"): 8,
        ("MODIFIED", "MODIFIED"): 71,
    }


def test_the_flagship_still_agrees_three_ways(run: EvalRun) -> None:
    """The AI Act row, now reached through the eval harness rather than a test fixture."""
    case = next(item for item in run.cases if item.case_id == "32024R1689@20260727")
    assert case.report is not None
    assert [item.count for item in case.report.signals] == [45, 45, 45]
    for pair in case.report.agreements:
        assert (pair.precision, pair.recall, pair.f1) == (1.0, 1.0, 1.0), pair
    assert case.disputed == 0


def test_the_corrigendum_consolidation_scores_nothing_and_stays_in(run: EvalRun) -> None:
    """A corrigendum is not an amendment, so nobody annotated this window and nothing dissents.

    Until 2026-08-12 this case scored zero precision over 15 diff-only units and shipped all 15
    of its changes `disputed`, because a metadata signal handed no annotations was reported as
    available and every unit the diff found then resolved to `ABSENT`. It does not score zero
    now, it scores nothing: `agreement` is `None` because a pairing needs two signals, and the
    15 units are not diff-only because there is no reference set for them to be missing from.

    Every clause below carries the fix. The case is still scored and its 15 changes still ship,
    so the transition was not dropped to reach the number; the metadata note still counts the
    annotations it did not find, so the absence is stated rather than implied; and the
    structural diff still names all 15 units, so nothing was lost on the way in.
    """
    case = next(item for item in run.cases if item.case_id == "32017R0745@20170505")
    assert case.scored and case.changes == 15
    assert case.agreement(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA) is None
    assert case.diff_only_units == 0
    assert case.disputed == 0
    assert case.report is not None
    assert case.report.disagreements == ()
    assert len(case.report.units_of(Signal.STRUCTURAL_DIFF)) == 15
    metadata = next(item for item in case.report.signals if item.signal is Signal.CORPUS_METADATA)
    assert metadata.available is False
    assert metadata.units == ()
    assert metadata.note == "0 annotations in (2017-04-05, 2017-05-05]"


def test_the_annex_numbering_mismatch_is_published_not_hidden(run: EvalRun) -> None:
    """`AN 4`/`AN 5` in a legacy notice against `AN IV`/`AN V` in the markup: 0 shared units.

    The vocabulary disagreement is the point of the case and is untouched. Two signals name the
    same two annexes in two spellings, neither shares a unit with the other, and all four
    coordinates ship disputed rather than being reconciled by a table of equivalent numerals.

    What left this transition on 2026-09-04 is two phantoms beside them. `32008R0987` states
    both of its instructions in prose with no list, so the whole article was the clause and its
    own heading was read as the provision the prose pointed at: the claims came out `AR 1` and
    `AR 2`, coordinates neither of the other two signals named. They now read `AN IV` and
    `AN V`, which is where the structural diff already was.
    """
    case = next(item for item in run.cases if item.case_id == "32006R1907@20081012")
    assert case.agreement(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA) == (2, 2, 0)
    assert case.report is not None
    disputed = {item.unit.canonical for item in case.report.disagreements}
    assert {"AN 4", "AN IV", "AN 5", "AN V"} <= disputed


def test_nothing_is_dropped_across_the_whole_corpus(run: EvalRun) -> None:
    """12 disputed of 100 changes, and every one of them ships.

    Until 2026-09-05 this read 13 of 101, with `(4, 3)` for the two unit counts: the third
    signal read an amending act whole and claimed every instruction in it in every window that
    act touched, however the act dated them. `32024R1860` orders MDR Article 10a into existence
    from 10 January 2025 and `32017R0745@20240709` ends six months before that, so the claim
    shipped in a window whose text does not contain the provision, with no text on either side
    and disputed against two signals that had never heard of it. The window now reaches the
    instruction parse as well, and only the act's own text dates a record. **12 of 100 is not
    13 of 101 improved.** One of the 101 was never a change in this window at all, so the
    denominator is a different one, and the right-hand side of both pairings the third signal
    enters is a different set of claims. The question each figure asks is unchanged.

    Until 2026-09-04 this read 17 of 104, with `(4, 6)` for the two unit counts: an amending
    article that states its instruction in prose rather than in a list had its own heading read
    as the provision the instruction pointed at, because the reference grammar keeps the first
    coordinate at each depth and the article title got there first. `32006R1907@20081012`
    shipped phantom `AR 1` and `AR 2` claims where its amender's prose names Annexes IV and V;
    `32017R0745@20230311` shipped a phantom `AR 1` and left its real `AR 44` disputed for want
    of the third confirmation it should have had. **13 of 101 is not 17 of 104 improved.** Three
    of the 104 were never changes at all, so the denominator is a different one, and the third
    signal now reads the amended act's article numbers where it read the amending act's, so the
    right-hand side of every pairing it takes part in is a different set of claims. The question
    is unchanged; the claims are not.

    Until 2026-08-12 this read 32 of 104: a metadata signal handed no annotations at all was
    reported as available, so every unit the diff found in an unannotated window resolved to
    `ABSENT`, and `OBSERVED` against `ABSENT` is a dispute. `32017R0745@20170505`'s 15 changes
    shipped disputed against a reference set nobody published. **17 is not 32 improved: the
    question changed**, from "did every signal name this unit" to "did every signal that had
    something to say name this unit". The 17 that remain all have a reference set to disagree
    with, which is why the REACH annex-numbering disputes below are untouched.

    Until 2026-08-11 it read 37 of 108: the instruction parser dropped the annex scope an
    article's lead-in establishes ("Annex I to Regulation (EU) 2017/745 is amended as
    follows:"), so `32025R2457`'s four section amendments were keyed at bare `SCT 10.4.x`
    beside the `AN I` unit every other signal used. That shipped four phantom units and five
    false disputes on `32017R0745@20260101`, which now agrees three ways.
    """
    assert (run.metrics.changes, run.metrics.disputed) == (100, 12)
    assert (run.metrics.diff_only_units, run.metrics.metadata_only_units) == (4, 2)
    assert sum(len(case.report.disagreements) for case in run.cases if case.report) == 12


def test_the_parser_accounts_for_every_element_it_read(run: EvalRun) -> None:
    """One unreadable document: a TIFF page scan shipped with an `.xml` name (2026-08-06)."""
    parser = run.metrics.parser
    assert (parser.unknown_elements, parser.unmapped_identifiers) == (0, 0)
    assert parser.documents_unreadable == 1
    assert (parser.documents, parser.units) == (67, 5382)


def test_every_explanation_replayed_from_a_committed_cassette_byte_for_byte(
    subset: SubsetRun,
) -> None:
    """The replay is a byte-level pin on the explain prompts. A cassette key is a sha256 over
    the model id and both messages, so a user message that moved by one byte is a loud
    `CassetteMiss` rather than a quiet re-record. Zero synthetic answers with every explained
    change replayed therefore asserts that the prompts built today are exactly the committed
    ones, which is what lets the header handed to the judge and the worksheet be read off the
    same value the prompt printed without changing what the model was sent."""
    assert subset.metrics.explained > 0
    assert subset.metrics.synthetic == 0
    assert subset.metrics.replayed == subset.metrics.explained


def test_every_sampled_triple_carries_the_header_of_a_committed_explain_prompt(
    sampled: tuple[Triple, ...],
) -> None:
    """The header the judge and the reviewer are shown is the writer's, byte for byte.

    Equality against the whole header block of a committed explain prompt, never containment: a
    paraphrase or a prefix would satisfy a containment check and still put different evidence in
    front of the two auditors, which is the drift that carrying one value to both prevents.
    """
    headers: set[str] = set()
    for path in sorted((SUBSET_CASSETTE_DIR / model_slug(DEFAULT_MODEL)).glob("*.json")):
        user = Cassette.model_validate_json(path.read_text(encoding="utf-8")).user
        headers.add(user.split("\n\nOFFERED CITATION KEYS", 1)[0])
    assert headers, "no committed explain prompts to check the sample against"
    for triple in sampled:
        assert triple.header, f"{triple.slug} carries no header"
        assert triple.header in headers, f"{triple.slug} carries a header no writer was shown"


def test_a_hand_review_is_published_only_while_it_describes_the_current_sample(
    sampled: tuple[Triple, ...],
) -> None:
    """The guard itself, asserted over the sample a real run builds, in both of its two states.

    Whether the committed sign-off happens to describe today's sample is a fact about today, not
    a property, so nothing here asserts it: the sample moves whenever a cassette is re-recorded,
    a prompt is edited or a change stops being sent to the model, and the answer to that is a
    fresh reading of twenty triples and a new sign-off. It is never a new digest typed into the
    committed file. What is a property is that there are exactly two outcomes and no third.
    """
    signoff = latest_signoff()
    assert signoff is not None, "the committed sign-off is missing"
    assert len(sampled) == 20

    describes_this_sample = signoff.model_copy(update={"sample_digest": sample_digest(sampled)})
    assert review_status(describes_this_sample, sampled) == signoff.summary
    assert review_status(signoff.model_copy(update={"sample_digest": "0" * 64}), sampled) == PENDING
    assert review_status(None, sampled) == PENDING


def test_the_report_publishes_the_guarded_string_and_never_invents_one(
    run: EvalRun, subset: SubsetRun, sampled: tuple[Triple, ...], tmp_path: Path
) -> None:
    """`replay` cannot claim a review; `attach_model_layer` reads the committed one and may."""
    signoff = latest_signoff()
    assert signoff is not None
    attached = attach_model_layer(run, subset, directory=tmp_path, write=False)
    assert attached.faithfulness is not None
    assert attached.faithfulness.human_review in {signoff.summary, PENDING}
    assert attached.faithfulness.human_review == review_status(signoff, sampled)
    assert list(tmp_path.iterdir()) == [], "a scoring run with --no-write writes nothing"


def test_the_committed_floors_are_cleared(run: EvalRun) -> None:
    assert check(run.metrics) == ()
    assert FLOORS.cases_scored == run.metrics.cases_scored


def test_the_third_signal_publishes_its_own_coverage(run: EvalRun) -> None:
    """Read on 13 of 18 windows; the rest name several amending acts, and say so.

    The six unread instructions are one shape: a REACH annex amender whose article delegates the
    work to its own annex ("Annex XVII to Regulation (EC) No 1907/2006 is amended in accordance
    with the Annex to this Regulation"), which states no instruction verb and so describes no
    change to read. A gap in a cross-check is counted, never approximated. The six did not move
    on 2026-09-04, when an amending article's own heading stopped being read as the provision
    its instruction points at: that changed which location a clause resolves to, not whether the
    clause states an instruction at all.
    """
    assert run.metrics.instruction_cases == 13
    assert run.metrics.instruction_unread == 6
    silent = [case for case in run.cases if case.instruction_coverage is None]
    assert len(silent) == 5
    assert all(case.instruction_note for case in silent)


def test_a_second_run_produces_the_same_bytes(corpus: EvalCorpus) -> None:
    """Byte-stable: no clock, no set iteration, no dict ordering anywhere in the scoring.

    One transition rather than eighteen: re-parsing REACH's annexes a second time proves
    nothing the disputed REACH pair does not, and costs a minute of every CI run.
    """
    runs = [
        run_corpus(
            CorpusReader(
                CellarClient(
                    CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR)), observed_on=OBSERVED_ON
                )
            ),
            corpus,
            run_date=RUN_DATE,
            revision="test",
            only="32006R1907@20081012",
        )
        for _ in range(2)
    ]
    assert runs[0].model_dump_json() == runs[1].model_dump_json()


def test_asking_for_a_transition_nobody_selected_fails_loudly(corpus: EvalCorpus) -> None:
    reader = CorpusReader(
        CellarClient(CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR)), observed_on=OBSERVED_ON)
    )
    with pytest.raises(LookupError, match="no such transition"):
        run_corpus(reader, corpus, run_date=RUN_DATE, only="32024R1689@19990101")
