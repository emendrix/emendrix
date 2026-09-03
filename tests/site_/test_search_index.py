"""The prebuilt index: acts, aliases, identifiers and touched provisions only."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from emendrix.core import ProvisionLocation, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.assets import search_js
from emendrix.site_.build import act_pages
from emendrix.site_.inputs import collect_site
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
    assert all(item["url"].startswith(f"acts/{site.acts[0].slug}/") for item in provisions)


def test_a_provision_with_no_number_is_labelled_by_its_word() -> None:
    """A change keyed to a whole annex is `Annex — <act>` in the index, never `AN — <act>`.

    The label is the only place a location's display form reaches a reader with no surrounding
    page to explain it, and the live index carried two rows reading `AN — …` until 2026-09-03.
    The change is relocated rather than authored, so the toy's own text and anchors still hold.
    """
    entry = _entry()
    emitted = entry.changes[0]
    change = emitted.change
    provision = change.provision.model_copy(update={"location": ProvisionLocation.parse("AN")})
    relocated = emitted.model_copy(
        update={"change": change.model_copy(update={"provision": provision})}
    )
    moved = entry.model_copy(update={"changes": (relocated, *entry.changes[1:])})
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(moved,))
    labels = [
        item["label"]
        for item in json.loads(search_index_json(site))["entries"]
        if item["kind"] == "provision"
    ]
    assert any(label.startswith("Annex — ") for label in labels), labels
    assert not any(label.startswith("AN — ") for label in labels), labels


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


def _indexed(watched: dict[str, object]) -> list[dict[str, str]]:
    watchlist = Watchlist.model_validate({"acts": [watched]})
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    return list(json.loads(search_index_json(site))["entries"])


def test_a_long_name_is_found_as_an_alias_and_lands_on_the_act_page() -> None:
    """To a search the long form is one more name the act answers to, not a second act."""
    entries = _indexed(
        {
            "celex": "32016R0679",
            "name": "GDPR",
            "long_name": "General Data Protection Regulation",
        }
    )
    rows = [item for item in entries if item["label"] == "General Data Protection Regulation"]
    assert rows == [
        {"kind": "alias", "label": "General Data Protection Regulation", "url": "acts/32016R0679/"}
    ]


def test_a_long_name_already_among_the_aliases_is_indexed_once() -> None:
    """The shipped example lists the AI Act's long form as an alias too; one row, not two."""
    entries = _indexed(
        {
            "celex": "32024R1689",
            "name": "AI Act",
            "long_name": "Artificial Intelligence Act",
            "aliases": ["Artificial Intelligence Act"],
        }
    )
    assert sum(item["label"] == "Artificial Intelligence Act" for item in entries) == 1


def test_provision_urls_are_the_provision_pages_the_tree_writes() -> None:
    """A provision row lands on that coordinate's own page, not on one arbitrary event.

    Checked against the builder's own slice rather than against a reconstruction of the path,
    which is what makes the row and the file agree by construction: a search hit that names a
    page nothing wrote is the sort of defect nobody reports, and it was the shape of the URLs
    these rows carried until the provision pages existed.
    """
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    act = site.acts[0]
    pages = act_pages(site, act)
    payload = json.loads(search_index_json(site))
    found = 0
    for item in payload["entries"]:
        if item["kind"] == "provision":
            assert "#" not in item["url"], item["url"]
            assert f"{item['url']}index.html" in pages, item["url"]
            found += 1
    assert found


def test_an_amending_instrument_is_one_row_under_its_name_and_one_under_its_key() -> None:
    """A reader who types the short name and one who types the identifier reach one page.

    The toy instrument has neither a declared label nor a rendered number, so its name *is*
    its key and the second row would say the same string twice; the branch that adds it is
    exercised by giving the mapping a number, which is what a CELEX yields on the live site.
    The rows come back in the index's own order, by folded label, so the identifier's row
    precedes the number's here rather than following it.
    """
    from site_entries import attributed_entry

    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(attributed_entry(),)
    )
    rows = [
        item
        for item in json.loads(search_index_json(site))["entries"]
        if item["url"].startswith("amendments/")
    ]
    assert rows == [
        {
            "kind": "amending",
            "label": "house-rules-amendment-1",
            "url": "amendments/house-rules-amendment-1/",
        }
    ]
    numbered = site.model_copy(
        update={
            "amending": {
                key: act.model_copy(update={"number": "Regulation (EU) 2026/1"})
                for key, act in site.amending.items()
            }
        }
    )
    rows = [
        item
        for item in json.loads(search_index_json(numbered))["entries"]
        if item["url"].startswith("amendments/")
    ]
    assert [(item["kind"], item["label"]) for item in rows] == [
        ("celex", "house-rules-amendment-1"),
        ("amending", "Regulation (EU) 2026/1"),
    ]


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
