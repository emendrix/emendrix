"""The twin map into a changelog repository: one commit when it moves, none when it does not."""

from __future__ import annotations

from pathlib import Path

import pytest
from twin_trees import ALPHA, BETA, changelog_repo, git_log, node, text, tree

from emendrix.output import NestedRepository
from emendrix.output.index import index_files
from emendrix.site_.entries import read_entries
from emendrix.site_.substance_inputs import read_registers
from emendrix.twins.build import render, twin_map
from emendrix.twins.model import TwinMap, twins_path
from emendrix.twins.write import NotARepository, open_repository, write_twin_map


def _map(version: str = "v1", change: dict[int, str] | None = None) -> TwinMap:
    alpha = tree(ALPHA, version, node("AR 1", text(40)), node("AR 2", text(40, 100)))
    beta = tree(BETA, "b1", node("AR 1", text(40, 100, change=change)), node("AR 3", text(40)))
    return twin_map(beta, alpha)


def test_the_path_puts_the_lower_key_first_whichever_way_it_is_asked() -> None:
    assert twins_path(BETA, ALPHA) == twins_path(ALPHA, BETA) == "twins/toy-alpha--toy-beta.json"


def test_a_first_write_commits_the_map_alone_and_a_rebuild_commits_nothing(
    tmp_path: Path,
) -> None:
    repo = changelog_repo(tmp_path / "changelog")
    before = len(git_log(repo.path))
    document = _map()
    first = write_twin_map(repo, document)
    assert first.path == "twins/toy-alpha--toy-beta.json"
    assert first.revision is not None and first.unchanged is False
    assert git_log(repo.path)[0] == "twins: alpha and beta at v1 and b1"
    assert (repo.path / first.path).read_text(encoding="utf-8") == render(document)
    again = write_twin_map(repo, _map())
    assert (again.revision, again.unchanged) == (None, True)
    assert len(git_log(repo.path)) == before + 1


def test_a_moved_map_is_committed_again_under_its_new_versions(tmp_path: Path) -> None:
    repo = changelog_repo(tmp_path / "changelog")
    write_twin_map(repo, _map())
    moved = write_twin_map(repo, _map("v2", change={3: "x"}))
    assert moved.revision is not None
    assert git_log(repo.path)[0] == "twins: alpha and beta at v2 and b1"


def test_a_dry_run_writes_nothing_and_says_whether_it_would(tmp_path: Path) -> None:
    repo = changelog_repo(tmp_path / "changelog")
    before = git_log(repo.path)
    dry = write_twin_map(repo, _map(), dry_run=True)
    assert (dry.revision, dry.unchanged) == (None, False)
    assert not (repo.path / dry.path).exists()
    assert git_log(repo.path) == before
    write_twin_map(repo, _map())
    assert write_twin_map(repo, _map(), dry_run=True).unchanged is True


def test_no_index_register_or_page_reader_sees_the_twins_directory(tmp_path: Path) -> None:
    repo = changelog_repo(tmp_path / "changelog")
    indexes, entries, registers = (
        index_files(repo.path),
        read_entries(repo.path),
        (read_registers(repo.path)),
    )
    write_twin_map(repo, _map())
    assert index_files(repo.path) == indexes
    for name, written in indexes.items():
        assert (repo.path / name).read_text(encoding="utf-8") == written
    assert read_entries(repo.path) == entries
    assert read_registers(repo.path) == registers


def test_a_path_with_no_repository_is_refused_rather_than_created(tmp_path: Path) -> None:
    with pytest.raises(NotARepository, match="not a git repository yet"):
        open_repository(tmp_path / "nowhere")
    assert not (tmp_path / "nowhere").exists()
    repo = changelog_repo(tmp_path / "changelog")
    with pytest.raises(NestedRepository):
        open_repository(repo.path / "inside")
