"""The faithfulness layer: sampling, the rubric, the cassettes, and the `pending` state.

No model is called here. The judge agent is exercised through a stub in the recorder
(`test_record_subset_cassettes.py`, marked `record`); what matters in a default run is that the
sample is deterministic, that the prompt the key is taken over is stable, and that a verdict
produced by a stub can never become a published rate.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from emendrix.eval_.judge import (
    SAMPLE_SIZE,
    FaithfulnessReport,
    Triple,
    Verdict,
    judge_model,
    prompt_for,
    sample,
)
from emendrix.eval_.judgements import (
    JUDGE_CASSETTE_DIR,
    RUBRIC_SHA,
    JudgeCassette,
    JudgeCassetteStore,
    judgement_key,
    replay,
)
from emendrix.eval_.model_metrics import SUBSET_CASSETTE_DIR
from emendrix.eval_.rubric import CONTEXT_LABEL, HEADER_LABEL, JUDGE_RUBRIC, judge_prompt
from emendrix.eval_.worksheet import (
    render_worksheet,
    worksheet_is_reviewed,
    worksheet_path,
    write_worksheet,
)
from emendrix.explain import (
    DEFAULT_MODEL,
    Cassette,
    CassetteCorrupt,
    ExplainSettings,
    cap_text,
    model_slug,
)

_EXPLAIN_TEXT: Final = re.compile(r"TEXT \(verbatim\):\n<<<(\w*)\n(.*?)\n>>>\1", re.S)
"""One BEFORE or AFTER block of an explain prompt, exactly as the model was shown it.

The back-reference is the per-prompt fence token, so a provision that itself contains `>>>`
cannot end the capture early. The token is empty on the prompts recorded before 2026-08-08,
when the delimiters were still literal, and the same pattern reads both.
"""

_EXPLAIN_CONTEXT: Final = re.compile(
    r"SURROUNDING CONTEXT \([^)]*\):\n<<<(\w*)\n(.*?)\n>>>\1", re.S
)
"""The surrounding-provision block of an explain prompt, if it carries one."""

_JUDGE_HEADER: Final = re.compile(rf"\A{re.escape(HEADER_LABEL)}:\n(.*?)\n\nBEFORE:", re.S)
_JUDGE_BEFORE: Final = re.compile(r"(?:\A|\n\n)BEFORE:\n(.*?)\n\nAFTER:", re.S)
_JUDGE_AFTER: Final = re.compile(
    rf"\n\nAFTER:\n(.*?)\n\n(?:{re.escape(CONTEXT_LABEL)}:|SENTENCES:)", re.S
)
_JUDGE_CONTEXT: Final = re.compile(rf"\n\n{re.escape(CONTEXT_LABEL)}:\n(.*?)\n\nSENTENCES:", re.S)


def _triple(index: int, *, fallback: bool = False) -> Triple:
    return Triple(
        case_id="32024R1689@20260727",
        unit=f"AR {index}",
        outcome="fallback" if fallback else "passed",
        change_type="modified",
        before=f"before {index}",
        after=f"after {index}",
        sentences=(f"sentence {index}",),
        fallback=fallback,
    )


def test_the_sample_is_spread_evenly_and_is_the_same_every_time() -> None:
    triples = tuple(_triple(index) for index in range(100))
    first = sample(triples, 5)
    assert [item.unit for item in first] == ["AR 0", "AR 25", "AR 50", "AR 74", "AR 99"]
    assert sample(triples, 5) == first


def test_a_sample_larger_than_the_pool_takes_the_pool() -> None:
    triples = tuple(_triple(index) for index in range(3))
    assert sample(triples) == triples
    assert SAMPLE_SIZE == 20


def test_the_prompt_opens_with_the_header_exactly_as_the_writer_saw_it() -> None:
    """Since 2026-08-09 the judge rules on the evidence the writer was given, and the writer's
    prompt opened with the pipeline header, so the judge's prompt does too, printed first and
    labelled as the pipeline's work rather than as a text. A triple recorded before the header
    entered the evidence base carries none, and its prompt keeps the exact shape the committed
    judgements answered, which is what keeps those judgements' keys derivable."""
    bare = prompt_for(_triple(5))
    assert bare.startswith("BEFORE:")
    assert "AFTER:" in bare and "SENTENCES:" in bare
    assert HEADER_LABEL not in bare

    header = "CHANGE TYPE: MODIFIED (an obviously synthetic header)\nPROVISION: Art. 5"
    prompt = prompt_for(_triple(5).model_copy(update={"header": header}))
    assert prompt.startswith(f"{HEADER_LABEL}:\n{header}\n\nBEFORE:")
    assert "OFFERED CITATION KEYS" not in prompt, "the citation keys reach neither auditor"


