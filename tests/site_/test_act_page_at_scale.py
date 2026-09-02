"""The act's page tree at the size it actually ships, from generated input rather than a fixture.

The committed golden proves the tree is correct over one small transition, and it is read by
hand, so it stays small on purpose. What ships is not small, and for a while it was one page:
the heaviest act page served on 2026-08-12 was 484 kB of HTML, and by 2026-08-13 an act with a
backfilled history served 6.1 MB carrying 2,170 collapsed evidence blocks in one document. The
tree split on 2026-08-31, one page per event with the act page as its timeline, which bounds a
page by one consolidation instead of by an act's whole history.

So this builds one act's whole tree, the index and two hundred event pages, through
`build.act_pages`, the slice the builder itself writes, and asserts the properties that only
have teeth at scale:

- every `id` is unique within its page, and the tree still mints its thousands of them;
- every link that carries a fragment resolves to a page in the tree that holds that `id`,
  which is where a depth or prefix mistake between the index and its event pages would land;
- one location appearing twice inside one event still mints the `-2` suffix, on the page that
  owns it, which is the only input the occurrence counter exists for;
- newest first survives two hundred events on the index;
- two renderings of one input are byte-identical, page for page.

Weight is pinned, not merely logged. The old rule here, that a byte count in an assertion is a
benchmark failing on a loaded machine, conflated bytes with stopwatches: the pages are
deterministic bytes over committed fixtures, so their sizes are exact numbers a reviewer can
hold still, and after the split the size of the heaviest page is the architectural property
this file exists to guard. Two literals carry it: the heaviest page, which is the client cost
of one event, and the tree's total, which catches weight quietly spreading back onto the
index. A moved figure is a finding to explain, never a number to adjust.

The input is the toy corpus with its coordinates moved. Its text is a flat's house rules and is
not legal content, so the tree fills with obviously synthetic events rather than invented law.
"""

from __future__ import annotations

import logging
import posixpath
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from emendrix.core import Change, Delta, ProvisionLocation, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.build import act_pages
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.urls import entry_anchors
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"

_FIRST_DETECTED: Final = date(2026, 1, 5)
"""Passed in, never read from a clock, and one day apart per event so ordering has work to do."""

_EVENTS: Final = 200
"""Enough events to put the generated tree well past any act the live site has served. A round
number rather than a tuned one: being over that mark is the point, tracking it is not."""

_HEAVIEST: Final = ("acts/house-rules/index.html", 170632)
"""The heaviest page in the generated tree, path and exact bytes, measured 2026-08-31 the day
the tree split. It is the index, because two hundred toy events of four small changes each make
light event pages and a long timeline; on the live site, where one event can carry hundreds of
provisions, the heaviest page is an event's. Either way the number moves only on purpose.

17 bytes heavier on 2026-09-02, when the act page's title started saying what the page holds:
`: every amendment` between the act's name and the site's, in the one `<title>` this build
writes, since it passes no site URL and so carries no Open Graph copy of it. Unmoved later
that day, when every change block grew a heading: the index carries cards, not blocks."""

_TOTAL_BYTES: Final = 972170
"""The whole tree's exact bytes over 201 pages, measured 2026-08-31: the number that catches
weight quietly spreading back onto the index without any one page growing past the heaviest.
Before the split this input rendered as one page, which is the shape 6.1 MB arrived in.

11 231 bytes heavier on 2026-09-02: the 17 above, and each of the two hundred event pages
moved its `<title>` from the version pair to the count and the dated clock, and its
description from "What changed in" to the same count and clock in a sentence. That is the
intended cost of a title that says what a reader learns by opening the page; no page
gained markup below the head.

17 600 bytes heavier on 2026-09-02, later the same day, when every change block opened with
an `<h3>` of three spans, pill, coordinate and title, and moved its applies line into a
paragraph of its own: 22 bytes a block, 88 an event page, over two hundred pages. That is the
cost of a heading a crawler can rank a passage under. No page here carries the in-page
provision index, since four changes is under the six it starts at."""

_IDS: Final = re.compile(r'\sid="([^"]*)"')
_LINKS: Final = re.compile(r'href="([^"]*)"')

