"""What the signals repair does to entries published before the signal rules, offline.

The strongest claim it can make is that the payload alone is enough: handed only an entry in
the shape the published record holds, it writes the entry the loop writes today from the same
pinned inputs, byte for byte. Everything else here is a narrower reading of that claim, or what
the command does with it.
"""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import pytest
from repaired_repo import PHANTOM, copied, log, poisoned_repo, porcelain, units_of
from signal_entries import (
    LEGACY_ANNEXES,
    REACH_CONTAINER,
    REACH_PAIRS,
    TOY_PHANTOM,
    reach_pair,
    toy_entry,
)
from typer.testing import CliRunner

from emendrix.cli import app
from emendrix.core import Signal, SignalReport
from emendrix.eu.cache import FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eu.signals import committed_metadata
from emendrix.output import ChangelogEntry, OutputRepo
from emendrix.repair import RepairResult, RepairTarget, read_targets, shift_between
from emendrix.repair.corroborate import instructions_of, signals_of
from emendrix.repair.signals import SILENT, by_act, needs, repair
from eu_pins import FIXTURE_DIR, OBSERVED_ON

runner = CliRunner()
WATCHLIST = Path(__file__).resolve().parents[2] / "watchlist.example.toml"


def identity(report: SignalReport | None) -> SignalReport | None:
    """A normaliser that knows no corpus: what the toy act is repaired with."""
    return report


def repaired(target: RepairTarget) -> RepairResult:
    """One entry through the repair, with the EU reading of location codes the command uses."""
    return repair(target, normalise_metadata=committed_metadata)


