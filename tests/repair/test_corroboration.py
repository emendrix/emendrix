"""What the corroboration repair does to an entry, and what the command does with the result.

The repair recomputes one signal and hands it to the merge; everything else about the entry is
carried over. So the two things worth asserting are that the merge's answer reaches the
committed document, and that nothing the model wrote moved on the way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from repaired_repo import (
    PHANTOM,
    copied,
    corrected,
    log,
    poisoned_repo,
    poisoned_target,
    porcelain,
    restored_unit,
    signal_of,
    units_of,
)
from typer.testing import CliRunner

from emendrix.cli import app
from emendrix.core import Signal
from emendrix.output import OutputRepo
from emendrix.repair import read_targets
from eu_pins import FIXTURE_DIR, OBSERVED_ON

runner = CliRunner()
WATCHLIST = Path(__file__).resolve().parents[2] / "watchlist.example.toml"


@pytest.fixture(scope="module")
def spoiled(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """The committed repository with the third signal's two defects put back into it."""
    return poisoned_repo(changelog_repo, tmp_path_factory.mktemp("spoiled") / "repo")


def run(repo: Path, *extra: str) -> str:
    """`emendrix repair corroboration` through the shipped command line, offline."""
    result = runner.invoke(
        app,
        [
            "repair",
            "corroboration",
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


def test_a_phantom_unit_the_corrected_signal_no_longer_names_is_dropped(spoiled: Path) -> None:
    """A unit only the misreading signal ever saw leaves the entry, and takes its dispute with it.

    It carries no text, so nothing was ever asked about it and nothing is lost by its going:
    what it cost was a unit on a published page that no version of the act has.
    """
    target = poisoned_target(spoiled)
    assert PHANTOM.canonical in units_of(target.entry)
    result = corrected(target)
    assert result.entry is not None
    assert PHANTOM.canonical not in units_of(result.entry)
    assert PHANTOM.canonical not in signal_of(result.entry, Signal.INSTRUCTION_PARSE)
    assert result.entry.counts.disputed < target.entry.counts.disputed
    assert result.detail == (
        f"dropped {PHANTOM.canonical}",
        f"{restored_unit(target)}: disputed flag flipped",
    )


def test_a_unit_that_gains_a_third_confirmation_keeps_its_committed_explanation(
    spoiled: Path,
) -> None:
    """The prose is reused rather than re-asked for, and that is the decided answer.

    The explanation was written under a prompt whose note said the signals disagreed, and that
    note instructed the model not to comment on the disagreement, so the sentences are a
    statement about the two texts and stay true. Re-asking would spend money to churn correct
    prose at a URL somebody may already have quoted.
    """
    target = poisoned_target(spoiled)
    unit = restored_unit(target)
    was = next(item for item in target.entry.changes if item.change.unit.canonical == unit)
    assert was.change.disputed and was.sentences

    result = corrected(target)
    assert result.entry is not None
    now = next(item for item in result.entry.changes if item.change.unit.canonical == unit)
    assert not now.change.disputed
    assert now.sentences == was.sentences
    assert now.outcome == was.outcome


def test_a_dry_run_writes_nothing(spoiled: Path, tmp_path: Path) -> None:
    """The same promise `backfill` makes, over a repository that does need a repair."""
    repository = copied(spoiled, tmp_path / "dry")
    before = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    revisions = log(repository)
    output = run(repository, "--dry-run")
    assert "disputed flags flipped" in output
    assert "dry run: nothing written" in output
    after = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    assert after == before
    assert log(repository) == revisions
    assert porcelain(repository) == ""


def test_the_command_commits_one_entry_and_records_what_it_did(
    spoiled: Path, tmp_path: Path
) -> None:
    """A real pass writes the repaired entry, says so in the subject, and records itself."""
    repository = copied(spoiled, tmp_path / "written")
    target = poisoned_target(repository)
    revisions = log(repository)
    run(repository)
    assert len(log(repository)) == len(revisions) + 1
    assert porcelain(repository) == ""

    entry = OutputRepo.open(repository).entry_for(target.entry.act, target.entry.to_version)
    assert entry is not None
    assert PHANTOM.canonical not in units_of(entry)
    assert [record.kind for record in entry.repairs] == ["corroboration"]
    assert entry.repairs[0].repaired_on == OBSERVED_ON
    assert entry.repairs[0].addressed == len(target.entry.changes)
    assert not entry.repairs[0].coordinates_checked

    subject = _subject(repository)
    assert subject.startswith(f"{entry.act.key}: {entry.to_version} corroboration repaired")


def test_a_second_pass_over_a_repaired_repository_commits_nothing(
    spoiled: Path, tmp_path: Path
) -> None:
    """Re-runnable through the command line too, record and all."""
    repository = copied(spoiled, tmp_path / "again")
    run(repository)
    revisions = log(repository)
    run(repository)
    assert log(repository) == revisions
    assert porcelain(repository) == ""


def test_the_entry_beside_the_repaired_one_keeps_its_bytes(spoiled: Path, tmp_path: Path) -> None:
    """A pass over a whole repository leaves what it has nothing to say about exactly as it was."""
    repository = copied(spoiled, tmp_path / "neighbour")
    repaired = poisoned_target(repository).path
    untouched = [target.path for target in read_targets(repository) if target.path != repaired]
    assert untouched
    before = {path: (repository / path).read_bytes() for path in untouched}
    run(repository)
    assert {path: (repository / path).read_bytes() for path in before} == before


def test_a_repair_with_nowhere_to_write_is_refused_before_anything_is_read(
    tmp_path: Path,
) -> None:
    """A missing output repository is an environment being wrong, and costs a message and exit 2."""
    empty = tmp_path / "watchlist.toml"
    empty.write_text('[[acts]]\ncelex = "32017R0745"\n', encoding="utf-8")
    result = runner.invoke(app, ["repair", "corroboration", "--watchlist", str(empty)])
    assert result.exit_code == 2
    assert "--output-repo" in result.output


def test_a_celex_that_is_not_one_is_refused(spoiled: Path) -> None:
    """`--act` is parsed before the repository is walked, like every other narrowing flag."""
    result = runner.invoke(
        app,
        [
            "repair",
            "corroboration",
            "--watchlist",
            str(WATCHLIST),
            "--output-repo",
            str(spoiled),
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
