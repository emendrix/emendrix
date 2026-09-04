"""What the restating repair selects, what it refuses to touch, and what it never moves.

The whole risk of this repair is the selector. It matches on text a change carries, and most of
the text in that field is the house register: a reason this project curated, written on a change
that predates the counted kind. So the first tests here are the negative ones, and the fixture
entry carries a curated reason with no kind beside every raw one precisely so that a predicate
reaching wider than it should fails here rather than restating a note that was never wrong.

Nothing in this file calls a model, reads a key or opens a socket.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from repaired_repo import (
    RAW_MODEL_FAILURE,
    RAW_PROVIDER_FAILURE,
    copied,
    log,
    porcelain,
    raw_reason_repo,
    unexplained_target,
)
from typer.testing import CliRunner

from emendrix.cli import app
from emendrix.explain import MODEL_FAILED, NOTHING_TO_EXPLAIN
from emendrix.output import OutputRepo
from emendrix.repair import explanations as explain_repair
from emendrix.repair import read_targets
from emendrix.repair.unexplained import KIND, needs, repair, selected, withheld
from eu_pins import OBSERVED_ON

runner = CliRunner()
WATCHLIST = Path(__file__).resolve().parents[2] / "watchlist.example.toml"

RESTATED = (0,)
"""The one change of the fixture entry whose note is a library's own error text."""

WITHHELD = (1,)
"""The one whose note names a provider that never answered, which is never stamped."""

CURATED = (2, 3)
"""The two carrying a curated reason and no kind, which this repair may never touch."""


