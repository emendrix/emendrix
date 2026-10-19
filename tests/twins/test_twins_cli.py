"""`emendrix twins build` over a temporary watchlist, text store and changelog repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from twin_trees import changelog_repo, git_log, node, text, tree
from typer.testing import CliRunner

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.core import ActId
from emendrix.output.config import OUTPUT_REPO_ENV
from emendrix.texts.config import TEXT_STORE_ENV
from emendrix.texts.store import TextStore
from eu_pins import AI_ACT, IVDR, MDR

runner = CliRunner()

MDR_ACT = ActId(corpus="eu", key=MDR)
IVDR_ACT = ActId(corpus="eu", key=IVDR)
NEWEST = "02017R0745-20250110"
PATH = f"twins/eu-{MDR}--eu-{IVDR}.json"


@pytest.fixture(autouse=True)
def _no_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TEXT_STORE_ENV, raising=False)
    monkeypatch.delenv(OUTPUT_REPO_ENV, raising=False)


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A store holding three MDR texts and one IVDR text, a repository, and a watchlist."""
    store = TextStore.create_or_open(tmp_path / "store")
    # The act as published sorts after every consolidation by name: newest is read by date.
    for version, start in ((MDR, 900), ("02017R0745-20200424", 800), (NEWEST, 0)):
        store.write(tree(MDR_ACT, version, node("AR 1", text(40, start))), version=version)
    ivdr = "02017R0746-20250110"
    store.write(tree(IVDR_ACT, ivdr, node("AR 2", text(40, change={1: "x"}))), version=ivdr)
    repo = changelog_repo(tmp_path / "changelog")
    watchlist = tmp_path / "watchlist.toml"
    watchlist.write_text(
        f'[[acts]]\ncelex = "{MDR}"\n\n[[acts]]\ncelex = "{IVDR}"\n\n'
        f'[[twins]]\nacts = ["{IVDR}", "{MDR}"]\n\n'
        f'[output]\nrepo_path = "{repo.path}"\ntext_store_path = "{store.root}"\n',
        encoding="utf-8",
    )
    return watchlist, store.root, repo.path


def _build(watchlist: Path, *flags: str) -> tuple[int, dict[str, Any]]:
    result = runner.invoke(
        app, ["twins", "build", "--watchlist", str(watchlist), "--summary", "json", *flags]
    )
    return result.exit_code, json.loads(result.stderr.splitlines()[-1])


def test_a_build_commits_the_map_of_the_newest_texts_once(setup: tuple[Path, Path, Path]) -> None:
    watchlist, _, repo = setup
    code, summary = _build(watchlist)
    assert code == 0
    [pair] = summary["pairs"]
    assert pair["outcome"] == "written"
    assert pair["versions"] == [NEWEST, "02017R0746-20250110"]
    assert (pair["path"], pair["pairs"], pair["unpaired"]) == (PATH, 1, [0, 0])
    assert git_log(repo)[0] == f"twins: {MDR} and {IVDR} at {NEWEST} and 02017R0746-20250110"
    document = json.loads((repo / PATH).read_text(encoding="utf-8"))
    assert [(row["a"], row["b"]) for row in document["pairs"]] == [("AR 1", "AR 2")]
    assert document["disclaimer"] == DISCLAIMER
    code, again = _build(watchlist)
    assert (code, again["pairs"][0]["outcome"]) == (0, "unchanged")
    assert len(git_log(repo)) == 2


def test_a_dry_run_says_it_would_write_and_writes_nothing(
    setup: tuple[Path, Path, Path],
) -> None:
    watchlist, _, repo = setup
    code, summary = _build(watchlist, "--dry-run")
    assert (code, summary["dry_run"], summary["pairs"][0]["outcome"]) == (
        0,
        True,
        "would_write",
    )
    assert not (repo / PATH).exists()
    assert len(git_log(repo)) == 1


def test_a_pair_naming_an_unwatched_act_or_one_with_no_text_is_a_counted_refusal(
    setup: tuple[Path, Path, Path],
) -> None:
    watchlist, store, _ = setup
    code, summary = _build(watchlist, "--pair", f"{MDR},{AI_ACT}")
    [refused] = summary["pairs"]
    assert (code, refused["outcome"]) == (0, "refused")
    assert AI_ACT in refused["detail"] and "watchlist" in refused["detail"]
    for path in (store / "eu" / IVDR).iterdir():
        path.unlink()
    code, summary = _build(watchlist)
    [refused] = summary["pairs"]
    assert (code, refused["outcome"]) == (0, "refused")
    assert "no stored version" in refused["detail"]


def test_the_text_summary_names_the_pair_and_carries_the_disclaimer(
    setup: tuple[Path, Path, Path],
) -> None:
    watchlist, _, _ = setup
    result = runner.invoke(app, ["twins", "build", "--watchlist", str(watchlist)])
    assert result.exit_code == 0
    assert f"{MDR} and {IVDR}: written {PATH}" in result.stderr
    assert result.stderr.strip().endswith(DISCLAIMER)


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--pair", f"{MDR}"], "two CELEX numbers"),
        (["--pair", f"{MDR},{MDR}"], "one act twice"),
        (["--text-store", "/nonexistent/store"], "is not a text store"),
    ],
)
def test_a_run_that_cannot_start_exits_two(
    setup: tuple[Path, Path, Path], flags: list[str], message: str
) -> None:
    watchlist, _, _ = setup
    result = runner.invoke(app, ["twins", "build", "--watchlist", str(watchlist), *flags])
    assert result.exit_code == 2
    assert message in result.stderr


def test_with_nothing_configured_the_command_refuses(tmp_path: Path) -> None:
    watchlist = tmp_path / "watchlist.toml"
    watchlist.write_text(f'[[acts]]\ncelex = "{MDR}"\n', encoding="utf-8")
    result = runner.invoke(app, ["twins", "build", "--watchlist", str(watchlist)])
    assert result.exit_code == 2
    assert "no text store is configured" in result.stderr
