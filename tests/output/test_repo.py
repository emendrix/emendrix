"""The output git repository, against real `git` in a temp directory, never this repo.

Every test here runs `git` for real, because the thing worth testing is the interaction with
it: that a repository is created when it is absent, that a commit contains exactly the two
files it should, that a second run of one event produces no second commit, and that a second
*event* prepends without disturbing the first.

The last test covers the embarrassing bug: a repository path that resolves inside another
working tree, emendrix's own most plausibly, is refused before a single file is written.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from toy_entries import OBSERVED_ON, toy_delta, toy_entry

from emendrix.core import VersionId
from emendrix.output import (
    MARKER,
    MARKER_FILE,
    ChangelogEntry,
    ForeignRepository,
    NestedRepository,
    OutputRepo,
    diff_only_entry,
)
from emendrix.output.git import AUTHOR_EMAIL, AUTHOR_NAME
from emendrix.output.json_out import payload_for


def git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def second_entry() -> ChangelogEntry:
    """The same act, a later version, so it lands as a second entry in one `CHANGELOG.md`."""
    delta = toy_delta()
    return diff_only_entry(
        delta.model_copy(update={"from_version": delta.to_version, "to_version": VersionId("v3")}),
        detected_on=OBSERVED_ON,
    )


@pytest.fixture
def repo(tmp_path: Path) -> OutputRepo:
    return OutputRepo.open(tmp_path / "changelog")


# ------------------------------------------------------------------ init and commit


def test_a_missing_repository_is_created_rather_than_demanded(repo: OutputRepo) -> None:
    assert not repo.path.exists()
    written = repo.write(toy_entry())
    assert written.initialised is True
    assert (repo.path / ".git").is_dir()
    assert (repo.path / "README.md").is_file(), "it says what the repository is, for a stranger"
    assert (repo.path / MARKER_FILE).is_file(), "and this says emendrix may write in it"


def test_the_commit_holds_the_two_files_of_one_act_and_says_what_it_is(
    repo: OutputRepo,
) -> None:
    written = repo.write(toy_entry())
    assert written.committed
    assert written.message == "house-rules: v1 -> v2 (4 changes)"
    files = sorted(git("show", "--name-only", "--format=", "HEAD", cwd=repo.path).split())
    assert files == [
        MARKER_FILE,
        "README.md",
        "toy/house-rules/CHANGELOG.md",
        "toy/house-rules/changes/v2.json",
    ]


def test_the_committer_is_the_tool_and_not_whoever_ran_it(repo: OutputRepo) -> None:
    repo.write(toy_entry())
    identity = git("show", "--format=%an <%ae>|%cn <%ce>", "--no-patch", "HEAD", cwd=repo.path)
    expected = f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>"
    assert identity.strip() == f"{expected}|{expected}"


def test_nothing_is_pushed_because_there_is_nowhere_to_push_to(repo: OutputRepo) -> None:
    """The repository is the user's. Ownership and hosting are not this tool's business."""
    repo.write(toy_entry())
    assert git("remote", cwd=repo.path).strip() == ""


# ------------------------------------------------------------------ idempotency


def test_re_emitting_one_event_produces_no_second_commit(repo: OutputRepo) -> None:
    """A cron entry running hourly makes one commit per amendment, not one per hour."""
    first = repo.write(toy_entry())
    again = repo.write(toy_entry())
    assert first.committed and not again.committed
    assert again.unchanged is True
    assert len(git("log", "--format=%H", cwd=repo.path).split()) == 1
    assert git("status", "--porcelain", cwd=repo.path) == ""


def test_a_repository_says_which_transition_it_already_holds(repo: OutputRepo) -> None:
    """The idempotence a backfill resumes on: the output path is the record, not a state file."""
    act = toy_entry().act
    assert repo.holds(act, VersionId("v2")) is False
    repo.write(toy_entry())
    assert repo.holds(act, VersionId("v2")) is True
    assert repo.holds(act, VersionId("v3")) is False


def test_an_entry_written_while_the_provider_refused_is_not_finished(repo: OutputRepo) -> None:
    """The credit-exhaustion case: the file exists, but nobody ever asked the model.

    `holds` and `holds_finished` disagree here on purpose. The file's existence is the whole
    resume record, so without the second question a backfill interrupted by an empty balance
    would publish the gap once and skip past it on every later run.
    """
    act = toy_entry().act
    repo.write(toy_entry())
    payload = repo.path / payload_for(act, VersionId("v2"))
    assert repo.holds_finished(act, VersionId("v2")) is True

    written = json.loads(payload.read_text(encoding="utf-8"))
    written["changes"][0]["unexplained_kind"] = "provider_unavailable"
    payload.write_text(json.dumps(written), encoding="utf-8")
    assert repo.holds(act, VersionId("v2")) is True
    assert repo.holds_finished(act, VersionId("v2")) is False

    written["changes"][0]["unexplained_kind"] = "model_failed"
    payload.write_text(json.dumps(written), encoding="utf-8")
    assert repo.holds_finished(act, VersionId("v2")) is True


def test_an_unreadable_payload_is_left_alone_rather_than_re_run(repo: OutputRepo) -> None:
    """A file this cannot parse is a reason to look at an entry, never to re-pay for it."""
    act = toy_entry().act
    repo.write(toy_entry())
    (repo.path / payload_for(act, VersionId("v2"))).write_text("{not json", encoding="utf-8")
    assert repo.holds_finished(act, VersionId("v2")) is True


def test_a_second_event_prepends_and_leaves_the_first_intact(repo: OutputRepo) -> None:
    repo.write(toy_entry())
    before = (repo.path / "toy" / "house-rules" / "CHANGELOG.md").read_text(encoding="utf-8")
    repo.write(second_entry())
    after = (repo.path / "toy" / "house-rules" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert after.index("v3 -->") < after.index("v2 -->"), "newest first"
    opening = f"<!-- emendrix:entry {MARKER} v2 -->"
    assert before[before.index(opening) :] in after, "the earlier entry is byte-identical"
    assert len(git("log", "--format=%H", cwd=repo.path).split()) == 2


def test_an_edited_entry_is_replaced_in_place_rather_than_duplicated(repo: OutputRepo) -> None:
    """Re-emitting after a code change updates the entry and keeps the file's order."""
    repo.write(toy_entry())
    repo.write(second_entry())
    changed = toy_entry().model_copy(update={"detected_on": OBSERVED_ON.replace(day=7)})
    repo.write(changed)
    text = (repo.path / "toy" / "house-rules" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert text.count(f"<!-- emendrix:entry {MARKER} v2 -->") == 1
    assert text.index("v3 -->") < text.index("v2 -->"), "position preserved, not moved to the top"
    assert "2026-08-07" in text


# ------------------------------------------------------------------ the guard


def test_a_path_inside_another_working_tree_is_refused_before_anything_is_written(
    tmp_path: Path,
) -> None:
    """The embarrassing bug: emendrix committing its own source, or vice versa."""
    outer = tmp_path / "some-project"
    outer.mkdir()
    git("init", cwd=outer)
    with pytest.raises(NestedRepository) as raised:
        OutputRepo.open(outer / "changelog")
    assert str(outer) in str(raised.value)
    assert not (outer / "changelog").exists()


def test_a_path_inside_the_emendrix_checkout_is_covered_by_that_rule() -> None:
    """Not a special case in the code: the general rule already forbids it."""
    with pytest.raises(NestedRepository):
        OutputRepo.open(Path(__file__).resolve().parent / "scratch-changelog")


def test_a_repository_emendrix_did_not_create_is_refused_too(tmp_path: Path) -> None:
    """The ancestor rule looks *above* the path, so on its own it accepts the repo root itself.

    `--output-repo .` from inside somebody's project would then commit changelogs straight into
    it. The marker file is what tells the two apart, and it is only written on init.
    """
    theirs = tmp_path / "their-project"
    theirs.mkdir()
    git("init", cwd=theirs)
    with pytest.raises(ForeignRepository, match=MARKER_FILE):
        OutputRepo.open(theirs)


def test_the_emendrix_checkout_itself_is_refused(tmp_path: Path) -> None:
    """The one path this must never accept, asserted directly rather than by argument."""
    with pytest.raises((ForeignRepository, NestedRepository)):
        OutputRepo.open(Path(__file__).resolve().parents[2])


def test_a_repository_emendrix_created_is_reopened_without_complaint(tmp_path: Path) -> None:
    """The marker is what makes the second run of a cron entry legal."""
    first = OutputRepo.open(tmp_path / "changelog")
    first.write(toy_entry())
    again = OutputRepo.open(tmp_path / "changelog")
    assert again.write(toy_entry()).unchanged is True
