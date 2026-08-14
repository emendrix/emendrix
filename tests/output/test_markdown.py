"""The Markdown changelog: a committed golden file, and the properties its format forces.

The golden is the MDR postponement rendered by the *whole shipped command* — pinned fixtures
for the documents, committed cassettes for the model, an output repository in a temp
directory, so it changes only when the product's primary artifact changes, which is exactly
when a reviewer should be made to look.

**What the golden is not evidence of.** Its sentences are a real model's, so the file finally
reads like the product, and that makes it tempting to treat as evidence of a good explanation. It
is not. Nothing here asserts anything about explanation quality, which has no free ground truth
and is measured, sampled and published by the eval harness instead. What this file asserts is the
*format*: the disclaimer, the citation links, visible truncation, and that a sentence the gate
wrote rather than the model is marked as one.

The gate-written sentence is asserted against a synthetic entry rather than the golden, because
the recorded model passes the gate on all nine changes and a format rule that only holds while a
recording happens to fail is not a rule the format enforces.

Everything not requiring real law is asserted against the toy corpus (`toy_entries.py`).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from toy_entries import disputed_entry, explained_entry, no_evidence_entry, toy_entry
from typer.testing import CliRunner

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.core import (
    ActId,
    Change,
    ChangeType,
    ProvisionLocation,
    ProvisionRef,
    ProvisionText,
    SignalObservation,
    SignalSet,
    SignalStatus,
    VersionId,
)
from emendrix.output import ChangelogEntry, render_entry, render_standalone
from emendrix.output.markdown import (
    QUOTE_CHAR_CAP,
    TITLE_CAP,
    _detail,
    dispute_text,
    short_title,
)
from eu_pins import FIXTURE_DIR, OBSERVED_ON
from run_pins import RUN_CASSETTE_DIR, TRANSITION

runner = CliRunner()

AMENDER_ONE = ActId(corpus="toy", key="amender-1")
AMENDER_TWO = ActId(corpus="toy", key="amender-2")
TOY_ACT = ActId(corpus="toy", key="house-rules")

GOLDEN = Path(__file__).resolve().parent / "golden" / "mdr-changelog.md"
"""Reviewed by hand on 2026-08-06 against the worked example, again on 2026-08-08 when the gate
started dropping applicability notes that do not quote the after text, a third time the same
day when the explainer was re-recorded against `openrouter:anthropic/claude-sonnet-5`, and a
fourth on 2026-08-09 when the sets were re-recorded at the 40 000-character prompt cap.

That fourth reading: no prompt of this transition is truncated any more, and the sameness
claims moved with the evidence. Art. 17's closing "all other text is unchanged" sentence is
replaced by two concrete per-paragraph date sentences; Annex IX's hedge scoped to "the portions
shown here" is gone with the marker it hedged against, and that entry now describes only the
changed deadline; Art. 120 still closes with "all other dates and wording in the article remain
unchanged", which is now a claim about an article shown whole. The recording still ships no
applicability note on any of the nine changes, and the file's `applies from` lines, which come
from the deterministic clock, are unaffected.

A fifth reading on 2026-08-09, when the detail line began naming the act that amended each
provision. The whole diff is one "amended by 32020R0561" part appended to nine detail lines,
one per change, and nine lines are all that differ. That identifier is the MDR postponement, and
it is printed as the corpus published it because the renderer holds no corpus knowledge. It
comes from the corpus's own modification annotations rather than from any prose. Nothing else
moved: the sentences are the same recording replayed, and the quotes, the counts and both
clocks are untouched.

A sixth reading on 2026-08-12, over the largest diff this file has ever taken: 165 lines became
303. Two independent things moved and neither is a rendering change. Stored text now carries a
separator wherever the markup opened a block, so every quoted provision breaks into the lines
the source document had instead of running "Article 113PenaltiesThe Member States" together on
one; the counts, the omitted-character totals and the truncation markers are computed over the
same provisions and the same cap. And the nine explanations are a new recording against the
same pinned model, because a prompt carrying the repaired text is a different prompt. The prose
is not better or worse than the recording it replaces, and nothing here reads it as either. The
two `applies from: unknown` lines now say what could not be read rather than what binds, which
is the deterministic clock's own wording and not the model's. The recording still ships no
applicability note on any of the nine changes, and all nine still pass the gate on the first
answer.

