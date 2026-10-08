"""The whole committed corpus, scored offline: the run CI does on every push.

**If one of these numbers moves, that is a finding to explain, not a test to update.** The
committed report under `reports/eval/` is the record of what was measured; this file
asserts the same figures through the same code, so a regression fails the build rather than
appearing quietly in the next report.

Two transitions in it were chosen as hard cases and stay in:

- the MDR's first consolidation carries only a corrigendum, so no amending act annotated its
  window and the metadata has no reference set to offer. It is scored, its 15 changes ship, and
  it contributes nothing to the localisation pairing. Until 2026-08-12 the empty reference set
  was read as a claim that nothing changed, which scored the pairing at zero precision over
  those 15 units and shipped every one of them `disputed`;
- REACH's 2007 → 2008 pair is where the two location vocabularies spell an annex differently:
  the legacy notice writes `AN 4` and `AN 5` where the markup writes `AN IV` and `AN V`. Until
  2026-10-08 neither signal shared a unit with the other and all four coordinates shipped
  `disputed`. Since that date the notice's Arabic annex numbers are read as the markup's Roman
  ones, and the pair agrees three ways: the disagreement this file used to assert was a
  difference of notation, not of substance.

Both are in the corpus on purpose. Curating them out is the one unrecoverable failure of this
project.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

from emendrix.core import Signal
from emendrix.core.changes import DisputeReason
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eval_.corpus import EvalCorpus, load_corpus
from emendrix.eval_.judge import Triple, sample
from emendrix.eval_.model_metrics import SUBSET_CASSETTE_DIR
from emendrix.eval_.model_run import SubsetRun, attach_model_layer, replay_engine, run_subset
from emendrix.eval_.report import dispute_reasons
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

    Until 2026-10-08 this read 79 shared units, P 0.952 / R 0.975 / F1 0.963, macro 0.915, over
    the same 17 transitions and the same 83 and 81 units. The metadata set was re-keyed that
    day: REACH's legacy `AN 4` and `AN 5` are read as the markup's `AN IV` and `AN V`, so two
    units the two signals always both named are now counted as shared. **This is not the
    localisation getting better**: the diff did not move, and the right-hand side is the same
    annotations under the markup's spelling. It is also the one fix to the corroboration that
    moves this figure, because the instruction parse never enters it and the metadata keys do.

    Until 2026-08-12 this read 18 transitions, 98 diff units, P 0.806 / F1 0.883 / macro 0.864.
    The transition that left is `32017R0745@20170505`, whose window no amending act annotated:
    its metadata signal is `UNAVAILABLE`, so there is nothing to pair the diff's 15 units with
    and they are left out of the denominator rather than counted as 15 misses. **These figures
    and the earlier ones are not the same measurement improved.** Recall is the one number
    computed over the same right-hand side either way, and it did not move.
    """
    pair = run.metrics.localisation
    assert pair is not None
    assert (pair.cases, pair.left_units, pair.right_units, pair.shared) == (17, 83, 81, 81)
    assert round(pair.micro_precision, 3) == 0.976
    assert round(pair.micro_recall, 3) == 1.000
    assert round(pair.micro_f1, 3) == 0.988
    assert round(pair.macro_f1, 3) == 0.974


