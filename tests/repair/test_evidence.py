"""What the evidence repair re-derives, what it pays to ask again, and what it never moves.

The repair reads the corpus, which is what makes it different from every other repair here, so
the first test is the one the rest rests on: an entry the shipped pipeline wrote today re-derives
to itself, change for change, and a pass over it has nothing to say and asks nothing. Everything
after it is one defect put back into that entry and the answer the repair gives for it.

Every test runs against the pinned fixture set and a committed cassette or a stub. None calls a
provider, none touches the network and none records anything.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
from repaired_repo import (
    PHANTOM,
    STALE,
    copied,
    log,
    poisoned_repo,
    poisoned_target,
    porcelain,
    stale_evidence_repo,
    stale_target,
    with_run_on,
)
from typer.testing import CliRunner

import stub_engine
from emendrix.cli import app
from emendrix.eu.links import render_citation
from emendrix.explain import DEFAULT_MODEL, CassetteMode, ExplainEngine, ExplainSettings
from emendrix.output import OutputRepo, digest_of, recorded_digests
from emendrix.output.provenance import keys_of
from emendrix.repair import RepairResult, RepairTarget, read_targets
from emendrix.repair.evidence import KIND
from emendrix.repair.reask import repair
from emendrix.repair.rederive import Rederived, Trees, read
from emendrix.session import adapter_for
from eu_pins import FIXTURE_DIR, OBSERVED_ON
from run_pins import RUN_CASSETTE_DIR

runner = CliRunner()
WATCHLIST = Path(__file__).resolve().parents[2] / "watchlist.example.toml"


@pytest.fixture(scope="module")
def stale(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """The committed repository with the three defects a re-derivation has to tell apart."""
    return stale_evidence_repo(changelog_repo, tmp_path_factory.mktemp("stale") / "repo")


def rederived(target: RepairTarget) -> Rederived:
    """One entry held against today's parse of the pinned fixtures, offline."""
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        found, note = read(target, Trees(adapter))
    assert found is not None, note
    return found


def replaying(cassettes: Path = RUN_CASSETTE_DIR) -> ExplainEngine:
    """The real engine in replay: no API key is read and no provider client is constructed."""
    return ExplainEngine(ExplainSettings(cassette_dir=cassettes, cassette_mode=CassetteMode.REPLAY))


def repaired(target: RepairTarget, engine: ExplainEngine) -> RepairResult:
    """One entry rebuilt from today's parse, at the async boundary the command owns."""
    return asyncio.run(repair(rederived(target), target, engine, render=render_citation))


