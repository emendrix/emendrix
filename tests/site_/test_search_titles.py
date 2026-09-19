"""A provision's row in the search index carries its title, and the script shows and matches it.

A reader who knows the FIC Regulation's Annex II as the allergens annex types a word of its
subject, not its number, so a provision's row carries the title its page prints, decided by the
same rule. A row with nothing to add carries no `title` key, so no other row grows.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from site_entries import attributed_entry

from emendrix.core import ProvisionLocation, ProvisionText, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.assets import search_js
from emendrix.site_.inputs import collect_site
from emendrix.site_.search_index import search_index_json
from emendrix.site_.style import STYLE
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
OBSERVED = date(2026, 8, 9)
FIC_SUBJECT = "SUBSTANCES OR PRODUCTS CAUSING ALLERGIES OR INTOLERANCES"


def _entry() -> ChangelogEntry:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return diff_only_entry(compute_delta(before, after), detected_on=OBSERVED)


def _index(*entries: ChangelogEntry) -> str:
    run = EvalRun.model_validate_json(latest_report(REPO / "reports" / "eval").read_bytes())
    site = collect_site(generated_on=OBSERVED, run=run, report=Path("r.json"), entries=entries)
    return search_index_json(site)


def _rows(*entries: ChangelogEntry) -> list[dict[str, str]]:
    return list(json.loads(_index(*entries))["entries"])


def _provisions(*entries: ChangelogEntry) -> dict[str, dict[str, str]]:
    return {row["url"]: row for row in _rows(*entries) if row["kind"] == "provision"}


def _rewritten(entry: ChangelogEntry, canonical: str, **update: object) -> ChangelogEntry:
    """The entry with one change's stored fields replaced, the rest untouched."""
    changes = tuple(
        emitted.model_copy(update={"change": emitted.change.model_copy(update=update)})
        if emitted.change.location.canonical == canonical
        else emitted
        for emitted in entry.changes
    )
    return entry.model_copy(update={"changes": changes})


def test_a_heading_that_says_more_than_the_coordinate_is_the_row_s_title() -> None:
    """The toy stores a word for every provision it touches, and each row carries its own."""
    entry = _entry()
    titles = {row["label"].split(" — ")[0]: row["title"] for row in _provisions(entry).values()}
    assert titles == {
        emitted.change.location.human: emitted.change.heading for emitted in entry.changes
    }


def test_an_annex_titled_only_by_its_number_takes_the_subject_its_text_opens_with() -> None:
    """The FIC shape: `ANNEX I` as the heading, the subject on the stored text's second line."""
    text = ProvisionText(f"ANNEX I\n{FIC_SUBJECT}\n1. Cereals containing gluten")
    entry = _rewritten(_entry(), "AN I", heading="ANNEX I", after=text)
    titles = [row.get("title") for row in _provisions(entry).values()]
    assert FIC_SUBJECT in titles
    assert "ANNEX I" not in titles


def test_a_bare_heading_leaves_no_title_key_in_the_bytes() -> None:
    """An article whose heading only repeats its coordinate has nothing to add, so no key."""
    human = ProvisionLocation.parse("AR 2").human
    entry = _rewritten(_entry(), "AR 2", heading=human)
    bare = [row for row in _provisions(entry).values() if row["label"].startswith(f"{human} — ")]
    assert len(bare) == 1
    assert set(bare[0]) == {"kind", "label", "url"}


def test_acts_aliases_and_amending_acts_carry_no_title_key() -> None:
    """Only a provision has a title here; an act's official title stays out of the index."""
    rows = _rows(attributed_entry())
    others = [row for row in rows if row["kind"] != "provision"]
    assert {row["kind"] for row in others} >= {"act", "amending"}
    assert all(set(row) == {"kind", "label", "url"} for row in others)
    assert '"title":""' not in _index(attributed_entry())


def test_the_script_ranks_every_label_match_above_every_title_match() -> None:
    """A label match scores 0, 1 or in [2, 3); a title-only match scores in [4, 5).

    There is no JavaScript runtime in this suite and none is added, so this reads the source.
    """
    script = search_js()
    body = script.split("function score(entry, query) {")[1].split("\n  }\n")[0]
    assert "return 2 + at / label.length;" in body
    assert 'var title = (entry.title || "").toLowerCase();' in body
    assert "return at < 0 ? -1 : 4 + at / title.length;" in body
    assert body.index("label.indexOf(query)") < body.index("title.indexOf(query)")


def test_the_script_prints_the_title_as_text_between_the_label_and_the_kind() -> None:
    """The law's words go in as text, never markup, with a space on each side so the row's
    accessible name reads label, title, kind as three words and not one run."""
    script = search_js()
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script
    body = script.split("function render(matches, searched) {")[1]
    assert 'link.textContent = entry.label + " ";' in body
    assert "title.textContent = entry.title;" in body
    assert 'link.appendChild(document.createTextNode(" "));' in body
    assert body.index("link.appendChild(title);") < body.index("link.appendChild(kind);")
    assert '"ttl ttl--caps" : "ttl"' in body


def test_the_sheet_keeps_a_result_s_title_to_one_muted_line() -> None:
    """Clipped by the sheet alone: the whole title stays in the DOM and the accessible name."""
    block = STYLE.split("#search .results .ttl {")[1].split("}")[0]
    for declaration in ("white-space: nowrap", "text-overflow: ellipsis", "var(--muted)"):
        assert declaration in block, declaration
    assert ".ttl--caps {" in STYLE