def test_a_missing_side_is_named_rather_than_left_blank() -> None:
    prompt = judge_prompt("", "after", ("s",))
    assert "BEFORE: (none — this side of the change does not exist)" in prompt


def test_the_judge_is_shown_the_text_it_was_handed_and_never_shortens_it() -> None:
    """A second, shorter cap here would ask the judge a different question. At 4000 characters
    where the explainer had 8000, the judge ruled on a prefix of the evidence the model read and
    marked accurate sentences unfaithful for describing text it could not see: measured
    2026-08-08, two of the three failures on that day's 20-triple sample were that and nothing
    else.
    """
    long_side = "x" * (ExplainSettings().text_char_cap * 2)
    prompt = judge_prompt(long_side, "after", ("s",))
    assert long_side in prompt, "the judge sees every character it was handed"
    assert "truncated" not in prompt, "the caller caps; this module must not cap again"


def test_the_texts_the_judge_rules_on_are_the_texts_the_model_read() -> None:
    """Capping belongs to one function, so the two cannot drift apart."""
    cap = ExplainSettings().text_char_cap
    provision = "y" * (cap + 500)
    shown, dropped = cap_text(provision, cap)

    assert dropped == 500
    assert "truncated by emendrix: 500 characters omitted" in shown, "the marker travels with it"
    assert judge_prompt(shown, "after", ("s",)).startswith(f"BEFORE:\n{shown}")


def test_the_rubric_is_a_snapshot_because_a_drifting_one_makes_runs_incomparable() -> None:
    assert JUDGE_RUBRIC.startswith("You are auditing one entry of a machine-generated changelog")
    assert "Does every published sentence follow from the evidence the writer was given?" in (
        JUDGE_RUBRIC
    )
    assert "a quotation of the provision is faithful by construction" in JUDGE_RUBRIC
    assert JUDGE_RUBRIC.endswith("say what you could not verify.")


def test_the_rubric_draws_the_line_between_the_header_and_the_texts() -> None:
    """Header facts ground claims about which provisions changed; only the two texts ground
    claims about what the words say. Without that boundary, showing the judge the header would
    let it agree with the pipeline instead of with the corpus, which is the hazard this module
    has always named; with it, a sentence that reports a coordinate from the header and declines
    to describe it is faithful, which is the case the judge most needs stated."""
    flat = " ".join(JUDGE_RUBRIC.split())
    assert "PIPELINE HEADER" in flat
    assert "Treat it as true." in flat
    assert "It grounds a claim about which provisions changed." in flat
    assert "It grounds no claim about what the words say" in flat
    assert "reports a coordinate from the header and declines to describe it is faithful" in flat


def test_the_rubric_names_each_class_the_judge_was_measured_missing() -> None:
    """Five lenient misses on 2026-08-08, in three classes, all now spelled out.

    The judge marked faithful an entry claiming two texts agree past a truncation marker, an
    entry claiming annex entries had been reordered when walking both tables shows they were
    not, and three entries restating a narrow textual change as a broad legal conclusion. Each
    of the three is asserted here, so removing one is a failing test rather than a quiet
    loosening of the instrument the faithfulness rate is measured with.
    """
    assert "describes content beyond a truncation marker" in JUDGE_RUBRIC
    assert "reordered, renumbered, added or counted a certain way" in JUDGE_RUBRIC
    assert "says what the change legally accomplishes rather than what the words changed" in (
        JUDGE_RUBRIC
    )
    assert "Take the sentences one at a time" in JUDGE_RUBRIC


def test_the_rubric_says_the_context_block_counts_as_evidence() -> None:
    """The judge rules on the evidence the writer had, so a sentence resting only on the
    surrounding provision is faithful. The alternative reading is defensible and this project
    cannot hold both: the 2026-08-08 cap fix already chose this one for the two main texts."""
    flat = " ".join(JUDGE_RUBRIC.split())
    assert "is not itself the change" in flat
    assert "resting on the SURROUNDING CONTEXT block" in flat
    assert "part of the evidence the writer had" in flat


