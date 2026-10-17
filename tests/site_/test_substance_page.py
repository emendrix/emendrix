"""A substance page, the index of them and each act's list, built over the toy act's register.

The wording rule is the one held hardest here. A page says where a number appears, and its own
prose never says what the law makes of a substance: the forbidden words are checked on the page
with its verbatim rows removed, because a row the act prints may well say such things itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from helpers import text_of
from toy_substances import SITE_URL, substance_site

from emendrix import DISCLAIMER
from emendrix.site_.build import write_site
from emendrix.site_.markup import escape
from emendrix.site_.pages.substances_index import INDEX_LEAD, PER_PAGE, render_substances_index
from emendrix.site_.substance_inputs import Substance
from emendrix.site_.substance_words import cut_name, standing_note

STANDING_NOTE = (
    "Where CAS 50-00-0 appears: every table entry that prints it among its identifiers, in the "
    "newest version of each act this record holds, and every recorded change to those entries. "
    "Many entries name a group of substances and print no number, so absence here is not "
    "absence from the law. Not legal advice."
)
"""The standing note as fixed on 2026-10-16, its number filled in. Copied, never generated."""

FORBIDDEN = (
    "restricted",
    "banned",
    "prohibited",
    "permitted",
    "allowed",
    "approved",
    "authorised",
    "regulated",
    "compliant",
    "safe",
    "hazardous",
    "listed as",
    "classified as",
    "not found in",
    "not covered by",
)
"""What the substance surface never says about a substance, in its own words."""

_HREF = re.compile(r'href="([^"]+)"')


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("substances") / "site"
    write_site(out, substance_site(accounts=True))
    return out


def _page(site: Path, slug: str) -> str:
    return (site / "substances" / slug / "index.html").read_text(encoding="utf-8")


def _prose(page: str) -> str:
    """The page's own words: no verbatim rows, no head, no tags."""
    body = page.split('<main id="content">', 1)[1]
    body = re.sub(r"<table>.*?</table>", "", body, flags=re.DOTALL)
    return text_of(body)


def test_the_standing_note_is_the_fixed_text() -> None:
    assert standing_note(Substance(scheme="cas", value="50-00-0")) == STANDING_NOTE


def test_the_sections_come_in_their_fixed_order(built: Path) -> None:
    page = _page(built, "cas-toy-1")
    marks = [
        '<h1>CAS toy-1 <span class="sub">Alpha compound</span></h1>',
        '<p class="facts">CAS toy-1 · <a href="../../substances/ec-toy-e1/">EC toy-e1</a>',
        escape(standing_note(Substance(scheme="cas", value="toy-1"))),
        "Where it appears now</h2>",
        'id="lookup">Look up a number</h2>',
        "Its history</h2>",
        "Sources</h2>",
        "Watch this substance",
        escape(DISCLAIMER.split(": ", 1)[1]),
    ]
    places = [page.index(mark) for mark in marks]
    assert places == sorted(places)


def test_no_page_of_the_surface_says_what_the_law_makes_of_a_substance(built: Path) -> None:
    pages = sorted((built / "substances").rglob("index.html"))
    assert len(pages) == 8, "six numbers, the index and one act's list"
    for path in pages:
        prose = _prose(path.read_text(encoding="utf-8")).casefold()
        for word in FORBIDDEN:
            assert not re.search(rf"\b{word}\b", prose), (path, word)


def test_every_link_on_a_substance_page_reaches_a_page_or_a_block_the_build_wrote(
    built: Path,
) -> None:
    for path in sorted((built / "substances").rglob("index.html")):
        for href in _HREF.findall(path.read_text(encoding="utf-8")):
            href = href.replace("&amp;", "&")
            if href.startswith(("https://", "#")) or "account/" in href:
                continue
            target, _, fragment = href.partition("#")
            file = (path.parent / target).resolve()
            file = file / "index.html" if file.is_dir() else file
            assert file.is_file(), (path, href)
            if fragment:
                assert f'id="{fragment}"' in file.read_text(encoding="utf-8"), (path, href)


