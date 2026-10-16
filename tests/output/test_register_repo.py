"""The register in the output repository: it rides its entry's commit, newest version only.

Against real `git` in a temporary directory, like `test_repo.py`. The entries are the toy
corpus's and the register is the invented one from `test_register.py`, so nothing here is law.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_register import toy_snapshot
from toy_entries import OBSERVED_ON, toy_delta, toy_entry

from emendrix.core import VersionId
from emendrix.output import (
    ChangelogEntry,
    OutputRepo,
    Register,
    diff_only_entry,
    register_for,
    register_path,
    render_register,
)


def git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def later_entry() -> ChangelogEntry:
    """The toy act's next transition, `v2` to `v3`, whose newer side the register reads."""
    delta = toy_delta()
    return diff_only_entry(
        delta.model_copy(update={"from_version": delta.to_version, "to_version": VersionId("v3")}),
        detected_on=OBSERVED_ON,
    )


def register_of(version: str = "v3") -> Register:
    snapshot = toy_snapshot()
    return register_for(snapshot.model_copy(update={"version": VersionId(version)}))


@pytest.fixture
def repo(tmp_path: Path) -> OutputRepo:
    return OutputRepo.open(tmp_path / "changelog")


def _file(repo: OutputRepo) -> Path:
    return repo.path / register_path(toy_entry().act)


def test_the_register_rides_the_commit_of_the_newest_entry(repo: OutputRepo) -> None:
    repo.write(toy_entry())
    written = repo.write(later_entry(), register=register_of())
    assert written.committed
    files = git("show", "--name-only", "--format=", "HEAD", cwd=repo.path).split()
    assert "toy/house-rules/register.json" in files
    assert "toy/house-rules/changes/v3.json" in files
    assert _file(repo).read_text(encoding="utf-8") == render_register(register_of())


def test_an_older_entry_written_later_leaves_the_newer_register_where_it_is(
    repo: OutputRepo,
) -> None:
    """A backfill writes history underneath; the register stays the newest version's."""
    repo.write(later_entry(), register=register_of("v3"))
    before = _file(repo).read_bytes()
    written = repo.write(toy_entry(), register=register_of("v2"))
    assert written.committed
    assert _file(repo).read_bytes() == before
    files = git("show", "--name-only", "--format=", "HEAD", cwd=repo.path).split()
    assert "toy/house-rules/register.json" not in files


def test_identical_bytes_commit_nothing(repo: OutputRepo) -> None:
    repo.write(later_entry(), register=register_of())
    head = git("rev-parse", "HEAD", cwd=repo.path)
    again = repo.write(later_entry(), register=register_of())
    assert again.unchanged and not again.committed
    assert git("rev-parse", "HEAD", cwd=repo.path) == head


def test_a_register_that_moved_alone_is_committed_under_its_own_subject(
    repo: OutputRepo,
) -> None:
    repo.write(later_entry())
    assert not _file(repo).exists()
    written = repo.write(later_entry(), register=register_of())
    assert written.committed
    assert written.message == "house-rules: register of v3 (4 entries)"


def test_an_entry_written_without_a_register_writes_none(repo: OutputRepo) -> None:
    """`emendrix backfill` writes entries this way: its registers come from `repair tables`."""
    repo.write(toy_entry())
    repo.write(later_entry())
    assert not _file(repo).exists()


def test_a_register_is_written_on_its_own_only_for_the_newest_entry(repo: OutputRepo) -> None:
    repo.write(toy_entry())
    repo.write(later_entry())
    stale = repo.write_register(register_of("v2"))
    assert not stale.newest and not stale.revision
    assert not _file(repo).exists()
    placed = repo.write_register(register_of("v3"))
    assert placed.revision and placed.newest
    files = git("show", "--name-only", "--format=", "HEAD", cwd=repo.path).split()
    assert files == ["toy/house-rules/register.json"]
    again = repo.write_register(register_of("v3"))
    assert again.unchanged and not again.revision
