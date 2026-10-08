"""The index rides every commit `OutputRepo.write` makes, against real `git` in a temp directory.

What a consumer relies on is that any commit of a changelogs repository is self-consistent: the
index it holds is the one its payloads produce. So every test here compares what was committed
with `index_files` over the same tree, and the order-independence and no-op properties the
changelog already has are asserted again with the index in the tree.
"""

from __future__ import annotations

import json
from pathlib import Path

from index_entries import SECOND_EVENT_ON, at_version, repaired, write_payload
from toy_entries import toy_entry

from emendrix.core import ActId
from emendrix.output import (
    INDEX_FILE,
    MARKER_FILE,
    ChangelogEntry,
    OutputRepo,
    index_files,
)
from emendrix.output.git import commit, git, init_repo
from emendrix.output.repo import INDEX_SUBJECT

_HOUSE = "toy/house-rules"
_GARDEN = "toy/garden-rules"


def garden(entry: ChangelogEntry) -> ChangelogEntry:
    """The same changes under a second act, so the root index has two rows to order."""
    return entry.model_copy(update={"act": ActId(corpus="toy", key="garden-rules")})


def later(entry: ChangelogEntry) -> ChangelogEntry:
    return at_version(entry, "v3", SECOND_EVENT_ON)


def head_files(repo: Path) -> list[str]:
    return sorted(git("show", "--name-only", "--format=", "HEAD", cwd=repo).split())


def commits(repo: Path) -> int:
    return len(git("log", "--format=%H", cwd=repo).split())


def tree(repo: Path) -> dict[str, bytes]:
    """Every file outside `.git`, by relative path."""
    return {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }


def committed_index(repo: Path) -> dict[str, str]:
    """Every index file `HEAD` holds, read from the commit rather than the working tree."""
    listed = git("ls-tree", "-r", "--name-only", "HEAD", cwd=repo).split()
    return {
        path: git("show", f"HEAD:{path}", cwd=repo)
        for path in sorted(listed)
        if path.rsplit("/", 1)[-1] == INDEX_FILE
    }


def old_repository(path: Path, *entries: ChangelogEntry) -> Path:
    """A repository emendrix made before it wrote an index: payloads and a marker, committed."""
    init_repo(path)
    (path / MARKER_FILE).write_text("emendrix output repository\n", encoding="utf-8")
    for entry in entries:
        write_payload(path, entry)
    git("add", "--", ".", cwd=path)
    commit(path, "an entry written before the index existed")
    return path


def test_one_write_commits_the_entry_and_both_index_files(tmp_path: Path) -> None:
    repo = OutputRepo.open(tmp_path / "changelog")
    repo.write(toy_entry())
    files = head_files(repo.path)
    assert INDEX_FILE in files
    assert f"{_HOUSE}/{INDEX_FILE}" in files
    assert f"{_HOUSE}/changes/v2.json" in files
    assert committed_index(repo.path) == index_files(repo.path)
    assert git("status", "--porcelain", cwd=repo.path) == ""


def test_a_batch_then_a_poll_leaves_the_tree_a_poll_then_a_batch_does(tmp_path: Path) -> None:
    batch = [toy_entry(), garden(toy_entry())]
    poll = later(toy_entry())
    first = OutputRepo.open(tmp_path / "batch-first")
    for entry in batch:
        first.write(entry)
    first.write(poll)
    second = OutputRepo.open(tmp_path / "poll-first")
    second.write(poll)
    for entry in reversed(batch):
        second.write(entry)

    assert tree(first.path) == tree(second.path)
    for repo in (first, second):
        assert committed_index(repo.path) == index_files(repo.path)
    root = json.loads((first.path / INDEX_FILE).read_text(encoding="utf-8"))
    assert [act["key"] for act in root["acts"]] == ["garden-rules", "house-rules"]


def test_re_emitting_an_entry_into_a_current_index_makes_no_commit(tmp_path: Path) -> None:
    """The hourly cron depends on this: one commit per amendment, not one per hour."""
    repo = OutputRepo.open(tmp_path / "changelog")
    repo.write(toy_entry())
    repo.write(garden(toy_entry()))
    before = tree(repo.path)

    again = repo.write(toy_entry())

    assert again.unchanged and not again.committed
    assert commits(repo.path) == 2
    assert tree(repo.path) == before


def test_a_repair_moves_only_its_event_row_and_its_act_s_root_row(tmp_path: Path) -> None:
    repo = OutputRepo.open(tmp_path / "changelog")
    for entry in (toy_entry(), later(toy_entry()), garden(toy_entry())):
        repo.write(entry)
    act_before = json.loads((repo.path / _HOUSE / INDEX_FILE).read_text(encoding="utf-8"))
    root_before = json.loads((repo.path / INDEX_FILE).read_text(encoding="utf-8"))

    written = repo.write(repaired(toy_entry(), "corroboration", SECOND_EVENT_ON), message="repair")

    assert written.message == "repair"
    assert not any(path.startswith(f"{_GARDEN}/") for path in head_files(repo.path))
    act_after = json.loads((repo.path / _HOUSE / INDEX_FILE).read_text(encoding="utf-8"))
    root_after = json.loads((repo.path / INDEX_FILE).read_text(encoding="utf-8"))
    newer, older = act_after["events"]
    assert newer == act_before["events"][0]
    assert older != act_before["events"][1]
    assert older["updated_on"] == SECOND_EVENT_ON.isoformat()
    assert older["repairs"] == [
        {"kind": "corroboration", "repaired_on": SECOND_EVENT_ON.isoformat()}
    ]
    assert act_after["provisions"] == act_before["provisions"]
    garden_row, house_row = root_after["acts"]
    assert garden_row == root_before["acts"][0]
    assert house_row != root_before["acts"][1]
    assert committed_index(repo.path) == index_files(repo.path)


def test_a_repository_without_an_index_gets_both_on_its_next_write(tmp_path: Path) -> None:
    """Another act's index is built once from its payloads when it has none, and committed."""
    path = old_repository(tmp_path / "old", toy_entry(), garden(toy_entry()))
    repo = OutputRepo.open(path)

    written = repo.write(later(toy_entry()))

    assert written.committed
    files = head_files(path)
    for index in (INDEX_FILE, f"{_HOUSE}/{INDEX_FILE}", f"{_GARDEN}/{INDEX_FILE}"):
        assert index in files
    assert committed_index(path) == index_files(path)
    assert git("status", "--porcelain", cwd=path) == ""


def test_an_unchanged_entry_into_a_stale_index_commits_the_index_alone(tmp_path: Path) -> None:
    """The subject says what the commit did: no entry moved, so it is not an emission."""
    repo = OutputRepo.open(tmp_path / "changelog")
    repo.write(toy_entry())
    git("rm", "--quiet", "--", INDEX_FILE, f"{_HOUSE}/{INDEX_FILE}", cwd=repo.path)
    commit(repo.path, "the index removed by hand")

    again = repo.write(toy_entry())

    assert again.committed and again.message == INDEX_SUBJECT
    assert head_files(repo.path) == [INDEX_FILE, f"{_HOUSE}/{INDEX_FILE}"]
    assert committed_index(repo.path) == index_files(repo.path)
