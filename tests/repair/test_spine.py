"""The four properties every repair kind holds, plus what a repair may never move.

They are one test each and named for what breaks, because the whole exercise is pointless
without them: a repair that rewrote a neighbouring explanation, or that wrote every file it
read, would be worse than the defect it corrects.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from repaired_repo import (
    copied,
    corrected,
    log,
    poisoned_repo,
    poisoned_target,
    porcelain,
    restored_unit,
)

from emendrix.output import OutputRepo, split_entries
from emendrix.output.json_out import RepairRecord
from emendrix.repair import (
    delta_of,
    moved,
    read_targets,
    rebuild,
    shift_between,
    with_record,
)
from emendrix.repair.corroborate import KIND, needs
from eu_pins import OBSERVED_ON


@pytest.fixture(scope="module")
def spoiled(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """The committed repository with the third signal's two defects put back into it."""
    return poisoned_repo(changelog_repo, tmp_path_factory.mktemp("spoiled") / "repo")


def test_taking_an_entry_apart_and_putting_it_back_reproduces_its_bytes(
    changelog_repo: Path,
) -> None:
    """Round-trip identity, over every entry the shipped command chain wrote.

    This is the test that decides which fields `delta_of` strips: too few and the merge reads a
    stale verdict as an input, too many and something the diff supplied is lost. Either way the
    bytes move and the failure names the entry.
    """
    targets = read_targets(changelog_repo)
    assert targets, "the fixture repository holds no committed entry"
    for target in targets:
        entry = target.entry
        rebuilt = rebuild(
            entry,
            delta=delta_of(entry),
            corroboration=entry.corroboration,
            changes=entry.changes,
        )
        assert rebuilt.to_json() == entry.to_json(), target.path


def test_repairing_one_change_leaves_every_sibling_byte_identical(
    spoiled: Path, tmp_path: Path
) -> None:
    """The failure that would make the whole exercise pointless, asserted from both sides.

    Inside the entry: every change the repair did not touch keeps its prose, its citations and
    its gate outcome. Inside the file: every other entry keeps its bytes, marker to marker.
    """
    repository = OutputRepo.open(copied(spoiled, tmp_path / "siblings"))
    target = poisoned_target(repository.path)
    result = corrected(target)
    assert result.entry is not None
    before = {item.change.unit.canonical: item for item in target.entry.changes}
    kept = restored_unit(target)
    for item in result.entry.changes:
        unit = item.change.unit.canonical
        if unit not in before or unit == kept:
            continue
        assert item.sentences == before[unit].sentences, unit
        assert item.applicability_note == before[unit].applicability_note, unit
        assert item.outcome == before[unit].outcome, unit

    changelog = repository.act_dir(result.entry) / "CHANGELOG.md"
    was = split_entries(changelog.read_text(encoding="utf-8"))
    assert len(was) > 1, "the file needs a sibling entry for this assertion to mean anything"
    repository.write(result.entry, message="corrected")
    now = split_entries(changelog.read_text(encoding="utf-8"))
    assert [key for key, _ in was] == [key for key, _ in now]
    rewritten = [key for (key, old), (_, new) in zip(was, now, strict=True) if old != new]
    assert rewritten == [result.entry.key]


def test_an_entry_the_repair_does_not_change_is_not_written(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """No-op safety: a pass over a repository it has nothing to say about writes nothing."""
    repository = OutputRepo.open(copied(changelog_repo, tmp_path / "clean"))
    revisions = log(repository.path)
    for target in read_targets(repository.path):
        assert needs(target), target.path
        assert corrected(target).entry is None, target.path
    assert porcelain(repository.path) == ""
    assert log(repository.path) == revisions


def test_running_the_repair_twice_produces_one_commit(spoiled: Path, tmp_path: Path) -> None:
    """Re-runnable: the second pass finds the entry already correct and writes nothing."""
    repository = OutputRepo.open(copied(spoiled, tmp_path / "twice"))
    first = corrected(poisoned_target(repository.path))
    assert first.entry is not None
    before = log(repository.path)
    repository.write(first.entry, message="first")
    after_one = log(repository.path)
    assert len(after_one) == len(before) + 1

    assert corrected(poisoned_target(repository.path)).entry is None
    assert log(repository.path) == after_one
    assert porcelain(repository.path) == ""


def test_the_run_record_is_carried_over_untouched(spoiled: Path) -> None:
    """`explain` and `gate` record one run and stay as it left them; `counts` counts what ships."""
    target = poisoned_target(spoiled)
    result = corrected(target)
    assert result.entry is not None
    assert result.entry.explain == target.entry.explain
    assert result.entry.gate == target.entry.gate
    assert result.entry.counts != target.entry.counts


def test_detected_on_is_the_date_the_amendment_was_detected(spoiled: Path) -> None:
    """A repair is not a detection, so the date the entry carries does not move."""
    target = poisoned_target(spoiled)
    result = corrected(target)
    assert result.entry is not None
    assert result.entry.detected_on == target.entry.detected_on


def test_a_repair_record_is_appended_only_when_something_moved(changelog_repo: Path) -> None:
    """The ordering rule: a record added before the comparison makes every entry differ.

    Appending first would make a rebuilt entry differ from its original by the record alone, so
    a repair that changed nothing would write, and the next run would write again for ever.
    """
    entry = read_targets(changelog_repo)[0].entry
    rebuilt = rebuild(
        entry, delta=delta_of(entry), corroboration=entry.corroboration, changes=entry.changes
    )
    assert not moved(entry, rebuilt)
    assert rebuilt.repairs == ()
    stamped = with_record(rebuilt, RepairRecord(kind=KIND, repaired_on=OBSERVED_ON))
    assert moved(entry, stamped)
    assert len(stamped.repairs) == 1


def test_a_repair_reports_the_disputed_flags_it_flipped(spoiled: Path) -> None:
    """The one figure that cannot be read off the published record, counted per entry."""
    target = poisoned_target(spoiled)
    result = corrected(target)
    assert result.entry is not None
    shift = shift_between(target.entry, result.entry)
    assert shift.disputed_flipped == (restored_unit(target),)
    assert shift.gained == ()
    assert len(shift.dropped) == 1