@pytest.fixture(scope="module")
def raw(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """The committed repository with the notes written before the kinds existed put back."""
    return raw_reason_repo(changelog_repo, tmp_path_factory.mktemp("raw") / "repo")


def run(repo: Path, *extra: str) -> str:
    """`emendrix repair unexplained` through the shipped command line, offline."""
    result = runner.invoke(
        app,
        [
            "repair",
            "unexplained",
            "--watchlist",
            str(WATCHLIST),
            "--output-repo",
            str(repo),
            "--repaired-on",
            OBSERVED_ON.isoformat(),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_only_a_librarys_own_error_text_is_selected(raw: Path) -> None:
    """The exact-match promise, from both sides, on one entry holding all four notes.

    The two curated reasons carry no kind either, so they are indistinguishable from the raw
    ones by anything except the text itself. That is what makes them the test.
    """
    entry = unexplained_target(raw).entry
    assert selected(entry) == RESTATED
    assert withheld(entry) == WITHHELD
    assert entry.changes[0].unexplained == RAW_MODEL_FAILURE
    assert entry.changes[1].unexplained == RAW_PROVIDER_FAILURE
    assert [entry.changes[index].unexplained for index in CURATED] == [
        NOTHING_TO_EXPLAIN,
        MODEL_FAILED,
    ]
    assert all(not entry.changes[index].unexplained_kind for index in range(4))


def test_a_repository_of_curated_reasons_alone_is_never_selected(changelog_repo: Path) -> None:
    """A pass over entries this repair has nothing to say about addresses nothing at all."""
    for target in read_targets(changelog_repo):
        assert selected(target.entry) == ()
        assert withheld(target.entry) == ()
        assert not needs(target)


def test_a_restated_note_says_what_the_code_would_say_today(raw: Path) -> None:
    """The sentence becomes the curated one and the kind is stamped, which is the whole point.

    The second assertion is the reason the kind matters as much as the sentence: the change is
    now the shape `repair explanations` selects, so a gap that no selector could reach is one
    the paid repair can be pointed at.
    """
    target = unexplained_target(raw)
    result = repair(target)
    assert result.entry is not None
    restated = result.entry.changes[0]
    assert restated.unexplained == MODEL_FAILED
    assert restated.unexplained_kind == "model_failed"
    assert not restated.sentences
    assert explain_repair.selected(result.entry) == (0, 3)
    assert (result.addressed, result.repaired, result.remaining) == (2, 1, 1)


def test_a_provider_shape_note_is_counted_and_never_stamped(raw: Path) -> None:
    """The trap: a settled kind here would lie, and an unfinished one would cost a re-run.

    `holds_finished` reads `provider_unavailable` as an entry a later pass must complete, and
    completing it re-runs the whole transition, prose that is already correct included. So a
    note of this shape is counted and left exactly as it was found.
    """
    target = unexplained_target(raw)
    result = repair(target)
    assert result.entry is not None
    withheld_change = result.entry.changes[1]
    assert withheld_change.unexplained == RAW_PROVIDER_FAILURE
    assert withheld_change.unexplained_kind == ""
    assert result.remaining == 1
    assert any("provider" in line for line in result.detail)

    repository = OutputRepo.open(raw)
    assert repository.holds_finished(result.entry.act, result.entry.to_version)


def test_the_changes_beside_a_restated_one_keep_their_bytes(raw: Path) -> None:
    """Sibling identity inside the entry: the curated notes and every explanation stand."""
    target = unexplained_target(raw)
    result = repair(target)
    assert result.entry is not None
    for index in range(1, len(target.entry.changes)):
        assert (
            result.entry.changes[index].model_dump_json()
            == target.entry.changes[index].model_dump_json()
        ), index


def test_the_run_record_and_the_detection_date_do_not_move(raw: Path) -> None:
    """A repair is not a detection and retracts no call that was made."""
    target = unexplained_target(raw)
    result = repair(target)
    assert result.entry is not None
    assert result.entry.explain == target.entry.explain
    assert result.entry.gate == target.entry.gate
    assert result.entry.detected_on == target.entry.detected_on
    assert result.entry.counts == target.entry.counts


def test_the_verbatim_texts_do_not_move(raw: Path) -> None:
    """Verbatim means verbatim: a restated note rewrites a sentence and never a text."""
    target = unexplained_target(raw)
    result = repair(target)
    assert result.entry is not None
    for was, now in zip(target.entry.changes, result.entry.changes, strict=True):
        assert now.change.provision == was.change.provision
        assert now.change.before == was.change.before
        assert now.change.after == was.change.after


def test_a_dry_run_writes_nothing(raw: Path, tmp_path: Path) -> None:
    """The same promise the sibling verbs make, over a repository that does need the repair."""
    repository = copied(raw, tmp_path / "dry")
    before = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    revisions = log(repository)

    output = run(repository, "--dry-run")
    assert "1 changes repaired" in output
    assert "1 not repaired" in output
    assert "provider" in output
    assert "dry run: nothing written" in output

    after = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    assert after == before
    assert log(repository) == revisions
    assert porcelain(repository) == ""


def test_the_command_commits_one_entry_and_records_what_it_did(raw: Path, tmp_path: Path) -> None:
    """A real pass writes the entry, says so in the subject, and records both counts."""
    repository = copied(raw, tmp_path / "written")
    target = unexplained_target(repository)
    revisions = log(repository)

    run(repository)
    assert len(log(repository)) == len(revisions) + 1
    assert porcelain(repository) == ""

    entry = OutputRepo.open(repository).entry_for(target.entry.act, target.entry.to_version)
    assert entry is not None
    assert entry.changes[0].unexplained == MODEL_FAILED
    assert entry.changes[0].unexplained_kind == "model_failed"
    record = entry.repairs[-1]
    assert record.kind == KIND
    assert (record.addressed, record.repaired, record.remaining) == (2, 1, 1)
    assert record.repaired_on == OBSERVED_ON
    assert record.usage.requests == 0
    assert not record.coordinates_checked
    assert _subject(repository) == (
        f"{entry.act.key}: {entry.to_version} unexplained notes restated (1 of 2 changes)"
    )


def test_a_second_pass_over_a_restated_repository_commits_nothing(
    raw: Path, tmp_path: Path
) -> None:
    """Re-runnable: the note is in the house register now, so nothing selects it again."""
    repository = copied(raw, tmp_path / "again")
    run(repository)
    revisions = log(repository)

    run(repository)
    assert log(repository) == revisions
    assert porcelain(repository) == ""
    assert not [target for target in read_targets(repository) if selected(target.entry)]


def test_the_entry_beside_the_restated_one_keeps_its_bytes(raw: Path, tmp_path: Path) -> None:
    """A pass over a whole repository leaves what it has nothing to say about exactly as it was."""
    repository = copied(raw, tmp_path / "neighbour")
    restated = unexplained_target(repository).path
    untouched = [target.path for target in read_targets(repository) if target.path != restated]
    assert untouched
    before = {path: (repository / path).read_bytes() for path in untouched}
    run(repository)
    assert {path: (repository / path).read_bytes() for path in before} == before


def test_a_limit_stops_the_pass_at_the_entries_it_would_change(raw: Path, tmp_path: Path) -> None:
    """`--limit` counts entries here, because this repair pays for nothing per change."""
    repository = copied(raw, tmp_path / "limited")
    output = run(repository, "--dry-run", "--limit", "1")
    assert "1 would change" in output


def test_a_repair_with_nowhere_to_write_is_refused_before_anything_is_read(
    tmp_path: Path,
) -> None:
    """A missing output repository is an environment being wrong, and costs a message and exit 2."""
    empty = tmp_path / "watchlist.toml"
    empty.write_text('[[acts]]\ncelex = "32017R0745"\n', encoding="utf-8")
    result = runner.invoke(app, ["repair", "unexplained", "--watchlist", str(empty)])
    assert result.exit_code == 2
    assert "--output-repo" in result.output


def test_a_celex_that_is_not_one_is_refused(raw: Path) -> None:
    """`--act` is parsed before the repository is walked, like every other narrowing flag."""
    result = runner.invoke(
        app,
        [
            "repair",
            "unexplained",
            "--watchlist",
            str(WATCHLIST),
            "--output-repo",
            str(raw),
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