def run(repo: Path, *extra: str) -> str:
    """`emendrix repair evidence` through the shipped command line, over the fixture set."""
    result = runner.invoke(
        app,
        [
            "repair",
            "evidence",
            "--watchlist",
            str(WATCHLIST),
            "--output-repo",
            str(repo),
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--repaired-on",
            OBSERVED_ON.isoformat(),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_an_entry_written_today_re_derives_to_itself_and_costs_nothing(
    changelog_repo: Path,
) -> None:
    """The baseline the whole verb rests on, and the one that would catch it drifting.

    Every change of an entry the shipped pipeline has just written still reads as the evidence
    it was written about, so a pass over it asks nothing, writes nothing and prices nothing.
    If a re-derivation stopped reproducing the delta the loop emits, this is what would say so.
    """
    target = read_targets(changelog_repo)[0]
    plan = rederived(target).plan
    assert len(plan.carried) == len(target.entry.changes)
    assert (plan.reasked, plan.added, plan.withdrawn, plan.restored) == ((), (), (), ())
    assert not plan.moves


def test_a_unit_that_has_always_carried_no_text_moves_nothing(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """A change nothing was ever asked about is restated identically, so it is not a correction.

    Its evidence is a value of its own and it reads as matching, which keeps every entry holding
    one out of a pass that has nothing to do to it. Without that, an entry would be rebuilt for
    the constant it already carries.
    """
    target = poisoned_target(poisoned_repo(changelog_repo, tmp_path / "textless"))
    plan = rederived(target).plan
    assert plan.restated and not plan.emptied
    assert not plan.moves


def test_a_change_whose_evidence_moved_is_asked_again_and_its_siblings_keep_their_bytes(
    stale: Path, changelog_repo: Path
) -> None:
    """The corrected text is what the model is shown, and the answer lands on that change.

    Replaying the exchange the pipeline recorded over the corrected text reproduces the prose
    the entry was published with, which is a stronger check than "some sentences appeared": the
    prompt was rebuilt from today's parse and hashed to the key that recording was made under.
    """
    target = stale_target(stale)
    result = repaired(target, replaying())
    assert result.entry is not None
    assert (result.addressed, result.repaired, result.remaining) == (2, 2, 0)

    was = read_targets(changelog_repo)[0].entry
    now = result.entry.changes[STALE]
    assert now.change.after == was.changes[STALE].change.after
    assert now.sentences == was.changes[STALE].sentences
    assert now.outcome == was.changes[STALE].outcome
    untouched = [item for item in result.entry.changes if item.change.location != PHANTOM]
    for index, item in enumerate(untouched[STALE + 1 :], start=STALE + 1):
        assert item.model_dump_json() == was.changes[index].model_dump_json(), index


def test_a_change_absent_from_todays_delta_is_withdrawn_and_counted(stale: Path) -> None:
    """A unit today's parse finds no change for leaves the entry, prose and all.

    It is counted apart from the changes asked about, because a withdrawal answers a different
    question from a correction: nothing was re-explained and nothing was paid for.
    """
    target = stale_target(stale)
    found = rederived(target)
    assert found.plan.withdrawn == (PHANTOM.canonical,)
    assert PHANTOM.canonical in {item.change.location.canonical for item in target.entry.changes}

    result = repaired(target, replaying())
    assert result.entry is not None
    assert PHANTOM.canonical not in {
        item.change.location.canonical for item in result.entry.changes
    }
    assert f"{PHANTOM.canonical}: withdrawn" in result.detail


def test_a_change_only_todays_delta_holds_is_added_and_counted_apart(stale: Path) -> None:
    """A change the entry never published is asked about, and never as a re-ask.

    The two counts are separate because they answer different questions: one says how much
    prose was written about evidence that has since moved, the other how much the entry never
    had at all.
    """
    target = stale_target(stale)
    found = rederived(target)
    assert len(found.plan.added) == 1 and len(found.plan.reasked) == 1
    added = found.delta.changes[found.plan.added[0]]
    assert added.location.canonical not in {
        item.change.location.canonical for item in target.entry.changes
    }

    result = repaired(target, replaying())
    assert result.entry is not None
    now = [item for item in result.entry.changes if item.change.location == added.location]
    assert len(now) == 1 and now[0].sentences


def test_a_change_that_fails_again_keeps_its_sentence_and_the_text_it_was_written_about(
    stale: Path,
) -> None:
    """The rule `explanations` already has, and the half this repair adds to it.

    A failure is left exactly as it was found, which here means the stored text stays with the
    prose: correcting one without the other would leave a reader sentences about one text
    beside another, and would leave the next pass unable to see the change is still stale.
    """
    target = stale_target(stale)
    result = repaired(target, stub_engine.engine(stub_engine.refusing()))
    assert result.entry is not None
    assert (result.addressed, result.repaired, result.remaining) == (2, 0, 2)
    assert result.entry.changes[STALE].model_dump_json() == (
        target.entry.changes[STALE].model_dump_json()
    )
    assert all("left as it was" in line for line in result.detail if line.startswith("AR 1:"))


def test_a_stored_text_a_digest_proves_is_stale_is_corrected_without_a_call(
    changelog_repo: Path,
) -> None:
    """The cheap half of the same question, and the reason the digest was worth recording.

    Where an entry's own record says the sentences were written about the text today's parser
    produces, a stored text that has drifted from it is a stale document rather than a stale
    explanation. It is corrected, it is counted apart, and nothing is asked or paid for.
    """
    target = with_run_on(read_targets(changelog_repo)[0])
    plan = rederived(target).plan
    assert plan.restored == (STALE,)
    assert not plan.reasked and not plan.added and not plan.withdrawn
    assert plan.moves

    result = repaired(target, replaying(Path("nothing-is-replayed-here")))
    assert result.entry is not None
    assert (result.addressed, result.repaired) == (0, 0)
    was = read_targets(changelog_repo)[0].entry
    assert result.entry.changes[STALE].change.after == was.changes[STALE].change.after
    assert result.entry.changes[STALE].sentences == was.changes[STALE].sentences


def test_the_act_the_versions_and_the_file_do_not_move(stale: Path, tmp_path: Path) -> None:
    """A permalink and a feed id are built from these, so a repair that moved one is a bug."""
    repository = copied(stale, tmp_path / "permalink")
    tracked = _tracked(repository)
    target = stale_target(repository)

    run(repository, "--cassettes", "replay")

    assert _tracked(repository) == tracked
    entry = OutputRepo.open(repository).entry_for(target.entry.act, target.entry.to_version)
    assert entry is not None
    assert (entry.act, entry.from_version, entry.to_version) == (
        target.entry.act,
        target.entry.from_version,
        target.entry.to_version,
    )
    assert entry.detected_on == target.entry.detected_on
    assert entry.explain == target.entry.explain


def test_a_change_asked_again_records_what_it_was_shown_and_its_siblings_do_not(
    stale: Path,
) -> None:
    """A re-ask is a call this pass watched, so its digest is a fact rather than a derivation.

    Every change of the published corpus carries no provenance and keeps none: this pass
    watched no call about them, and a digest derived from their stored text would assert one.
    """
    target = stale_target(stale)
    assert not target.entry.evidence
    result = repaired(target, replaying())
    assert result.entry is not None
    keys = keys_of(item.change for item in result.entry.changes)
    recorded = recorded_digests(result.entry.evidence)
    asked = {keys[index] for index, item in enumerate(result.entry.changes) if item.sentences}
    assert set(recorded) < asked
    for key, digest in recorded.items():
        assert digest == digest_of(result.entry.changes[keys.index(key)].change)


def test_a_dry_run_builds_no_engine_reads_no_key_and_writes_nothing(
    stale: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mode's whole promise: it re-parses the corpus and prices the work with no key at all."""
    for variable in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    repository = copied(stale, tmp_path / "dry")
    before = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    revisions = log(repository)

    output = run(repository, "--dry-run")
    assert "1 re-asked · 1 added · 1 withdrawn" in output
    assert "prompt characters" in output
    assert DEFAULT_MODEL in output
    assert "floor" in output
    assert "nothing written, nothing asked, no engine built" in output
    assert "could not be re-derived" in output

    after = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    assert after == before
    assert log(repository) == revisions
    assert porcelain(repository) == ""


def test_a_limited_pass_never_starts_an_entry_it_cannot_pay_for(
    stale: Path, tmp_path: Path
) -> None:
    """`--limit` counts changes, and half a corrected entry is worse than none of one.

    Writing today's text under a change nobody re-explained would leave prose about one text
    beside another and hide the staleness from the next pass, so a budget that cannot cover an
    entry stops the pass rather than splitting it.
    """
    repository = copied(stale, tmp_path / "limited")
    revisions = log(repository)
    output = run(repository, "--limit", "1", "--cassettes", "replay")
    assert "stopped before" in output
    assert log(repository) == revisions
    assert porcelain(repository) == ""


def test_a_repaired_entry_records_the_pass_and_that_the_coordinate_check_ran(
    stale: Path, tmp_path: Path
) -> None:
    """This repair holds both trees, so the gate's coordinate check runs and the record says so.

    Every other repair records `coordinates_checked: false` because it works from a payload and
    has no trees to compute the support sets from. An unrun check may not read as a passed one,
    and a check that did run may not read as unrun either.
    """
    repository = copied(stale, tmp_path / "recorded")
    target = stale_target(repository)
    revisions = log(repository)

    run(repository, "--cassettes", "replay")
    assert len(log(repository)) == len(revisions) + 1
    assert porcelain(repository) == ""

    entry = OutputRepo.open(repository).entry_for(target.entry.act, target.entry.to_version)
    assert entry is not None
    record = entry.repairs[-1]
    assert record.kind == KIND
    assert record.coordinates_checked
    assert (record.addressed, record.repaired, record.remaining) == (2, 2, 0)
    assert record.repaired_on == OBSERVED_ON
    assert _subject(repository).startswith(
        f"{entry.act.key}: {entry.to_version} evidence repaired (2 of 2 changes)"
    )


def test_a_second_pass_over_the_same_repository_is_a_no_op(stale: Path, tmp_path: Path) -> None:
    """Re-runnable: with every change reading as its own evidence, nothing is written again."""
    repository = copied(stale, tmp_path / "twice")
    run(repository, "--cassettes", "replay")
    revisions = log(repository)

    output = run(repository, "--cassettes", "replay")
    assert log(repository) == revisions
    assert porcelain(repository) == ""
    assert "0 changes repaired" in output


def test_a_transition_todays_parse_cannot_produce_is_counted_and_left_alone(
    stale: Path, tmp_path: Path
) -> None:
    """A version the fixtures do not hold is a coverage gap, named, and never an exception."""
    repository = copied(stale, tmp_path / "underivable")
    neighbour = min(read_targets(repository), key=lambda target: target.path)
    before = (repository / neighbour.path).read_bytes()

    output = run(repository, "--cassettes", "replay")
    assert "1 transitions could not be re-derived today" in output
    assert str(neighbour.entry.from_version) in output
    assert (repository / neighbour.path).read_bytes() == before


def _tracked(repository: Path) -> list[str]:
    """Every file the repository holds, so an added, removed or renamed one is a failure."""
    return sorted(_git(repository, "ls-files").split())


def _subject(repository: Path) -> str:
    return _git(repository, "log", "--format=%s", "-1").strip()


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=repository, capture_output=True, text=True, check=True
    ).stdout
