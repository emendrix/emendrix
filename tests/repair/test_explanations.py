"""What the explanation repair asks for, what it refuses to touch, and what it never moves.

The repair rebuilds a prompt out of a committed payload and asks the model again, so the first
test here is the one the whole thing rests on: a prompt rebuilt from the document hashes to the
key of the exchange the pipeline actually recorded. Everything after it is what happens around
that call, and every test runs against a committed cassette or a stub. None calls a provider
and none records anything.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
from repaired_repo import copied, log, porcelain, unexplained_repo, unexplained_target
from typer.testing import CliRunner

import stub_engine
from emendrix.cli import app
from emendrix.eu.links import render_citation
from emendrix.explain import (
    DEFAULT_MODEL,
    MODEL_FAILED,
    CassetteMiss,
    CassetteMode,
    CassetteStore,
    ExplainEngine,
    ExplainSettings,
    build_context,
    build_prompt,
    cassette_key,
)
from emendrix.gate import GateOutcome
from emendrix.output import OutputRepo, digest_of, recorded_digests
from emendrix.output.provenance import keys_of
from emendrix.repair import RepairResult, RepairTarget, read_targets
from emendrix.repair.explanations import KIND, needs, repair, selected
from eu_pins import OBSERVED_ON
from run_pins import RUN_CASSETTE_DIR, TRANSITION

runner = CliRunner()
WATCHLIST = Path(__file__).resolve().parents[2] / "watchlist.example.toml"

FAILED = (0, 1)
"""The two changes the fixture repository leaves the model having answered badly about."""


@pytest.fixture(scope="module")
def unexplained(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """The committed repository with the prose taken off one change of each counted state."""
    return unexplained_repo(changelog_repo, tmp_path_factory.mktemp("unexplained") / "repo")


def replaying(cassettes: Path = RUN_CASSETTE_DIR) -> ExplainEngine:
    """The real engine in replay: no API key is read and no provider client is constructed."""
    return ExplainEngine(ExplainSettings(cassette_dir=cassettes, cassette_mode=CassetteMode.REPLAY))


def repaired(
    target: RepairTarget, engine: ExplainEngine, *, limit: int | None = None
) -> RepairResult:
    """One entry repaired, with the corpus's own citation renderer, at the async boundary."""
    return asyncio.run(repair(target, engine, render=render_citation, limit=limit))


