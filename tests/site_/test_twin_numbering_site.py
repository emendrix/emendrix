"""A pair whose texts differ in numbering alone is shown as an identical pair is.

It has no twin page and no line in the twins sitemap, its line on the pair index is unlinked
and says why, and the note and the provision line say `identical text apart from numbering`
under the `textually similar` gloss, with no link to a page that does not exist.
"""

from __future__ import annotations

from helpers import text_of
from site_entries import attributed_entry
from toy_twins import pair, sister_of, toy_map, toy_site

from emendrix.site_.inputs import SiteInputs
from emendrix.site_.pages.twins_index import render_twin_pair
from emendrix.site_.twin_inputs import TwinMaps
from emendrix.site_.twin_model import twin_views
from emendrix.site_.twin_note import COMPARE, RENUMBERED, SIMILAR, twin_line, twin_note
from emendrix.site_.twin_pages import twin_pages
from emendrix.site_.twin_sitemap import twin_entries
from toy_corpus import HOUSE_RULES

ROOT = "../../../"


def _site() -> SiteInputs:
    entry = attributed_entry()
    renumbered = pair(
        "AR 2", "AR 9", 0.97, numbering_only=True, children=(("AR 2 PA 1", "AR 9 PA 1", 0.95),)
    )
    differs = pair("AN I", "AN I", 0.93)
    maps = TwinMaps(maps=(toy_map(renumbered, differs),))
    return toy_site(entry, sister_of(entry), maps=maps)


def test_a_numbering_only_pair_has_no_page_and_no_sitemap_line() -> None:
    site = _site()
    (view,) = twin_views(site)
    assert [shown.pair.a for shown in view.pages] == ["AN I"]
    files = twin_pages(site)
    assert not any(path.endswith("/ar-2/index.html") for path in files)
    assert any(path.endswith("/an-i/index.html") for path in files)
    listed = [path for path, _ in twin_entries(site)]
    assert not any(path.endswith("/ar-2/") for path in listed)
    assert any(path.endswith("/an-i/") for path in listed)


def test_the_pair_index_lists_it_unlinked_and_says_why() -> None:
    site = _site()
    (view,) = twin_views(site)
    index = render_twin_pair(site, view)
    words = text_of(index)
    assert f"house-rules Art. 2 and house-rules-sister Art. 9 · {RENUMBERED}" in words
    assert "2 pairs of provisions, 0 with identical text, 1 with identical text apart" in words
    assert 'ar-2/"' not in index


def test_the_note_and_the_line_say_identical_apart_from_numbering_with_no_compare_link() -> None:
    site = _site()
    act = next(item for item in site.acts if item.act == HOUSE_RULES)
    entry = attributed_entry()
    (emitted,) = [e for e in entry.changes if e.change.location.canonical == "AR 2"]
    (note,) = twin_note(site, act, entry, emitted, ROOT)
    (line,) = twin_line(site, act, "AR 2", ROOT)
    for said in (note, line):
        words = text_of(said)
        assert f"{SIMILAR} ({RENUMBERED})" in words, words
        assert COMPARE not in words
        assert "twins/" not in said