@pytest.fixture(scope="module")
def reach(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, ChangelogEntry]]:
    """A repository of three REACH entries in their older shape, and each one as built today."""
    client = CellarClient(
        CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR)), observed_on=OBSERVED_ON
    )
    repository = OutputRepo.open(tmp_path_factory.mktemp("reach") / "repo")
    today: dict[str, ChangelogEntry] = {}
    for before, after in REACH_PAIRS:
        older, current = reach_pair(client, before, after)
        repository.write(older)
        today[after] = current
    return repository.path, today


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A repository holding the toy transition with an instruction-only row."""
    repository = OutputRepo.open(tmp_path_factory.mktemp("toy") / "repo")
    repository.write(toy_entry())
    return repository.path


@pytest.fixture(scope="module")
def spoiled(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """The committed MDR repository with an instruction-only row and its neighbour."""
    return poisoned_repo(changelog_repo, tmp_path_factory.mktemp("spoiled") / "repo")


def by_version(root: Path) -> dict[str, RepairTarget]:
    return {str(target.entry.to_version): target for target in read_targets(root)}


def run(repo: Path, *extra: str) -> str:
    """`emendrix repair signals` through the shipped command line."""
    result = runner.invoke(
        app,
        [
            "repair",
            "signals",
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


# ------------------------------------------------------------------ the rules


def test_an_older_entry_comes_out_as_the_entry_the_loop_writes_today(
    reach: tuple[Path, dict[str, ChangelogEntry]],
) -> None:
    """From the committed claims alone, with no notice re-read and no package fetched."""
    root, today = reach
    for version, target in by_version(root).items():
        result = repaired(target)
        assert result.entry is not None, version
        assert result.entry.to_json() == today[version].to_json(), version


def test_a_legacy_annex_numeral_reads_as_the_annex_and_stops_being_disputed(
    reach: tuple[Path, dict[str, ChangelogEntry]],
) -> None:
    """`AN 4` was a notation, not a disagreement: the row goes and `AN IV` agrees three ways."""
    target = by_version(reach[0])[REACH_PAIRS[0][1]]
    assert set(LEGACY_ANNEXES.values()) <= set(units_of(target.entry))
    assert all(item.change.disputed for item in target.entry.changes)

    result = repaired(target)
    assert result.entry is not None
    assert units_of(result.entry) == tuple(LEGACY_ANNEXES)
    for item in result.entry.changes:
        assert not item.change.disputed and item.change.dispute_reason is None
        assert item.change.in_force is not None
    metadata = signals_of(result.entry)
    assert metadata is not None
    assert {unit.canonical for unit in metadata.units} == set(LEGACY_ANNEXES)


def test_a_container_key_is_counted_in_the_note_and_is_no_longer_a_row(
    reach: tuple[Path, dict[str, ChangelogEntry]],
) -> None:
    target = by_version(reach[0])[REACH_PAIRS[1][1]]
    assert REACH_CONTAINER in units_of(target.entry)
    result = repaired(target)
    assert result.entry is not None
    assert REACH_CONTAINER not in units_of(result.entry)
    metadata = signals_of(result.entry)
    assert metadata is not None and metadata.note is not None
    assert "1 annotations named a part, chapter, title or recital" in metadata.note
    assert result.entry.counts.disputed == target.entry.counts.disputed - 1


def test_an_instruction_parse_claiming_nothing_comes_out_unavailable(
    reach: tuple[Path, dict[str, ChangelogEntry]],
) -> None:
    """Silence is not dissent: the one change the diff found stops being disputed."""
    target = by_version(reach[0])[REACH_PAIRS[2][1]]
    committed = instructions_of(target.entry)
    assert committed is not None and committed.available and not committed.claims
    assert target.entry.counts.disputed == 1

    result = repaired(target)
    assert result.entry is not None
    now = instructions_of(result.entry)
    assert now is not None and not now.available
    assert now.note == f"{committed.note}, {SILENT}"
    assert result.entry.counts.disputed == 0


def test_every_disputed_change_says_why(
    reach: tuple[Path, dict[str, ChangelogEntry]], spoiled: Path, toy: Path
) -> None:
    for root in (reach[0], spoiled, toy):
        for target in read_targets(root):
            result = repaired(target)
            entry = target.entry if result.entry is None else result.entry
            for item in entry.changes:
                assert (item.change.dispute_reason is None) is (not item.change.disputed)


def test_a_toy_row_only_the_instruction_parse_named_moves_to_the_report(toy: Path) -> None:
    """Over a corpus that is not law, with a normaliser that knows nothing about any."""
    (target,) = read_targets(toy)
    assert TOY_PHANTOM.canonical in units_of(target.entry)
    result = repair(target, normalise_metadata=identity)
    assert result.entry is not None and result.entry.corroboration is not None
    assert TOY_PHANTOM.canonical not in units_of(result.entry)
    assert "AR 9" in units_of(result.entry), "a row the metadata names is still appended"
    assert result.entry.corroboration.instruction_only_units == (TOY_PHANTOM,)
    assert result.detail == (f"dropped {TOY_PHANTOM.canonical}",)


def test_the_prose_and_the_run_record_are_carried_over_byte_identical(spoiled: Path) -> None:
    """Only the instruction-only row moves; the dispute the committed signal still holds stays.

    The repair re-parses nothing, so a unit the committed instruction signal misses is still
    missed: correcting a parse is the corroboration repair's business.
    """
    for target in read_targets(spoiled):
        result = repaired(target)
        if target.entry.corroboration is None:
            assert not needs(target)
            continue
        assert result.entry is not None
        assert result.detail == (f"dropped {PHANTOM.canonical}",)
        before, after = target.entry, result.entry
        assert after.explain == before.explain and after.gate == before.gate
        kept = {item.change.unit.canonical: item for item in after.changes}
        for item in before.changes:
            if item.change.unit.canonical == PHANTOM.canonical:
                continue
            now = kept[item.change.unit.canonical]
            assert now.model_dump_json() == item.model_dump_json()


def test_an_entry_already_under_the_rules_is_untouched(
    changelog_repo: Path, reach: tuple[Path, dict[str, ChangelogEntry]]
) -> None:
    """What the loop writes today, and what this repair wrote, are both left alone."""
    for target in read_targets(changelog_repo):
        assert repaired(target).entry is None, target.path
    for version, entry in reach[1].items():
        assert repaired(RepairTarget(path=Path(version), entry=entry)).entry is None


def test_an_older_schema_alone_is_not_a_reason_to_rewrite(changelog_repo: Path) -> None:
    """An entry the rules leave alone is not rewritten for its schema version or its counts.

    Re-serialised through today's model, an entry written under `1.0` differs from its bytes,
    and that is corrected when something rewrites the entry, never by a bulk pass that has
    nothing of its own to say about it.
    """
    for target in read_targets(changelog_repo):
        older = target.entry.model_copy(update={"schema_version": "1.0"})
        assert repaired(RepairTarget(path=target.path, entry=older)).entry is None


def test_a_second_pass_changes_nothing(
    reach: tuple[Path, dict[str, ChangelogEntry]], spoiled: Path, toy: Path
) -> None:
    for root in (reach[0], spoiled, toy):
        for target in read_targets(root):
            first = repair(target, normalise_metadata=committed_metadata).entry
            if first is None:
                continue
            again = RepairTarget(path=target.path, entry=first)
            assert repaired(again).entry is None, target.path


def test_the_tally_counts_rows_and_disputes_on_both_sides(
    reach: tuple[Path, dict[str, ChangelogEntry]],
) -> None:
    """The three REACH entries: three disputed textless rows go and three disputes clear.

    The rows are the two legacy numerals and the container; the cleared disputes are `AN IV`,
    `AN V` and the one change the silent parse disputed, so 38 disputed changes become 32. The
    flips are also read off the shift every other figure of the repair comes from.
    """
    results = [repaired(target) for target in read_targets(reach[0])]
    (act,), total = by_act(results)
    assert act.model_dump(exclude={"act"}) == total.model_dump(exclude={"act"})
    assert total.entries == total.changed == 3
    assert total.textless_before - total.textless_after == 3
    assert total.changes_before - total.changes_after == 3
    assert (total.cleared, total.raised) == (3, 0)
    assert (total.disputed_before, total.disputed_after) == (38, 32)
    flipped = sum(
        len(shift_between(result.target.entry, result.entry).disputed_flipped)
        for result in results
        if result.entry is not None
    )
    assert total.cleared == flipped
    assert total.disputed_after == sum(entry.counts.disputed for entry in reach[1].values())


# ------------------------------------------------------------------ the command


def test_a_dry_run_prints_the_tally_and_writes_nothing(
    reach: tuple[Path, dict[str, ChangelogEntry]], tmp_path: Path
) -> None:
    repository = copied(reach[0], tmp_path / "dry")
    before = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    revisions = log(repository)
    output = run(repository, "--dry-run")
    assert "total: 3 entries addressed · 3 would change" in output
    assert "textless rows 3 -> 0" in output
    assert "0 undisputed to disputed" in output
    assert "dry run: nothing written" in output
    after = {path: path.read_bytes() for path in sorted(repository.rglob("*")) if path.is_file()}
    assert after == before
    assert log(repository) == revisions
    assert porcelain(repository) == ""


def test_the_command_opens_no_socket_and_builds_no_client(
    reach: tuple[Path, dict[str, ChangelogEntry]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real pass, with every way to the network refused for its duration."""

    def refused(*_: object, **__: object) -> None:
        raise AssertionError("the signals repair reached for the network")

    repository = copied(reach[0], tmp_path / "offline")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(CellarClient, "__init__", refused)
    run(repository)
    assert all(
        [record.kind for record in target.entry.repairs] == ["signals"]
        for target in read_targets(repository)
    )


