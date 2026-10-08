"""`emendrix index rebuild`: one commit over a repository that predates the index, then none.

The command reaches no network and reads no clock, so every test runs it in process over a
repository built in a temp directory, with real `git`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from index_entries import write_payload
from toy_entries import toy_entry
from typer.testing import CliRunner

from emendrix.cli import app
from emendrix.core import ActId
from emendrix.output import (
    INDEX_FILE,
    MARKER_FILE,
    OUTPUT_REPO_ENV,
    ChangelogEntry,
    ForeignRepository,
    OutputRepo,
    index_files,
)
from emendrix.output.git import commit, git, init_repo
from emendrix.output.repo import INDEX_SUBJECT

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_ambient_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(OUTPUT_REPO_ENV, raising=False)


def garden(entry: ChangelogEntry) -> ChangelogEntry:
    return entry.model_copy(update={"act": ActId(corpus="toy", key="garden-rules")})


@pytest.fixture
def old(tmp_path: Path) -> Path:
    """A repository emendrix made before it wrote an index: payloads and a marker, committed."""
    path = tmp_path / "old"
    init_repo(path)
    (path / MARKER_FILE).write_text("emendrix output repository\n", encoding="utf-8")
    for entry in (toy_entry(), garden(toy_entry())):
        write_payload(path, entry)
    git("add", "--", ".", cwd=path)
    commit(path, "entries written before the index existed")
    return path


def rebuild(*arguments: str) -> tuple[int, str]:
    result = runner.invoke(app, ["index", "rebuild", *arguments])
    return result.exit_code, result.output


def commits(repo: Path) -> int:
    return len(git("log", "--format=%H", cwd=repo).split())


def test_a_rebuild_indexes_an_old_repository_in_one_commit(old: Path) -> None:
    code, output = rebuild("--output-repo", str(old))
    assert code == 0, output
    assert commits(old) == 2
    assert git("log", "-1", "--format=%s", cwd=old).strip() == INDEX_SUBJECT
    expected = index_files(old)
    listed = sorted(git("show", "--name-only", "--format=", "HEAD", cwd=old).split())
    assert listed == sorted(expected)
    assert {path: git("show", f"HEAD:{path}", cwd=old) for path in expected} == expected
    assert git("status", "--porcelain", cwd=old) == ""


def test_a_second_rebuild_makes_no_commit(old: Path) -> None:
    rebuild("--output-repo", str(old))
    code, output = rebuild("--output-repo", str(old))
    assert code == 0, output
    assert "current" in output
    assert commits(old) == 2


def test_the_environment_names_the_repository_too(
    old: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OUTPUT_REPO_ENV, str(old))
    code, output = rebuild()
    assert code == 0, output
    assert (old / INDEX_FILE).is_file()


def test_a_dry_run_names_the_files_and_writes_nothing(old: Path) -> None:
    code, output = rebuild("--output-repo", str(old), "--dry-run")
    assert code == 0, output
    assert f"would write {INDEX_FILE} (" in output
    assert "toy/house-rules/index.json" in output
    assert not (old / INDEX_FILE).exists()
    assert not (old / "toy/house-rules" / INDEX_FILE).exists()
    assert commits(old) == 1
    assert git("status", "--porcelain", cwd=old) == ""


def test_a_foreign_repository_is_refused_as_the_writer_refuses_it(tmp_path: Path) -> None:
    foreign = tmp_path / "foreign"
    init_repo(foreign)
    with pytest.raises(ForeignRepository) as refused:
        OutputRepo.open(foreign)
    code, output = rebuild("--output-repo", str(foreign))
    assert code == 2
    assert str(refused.value) in output
    assert not (foreign / INDEX_FILE).exists()


def test_no_repository_configured_is_a_message_and_not_a_guess() -> None:
    code, output = rebuild()
    assert code == 2
    assert "--output-repo" in output