_logger = logging.getLogger(__name__)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _template() -> Delta:
    """The toy corpus's one transition, parsed once and reshaped per event below."""
    adapter = ToyCorpusAdapter(observed_on=_FIRST_DETECTED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _relocate(change: Change, canonical: str) -> Change:
    """The same change at another coordinate. Only the location moves; the text stays the toy's."""
    provision = change.provision.model_copy(update={"location": ProvisionLocation.parse(canonical)})
    return change.model_copy(update={"provision": provision})


def _placed(changes: tuple[Change, ...], index: int) -> tuple[Change, ...]:
    """One event's changes, laid out to stress every way two anchors could come out equal.

    The first and third share one coordinate inside one event, which is the only input that
    makes `entry_anchors` emit its `-2` suffix. The second is a sub-provision coordinate, whose
    canonical string carries the spaces and the parentheses `location_slug` rewrites. The fourth
    keeps the toy's own annex, so one location is touched by every event and the index has to
    settle on a single target for it.
    """
    article = f"AR {index}"
    return (
        _relocate(changes[0], article),
        _relocate(changes[1], f"{article} PA 1 ALN 1 PTA (b)"),
        _relocate(changes[2], article),
        changes[3],
    )


def _entries() -> tuple[ChangelogEntry, ...]:
    """`_EVENTS` events on one act, each on its own version pair and its own detection date."""
    template = _template()
    return tuple(
        diff_only_entry(
            template.model_copy(
                update={
                    "from_version": VersionId(f"v{index}"),
                    "to_version": VersionId(f"v{index + 1}"),
                    "changes": _placed(template.changes, index),
                }
            ),
            detected_on=_FIRST_DETECTED + timedelta(days=index),
        )
        for index in range(1, _EVENTS + 1)
    )


def _pages(entries: tuple[ChangelogEntry, ...]) -> dict[str, str]:
    """The act's whole tree as the builder writes it: one index, one page per event."""
    site: SiteInputs = collect_site(
        generated_on=_FIRST_DETECTED, run=_run(), report=Path("r.json"), entries=entries
    )
    assert len(site.acts) == 1
    return act_pages(site, site.acts[0])


def _index_path(pages: dict[str, str]) -> str:
    (path,) = [name for name in pages if name.count("/") == 2]
    return path


def test_every_id_within_a_page_is_unique_and_the_tree_keeps_its_thousands() -> None:
    """The assertion the tree exists to carry: no fragment on any page is ambiguous.

    Two ids that match send one link to whichever the browser reaches first, and on these
    pages the links are the navigation. The total floor keeps the split honest: spreading the
    evidence over two hundred pages must not quietly shed the anchors it existed to hold.
    """
    pages = _pages(_entries())
    total = 0
    for path, rendered in pages.items():
        ids = _IDS.findall(rendered)
        duplicated = sorted({value for value in ids if ids.count(value) > 1})
        assert duplicated == [], path
        total += len(ids)
    assert total > 1000


def test_every_fragment_link_across_the_act_tree_resolves() -> None:
    """A link carrying a fragment lands on a page in this tree that holds that id.

    This is where a depth or prefix mistake between the index and two hundred event pages
    shows first: the sidebar's provision links and the cards' event links are cross-page now,
    and a counter or a climb computed differently on either side is a link into nothing.
    """
    pages = _pages(_entries())
    checked = 0
    for path, rendered in pages.items():
        base = posixpath.dirname(path)
        for href in _LINKS.findall(rendered):
            if "#" not in href or href.startswith("https://"):
                continue
            target, _, fragment = href.partition("#")
            landing = (
                path
                if not target
                else f"{posixpath.normpath(posixpath.join(base, target))}/index.html"
            )
            assert landing in pages, f"{path}: {href}"
            assert f'id="{fragment}"' in pages[landing], f"{path}: {href}"
            checked += 1
    assert checked > _EVENTS, "the sidebar's provision links alone outnumber the events"


def test_the_repeated_coordinate_is_what_makes_the_suffix_appear() -> None:
    """Without this the uniqueness test could pass on input that never repeats a location, and
    the counter it is meant to cover would go unexercised.

    The repeat is read back positionally rather than by looking for a `-2` ending, because a
    first occurrence at `AR 2` ends that way too. That near miss is the anchor scheme's one
    documented soft spot, and it is why the suffix is never matched by shape here. Each anchor
    is asserted on the page that owns it, since no other page holds change anchors any more.
    """
    entries = _entries()
    pages = _pages(entries)
    seen: set[str] = set()
    for entry in entries:
        repeat = entry_anchors(
            entry.key, [emitted.change.location.canonical for emitted in entry.changes]
        )[2]
        assert repeat.endswith("-2")
        seen.add(repeat)
        (page,) = [rendered for path, rendered in pages.items() if f"/{entry.key}/" in path]
        assert f'id="{repeat}"' in page
    assert len(seen) == _EVENTS


def test_two_hundred_events_still_arrive_newest_first() -> None:
    """Dates differ by a day across the whole run, so a sort that fell back to insertion order
    or to the version string would show up here rather than on a three-entry page."""
    entries = _entries()
    pages = _pages(entries)
    index = pages[_index_path(pages)]
    newest = max(entries, key=lambda entry: entry.detected_on)
    oldest = min(entries, key=lambda entry: entry.detected_on)
    assert index.index(f'id="{newest.key}"') < index.index(f'id="{oldest.key}"')


def test_the_whole_act_tree_is_still_byte_stable() -> None:
    """Byte stability is a property of the whole tree, and a tree this size is where a set
    iteration or a dictionary order would be most likely to leak into the output."""
    entries = _entries()
    assert _pages(entries) == _pages(entries)


def test_the_tree_weight_is_a_reviewed_number() -> None:
    """The heaviest page and the total, both exact, both updated only on purpose.

    The heaviest page is the client cost of one event, which is what the split bought; the
    total is what catches that cost quietly migrating back onto the index. Regenerate both
    literals from the failure this test prints, and say why in a dated line here: the act page
    weighed 6.1 MB on the live site before the split, and nobody measured it growing.
    """
    pages = _pages(_entries())
    heaviest = max(pages.items(), key=lambda item: (len(item[1].encode()), item[0]))
    total = sum(len(rendered.encode()) for rendered in pages.values())
    _logger.info(
        "act tree: %d pages, %d bytes total, heaviest %s at %d bytes",
        len(pages),
        total,
        heaviest[0],
        len(heaviest[1].encode()),
    )
    assert (heaviest[0], len(heaviest[1].encode())) == _HEAVIEST, (
        f"the heaviest page is now {heaviest[0]} at {len(heaviest[1].encode())} bytes; "
        "if that is intended, update _HEAVIEST and say why"
    )
    assert total == _TOTAL_BYTES, (
        f"the tree now totals {total} bytes; if that is intended, update _TOTAL_BYTES and say why"
    )