def run(repo: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> str:
    """`emendrix repair explanations` through the shipped command line, replaying cassettes."""
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", str(RUN_CASSETTE_DIR))
    result = runner.invoke(
        app,
        [
            "repair",
            "explanations",
            "--watchlist",
            str(WATCHLIST),
            "--output-repo",
            str(repo),
            "--cassettes",
            "replay",
            "--repaired-on",
            OBSERVED_ON.isoformat(),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_a_prompt_rebuilt_from_a_committed_payload_matches_its_cassette_key(
    changelog_repo: Path,
) -> None:
    """The reconstruction is exact, and this is the test that would catch it drifting.

    A change carries both its verbatim texts, so the context and the prompt are pure functions
    of the committed document. If either grew a dependency the payload cannot supply, the
    rebuilt prompt would hash to a key nothing recorded and the model would be asked a
    different question about the same change.
    """
    held = set(CassetteStore(RUN_CASSETTE_DIR).keys(DEFAULT_MODEL))
    settings = ExplainSettings()
    checked = 0
    for target in read_targets(changelog_repo):
        entry = target.entry
        for item in entry.changes:
            if not item.sentences:
                continue
            change = item.change
            context = build_context(
                change, from_version=entry.from_version, to_version=entry.to_version
            )
            parts = build_prompt(change, context, settings)
            key = cassette_key(DEFAULT_MODEL, parts.system, parts.user)
            assert key in held, change.location.canonical
            checked += 1
    assert checked == TRANSITION.changes


def test_only_a_model_failure_is_selected(unexplained: Path) -> None:
    """Both routes to the same state are selected, and the other three states are not.

    `nothing_to_explain` and `no_evidence_past_cap` are answers about a change rather than
    failures, and `provider_unavailable` leaves the entry unfinished, so the resume path
    completes it without anybody invoking a repair.
    """
    target = unexplained_target(unexplained)
    entry = target.entry
    assert selected(entry) == FAILED
    assert needs(target)
    assert entry.changes[0].unexplained_kind == "model_failed"
    assert entry.changes[1].unexplained_kind == ""
    assert entry.changes[1].unexplained.startswith(MODEL_FAILED)
    assert [item.unexplained_kind for item in entry.changes[2:5]] == [
        "nothing_to_explain",
        "no_evidence_past_cap",
        "provider_unavailable",
    ]


def test_a_repaired_change_gets_prose_and_its_siblings_do_not_move(
    unexplained: Path, changelog_repo: Path
) -> None:
    """The repaired changes carry sentences again; every other change keeps its bytes.

    Replaying the same exchange reproduces the prose the pipeline first wrote, which is a
    stronger check than "some sentences appeared": the splice puts the answer back on the
    change it was asked about, citations and gate outcome included.
    """
    target = unexplained_target(unexplained)
    result = repaired(target, replaying())
    assert result.entry is not None
    assert (result.addressed, result.repaired, result.remaining) == (2, 2, 0)

    was = read_targets(changelog_repo)[0].entry
    for index in FAILED:
        now = result.entry.changes[index]
        assert now.sentences == was.changes[index].sentences
        assert now.applicability_note == was.changes[index].applicability_note
        assert now.outcome == was.changes[index].outcome
        assert not now.unexplained and not now.unexplained_kind
    for index in range(len(FAILED), len(target.entry.changes)):
        assert (
            result.entry.changes[index].model_dump_json()
            == target.entry.changes[index].model_dump_json()
        ), index


def test_a_change_that_fails_again_is_counted_and_left_alone(unexplained: Path) -> None:
    """A repair that repaired nothing writes nothing and leaves the state it found."""
    target = unexplained_target(unexplained)
    result = repaired(target, stub_engine.engine(stub_engine.refusing()))
    assert result.entry is None
    assert (result.addressed, result.repaired, result.remaining) == (2, 0, 2)
    assert all(line.endswith(": still unexplained") for line in result.detail)

    again = unexplained_target(unexplained)
    assert again.entry.to_json() == target.entry.to_json()
    assert again.entry.changes[0].unexplained == MODEL_FAILED
    assert selected(again.entry) == FAILED


def test_the_citation_gate_still_rejects_a_key_that_was_not_offered(unexplained: Path) -> None:
    """A narrower resolver is not a wider gate: an unknown key is still rejected as unknown.

    The answer that cites nothing real is replaced by the gate's own verbatim quotation, which
    is correct by construction and visibly marked, and the invented key reaches no reader.
    """
    target = unexplained_target(unexplained)
    result = repaired(target, stub_engine.engine(stub_engine.citing_nothing_real()), limit=1)
    assert result.entry is not None
    change = result.entry.changes[0]
    assert change.outcome is GateOutcome.FALLBACK
    assert change.sentences and all(sentence.fallback for sentence in change.sentences)
    assert stub_engine.INVENTED_KEY not in result.entry.to_json()


def test_a_limit_counts_changes_rather_than_entries(unexplained: Path) -> None:
    """What caps spend is the number of calls, so one large entry cannot take a whole budget."""
    target = unexplained_target(unexplained)
    result = repaired(target, replaying(), limit=1)
    assert result.entry is not None
    assert (result.addressed, result.repaired) == (1, 1)
    assert selected(result.entry) == (FAILED[1],)


def test_the_explain_and_gate_blocks_of_the_original_run_do_not_move(unexplained: Path) -> None:
    """They record the run that produced the entry, and a repair retracts none of it.

    What this pass did is on the entry as a repair record instead, which is why the two are
    never summed: a lifetime total would answer neither question.
    """
    target = unexplained_target(unexplained)
    result = repaired(target, replaying())
    assert result.entry is not None
    assert result.entry.explain == target.entry.explain
    assert result.entry.gate == target.entry.gate
    assert result.entry.detected_on == target.entry.detected_on


def test_a_change_asked_again_records_what_it_was_shown_and_its_siblings_do_not(
    unexplained: Path,
) -> None:
    """A re-ask is a call this pass watched, so its digest is a fact rather than a derivation.

    The entries this fixture is built from carry a digest for every change already. What the
    test holds is the rule: the two changes asked again carry the digest of the texts the
    prompt was rebuilt from, and every sibling's record is byte-identical to the one it
    arrived with.
    """
    target = unexplained_target(unexplained)
    result = repaired(target, replaying())
    assert result.entry is not None
    before = recorded_digests(target.entry.evidence)
    after = recorded_digests(result.entry.evidence)
    asked = {
        key
        for index, key in enumerate(keys_of(item.change for item in result.entry.changes))
        if index in FAILED
    }
    assert asked <= set(after)
    for index in FAILED:
        change = result.entry.changes[index].change
        key = keys_of(item.change for item in result.entry.changes)[index]
        assert after[key] == digest_of(change)
    assert {key: value for key, value in after.items() if key not in asked} == {
        key: value for key, value in before.items() if key not in asked
    }


def test_an_entry_that_carried_no_digest_gains_one_only_where_a_call_was_made(
    unexplained: Path,
) -> None:
    """Every change published before 2026-09-05 has unknown provenance and keeps it.

    A pass that re-asks about one of them has watched that one call and may say what it showed.
    It has watched none of the others, and inventing a digest for those would assert a fact
    about a call nobody made.
    """
    target = unexplained_target(unexplained)
    older = target.entry.model_copy(update={"evidence": ()})
    result = repaired(RepairTarget(path=target.path, entry=older), replaying())
    assert result.entry is not None
    keys = keys_of(item.change for item in result.entry.changes)
    recorded = recorded_digests(result.entry.evidence)
    assert set(recorded) == {keys[index] for index in FAILED}


def test_a_cassette_miss_is_not_swallowed(unexplained: Path, tmp_path: Path) -> None:
    """An unrecorded prompt is a build fault, never one more change counted as still failed."""
    target = unexplained_target(unexplained)
    with pytest.raises(CassetteMiss):
        repaired(target, replaying(tmp_path / "empty"))


def test_a_dry_run_builds_no_engine_and_writes_nothing(
    unexplained: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mode's whole promise: it prices the work with no key in the environment at all."""
    for variable in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    repository = copied(unexplained, tmp_path / "dry")
    before = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    revisions = log(repository)

    output = run(repository, monkeypatch, "--dry-run")
    assert "2 changes" in output
    assert "prompt characters" in output
    assert DEFAULT_MODEL in output
    assert "floor" in output
    assert "nothing written, nothing asked" in output

    after = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    assert after == before
    assert log(repository) == revisions
    assert porcelain(repository) == ""


def test_a_repaired_entry_records_that_no_coordinate_check_ran(
    unexplained: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repair holds no trees, so the check did not run and the record says so.

    Both halves matter: the entry must not read as though a check passed, and the operator
    must be told in words rather than left to notice a false flag in the JSON.
    """
    repository = copied(unexplained, tmp_path / "recorded")
    target = unexplained_target(repository)
    revisions = log(repository)

    output = run(repository, monkeypatch)
    assert "no coordinate check ran" in output
    assert len(log(repository)) == len(revisions) + 1
    assert porcelain(repository) == ""

    entry = OutputRepo.open(repository).entry_for(target.entry.act, target.entry.to_version)
    assert entry is not None
    record = entry.repairs[-1]
    assert record.kind == KIND
    assert not record.coordinates_checked
    assert (record.addressed, record.repaired, record.remaining) == (2, 2, 0)
    assert record.repaired_on == OBSERVED_ON
    assert _subject(repository).startswith(
        f"{entry.act.key}: {entry.to_version} explanations repaired (2 of 2 changes)"
    )


def test_a_second_repair_of_the_same_entry_is_a_no_op(
    unexplained: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-runnable: with nothing left to ask about, the second pass writes and commits nothing."""
    repository = copied(unexplained, tmp_path / "twice")
    run(repository, monkeypatch)
    revisions = log(repository)

    run(repository, monkeypatch)
    assert log(repository) == revisions
    assert porcelain(repository) == ""
    assert not [target for target in read_targets(repository) if needs(target)]


def test_the_entry_beside_a_repaired_one_keeps_its_bytes(
    unexplained: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pass over a whole repository leaves what it has nothing to say about exactly as it was."""
    repository = copied(unexplained, tmp_path / "neighbour")
    repaired_path = unexplained_target(repository).path
    untouched = [target.path for target in read_targets(repository) if target.path != repaired_path]
    assert untouched
    before = {path: (repository / path).read_bytes() for path in untouched}
    run(repository, monkeypatch)
    assert {path: (repository / path).read_bytes() for path in before} == before


def test_a_repair_with_nowhere_to_write_is_refused_before_anything_is_read(tmp_path: Path) -> None:
    """A missing output repository costs a message and exit 2, before a payload is opened."""
    empty = tmp_path / "watchlist.toml"
    empty.write_text('[[acts]]\ncelex = "32017R0745"\n', encoding="utf-8")
    result = runner.invoke(app, ["repair", "explanations", "--watchlist", str(empty)])
    assert result.exit_code == 2
    assert "--output-repo" in result.output


def test_a_celex_that_is_not_one_is_refused(unexplained: Path) -> None:
    """`--act` is parsed before the repository is walked, as it is for every narrowing flag."""
    result = runner.invoke(
        app,
        [
            "repair",
            "explanations",
            "--watchlist",
            str(WATCHLIST),
            "--output-repo",
            str(unexplained),
            "--act",
            "not-a-celex",
        ],
    )
    assert result.exit_code == 2


def _subject(repository: Path) -> str:
    return subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
