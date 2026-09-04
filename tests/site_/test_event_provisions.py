"""What a change block is on the page, and the index a long page opens with.

A sibling of `test_event_page.py` rather than a tail on it: that module holds the honesty
markers a block may never lose (anchor, disagreement, provenance, a stated reason), and this
one holds the block's shape, a heading per provision with the applies line outside it, the
size of the difference that heading prints, and the in-page index that lists every block by the
anchor it carries. Each module builds its own toy page, as every site test module does, so a
scoped run of either stands on its own.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from site_entries import untouched_entry

from emendrix.core import Delta, ProvisionLocation, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.graph.report import EmittedChange
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.magnitude import magnitude_html, weight_class
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.event_index import INDEX_ABOVE
from emendrix.site_.pages.texts import RenderedText, text_blocks
from emendrix.site_.urls import location_slug
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)

_INDEX = re.compile(r'<nav class="touched".*?</nav>', re.DOTALL)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _site(*entries: ChangelogEntry) -> SiteInputs:
    return collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries)


def _page(entry: ChangelogEntry) -> str:
    site = _site(entry)
    entry = site.acts[0].entries[0]
    return render_event_page(site, site.acts[0], entry, text_blocks(entry))


def _entry() -> ChangelogEntry:
    return diff_only_entry(_delta(), detected_on=OBSERVED)


def _many(entry: ChangelogEntry, n: int) -> ChangelogEntry:
    """The toy entry's first change at `n` coordinates, moved the way the scale test moves
    them, with its own coordinate kept first and last so the anchors carry a `-2` suffix. The
    fillers sit at `AR 101` upward, where the toy corpus has no article to collide with."""
    first = entry.changes[0]

    def at(canonical: str) -> EmittedChange:
        provision = first.change.provision.model_copy(
            update={"location": ProvisionLocation.parse(canonical)}
        )
        return first.model_copy(
            update={"change": first.change.model_copy(update={"provision": provision})}
        )

    fillers = (at(f"AR {100 + i}") for i in range(1, n - 1))
    return entry.model_copy(
        update={"changes": (first, *fillers, at(first.change.location.canonical))}
    )


def test_every_change_opens_with_a_heading_and_the_applies_line_stays_outside_it() -> None:
    """The provision is the unit a crawler ranks a passage under and a screen reader jumps to,
    so each block opens with an `<h3>` of pill, coordinate and title. The applies line is a
    fact about the change, not part of its name, and sits in its own paragraph after it.

    The coordinate is a link to that provision's own page, a sibling directory of this event's
    under the act: an event page answers what one consolidation did, and the reader who wants
    what has ever been done to that coordinate follows the heading."""
    entry = _entry()
    rendered = _page(entry)
    assert rendered.count("<h3>") == len(entry.changes)
    assert rendered.count('<div class="chg"') == len(entry.changes)
    assert rendered.count('<p class="applies">applies from: ') == len(entry.changes)
    for emitted in entry.changes:
        change = emitted.change
        slug = location_slug(change.location.canonical)
        assert f'<a class="loc" href="../{slug}/">{change.location.human}</a>' in rendered
        if change.heading:
            assert f'<span class="ttl">{change.heading}</span>' in rendered
    for heading in re.findall(r"<h3>.*?</h3>", rendered):
        assert "applies from" not in heading
        assert '<span class="pill' in heading
    assert rendered.index('<div class="chg"') < rendered.index("<h3>")


def test_a_change_with_no_title_carries_no_title_span() -> None:
    """`heading` is optional on a change; the span is then absent, never empty."""
    entry = _entry()
    bare = entry.model_copy(
        update={
            "changes": tuple(
                emitted.model_copy(
                    update={"change": emitted.change.model_copy(update={"heading": None})}
                )
                for emitted in entry.changes
            )
        }
    )
    rendered = _page(bare)
    assert rendered.count("<h3>") == len(bare.changes)
    assert 'class="ttl"' not in rendered


def test_a_long_page_opens_with_an_index_of_its_blocks_and_a_short_one_does_not() -> None:
    """Six or more changes get a list of the touched provisions above the blocks; four do not,
    since a list of headings the reader can already see is a second copy. Zero changes is on
    the short side of that line too, so an untouched event never opens with an empty list."""
    entry = _entry()
    assert 0 < len(entry.changes) < INDEX_ABOVE
    assert '<nav class="touched"' not in _page(entry)
    assert '<nav class="touched"' not in _page(untouched_entry())

    rendered = _page(_many(entry, INDEX_ABOVE))
    assert rendered.count('<nav class="touched" aria-label="Provisions in this event">') == 1
    (index,) = _INDEX.findall(rendered)
    assert rendered.index(index) < rendered.index('<div class="chg"')
    links = re.findall(r'href="#([^"]+)"', index)
    assert len(links) == INDEX_ABOVE
    assert links == re.findall(r'<div class="chg" id="([^"]+)"', rendered)
    assert index.count("<li ") == INDEX_ABOVE
    assert index.count('<span class="pill') == INDEX_ABOVE


def test_the_index_lists_a_repeated_coordinate_once_per_block() -> None:
    """The index is a table of contents for the blocks below, not a set of coordinates: a
    coordinate touched twice in one event is listed twice, each link on its own anchor."""
    entry = _many(_entry(), INDEX_ABOVE)
    human = entry.changes[0].change.location.human
    assert entry.changes[-1].change.location.human == human
    (index,) = _INDEX.findall(_page(entry))
    assert index.count(f">{human}</a>") == 2
    links = re.findall(r'href="#([^"]+)"', index)
    assert links[-1] == links[0] + "-2"


def test_every_change_heading_ends_with_a_permalink_to_its_own_block() -> None:
    """A page can carry hundreds of blocks and every one of them has always been addressable.

    The link makes that reachable without knowing the anchor scheme, and it can only point at
    the block it sits in: the href is read back off the block's own `id` here, so a heading
    borrowing another block's anchor would fail rather than merely look right.
    """
    rendered = _page(_entry())
    blocks = re.findall(r'<div class="chg" id="([^"]+)">(.*?)</h3>', rendered, re.DOTALL)
    assert len(blocks) == len(_entry().changes)
    for anchor, opening in blocks:
        assert opening.endswith(
            f'<a class="permalink" href="#{anchor}" aria-label="Link to this change">§</a>'
        )


def test_a_long_page_puts_its_index_in_the_layout_beside_the_changes() -> None:
    """The wrapper is the act page's own two-column grid, so one stylesheet rule serves both.

    Order matters and is asserted: the index is the first child, the changes the second, which
    is what puts the map in the left column and is also the reading order with no stylesheet
    at all.
    """
    rendered = _page(_many(_entry(), INDEX_ABOVE))
    assert rendered.count('<div class="layout event-layout">') == 1
    assert rendered.count('<section class="changes">') == 1
    opening = rendered.index('<div class="layout event-layout">')
    assert opening < rendered.index('<nav class="touched"')
    assert rendered.index('<nav class="touched"') < rendered.index('<section class="changes">')
    assert rendered.index('<section class="changes">') < rendered.index('<div class="chg"')


def test_a_short_page_carries_no_wrapper_and_no_way_back_to_a_top_it_can_see() -> None:
    """The index threshold is the only one: below it there is no column and no back link."""
    rendered = _page(_entry())
    assert "event-layout" not in rendered
    assert '<section class="changes">' not in rendered
    assert "Back to top" not in rendered


def test_a_long_page_ends_with_the_way_back_to_the_top() -> None:
    """Aimed at the id the skip link already targets, so nothing addressable is minted."""
    rendered = _page(_many(_entry(), INDEX_ABOVE))
    back = '<p class="small backtop"><a href="#content">Back to top ↑</a></p>'
    assert rendered.count(back) == 1
    assert rendered.rindex('<div class="chg"') < rendered.index(back)
    assert rendered.index(back) < rendered.index("</section>")
    assert 'id="content"' in rendered


def test_the_index_says_how_many_blocks_it_lists_rather_than_how_many_provisions() -> None:
    """The column needs a label of its own, and the number has to be the list's own length.

    This entry touches one coordinate twice, so six blocks stand over five provisions and the
    event's own facts line counts provisions. A label reading `6 provisions` beside a line
    saying five would be read as one of the two being wrong, so the label counts the blocks it
    is a list of and names them as what they are.
    """
    entry = _many(_entry(), INDEX_ABOVE)
    coordinates = {emitted.change.location.canonical for emitted in entry.changes}
    assert len(entry.changes) == INDEX_ABOVE
    assert len(coordinates) == INDEX_ABOVE - 1
    (index,) = _INDEX.findall(_page(entry))
    assert f'<p class="small muted">{INDEX_ABOVE} changes in this event · ' in index
    assert index.count("<li ") == INDEX_ABOVE


# ------------------------------------------------------------------ how much of each moved


def _blocks(entry: ChangelogEntry) -> tuple[str, tuple[RenderedText, ...]]:
    """The page and the evidence blocks it was built from, so the two can be checked against
    each other rather than against a number written down here."""
    site = _site(entry)
    entry = site.acts[0].entries[0]
    texts = text_blocks(entry)
    return render_event_page(site, site.acts[0], entry, texts), texts


def test_every_change_heading_says_how_much_of_the_provision_moved() -> None:
    """One figure per block, inside the heading, beside the pill that says what kind it was.

    A punctuation fix and a rewritten paragraph are both `MODIFIED`, and this is what tells
    them apart without opening forty-five blocks. The figure is the block's own, so it is read
    back off the evidence the page was built from rather than restated here.
    """
    rendered, texts = _blocks(_entry())
    headings = re.findall(r"<h3>.*?</h3>", rendered)
    assert len(headings) == len(texts)
    for heading, text in zip(headings, texts, strict=True):
        assert heading.count('<span class="mag"') == 1
        assert magnitude_html(text) in heading
        assert heading.index('<span class="pill') < heading.index('<span class="mag"')


def test_the_index_weights_each_link_by_the_characters_its_own_block_moved() -> None:
    """The map and the page carry one measurement, so the class is the block's own decade."""
    entry = _many(_entry(), INDEX_ABOVE)
    rendered, texts = _blocks(entry)
    (index,) = _INDEX.findall(rendered)
    classes = re.findall(r'<li class="([^"]+)">', index)
    assert classes == [weight_class(text) for text in texts]
    assert index.count('<span class="mag"') == INDEX_ABOVE
    for text in texts:
        assert magnitude_html(text) in index


def test_the_index_label_totals_the_characters_of_the_blocks_it_lists() -> None:
    """Summed over the same blocks, and labelled `characters`, which is all it counts.

    Nothing on the page reads it as a size of anything else: the label names the unit, and the
    methodology page carries the paragraph saying what a character count is not.
    """
    entry = _many(_entry(), INDEX_ABOVE)
    rendered, texts = _blocks(entry)
    (index,) = _INDEX.findall(rendered)
    inserted = sum(text.inserted for text in texts)
    deleted = sum(text.deleted for text in texts)
    assert inserted and deleted
    label = (
        f'<p class="small muted">{INDEX_ABOVE} changes in this event · '
        f"+{inserted:,} −{deleted:,} characters</p>"
    )
    assert label in index
