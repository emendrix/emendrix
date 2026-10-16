"""`emendrix repair tables`: the keyed diff of table entries set on entries published before it.

The seeded repository holds REACH entries the loop's own diff wrote from committed packages,
put back into the shape a `1.2` document has: every `table_entries` null and the schema version
before the field existed. The strongest claim is that the repair then writes exactly what the
loop writes today for the field it addresses and nothing else, byte for byte. Every read goes
through the pinned fixture set, so nothing here reaches the network.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from emendrix.cli import app
from emendrix.core import ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eu.identifiers import Celex, act_id
from emendrix.output import ChangelogEntry, OutputRepo, diff_only_entry, register_path
from emendrix.repair import RepairTarget, read_targets
from emendrix.repair.cli import profiled_units
from emendrix.repair.entries import KIND, by_act, needs, newest_targets, repair, snapshot_for
from emendrix.repair.rederive import Trees
from emendrix.session import adapter_for
from eu_pins import FIXTURE_DIR, OBSERVED_ON, REACH

runner = CliRunner()
WATCHLIST = Path(__file__).resolve().parents[2] / "watchlist.example.toml"
ACT = act_id(Celex.parse(REACH))
PAIRS = (("20160203", "20160308"), ("20170302", "20170704"))
"""Two consecutive REACH transitions, each with a change in a profiled annex."""


def _published(before: str, after: str) -> ChangelogEntry:
    """The loop's entry for one pair, as a document written before `table_entries` existed."""
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        older = adapter.fetch_version(ACT, VersionId(f"02006R1907-{before}"))
        newer = adapter.fetch_version(ACT, VersionId(f"02006R1907-{after}"))
    assert isinstance(older, ProvisionTree) and isinstance(newer, ProvisionTree)
    entry = diff_only_entry(compute_delta(older, newer), detected_on=OBSERVED_ON)
    changes = tuple(
        item.model_copy(update={"change": item.change.model_copy(update={"table_entries": None})})
        for item in entry.changes
    )
    return entry.model_copy(update={"changes": changes, "schema_version": "1.2"})


def _today(before: str, after: str) -> ChangelogEntry:
    """The same pair as the loop writes it today."""
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        older = adapter.fetch_version(ACT, VersionId(f"02006R1907-{before}"))
        newer = adapter.fetch_version(ACT, VersionId(f"02006R1907-{after}"))
    assert isinstance(older, ProvisionTree) and isinstance(newer, ProvisionTree)
    return diff_only_entry(compute_delta(older, newer), detected_on=OBSERVED_ON)


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo = OutputRepo.open(tmp_path_factory.mktemp("tables") / "changelog")
    for before, after in PAIRS:
        repo.write(_published(before, after))
    return repo.path


def _copy(source: Path, destination: Path) -> Path:
    subprocess.run(["cp", "-R", str(source), str(destination)], check=True)
    return destination


def _git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def run(repo: Path, *extra: str) -> str:
    result = runner.invoke(
        app,
        [
            "repair",
            "tables",
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


def _without(document: dict[str, Any]) -> dict[str, Any]:
    """A payload with the three fields the repair may move taken out."""
    rest = {
        key: value for key, value in document.items() if key not in ("schema_version", "repairs")
    }
    rest["changes"] = [
        {**item, "change": {k: v for k, v in item["change"].items() if k != "table_entries"}}
        for item in document["changes"]
    ]
    return rest


def test_an_entry_published_before_the_field_needs_the_repair(seeded: Path) -> None:
    profiled = profiled_units()
    targets = read_targets(seeded)
    assert len(targets) == 2
    assert all(needs(target, profiled) for target in targets)
    assert not needs(targets[0], {})


def test_the_repair_moves_table_entries_and_nothing_else(seeded: Path) -> None:
    profiled = profiled_units()
    targets = read_targets(seeded)
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        trees = Trees(adapter)
        results = [repair(target, trees, profiled) for target in targets]
    for (before, after), target, result in zip(PAIRS, targets, results, strict=True):
        rebuilt = result.entry
        assert rebuilt is not None and result.remaining == 0
        assert rebuilt.schema_version == "1.3"
        original = json.loads(target.entry.to_json())
        assert _without(json.loads(rebuilt.to_json())) == _without(original)
        expected = [item.change.table_entries for item in _today(before, after).changes]
        assert [item.change.table_entries for item in rebuilt.changes] == expected
        assert result.repaired == sum(1 for delta in expected if delta is not None) > 0
    acts, total = by_act(results, {REACH: 2})
    assert [tally.act for tally in acts] == [REACH]
    assert (total.examined, total.rewritten, total.underivable) == (2, 2, 0)
    assert total.added >= 13 and total.whitespace_only >= 604


def test_a_version_the_corpus_cannot_produce_is_counted_and_left(seeded: Path) -> None:
    target = read_targets(seeded)[0]
    missing = target.entry.model_copy(update={"to_version": VersionId("02006R1907-20990101")})
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        result = repair(
            RepairTarget(path=target.path, entry=missing), Trees(adapter), profiled_units()
        )
    assert result.entry is None
    assert result.repaired == 0 and result.remaining == result.addressed > 0
    assert result.detail and "02006R1907-20990101" in result.detail[0]


def test_the_register_is_read_from_the_newest_published_version(seeded: Path) -> None:
    profiled = profiled_units()
    (newest,) = newest_targets(read_targets(seeded), profiled)
    assert str(newest.entry.to_version) == "02006R1907-20170704"
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        snapshot = snapshot_for(newest, Trees(adapter))
    assert not isinstance(snapshot, str)
    assert snapshot.version == newest.entry.to_version and snapshot.reading.entries


def test_a_dry_run_writes_nothing(seeded: Path, tmp_path: Path) -> None:
    repo = _copy(seeded, tmp_path / "dry")
    head = _git("rev-parse", "HEAD", cwd=repo)
    output = run(repo, "--dry-run")
    assert f"{REACH}: 2 entries examined · 2 rewritten" in output
    assert "dry run: nothing written" in output
    assert "(dry run: not written)" in output
    assert "elapsed " in output
    assert _git("rev-parse", "HEAD", cwd=repo) == head
    assert _git("status", "--porcelain", cwd=repo) == ""
    assert not (repo / register_path(ACT)).exists()


def test_a_pass_commits_each_entry_then_the_register_and_a_second_finds_nothing(
    seeded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(*_: object, **__: object) -> None:
        raise AssertionError("the tables repair reached for the network")

    repo = _copy(seeded, tmp_path / "wet")
    commits = len(_git("log", "--format=%H", cwd=repo).split())
    monkeypatch.setattr(socket.socket, "connect", refused)
    run(repo)
    assert len(_git("log", "--format=%H", cwd=repo).split()) == commits + 3
    subjects = _git("log", "--format=%s", "-3", cwd=repo).splitlines()
    assert subjects[0].startswith(f"{REACH}: register of 02006R1907-20170704 (")
    assert subjects[1] == f"{REACH}: 02006R1907-20170704 {KIND} repaired (2 of 2 changes)"
    for target in read_targets(repo):
        assert target.entry.schema_version == "1.3"
        assert [record.kind for record in target.entry.repairs] == [KIND]
    register = json.loads((repo / register_path(ACT)).read_text(encoding="utf-8"))
    assert register["version"] == "02006R1907-20170704"

    head = _git("rev-parse", "HEAD", cwd=repo)
    output = run(repo)
    assert f"{REACH}: 2 entries examined · 0 rewritten" in output
    assert "unchanged" in output
    assert _git("rev-parse", "HEAD", cwd=repo) == head
