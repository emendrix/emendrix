"""`emendrix texts build|show` over the pinned MDR fixtures, and the command's refusals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.core import ProvisionTree, VersionId
from emendrix.eu.identifiers import Celex, act_id
from emendrix.session import adapter_for
from emendrix.texts.config import TEXT_STORE_ENV
from eu_pins import FIXTURE_DIR, MDR, OBSERVED_ON

runner = CliRunner()

MDR_LATEST = "02017R0745-20260101"
MDR_CONSOLIDATIONS = (
    "02017R0745-20170505",
    "02017R0745-20200424",
    "02017R0745-20230311",
    "02017R0745-20230320",
    "02017R0745-20240709",
    "02017R0745-20250110",
    MDR_LATEST,
)


def _watchlist(tmp_path: Path, extra: str = "") -> Path:
    path = tmp_path / "watchlist.toml"
    path.write_text(f'[[acts]]\ncelex = "{MDR}"\n{extra}', encoding="utf-8")
    return path


def _build(watchlist: Path, *flags: str) -> list[str]:
    return [
        "texts",
        "build",
        "--watchlist",
        str(watchlist),
        "--fixture-dir",
        str(FIXTURE_DIR),
        "--observed-on",
        OBSERVED_ON.isoformat(),
        *flags,
    ]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    """One build of the whole MDR fixture set, shared: it is the slowest thing here."""
    root = tmp_path_factory.mktemp("texts")
    store = root / "store"
    result = runner.invoke(
        app,
        _build(_watchlist(root), "--act", MDR, "--text-store", str(store), "--summary", "json"),
    )
    assert result.exit_code == 0, result.output
    return store, json.loads(result.stderr.strip().splitlines()[-1])


def test_a_build_stores_every_version_the_fixtures_answer(
    built: tuple[Path, dict[str, object]],
) -> None:
    store, summary = built
    total = summary["total"]
    assert isinstance(total, dict)
    # The tree notice lists the OJ text and the seven consolidations, and every one is pinned.
    assert (total["listed"], total["written"], total["fetch_failed"], total["states"]) == (
        8,
        8,
        0,
        {},
    )
    names = sorted(path.name for path in (store / "eu" / MDR).iterdir())
    assert names == sorted([f"{version}.jsonl.gz" for version in (*MDR_CONSOLIDATIONS, MDR)])


def test_a_second_build_writes_nothing_and_says_so(
    tmp_path: Path, built: tuple[Path, dict[str, object]]
) -> None:
    store, _ = built
    result = runner.invoke(app, _build(_watchlist(tmp_path), "--text-store", str(store)))
    assert result.exit_code == 0, result.output
    assert "8 already stored · 0 written" in result.stderr
    assert "wrote nothing" in result.stderr


def test_show_prints_a_units_text_verbatim(built: tuple[Path, dict[str, object]]) -> None:
    store, _ = built
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        tree = adapter.fetch_version(act_id(Celex.parse(MDR)), VersionId(MDR_LATEST))
    assert isinstance(tree, ProvisionTree)
    node = tree.find("AR 10 PA 9")
    assert node is not None
    result = runner.invoke(
        app, ["texts", "show", MDR, MDR_LATEST, "AR 10 PA 9", "--text-store", str(store)]
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == node.text + "\n"
    assert DISCLAIMER in result.stderr


def test_show_lists_the_units_of_a_stored_version(built: tuple[Path, dict[str, object]]) -> None:
    store, _ = built
    result = runner.invoke(app, ["texts", "show", MDR, MDR_LATEST, "--text-store", str(store)])
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0].startswith(f"{MDR} {MDR_LATEST} (served {MDR_LATEST})")
    assert lines[1].startswith("AR 1")


def test_show_refuses_a_version_the_store_lacks(built: tuple[Path, dict[str, object]]) -> None:
    store, _ = built
    result = runner.invoke(
        app, ["texts", "show", MDR, "02017R0745-20990101", "--text-store", str(store)]
    )
    assert result.exit_code == 2
    assert "not in the store" in result.stderr


def test_no_store_configured_exits_2_with_the_three_ways_to_configure_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TEXT_STORE_ENV, raising=False)
    result = runner.invoke(app, _build(_watchlist(tmp_path)))
    assert result.exit_code == 2
    assert f"give --text-store, set {TEXT_STORE_ENV} or set [output] text_store_path" in (
        result.stderr
    )


def test_the_watchlist_and_the_environment_name_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "from-file"
    watchlist = _watchlist(tmp_path, f'[output]\ntext_store_path = "{configured}"\n')
    monkeypatch.delenv(TEXT_STORE_ENV, raising=False)
    result = runner.invoke(app, _build(watchlist, "--dry-run"))
    assert result.exit_code == 0, result.output
    assert f"store {configured}" in result.stderr
    assert "dry run: 8 versions would be fetched." in result.stderr
    assert not configured.exists(), "a dry run creates nothing"
    from_env = tmp_path / "from-env"
    monkeypatch.setenv(TEXT_STORE_ENV, str(from_env))
    result = runner.invoke(app, _build(watchlist, "--dry-run"))
    assert f"store {from_env}" in result.stderr


def test_a_store_inside_the_repository_exits_2(tmp_path: Path) -> None:
    inside = Path(__file__).resolve().parents[2] / "texts-store-refused"
    result = runner.invoke(app, _build(_watchlist(tmp_path), "--text-store", str(inside)))
    assert result.exit_code == 2
    assert "inside the git working tree" in result.stderr
    assert not inside.exists()


def test_an_act_not_on_the_watchlist_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        _build(_watchlist(tmp_path), "--act", "32024R1689", "--text-store", str(tmp_path / "s")),
    )
    assert result.exit_code == 2
    assert "not on the watchlist" in result.stderr