def test_the_context_block_is_printed_for_the_judge_and_omitted_when_there_is_none() -> None:
    """Closed on 2026-08-08: an explainer shown an enclosing provision the judge never received
    was marked unfaithful for using it."""
    with_context = judge_prompt("before", "after", ("s",), "the enclosing provision")
    assert f"{CONTEXT_LABEL}:\nthe enclosing provision" in with_context
    assert with_context.index(CONTEXT_LABEL) > with_context.index("AFTER:")
    assert with_context.index(CONTEXT_LABEL) < with_context.index("SENTENCES:")
    assert "SURROUNDING CONTEXT" not in judge_prompt("before", "after", ("s",))


def test_the_key_changes_with_the_judge_the_prompt_the_schema_and_the_rubric() -> None:
    base = judgement_key("a", "prompt")
    assert base != judgement_key("b", "prompt")
    assert base != judgement_key("a", "other")
    assert base != judgement_key("a", "prompt", 2)
    assert base != judgement_key("a", "prompt", rubric_sha="abc")
    assert judgement_key("a", "prompt", rubric_sha="abc") != judgement_key(
        "a", "prompt", rubric_sha="def"
    )


def test_a_judgement_recorded_before_the_rubric_entered_the_key_still_derives_its_own_name() -> (
    None
):
    """The empty `rubric_sha` reproduces the pre-2026-08-08 payload byte for byte, which is what
    lets the twenty judgements recorded that day keep loading: they are the labelled set a new
    judge is scored against, so they must stay readable after the key changed under them."""
    assert judgement_key("a", "prompt", rubric_sha="") == judgement_key("a", "prompt")
    assert hashlib.sha256(JUDGE_RUBRIC.encode("utf-8")).hexdigest() == RUBRIC_SHA


def test_a_cassette_that_does_not_hash_to_its_own_name_is_refused(tmp_path: Path) -> None:
    """`CassetteCorrupt`, the same exception the explain stage raises, from the same check.

    Both stores are `JsonCassetteStore`, so this is the shared read path and the shared
    exception, named after the condition it reports.
    """
    store = JudgeCassetteStore(tmp_path)
    cassette = JudgeCassette(
        judge_model="m",
        key=judgement_key("m", "the exchange as recorded"),
        synthetic=True,
        recorded_with="TestModel",
        prompt="the exchange as recorded",
        output=Verdict(faithful=True),
    )
    path = store.save(cassette)
    path.write_text(path.read_text(encoding="utf-8").replace("as recorded", "as edited"), "utf-8")
    with pytest.raises(CassetteCorrupt, match="does not hash to its own name"):
        store.load("m", cassette.key)


def test_replay_reads_disk_and_reports_a_triple_nobody_judged(tmp_path: Path) -> None:
    store = JudgeCassetteStore(tmp_path)
    judged, unjudged = _triple(1), _triple(2)
    store.save(
        JudgeCassette(
            judge_model="m",
            key=judgement_key("m", prompt_for(judged), rubric_sha=RUBRIC_SHA),
            synthetic=False,
            recorded_with="m",
            prompt=prompt_for(judged),
            rubric_sha=RUBRIC_SHA,
            output=Verdict(faithful=True),
        )
    )
    report = replay((judged, unjudged), judge_model="m", store=store)
    assert (report.sampled, report.judged, report.faithful) == (2, 1, 1)
    assert report.rate == 1.0
    assert report.human_review == "pending"


def test_a_stub_judgement_never_becomes_a_published_rate() -> None:
    """The honesty switch: synthetic verdicts are counted and the rate is withheld."""
    synthetic = FaithfulnessReport(judge_model="m", sampled=2, judged=2, faithful=2, synthetic=2)
    assert synthetic.publishable is False
    assert synthetic.rate is None
    real = synthetic.model_copy(update={"synthetic": 0})
    assert real.publishable is True
    assert real.rate == 1.0


