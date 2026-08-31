"""The prebuilt index: acts, aliases, identifiers and touched provisions only."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from emendrix.core import ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.assets import search_js
from emendrix.site_.inputs import collect_site
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.search_index import search_index_json
from emendrix.watch.config import Watchlist
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _entry() -> ChangelogEntry:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return diff_only_entry(compute_delta(before, after), detected_on=OBSERVED)


def test_acts_aliases_and_touched_provisions_are_in_the_index() -> None:
    entry = _entry()
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(entry,))
    payload = json.loads(search_index_json(site))
    kinds = {item["kind"] for item in payload["entries"]}
    assert "act" in kinds and "provision" in kinds
    provisions = [item for item in payload["entries"] if item["kind"] == "provision"]
    touched = {emitted.change.location.canonical for emitted in entry.changes}
    assert len(provisions) == len(touched)
    assert all("#" in item["url"] for item in provisions)


def test_an_alias_finds_the_same_page_as_the_name() -> None:
    watchlist = Watchlist.model_validate(
        {
            "acts": [
                {
                    "celex": "32016R0679",
                    "name": "GDPR",
                    "aliases": ["Data Protection Regulation"],
                }
            ]
        }
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    payload = json.loads(search_index_json(site))
    urls = {item["label"]: item["url"] for item in payload["entries"]}
    assert urls["GDPR"] == urls["Data Protection Regulation"] == "acts/32016R0679/"
    assert urls["32016R0679"] == "acts/32016R0679/"


def test_provision_urls_are_the_anchors_the_event_page_publishes() -> None:
    """The index may not recount occurrences: it reads the event page's own anchor scheme,
    and it points at the page that holds the change rather than at the act's timeline."""
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    act = site.acts[0]
    pages = {
        f"acts/{act.slug}/{entry.key}/": render_event_page(site, act, entry)
        for entry in act.entries
    }
    payload = json.loads(search_index_json(site))
    for item in payload["entries"]:
        if item["kind"] == "provision":
            path, _, anchor = item["url"].partition("#")
            assert path in pages, item["url"]
            assert f'id="{anchor}"' in pages[path]


def test_the_index_bytes_are_deterministic() -> None:
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    assert search_index_json(site) == search_index_json(site)
    assert search_index_json(site).endswith("\n")


def test_the_script_ships_exactly_as_committed() -> None:
    """The asset is read back, not rebuilt, so the reviewed file is the shipped file.

    The cookie check is on the API rather than on the word: the script's own header says it
    sets no cookies, and what makes that true is that `document.cookie` never appears.
    """
    script = search_js()
    assert "search-index.json" in script
    assert "document.cookie" not in script


def test_the_script_reaches_no_third_party() -> None:
    """The methodology page promises the only outward links go to EUR-Lex. Hold it to that."""
    script = search_js()
    assert "https://" not in script and "http://" not in script
    assert "localStorage" not in script and "XMLHttpRequest" not in script