def test_classification_agrees_on_every_shared_unit(run: EvalRun) -> None:
    """81 units both signals named, and not one kind disagreement among them.

    79 until 2026-10-08, when REACH's `AN IV` and `AN V` became units both signals name rather
    than two spellings neither shared; both are modifications on either side.
    """
    assert run.metrics.classification_accuracy == 1.0
    assert run.metrics.classification_units == 81
    assert {(cell.diff, cell.metadata): cell.count for cell in run.metrics.confusion} == {
        ("INSERTED", "INSERTED"): 8,
        ("MODIFIED", "MODIFIED"): 73,
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


def test_the_legacy_annex_numbers_name_the_annexes_the_markup_names(run: EvalRun) -> None:
    """`AN 4`/`AN 5` in a legacy notice are the markup's `AN IV`/`AN V`: 2 shared units of 2.

    Until 2026-10-08 this asserted the opposite: two signals named the same two annexes in two
    spellings, neither shared a unit with the other, and all four coordinates shipped disputed.
    That disagreement was a difference of notation. The notice's Arabic annex numbers are read
    as the markup's Roman ones now, by an explicit converter in the EU adapter, so the pair has
    two changes where it had four, and all three signals agree on both. Nothing that carried
    text left the record: the two rows that went were the textless `AN 4` and `AN 5`.

    What left this transition on 2026-09-04 is two phantoms beside them. `32008R0987` states
    both of its instructions in prose with no list, so the whole article was the clause and its
    own heading was read as the provision the prose pointed at: the claims came out `AR 1` and
    `AR 2`, coordinates neither of the other two signals named. They now read `AN IV` and
    `AN V`, which is where the structural diff already was.
    """
    case = next(item for item in run.cases if item.case_id == "32006R1907@20081012")
    assert case.agreement(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA) == (2, 2, 2)
    assert (case.changes, case.disputed, case.metadata_only_units) == (2, 0, 0)
    assert case.report is not None
    assert case.report.disagreements == ()
    for signal in Signal:
        assert {unit.canonical for unit in case.report.units_of(signal)} == {"AN IV", "AN V"}


def test_nothing_is_dropped_across_the_whole_corpus(run: EvalRun) -> None:
    """2 disputed of 98 changes, and every one of them ships.

    It read 6 of 100, with `(4, 2)` for the two unit counts, until the metadata's location
    codes were read as the markup's units on 2026-10-08. REACH's `@20081012` shipped `AN 4` and
    `AN 5` as textless metadata-only changes and `AN IV` and `AN V` as diff-only ones, all four
    disputed, because the legacy notice numbers those annexes in Arabic. The notice's numbers
    are read as the markup's now, so the pair is two changes that agree three ways. **2 of 98
    is not 6 of 100 improved.** Two of the 100 were the same annexes under a second spelling,
    so the denominator is a different one, and the metadata set every pairing reads is
    re-keyed. The question is unchanged.

    Before that, also on 2026-10-08, it read 12 of 100. Six REACH transitions (`@20121009`,
    `@20160308`, `@20190702`, `@20220501`, `@20240606`, `@20260511`) each shipped one change
    disputed by an instruction signal that had read its amending act and claimed nothing in
    that window. Such a signal is `UNAVAILABLE` now, the rule the metadata signal has followed
    since 2026-08-12, so silence there is no longer counted as dissent. **6 of 100 is not 12 of
    100 improved.** The rows are the same 100; the question changed, from "did every signal that
    read something name this unit" to "did every signal that claimed something in this window
    name it". No unit is named by the instruction parse alone anywhere in the corpus, so the
    rule that lists such units in the report rather than appending them moves no row here.

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
    with, which is why that fix left the REACH annex-numbering disputes as they were.

    Until 2026-08-11 it read 37 of 108: the instruction parser dropped the annex scope an
    article's lead-in establishes ("Annex I to Regulation (EU) 2017/745 is amended as
    follows:"), so `32025R2457`'s four section amendments were keyed at bare `SCT 10.4.x`
    beside the `AN I` unit every other signal used. That shipped four phantom units and five
    false disputes on `32017R0745@20260101`, which now agrees three ways.
    """
    assert (run.metrics.changes, run.metrics.disputed) == (98, 2)
    assert (run.metrics.diff_only_units, run.metrics.metadata_only_units) == (2, 0)
    assert run.metrics.instruction_only_units == 0
    assert sum(len(case.report.disagreements) for case in run.cases if case.report) == 2


SILENT_THIRD_SIGNAL = (
    "32006R1907@20121009",
    "32006R1907@20160308",
    "32006R1907@20190702",
    "32006R1907@20220501",
    "32006R1907@20240606",
    "32006R1907@20260511",
)
"""The REACH windows whose amending act was read and claimed nothing inside them."""


def test_both_disputed_changes_are_the_metadata_falling_silent(run: EvalRun) -> None:
    """The report's reason table over the corpus: 2 disputed, both `metadata_silent`.

    REACH's `@20150323` `AN I` and `@20210215` `AN XIV`: the structural diff found each and the
    annotations of a window the corpus did annotate do not name it. Every other code reads zero,
    and the counts sum to the disputed figure, so no disputed change is left without a reason.
    """
    reasons = dispute_reasons(run)
    assert sum(reasons.values()) == run.metrics.disputed == 2
    assert {reason: total for reason, total in reasons.items() if total} == {
        DisputeReason.METADATA_SILENT: 2
    }


def test_a_third_signal_that_claims_nothing_in_its_window_takes_no_part(run: EvalRun) -> None:
    """Both instruction pairings over 7 transitions, where they were over 13 until 2026-10-08.

    Until then the six windows above each entered both pairings with an empty instruction set,
    scoring 0.000 against one unit, and read diff against instruction parse P 0.917 / R 1.000 /
    F1 0.957, macro 0.538, and metadata against instruction parse P 0.889 / R 0.970 / F1 0.928,
    macro 0.462. Those signals are `UNAVAILABLE` now and leave the denominator. **The figures
    below are not the instruction parse getting more accurate**: they are computed over a
    smaller set of transitions, the seven where the third signal claimed something, and the
    right-hand side of each pairing is the same 66 units it was before. The parse still read
    all thirteen windows, which is what the coverage line counts.

    Metadata against instruction parse read 64 shared, 0.970 / 0.970 / 0.970, macro 0.857,
    until the metadata's location codes were read as the markup's units, also on 2026-10-08:
    REACH's legacy `AN 4` and `AN 5` are now the `AN IV` and `AN V` the parse already named.
    The two signals named the same annexes before and after; only the metadata's spelling of
    them moved.
    """
    for case_id in SILENT_THIRD_SIGNAL:
        case = next(item for item in run.cases if item.case_id == case_id)
        assert case.report is not None
        assert (case.changes, case.disputed) == (1, 0), case_id
        assert case.instruction_coverage is not None, case_id
        third = next(s for s in case.report.signals if s.signal is Signal.INSTRUCTION_PARSE)
        assert third.available is False, case_id
        assert third.note is not None and "nothing claimed in this window" in third.note

    prose = run.metrics.instruction_agreement
    assert prose is not None
    assert (prose.cases, prose.left_units, prose.right_units, prose.shared) == (7, 66, 66, 66)
    assert (prose.micro_precision, prose.micro_recall, prose.micro_f1) == (1.0, 1.0, 1.0)
    assert prose.macro_f1 == 1.0

    meta = run.metrics.metadata_instruction
    assert meta is not None
    assert (meta.cases, meta.left_units, meta.right_units, meta.shared) == (7, 66, 66, 66)
    assert (meta.micro_precision, meta.micro_recall, meta.micro_f1) == (1.0, 1.0, 1.0)
    assert meta.macro_f1 == 1.0


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

    Read is not the same as available: since 2026-10-08 six of the thirteen claim nothing in
    their window and are `UNAVAILABLE`, so the pairings count seven while this counts thirteen.

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
    nothing the REACH pair does not, and costs a minute of every CI run.
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