def test_the_command_records_what_it_did_and_a_second_pass_commits_nothing(
    reach: tuple[Path, dict[str, ChangelogEntry]], tmp_path: Path
) -> None:
    repository = copied(reach[0], tmp_path / "written")
    older = by_version(repository)
    revisions = log(repository)
    run(repository)
    assert len(log(repository)) == len(revisions) + len(older)
    assert porcelain(repository) == ""

    for version, target in by_version(repository).items():
        was = older[version].entry
        (record,) = target.entry.repairs
        assert record.kind == "signals" and record.repaired_on == OBSERVED_ON
        assert record.addressed == len(was.changes)
        assert record.repaired == shift_between(was, target.entry).changed
        assert record.remaining == 0 and not record.coordinates_checked
        assert target.entry.model_copy(update={"repairs": ()}).to_json() == (
            reach[1][version].to_json()
        )
    subject = _subject(repository)
    assert " signals repaired (" in subject

    settled = log(repository)
    run(repository)
    assert log(repository) == settled


def test_the_entry_beside_the_repaired_one_keeps_its_bytes(spoiled: Path, tmp_path: Path) -> None:
    repository = copied(spoiled, tmp_path / "neighbour")
    untouched = [t.path for t in read_targets(repository) if t.entry.corroboration is None]
    assert untouched
    before = {path: (repository / path).read_bytes() for path in untouched}
    run(repository)
    assert {path: (repository / path).read_bytes() for path in before} == before
    report = OutputRepo.open(repository)
    (target,) = [t for t in read_targets(repository) if t.entry.corroboration is not None]
    entry = report.entry_for(target.entry.act, target.entry.to_version)
    assert entry is not None and entry.corroboration is not None
    assert PHANTOM in entry.corroboration.instruction_only_units
    assert Signal.INSTRUCTION_PARSE in {item.signal for item in entry.corroboration.signals}


def _subject(repository: Path) -> str:
    return subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