def test_the_last_change_and_the_history_link_the_change_block_on_its_event_page(
    built: Path,
) -> None:
    page = _page(built, "cas-toy-1")
    assert page.count('href="../../acts/house-rules/v2/#v2-an-i"') == 2
    assert 'href="../../acts/house-rules/an-i/">Annex I on this site</a>' in page
    assert "the act that change names" in page


def test_a_number_no_entry_prints_now_says_so_in_the_one_form_absence_takes(built: Path) -> None:
    page = _page(built, "cas-toy-9")
    assert "No entry in the newest versions the record holds prints this number" in page
    assert "removed" in page and "Gone compound" in page


def test_an_unkeyed_row_and_an_unchanged_entry_say_why_no_change_is_dated(built: Path) -> None:
    assert "This row carries no key, so no change to it is compared." in _page(built, "cas-toy-4")
    two = _page(built, "cas-toy-2")
    assert "No change to this entry since the first version the record holds, in force" in two


def test_a_duplicate_ec_page_is_canonical_to_its_cas_page_and_the_rest_to_themselves(
    built: Path,
) -> None:
    canonical = '<link rel="canonical" href="{}">'
    assert canonical.format(f"{SITE_URL}/substances/cas-toy-1/") in _page(built, "ec-toy-e1")
    assert canonical.format(f"{SITE_URL}/substances/ec-toy-e2/") in _page(built, "ec-toy-e2")
    assert canonical.format(f"{SITE_URL}/substances/cas-toy-1/") in _page(built, "cas-toy-1")


def test_the_watch_link_is_written_only_with_accounts(tmp_path: Path) -> None:
    write_site(tmp_path, substance_site())
    assert "account/watch" not in _page(tmp_path, "cas-toy-1")


def test_every_page_carries_the_disclaimer_and_asks_for_the_substance_index(built: Path) -> None:
    for path in sorted((built / "substances").rglob("index.html")):
        page = path.read_text(encoding="utf-8")
        assert escape(DISCLAIMER) in text_of(page), path
        assert " data-substances></div>" in page, path


def test_the_title_and_description_lead_with_the_number_and_where_it_appears(
    built: Path,
) -> None:
    page = _page(built, "cas-toy-1")
    assert ("<title>CAS toy-1 (Alpha compound): house-rules Annex I entry and every change") in page
    description = re.search(r'<meta name="description" content="([^"]+)"', page)
    assert description is not None
    assert description.group(1).startswith(
        "CAS toy-1, EC toy-e1 appears in 1 entry in the newest versions emendrix holds"
    )


def test_a_name_is_cut_at_its_first_semicolon_then_on_a_word_boundary() -> None:
    assert cut_name("Alpha compound; and its salts") == "Alpha compound"
    assert cut_name("Alpha (beta; gamma) and its salts") == "Alpha", "no half a bracket"
    assert cut_name("Alpha (beta) compound") == "Alpha (beta) compound"
    long = "word " * 20
    cut = cut_name(long)
    assert cut.endswith("…") and len(cut) <= 41 and " " not in cut[-2:]


def test_the_structured_data_is_a_trail_and_a_page_about_the_act(built: Path) -> None:
    page = _page(built, "cas-toy-1")
    types = re.findall(r'"@type": "(\w+)"', page)
    assert set(types) == {"BreadcrumbList", "ListItem", "WebPage", "Legislation"}
    assert '"hasPart"' in page and "dateModified" not in page


def test_the_index_counts_each_act_and_with_no_register_says_so() -> None:
    index = render_substances_index(substance_site())
    assert escape(INDEX_LEAD) in index
    assert "house-rules</a>: 4 CAS numbers and 2 EC numbers" in index
    empty = substance_site().model_copy(update={"substances": type(substance_site().substances)()})
    assert "No act in this build has a register" in render_substances_index(empty)


def test_an_act_list_names_every_number_it_prints_in_order(built: Path) -> None:
    listed = (built / "substances" / "acts" / "house-rules" / "index.html").read_text("utf-8")
    found = re.findall(r'href="\.\./\.\./\.\./substances/([^/]+)/"', listed)
    assert found == ["cas-toy-1", "cas-toy-2", "cas-toy-4", "cas-toy-9", "ec-toy-e1", "ec-toy-e2"]
    assert PER_PAGE == 2000
