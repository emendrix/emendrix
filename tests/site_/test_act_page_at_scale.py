"""The act page at the size it actually ships, from generated input rather than a fixture.

The committed golden proves the tree is correct over one small transition, and it is read by
hand, so it stays small on purpose. The page that ships is not small: on 2026-08-12 the heaviest
act page served was 484 kB of HTML carrying that act's whole watched history in one document.
That is exactly where an ordering slip or an anchor collision shows first, because the act
page's fragments are the site's whole navigation and `urls.entry_anchors` counts occurrences
per entry.

So this builds one act page out of many generated events and asserts the properties that only
have teeth at scale:

- every `id` on the page is unique, upwards of a thousand of them, including one location
  appearing twice inside one event, which is the only input the occurrence counter exists for;
- every in-page link lands on an `id` the same page carries, so the index and the blocks it
  points at cannot drift apart;
- newest first survives two hundred events;
- two renderings of one input are byte-identical.

Weight is logged, never asserted. A byte count or a stopwatch in an assertion is a benchmark
that fails on a loaded machine, and the size that reaches a reader is the compressed one: that
484 kB page is served `content-encoding: gzip` and arrives as 109,558 bytes, measured
2026-08-12, which is why nothing here renders around the page's size.

The input is the toy corpus with its coordinates moved. Its text is a flat's house rules and is
not legal content, so the page fills with obviously synthetic events rather than invented law.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from emendrix.core import Change, Delta, ProvisionLocation, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.markup import Html
from emendrix.site_.pages.act import render_act
from emendrix.site_.urls import entry_anchors
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"

_FIRST_DETECTED: Final = date(2026, 1, 5)
"""Passed in, never read from a clock, and one day apart per event so ordering has work to do."""

_EVENTS: Final = 200
"""Enough events to put the generated page past the heaviest one the live site served on
2026-08-12, which was 484 kB. A round number rather than a tuned one: being over that mark is
the point, tracking it is not."""

_IDS: Final = re.compile(r'\sid="([^"]*)"')
_FRAGMENTS: Final = re.compile(r'href="#([^"]*)"')

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
    settle on a single anchor for it.
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


def _page(entries: tuple[ChangelogEntry, ...]) -> Html:
    site: SiteInputs = collect_site(
        generated_on=_FIRST_DETECTED, run=_run(), report=Path("r.json"), entries=entries
    )
    assert len(site.acts) == 1
    return render_act(site, site.acts[0])


def test_a_page_of_two_hundred_events_mints_every_id_exactly_once() -> None:
    """The assertion the heaviest page exists to carry: no fragment on it is ambiguous.

    Two ids that match send one link to whichever the browser reaches first, and on this page
    the links are the navigation. The count is checked alongside the set so the test cannot pass
    by rendering fewer ids than it generated.
    """
    entries = _entries()
    started = time.perf_counter()
    rendered = _page(entries)
    elapsed = time.perf_counter() - started
    _logger.info(
        "act page: %d events, %d changes, %d bytes, rendered in %.0f ms",
        len(entries),
        sum(len(entry.changes) for entry in entries),
        len(rendered.encode()),
        elapsed * 1000,
    )
    ids = _IDS.findall(rendered)
    duplicated = sorted({value for value in ids if ids.count(value) > 1})
    assert duplicated == []
    assert len(set(ids)) == len(ids)


def test_every_anchor_the_page_generates_is_on_the_page() -> None:
    """`entry_anchors` is the one counter a caller could get subtly wrong, so it is recomputed
    here from the entries and matched against the markup, rather than trusted."""
    entries = _entries()
    rendered = _page(entries)
    ids = set(_IDS.findall(rendered))
    for entry in entries:
        assert entry.key in ids
        for anchor in entry_anchors(
            entry.key, [emitted.change.location.canonical for emitted in entry.changes]
        ):
            assert anchor in ids


def test_the_repeated_coordinate_is_what_makes_the_suffix_appear() -> None:
    """Without this the uniqueness test could pass on input that never repeats a location, and
    the counter it is meant to cover would go unexercised.

    The repeat is read back positionally rather than by looking for a `-2` ending, because a
    first occurrence at `AR 2` ends that way too. That near miss is the anchor scheme's one
    documented soft spot, and it is why the suffix is never matched by shape here.
    """
    entries = _entries()
    rendered = _page(entries)
    ids = set(_IDS.findall(rendered))
    repeats = [
        entry_anchors(entry.key, [emitted.change.location.canonical for emitted in entry.changes])[
            2
        ]
        for entry in entries
    ]
    assert len(set(repeats)) == _EVENTS
    for anchor in repeats:
        assert anchor.endswith("-2")
        assert anchor in ids


def test_no_link_on_the_page_points_at_a_fragment_the_page_does_not_hold() -> None:
    """The index and the timeline are built from one anchor computation; this is the check that
    they were, over a page with two hundred entries in the index."""
    rendered = _page(_entries())
    ids = set(_IDS.findall(rendered))
    fragments = set(_FRAGMENTS.findall(rendered))
    assert fragments
    assert fragments <= ids


def test_two_hundred_events_still_arrive_newest_first() -> None:
    """Dates differ by a day across the whole run, so a sort that fell back to insertion order
    or to the version string would show up here rather than on a three-entry page."""
    entries = _entries()
    rendered = _page(entries)
    newest = max(entries, key=lambda entry: entry.detected_on)
    oldest = min(entries, key=lambda entry: entry.detected_on)
    assert rendered.index(f'id="{newest.key}"') < rendered.index(f'id="{oldest.key}"')


def test_the_heaviest_page_is_still_byte_stable() -> None:
    """Byte stability is a property of the whole tree, and a page this size is where a set
    iteration or a dictionary order would be most likely to leak into the output."""
    entries = _entries()
    assert _page(entries) == _page(entries)
