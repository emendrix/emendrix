"""The half of the API the site writes: the catalogue, the schemas, and nothing of the record.

Walked over built trees, because what the catalogue promises is a relationship between its
addresses and the files the same build wrote: an address that names no page is worse than no
catalogue at all, since the hosted MCP server hands those addresses to a model as permalinks.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
from helpers import REPO, REPORTS, SITE_URL, WATCHLIST, build, runner

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.output import ChangelogEntry
from emendrix.output.schemas import SUFFIX, schema_document, schema_documents
from emendrix.site_.api_files import CATALOGUE, PROVENANCE, Catalogue
from eu_pins import OBSERVED_ON

SCHEMA_DIR = REPO / "docs" / "schema"

_REGENERATE = (
    "uv run python -c 'from pathlib import Path; from emendrix.site_.api_files import Catalogue; "
    "from emendrix.output.schemas import schema_document; "
    'Path("docs/schema/catalogue.schema.json").write_text('
    'schema_document("catalogue", Catalogue), encoding="utf-8")\''
)


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("api") / "site", changelog_repo)


def _catalogue(site: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((site / CATALOGUE).read_text(encoding="utf-8"))
    return loaded


def _entries(repo: Path) -> list[ChangelogEntry]:
    payloads = sorted(repo.glob("*/*/changes/*.json"))
    assert payloads
    return [ChangelogEntry.model_validate_json(path.read_bytes()) for path in payloads]


def _page(site: Path, url: str) -> Path:
    assert url.startswith(f"{SITE_URL}/"), url
    return site / url.removeprefix(f"{SITE_URL}/") / "index.html"


def test_the_catalogue_lists_every_watched_act_sorted_quiet_ones_included(site: Path) -> None:
    catalogue = _catalogue(site)
    assert catalogue["catalogue_schema"] == "1.0"
    assert catalogue["disclaimer"] == DISCLAIMER
    assert catalogue["provenance"] == PROVENANCE
    acts = catalogue["acts"]
    keys = [(act["corpus"], act["key"]) for act in acts]
    assert keys == sorted(keys)
    watched = tomllib.loads(WATCHLIST.read_text(encoding="utf-8"))["acts"]
    assert {key for _, key in keys} == {act["celex"] for act in watched}
    assert any(not act["events"] and not act["provisions"] for act in acts), "no quiet act"
    Catalogue.model_validate(catalogue)


def test_every_address_names_a_page_or_feed_the_same_build_wrote(site: Path) -> None:
    for act in _catalogue(site)["acts"]:
        assert _page(site, act["url"]).is_file(), act["url"]
        assert (site / act["feed"].removeprefix(f"{SITE_URL}/")).is_file(), act["feed"]
        for url in (*act["provisions"].values(), *act["events"].values()):
            assert _page(site, url).is_file(), url


def test_one_provision_per_touched_location_and_one_event_per_entry(
    site: Path, changelog_repo: Path
) -> None:
    entries = _entries(changelog_repo)
    rows = {act["key"]: act for act in _catalogue(site)["acts"]}
    for key in {entry.act.key for entry in entries}:
        mine = [entry for entry in entries if entry.act.key == key]
        touched = {emitted.change.location.canonical for entry in mine for emitted in entry.changes}
        assert set(rows[key]["provisions"]) == touched
        assert set(rows[key]["events"]) == {entry.key for entry in mine}
    assert "AN I" not in rows["32017R0745"]["provisions"], "an untouched annex has no page"


def test_the_api_files_are_byte_identical_across_two_builds(
    tmp_path: Path, changelog_repo: Path
) -> None:
    first = build(tmp_path / "one", changelog_repo)
    second = build(tmp_path / "two", changelog_repo)
    written = sorted(path.relative_to(first) for path in (first / "api").rglob("*.json"))
    assert written
    for name in written:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_every_schema_the_site_writes_is_the_committed_file(site: Path) -> None:
    written = sorted((site / "api" / "v1" / "schema").iterdir())
    expected = {*schema_documents(), f"catalogue{SUFFIX}"}
    assert {path.name for path in written} == expected
    for path in written:
        assert path.read_bytes() == (SCHEMA_DIR / path.name).read_bytes(), path.name


def test_the_committed_catalogue_schema_is_what_the_model_generates() -> None:
    committed = (SCHEMA_DIR / f"catalogue{SUFFIX}").read_text(encoding="utf-8")
    assert committed == schema_document("catalogue", Catalogue), (
        f"docs/schema/catalogue{SUFFIX} differs from the model; if the change is intended, run "
        f"`{_REGENERATE}` from the repository root and read the diff"
    )


def test_the_site_writes_nothing_of_the_record(site: Path) -> None:
    """The record is served from the changelogs volume; a copy here would shadow it or go stale."""
    under = sorted(
        path.relative_to(site / "api" / "v1").as_posix()
        for path in (site / "api" / "v1").rglob("*")
    )
    assert not (site / "api" / "v1" / "index.json").exists()
    assert all(name == "catalogue.json" or name.startswith("schema") for name in under), under


def test_without_a_site_url_addresses_are_relative_and_no_feed_is_named(
    tmp_path: Path, changelog_repo: Path
) -> None:
    out = tmp_path / "site"
    arguments = [
        "site",
        "build",
        "--out",
        str(out),
        "--report-dir",
        str(REPORTS),
        "--watchlist",
        str(WATCHLIST),
        "--generated-on",
        OBSERVED_ON.isoformat(),
        "--changelogs",
        str(changelog_repo),
    ]
    result = runner.invoke(app, arguments, env={"EMENDRIX_OUTPUT_REPO": ""})
    assert result.exit_code == 0, result.output
    for act in _catalogue(out)["acts"]:
        assert act["feed"] is None
        for url in (act["url"], *act["provisions"].values(), *act["events"].values()):
            assert not url.startswith("https://"), url
            assert (out / url / "index.html").is_file(), url
