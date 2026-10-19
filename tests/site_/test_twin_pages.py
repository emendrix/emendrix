"""The twin pages, the pair index and the twins index, over the real MDR/IVDR map.

The map is built from the pinned 20250110 consolidations of both acts and committed into a copy
of the changelog repository, as `twins build` would commit it; the site is built over that copy
by the shipped command. The full-text checks read the same two fixtures through the adapter, so
"no page carries a unit's text" is asserted against the text the map was computed from.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from helpers import build, text_of, twinned
from site_entries import attributed_entry
from toy_twins import pair, sister_of, toy_map, toy_site

from emendrix import DISCLAIMER
from emendrix.core import ActId, ProvisionTree, VersionId
from emendrix.session import adapter_for
from emendrix.site_.markup import escape
from emendrix.site_.pages.twin import WITHHELD, render_twin_page
from emendrix.site_.twin_inputs import TwinMaps
from emendrix.site_.twin_model import twin_views
from emendrix.site_.twin_note import SIMILAR
from emendrix.twins.model import Passage, TwinMap, TwinPair
from emendrix.twins.passages import CUT, MAX_PASSAGES, PASSAGE_CHARS
from eu_pins import FIXTURE_DIR, IVDR, IVDR_TWIN, MDR, MDR_TWIN, OBSERVED_ON

PAIR = "eu-32017R0745--eu-32017R0746"


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return twinned(changelog_repo, tmp_path_factory.mktemp("twin-repo"))


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("twin-pages") / "site", repo)


@pytest.fixture(scope="module")
def document(repo: Path) -> TwinMap:
    return TwinMap.model_validate_json((repo / "twins" / f"{PAIR}.json").read_bytes())


@pytest.fixture(scope="module")
def trees() -> tuple[ProvisionTree, ProvisionTree]:
    found: list[ProvisionTree] = []
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        for key, version in ((MDR, MDR_TWIN), (IVDR, IVDR_TWIN)):
            fetched = adapter.fetch_version(ActId(corpus="eu", key=key), VersionId(version))
            assert isinstance(fetched, ProvisionTree), fetched
            found.append(fetched)
    return found[0], found[1]


def _pages(site: Path) -> dict[str, str]:
    under = site / "twins" / PAIR
    return {
        path.parent.name: path.read_text(encoding="utf-8")
        for path in sorted(under.glob("*/index.html"))
    }


def _slug(canonical: str) -> str:
    return canonical.lower().replace(" ", "-")


def test_a_page_per_non_identical_pair_and_none_for_the_identical_one(
    site: Path, document: TwinMap
) -> None:
    pages = _pages(site)
    expected = {_slug(one.a) for one in document.pairs if not one.identical}
    assert set(pages) == expected
    assert len(pages) == 84
    assert [one.a for one in document.pairs if one.identical] == ["AR 12"]
    index = (site / "twins" / PAIR / "index.html").read_text(encoding="utf-8")
    assert "Medical Devices Regulation Art. 12 and IVDR Art. 12 · identical text" in text_of(index)
    assert "ar-12/" not in index


def test_the_title_and_description_name_both_acts_and_both_coordinates(site: Path) -> None:
    page = _pages(site)["ar-10"]
    assert (
        "<title>Medical Devices Regulation Art. 10 and IVDR Art. 10: where the texts differ" in page
    )
    (description,) = re.findall(r'<meta name="description" content="([^"]*)">', page)
    assert "Medical Devices Regulation Art. 10" in description
    assert "IVDR Art. 10" in description
    assert SIMILAR in description
    assert '<link rel="canonical" href="https://example.invalid/site/twins/' in page
    assert "noindex" not in page


def _rows(page: str) -> list[list[str]]:
    body = page[page.index("<tbody") : page.index("</tbody>")] if "<tbody" in page else ""
    return [
        [text_of(cell) for cell in re.findall(r'<p class="diff">(.*?)</p>', row)]
        for row in re.findall(r"<tr role=\"row\">(.*?)</tr>", body)
    ]


def test_the_passage_table_obeys_the_caps(site: Path, document: TwinMap) -> None:
    pages = _pages(site)
    for one in document.pairs:
        if one.identical:
            continue
        page = pages[_slug(one.a)]
        rows = _rows(page)
        if one.passages_withheld:
            assert rows == [], one.a
            continue
        assert 0 < len(rows) <= MAX_PASSAGES, one.a
        assert len(rows) == len(one.passages)
        for row in rows:
            assert len(row) == 2
            for side in row:
                assert len(side) <= PASSAGE_CHARS + len(CUT), (one.a, side)
        if one.passages_omitted:
            assert f"{one.passages_omitted} more passage" in text_of(page)


def test_a_withheld_pair_says_so_and_shows_no_passage(site: Path, document: TwinMap) -> None:
    withheld = [one for one in document.pairs if one.passages_withheld]
    assert len(withheld) == 32
    for one in withheld:
        page = _pages(site)[_slug(one.a)]
        assert escape(WITHHELD) in page
        assert '<p class="diff">' not in page


def test_no_twin_page_carries_either_units_full_text(
    site: Path, document: TwinMap, trees: tuple[ProvisionTree, ProvisionTree]
) -> None:
    mdr, ivdr = trees
    pages = _pages(site)
    checked = 0
    for one in document.pairs:
        if one.identical:
            continue
        page = text_of(pages[_slug(one.a)])
        for tree, unit in ((mdr, one.a), (ivdr, one.b)):
            node = tree.find(unit)
            assert node is not None
            text = str(node.comparison_text)
            assert escape(text) not in page, unit
            for start in range(0, max(1, len(text) - 1000), 250):
                window = text[start : start + 1000]
                if len(window) == 1000:
                    assert escape(window) not in page, (unit, start)
                    checked += 1
    assert checked > 100


def test_every_twin_page_links_both_units_on_eur_lex_and_carries_the_disclaimer(
    site: Path,
) -> None:
    for slug, page in _pages(site).items():
        assert page.count("https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:") >= 2
        assert "CELEX:02017R0745-20250110#" in page, slug
        assert "CELEX:02017R0746-20250110#" in page, slug
        assert escape(DISCLAIMER) in text_of(page), slug
        assert SIMILAR in text_of(page), slug
    for index in (site / "twins" / "index.html", site / "twins" / PAIR / "index.html"):
        page = index.read_text(encoding="utf-8")
        assert escape(DISCLAIMER) in text_of(page)
        assert SIMILAR in text_of(page)


def test_the_pair_index_lists_every_pair_in_order_and_the_unpaired_units(
    site: Path, document: TwinMap
) -> None:
    index = (site / "twins" / PAIR / "index.html").read_text(encoding="utf-8")
    positions = [index.index(f"{_slug(one.a)}/") for one in document.pairs if not one.identical]
    assert positions == sorted(positions)
    words = text_of(index)
    assert "56 provisions of Medical Devices Regulation with no twin in IVDR" in words
    assert "44 provisions of IVDR with no twin in Medical Devices Regulation" in words
    assert f"../../api/v1/twins/{PAIR}.json" in index


def test_both_act_pages_link_their_pair_index_and_the_twins_index_lists_the_pair(
    site: Path,
) -> None:
    mdr = (site / "acts" / MDR / "index.html").read_text(encoding="utf-8")
    ivdr = (site / "acts" / IVDR / "index.html").read_text(encoding="utf-8")
    assert f'<a href="../../twins/{PAIR}/">Textual twins in IVDR</a>' in mdr
    assert f'<a href="../../twins/{PAIR}/">Textual twins in Medical Devices Regulation</a>' in ivdr
    other = (site / "acts" / "32024R1689" / "index.html").read_text(encoding="utf-8")
    assert "twins/" not in other
    twins = (site / "twins" / "index.html").read_text(encoding="utf-8")
    assert f'href="../twins/{PAIR}/"' in twins


def test_the_note_and_the_provision_line_link_the_twin_page(site: Path) -> None:
    href = f"../../../twins/{PAIR}/ar-113/"
    event = (site / "acts" / MDR / "02017R0745-20200424" / "index.html").read_text("utf-8")
    provision = (site / "acts" / MDR / "ar-113" / "index.html").read_text(encoding="utf-8")
    assert f'<a href="{href}">See where the two texts differ</a>' in event
    assert f'<a href="{href}">See where the two texts differ</a>' in provision
    assert (site / "twins" / PAIR / "ar-113" / "index.html").is_file()


def test_no_twin_file_is_written_without_a_map(tmp_path: Path, changelog_repo: Path) -> None:
    bare = build(tmp_path / "site", changelog_repo)
    assert not (bare / "twins").exists()
    assert not (bare / "api" / "v1" / "twins").exists()


def test_a_page_lists_both_units_changes_newest_first_with_links_to_their_versions() -> None:
    entry = attributed_entry()
    site = toy_site(entry, sister_of(entry), maps=TwinMaps(maps=(toy_map(pair("AR 2", "AR 2")),)))
    (view,) = twin_views(site)
    (shown,) = view.pages
    assert [change.act.act.key for change in shown.changes] == ["house-rules", "house-rules-sister"]
    page = render_twin_page(site, view, shown)
    assert "Changes since the texts were paired" in page
    assert page.count(f"/{entry.key}/#") == 2


def _toy_page(one: TwinPair) -> str:
    entry = attributed_entry()
    site = toy_site(entry, sister_of(entry), maps=TwinMaps(maps=(toy_map(one),)))
    (view,) = twin_views(site)
    return render_twin_page(site, view, view.pages[0])


def test_a_cut_side_is_marked_and_the_passages_beyond_the_cap_are_counted() -> None:
    cut = Passage(a="a" * PASSAGE_CHARS + CUT, b="", cut=True)
    one = pair("AR 2", "AR 2").model_copy(update={"passages": (cut,), "passages_omitted": 3})
    page = _toy_page(one)
    assert f'{"a" * PASSAGE_CHARS}<span class="elided">{CUT}</span>' in page
    assert '<span class="elided">no words</span>' in page
    assert "3 more passages not shown" in text_of(page)


def test_a_withheld_pair_renders_the_sentence_and_no_passage() -> None:
    page = _toy_page(pair("AR 2", "AR 2").model_copy(update={"passages_withheld": True}))
    assert escape(WITHHELD) in page
    assert '<p class="diff">' not in page
