"""What a change block is on the page, and the index a long page opens with.

A sibling of `test_event_page.py` rather than a tail on it: that module holds the honesty
markers a block may never lose (anchor, disagreement, provenance, a stated reason), and this
one holds the block's shape, a heading per provision with the applies line outside it, and
the in-page index that lists every block by the anchor it carries. Each module builds its own
toy page, as every site test module does, so a scoped run of either stands on its own.
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
from emendrix.site_.pages.act_event import INDEX_ABOVE
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.texts import text_blocks
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
    assert rendered.count('<p class="applies">applies from ') == len(entry.changes)
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
    assert index.count("<li>") == INDEX_ABOVE
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