To regenerate: run the command in `changelog()` against a scratch directory and copy the
written file over this one, then *read the diff*, because that is the review."""


@pytest.fixture(autouse=True)
def _replay_from_the_run_cassettes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", str(RUN_CASSETTE_DIR))
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "replay")
    monkeypatch.delenv("EMENDRIX_OUTPUT_REPO", raising=False)
    for variable in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(variable, raising=False)


def changelog(tmp_path: Path) -> str:
    """The MDR transition through `emendrix explain`, as committed `CHANGELOG.md` bytes."""
    result = runner.invoke(
        app,
        [
            "explain",
            TRANSITION.celex,
            TRANSITION.from_version,
            TRANSITION.to_version,
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--observed-on",
            OBSERVED_ON.isoformat(),
            "--json-out",
            str(tmp_path / "report.json"),
            "--output-repo",
            str(tmp_path / "changelog"),
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    written = tmp_path / "changelog" / "eu" / TRANSITION.celex / "CHANGELOG.md"
    return written.read_text(encoding="utf-8")


# ------------------------------------------------------------------ the golden


def test_the_committed_golden_is_what_the_command_writes(tmp_path: Path) -> None:
    """Byte-equality with the reviewed file. A diff here is a product change, not a flake."""
    assert changelog(tmp_path) == GOLDEN.read_text(encoding="utf-8")


def test_two_runs_write_the_same_bytes(tmp_path: Path) -> None:
    """Changelogs are reviewed as git diffs, so a re-run may not move a single byte."""
    assert changelog(tmp_path / "one") == changelog(tmp_path / "two")


# ------------------------------------------------------------------ what the format forces


def test_the_changelog_carries_the_disclaimer(tmp_path: Path) -> None:
    """The disclaimer obligation, on the most user-facing output the project has."""
    written = changelog(tmp_path)
    assert DISCLAIMER.split(":")[0] in written
    assert "> Not legal advice:" in written


def test_every_shipped_sentence_carries_a_link_that_the_adapter_rendered(
    tmp_path: Path,
) -> None:
    """Citations are `Citation` objects by the time they get here; nothing invents a URL."""
    written = changelog(tmp_path)
    assert "](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:" in written
    assert ", v2](" in written, "labels are compacted against the two version tags"
    assert f"`v2` = `{TRANSITION.to_version}`" in written, "and the mapping is stated"


def test_the_golden_is_the_models_prose_and_says_so_by_saying_nothing(tmp_path: Path) -> None:
    """The complement of `test_the_model_and_the_gate_are_told_apart`, on the real artifact.

    All nine changes passed the gate, so the marking must be absent here: a stray "quoted
    verbatim" line would mean the renderer marks provenance it was not given. The marking itself
    is asserted against a synthetic entry, where a fallback can be constructed on purpose rather
    than waited for.
    """
    written = changelog(tmp_path)
    assert "Quoted verbatim by the citation gate" not in written
    assert written.count("**Gate** 0 sentences quoted verbatim") == 1


def test_a_truncated_quote_says_so_and_says_how_much(tmp_path: Path) -> None:
    """A silently cut "verbatim" quote is worse than a long one."""
    written = changelog(tmp_path)
    assert "truncated by emendrix:" in written
    assert "characters omitted" in written


def test_applicability_is_first_class_and_unknown_is_an_answer(tmp_path: Path) -> None:
    written = changelog(tmp_path)
    assert "· applies from: 2021-05-26" in written
    assert "· applies from: unknown (" in written


# ------------------------------------------------------------------ on the toy corpus


def test_the_renderer_runs_on_a_corpus_that_is_not_law() -> None:
    """The output package renders `EmittedDelta`, not EU documents. Proven, not asserted."""
    rendered = render_entry(toy_entry())
    assert "## House Rules of Flat 3B" in rendered
    assert "### `v1` → `v2`" in rendered
    assert "**MODIFIED · Art. 2 — Bins**" in rendered


def test_verbatim_text_reaches_the_page_untouched() -> None:
    """Irregular whitespace and all: normalising it here would be the bug."""
    rendered = render_entry(toy_entry())
    assert "> The bins go out on Tuesday evening,  and the recycling on the first Tuesday." in (
        rendered
    )
    assert "> Kitchen: Bo.   Bathroom: Cy.   Hallway: Ada." in rendered


def test_a_disputed_change_is_rendered_and_says_what_disagreed() -> None:
    """Never silently dropped, never merged away, and the marker names the disagreement."""
    rendered = render_entry(disputed_entry())
    assert "**MODIFIED · Art. 9**" in rendered
    assert "**DISPUTED** — seen by corpus metadata, not by the structural diff" in rendered
    assert "No text on either side" in rendered


def _signalled(signals: SignalSet) -> Change:
    """A minimal MODIFIED change carrying nothing but the verdicts the marker reads."""
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(
            act=TOY_ACT, version=VersionId("v2"), location=ProvisionLocation.parse("AR 9")
        ),
        before=ProvisionText("before"),
        after=ProvisionText("after"),
        signals=signals,
    )


def test_a_source_that_named_no_kind_is_still_counted_among_the_ones_that_looked() -> None:
    """A role code with no label leaves a signal observing with nothing to say about the kind.

    That is a counted coverage gap, not an absence. Dropping the clause would print two sources
    on a change three looked at, and would put this marker out of step with the page's
    (`site_/dispute.py`), which names it. Both renderers read the same verdicts.
    """
    observed = SignalObservation(status=SignalStatus.OBSERVED)
    change = _signalled(
        SignalSet(
            structural_diff=observed.model_copy(update={"change_types": (ChangeType.MODIFIED,)}),
            corpus_metadata=observed,
            instruction_parse=observed.model_copy(update={"change_types": (ChangeType.INSERTED,)}),
        )
    )
    assert dispute_text(change) == (
        "the signals disagree on the kind of change — the structural diff says MODIFIED, "
        "corpus metadata names no kind, the instruction parse says INSERTED"
    )


def test_an_unavailable_source_is_named_nowhere_in_the_marker() -> None:
    """A source handed nothing has not dissented, so it is neither observing nor missing."""
    change = _signalled(
        SignalSet(
            structural_diff=SignalObservation(
                status=SignalStatus.OBSERVED, change_types=(ChangeType.MODIFIED,)
            ),
            corpus_metadata=SignalObservation(status=SignalStatus.UNAVAILABLE),
            instruction_parse=SignalObservation(status=SignalStatus.ABSENT),
        )
    )
    rendered = dispute_text(change)
    assert rendered == "seen by the structural diff, not by the instruction parse"
    assert "corpus metadata" not in rendered


def test_a_textless_change_is_still_a_change() -> None:
    entry = disputed_entry()
    assert entry.counts.disputed == 1
    assert any(emitted.change.before is None for emitted in entry.changes)


def test_the_model_and_the_gate_are_told_apart() -> None:
    rendered = render_entry(explained_entry())
    written_by_the_gate = rendered.count("Quoted verbatim by the citation gate")
    assert written_by_the_gate == len(explained_entry().changes) - 1
    assert "Something about this provision changed." in rendered


def test_a_change_the_cap_left_no_evidence_for_says_so_in_English() -> None:
    """The reason is prose a reader meets, so it is asserted as the sentence they read."""
    rendered = render_entry(no_evidence_entry())
    assert (
        "*No explanation shipped — the difference between the two versions lies beyond the "
        "characters this stage can show, so no explanation was requested.*"
    ) in rendered
    assert "> The bins go out on Tuesday evening,  and the recycling on the first Tuesday." in (
        rendered
    ), "the entry still ships both verbatim texts; only the sentences are missing"


def test_a_standalone_entry_carries_the_disclaimer_because_it_has_no_file_around_it() -> None:
    assert render_standalone(toy_entry()).rstrip().endswith("engineering assistance only.")


def test_rendering_is_a_pure_function_of_the_entry() -> None:
    entry = toy_entry()
    assert render_entry(entry) == render_entry(entry.model_copy(deep=True))


def test_a_long_title_is_cut_visibly() -> None:
    assert short_title("x" * 10) == "x" * 10
    long = " ".join(["word"] * 60)
    assert short_title(long).endswith(" […]")
    assert len(short_title(long)) <= TITLE_CAP + 4


def test_the_quote_cap_is_a_documented_number() -> None:
    """It is a product decision, asserted rather than left to drift."""
    assert QUOTE_CHAR_CAP == 1500
    long_text = "x" * (QUOTE_CHAR_CAP + 25)
    entry = _with_after_text(toy_entry(), long_text)
    rendered = render_entry(entry)
    assert "truncated by emendrix: 25 characters omitted" in rendered


# ------------------------------------------------------------------ the detail line


def amended(
    *acts: ActId,
    changed_within: tuple[ProvisionLocation, ...] = (),
    dates_added: tuple[date, ...] = (),
) -> Change:
    """A minimal MODIFIED change, with only what the detail line reads set.

    `before` and `after` are both present because a MODIFIED change whose structural-diff
    signal is not ABSENT is required to carry them.
    """
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(
            act=TOY_ACT, version=VersionId("v2"), location=ProvisionLocation.parse("AR 2")
        ),
        before=ProvisionText("before"),
        after=ProvisionText("after"),
        amending_acts=acts,
        changed_within=changed_within,
        dates_added=dates_added,
    )


def test_the_detail_line_names_the_act_that_amended_the_provision() -> None:
    """A reader should not have to open the JSON to learn which act did this."""
    assert _detail(amended(AMENDER_ONE)) == ["", "*amended by* `amender-1`"]


def test_two_amending_acts_are_both_named_in_the_order_they_were_claimed() -> None:
    """Order is the corroborator's, and it is stable, so the rendering may not re-sort it."""
    rendered = _detail(amended(AMENDER_TWO, AMENDER_ONE))
    assert rendered == ["", "*amended by* `amender-2`, `amender-1`"]


def test_the_amender_comes_after_the_coordinates_and_the_dates() -> None:
    """The part is last, so every other detail line reads the same with or without it."""
    change = amended(
        AMENDER_ONE,
        changed_within=(ProvisionLocation.parse("AR 2 PA 1"),),
        dates_added=(date(2021, 5, 26),),
    )
    assert _detail(change) == [
        "",
        "*within* `AR 2 PA 1` · *dates* +2021-05-26 · *amended by* `amender-1`",
    ]


def test_a_change_with_no_amender_renders_exactly_as_it_did_before() -> None:
    """The part is omitted entirely rather than printed empty, and no detail line is invented."""
    assert _detail(amended()) == []


def _with_after_text(entry: ChangelogEntry, text: str) -> ChangelogEntry:
    """The same entry with one change's `after` text replaced: a cap-exercising double."""
    first, *rest = entry.changes
    replaced = first.model_copy(update={"change": first.change.model_copy(update={"after": text})})
    return entry.model_copy(update={"changes": (replaced, *rest)})