def test_the_committed_judgements_are_a_full_sample_by_the_default_judge() -> None:
    """CI replays these; a set nobody recorded would make the published section vanish quietly."""
    assert judge_model({}) == "openrouter:openai/gpt-5.6-sol"
    directory = JUDGE_CASSETTE_DIR / "openrouter_openai_gpt-5.6-sol"
    committed = sorted(directory.glob("*.json"))
    assert len(committed) == SAMPLE_SIZE
    store = JudgeCassetteStore(JUDGE_CASSETTE_DIR)
    for path in committed:
        # `load` re-derives the key from the file's own contents, so this also proves every
        # committed judgement is the exchange its name claims to be.
        found = store.load(judge_model({}), path.stem)
        assert found is not None


def test_every_committed_judgement_ruled_on_a_text_an_explanation_was_written_from() -> None:
    """The two committed artifact sets must describe the same evidence, exactly.

    A judgement whose BEFORE, AFTER or context text is merely a *prefix* of what the explainer
    read reads as a judgement of the explanation and is really a judgement of how long the
    provision was. Hence equality against a block some committed explain prompt actually
    contains, rather than containment: a prefix satisfies a containment check happily, which is
    how such a defect reaches a published rate with nothing complaining.

    The surrounding-context block is covered the same way and for the same reason. It is empty
    across this corpus today, so the check is a guard rather than a measurement: the day a
    prompt carries one, a judge shown a shorter version of it is the 2026-08-08 cap defect
    again, one block along.

    The pipeline header entered the evidence base on 2026-08-09 and is covered by the same
    equality: a judge shown a paraphrase of the header the writer read is ruling on different
    evidence, and both look right in isolation. A committed judgement with no header block
    predates the change and skips the check, exactly as an absent side does.
    """
    headers: set[str] = set()
    blocks: set[str] = set()
    for path in sorted((SUBSET_CASSETTE_DIR / model_slug(DEFAULT_MODEL)).glob("*.json")):
        user = Cassette.model_validate_json(path.read_text(encoding="utf-8")).user
        headers.add(user.split("\n\nOFFERED CITATION KEYS", 1)[0])
        for pattern in (_EXPLAIN_TEXT, _EXPLAIN_CONTEXT):
            blocks.update(match.group(2) for match in pattern.finditer(user))
    assert blocks, "no committed explain prompts to check the judgements against"

    stale = "re-record the judge set: -m 'record and live' -k judgements"
    directory = JUDGE_CASSETTE_DIR / model_slug(judge_model({}))
    for path in sorted(directory.glob("*.json")):
        prompt = JudgeCassette.model_validate_json(path.read_text(encoding="utf-8")).prompt
        assert "(truncated," not in prompt, (
            f"{path.name} carries a cap the judge applied itself, which is the one thing it may "
            f"not do: {stale}"
        )
        for pattern, evidence in (
            (_JUDGE_HEADER, headers),
            (_JUDGE_BEFORE, blocks),
            (_JUDGE_AFTER, blocks),
            (_JUDGE_CONTEXT, blocks),
        ):
            found = pattern.search(prompt)
            if found is None:
                continue  # an absent side is named rather than quoted; header and context omitted
            assert found.group(1) in evidence, (
                f"{path.name} ruled on evidence no committed explanation was written from; {stale}"
            )


def test_the_committed_judgements_say_what_recorded_them() -> None:
    """The honesty switch, asserted the other way round now that these are real.

    A rate is published only because these say `synthetic: false`; one that quietly went back to
    stub output would publish a number nobody measured, which is the single failure the layered
    report exists to prevent.
    """
    store = JudgeCassetteStore(JUDGE_CASSETTE_DIR)
    directory = JUDGE_CASSETTE_DIR / model_slug(judge_model({}))
    for path in sorted(directory.glob("*.json")):
        found = store.load(judge_model({}), path.stem)
        assert found is not None and found.synthetic is False
        assert found.recorded_with == found.judge_model == judge_model({})


def test_the_worksheet_is_generated_unticked_and_says_so() -> None:
    triples = (_triple(1), _triple(2, fallback=True))
    report = FaithfulnessReport(judge_model="m", sampled=2, judged=0, synthetic=0)
    sheet = render_worksheet(triples, report, date(2026, 8, 6), "abc1234")

    assert sheet.count("- [ ] Faithful") == 2
    assert "- [x]" not in sheet
    assert "nothing in emendrix ticks a box on its own behalf" in sheet
    assert "no judgement recorded" in sheet
    assert "carries a gate-written quotation" in sheet
    assert "Not legal advice" in sheet
    assert worksheet_path(date(2026, 8, 6), Path("reports")).name == (
        "faithfulness-review-2026-08-06.md"
    )


def test_the_worksheet_quotes_the_context_block_only_when_the_prompt_carried_one() -> None:
    """The reviewer has to read what the model read, under the heading the judge sees, or the
    two checks are answering different questions about the same sentences."""
    plain = _triple(1)
    with_context = _triple(2).model_copy(update={"context": "the enclosing house rules"})
    report = FaithfulnessReport(judge_model="m", sampled=2)
    sheet = render_worksheet((plain, with_context), report, date(2026, 8, 8), "abc1234")

    assert f"**{CONTEXT_LABEL}**" in sheet
    assert "the enclosing house rules" in sheet
    assert sheet.count(CONTEXT_LABEL) == 1, "a change with no enclosing provision shows no block"


def test_the_worksheet_quotes_the_header_first_and_only_when_the_triple_carries_one() -> None:
    """The reviewer reads the evidence in the order the writer saw it, under the heading the
    judge sees, or the two checks are answering different questions about the same sentences.
    A triple recorded before the header entered the evidence base shows no block."""
    bare = _triple(1)
    with_header = _triple(2).model_copy(
        update={"header": "PROVISION: Art. 2 (an obviously synthetic header)"}
    )
    report = FaithfulnessReport(judge_model="m", sampled=2)
    sheet = render_worksheet((bare, with_header), report, date(2026, 8, 9), "abc1234")

    assert sheet.count(f"**{HEADER_LABEL}**") == 1
    assert "PROVISION: Art. 2 (an obviously synthetic header)" in sheet
    second_entry = sheet.index("## 2.")
    assert (
        second_entry < sheet.index(f"**{HEADER_LABEL}**") < sheet.index("**Before**", second_entry)
    )


def test_the_reviewer_and_the_judge_are_asked_the_same_question() -> None:
    """One evidence base, one question. The worksheet's instruction carries the rubric's
    wording, boundary included, so a tick and a verdict disagree about the answer only, never
    about what was asked."""
    report = FaithfulnessReport(judge_model="m", sampled=1)
    sheet = render_worksheet((_triple(1),), report, date(2026, 8, 9), "abc1234")

    assert "follows from the evidence the writer was given" in sheet
    assert "It grounds no claim about what the words say" in sheet
    assert "reports a coordinate from the header and declines to describe it is faithful" in sheet
    assert "the texts as given" not in sheet


def test_a_reviewed_worksheet_is_never_overwritten_by_a_later_run(tmp_path: Path) -> None:
    """The sheet is named by the run date, so a second run on review day would overwrite it.

    A person reading two texts per entry is the only independent evidence the faithfulness row
    has, and it is unrecoverable except from git. A generated sheet never outranks a ticked one.
    """
    report = FaithfulnessReport(judge_model="m", sampled=1)
    first = write_worksheet(
        (_triple(1),), report, run_date=date(2026, 8, 6), revision="abc1234", directory=tmp_path
    )
    reviewed = first.read_text(encoding="utf-8").replace("- [ ] Faithful", "- [x] Faithful", 1)
    first.write_text(reviewed, encoding="utf-8")
    assert worksheet_is_reviewed(first) is True

    again = write_worksheet(
        (_triple(9), _triple(8)),
        report,
        run_date=date(2026, 8, 6),
        revision="deadbee",
        directory=tmp_path,
    )

    assert again == first
    assert again.read_text(encoding="utf-8") == reviewed


def test_an_unticked_worksheet_is_still_regenerated(tmp_path: Path) -> None:
    """The guard is a tick, not the file's existence: an untouched sheet must stay current."""
    report = FaithfulnessReport(judge_model="m", sampled=1)
    path = write_worksheet(
        (_triple(1),), report, run_date=date(2026, 8, 6), revision="abc1234", directory=tmp_path
    )
    assert worksheet_is_reviewed(path) is False

    write_worksheet(
        (_triple(2),), report, run_date=date(2026, 8, 6), revision="deadbee", directory=tmp_path
    )

    assert "sentence 2" in path.read_text(encoding="utf-8")


def test_a_worksheet_nobody_has_written_yet_is_not_reviewed(tmp_path: Path) -> None:
    assert worksheet_is_reviewed(tmp_path / "faithfulness-review-2026-08-06.md") is False
