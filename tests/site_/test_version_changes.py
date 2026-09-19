"""The line a short version's masthead opens with, naming each change it made.

A version under the index threshold had no map at its top, so on a phone its changes started
below the first screen. The line names them there instead, and the two maps split the pages
between them: one to five changes get the line, six or more the index, zero neither.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from emendrix.core import (
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionText,
    ProvisionTree,
)
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.graph.report import EmittedChange
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import collect_site
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.event_index import INDEX_ABOVE
from emendrix.site_.pages.texts import text_blocks
from emendrix.site_.pages.version_changes import changes_line
from emendrix.site_.urls import entry_anchors
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
GOLDEN = Path(__file__).resolve().parent / "golden"
OBSERVED = date(2026, 8, 9)

FIC_SUBJECT = "SUBSTANCES OR PRODUCTS CAUSING ALLERGIES OR INTOLERANCES"
FIC_TEXT = f"ANNEX II\n{FIC_SUBJECT}\n1. Cereals containing gluten, namely: wheat, rye"
"""The shape of the FIC Regulation's Annex II as its 2025-04-01 change stores it."""

_LINE = re.compile(r'<nav class="changes-line".*?</nav>', re.DOTALL)
_HREFS = re.compile(r'href="#([^"]+)"')
_IDS = re.compile(r'\sid="([^"]+)"')


def _entry() -> ChangelogEntry:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    delta: Delta = compute_delta(before, after)
    return diff_only_entry(delta, detected_on=OBSERVED)


def _at(emitted: EmittedChange, canonical: str, **update: object) -> EmittedChange:
    provision = emitted.change.provision.model_copy(
        update={"location": ProvisionLocation.parse(canonical)}
    )
    change = emitted.change.model_copy(update={"provision": provision, **update})
    return emitted.model_copy(update={"change": change})


def _sized(n: int) -> ChangelogEntry:
    """The toy entry's first change at `n` distinct article coordinates, in that order."""
    entry = _entry()
    first = entry.changes[0]
    return entry.model_copy(
        update={"changes": tuple(_at(first, f"AR {100 + i}") for i in range(n))}
    )


def _anchors(entry: ChangelogEntry) -> tuple[str, ...]:
    return entry_anchors(
        entry.key, [emitted.change.location.canonical for emitted in entry.changes]
    )


def _line(entry: ChangelogEntry) -> str:
    return "\n".join(changes_line(entry, _anchors(entry)))


def _page(entry: ChangelogEntry) -> str:
    site = collect_site(
        generated_on=OBSERVED,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry,),
    )
    entry = site.acts[0].entries[0]
    return render_event_page(site, site.acts[0], entry, text_blocks(entry))


def test_one_change_is_one_link_to_its_anchor() -> None:
    entry = _sized(1)
    (anchor,) = _anchors(entry)
    line = _line(entry)
    assert line.startswith('<nav class="changes-line" aria-label="Changes in this version">')
    assert _HREFS.findall(line) == [anchor]
    assert '<p><span class="lead">Changes:</span> <a href="#' in line


def test_five_changes_are_five_links_in_the_entry_s_order() -> None:
    entry = _sized(5)
    line = _line(entry)
    assert _HREFS.findall(line) == list(_anchors(entry))
    humans = re.findall(r'<a href="#[^"]+">([^<]+)</a>', line)
    assert humans == [emitted.change.location.human for emitted in entry.changes]
    assert line.count(" · ") == 4


def test_six_changes_and_none_print_nothing() -> None:
    assert changes_line(_sized(INDEX_ABOVE), _anchors(_sized(INDEX_ABOVE))) == []
    assert changes_line(_sized(0), ()) == []


def test_a_title_follows_its_coordinate_outside_the_link_and_the_separator_sits_between() -> None:
    entry = _entry()
    line = _line(entry)
    for emitted in entry.changes:
        heading = emitted.change.heading
        assert heading is not None
        assert f'{emitted.change.location.human}</a> <span class="ttl">{heading}</span>' in line
    assert "</span> · <a " in line
    assert " </span>" not in line and "  ·" not in line


def test_a_change_with_no_title_prints_its_coordinate_alone() -> None:
    entry = _sized(2)
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
    line = _line(bare)
    assert 'class="ttl' not in line
    assert re.search(r'</a> · <a href="#[^"]+">[^<]+</a></p>', line)


def test_an_annex_titled_only_by_its_number_prints_its_subject_in_small_capitals() -> None:
    entry = _entry()
    annex = _at(
        entry.changes[0],
        "AN II",
        heading="ANNEX II",
        change_type=ChangeType.MODIFIED,
        before=ProvisionText(FIC_TEXT),
        after=ProvisionText(FIC_TEXT),
    )
    line = _line(entry.model_copy(update={"changes": (annex,)}))
    assert f'Annex II</a> <span class="ttl ttl--caps">{FIC_SUBJECT}</span></p>' in line


def test_a_repeated_coordinate_links_each_block_on_its_own_anchor() -> None:
    entry = _entry()
    twice = entry.model_copy(update={"changes": (*entry.changes, entry.changes[0])})
    anchors = _anchors(twice)
    assert len(set(anchors)) == len(anchors)
    assert _HREFS.findall(_line(twice)) == list(anchors)


def test_the_line_opens_the_masthead_and_every_link_lands_on_the_page() -> None:
    rendered = _page(_entry())
    masthead = rendered.split('<div class="version-masthead"')[1]
    assert masthead.split(">", 1)[1].lstrip().startswith('<nav class="changes-line"')
    (line,) = _LINE.findall(rendered)
    ids = set(_IDS.findall(rendered))
    hrefs = _HREFS.findall(line)
    assert len(hrefs) == len(_entry().changes)
    assert all(fragment in ids for fragment in hrefs)
    assert 'class="touched"' not in rendered


def test_a_page_with_the_index_does_not_also_carry_the_line() -> None:
    rendered = _page(_sized(INDEX_ABOVE))
    assert 'class="touched"' in rendered
    assert 'class="changes-line"' not in rendered


def test_every_changes_line_fragment_in_the_golden_resolves_on_its_page() -> None:
    """Every golden version page either carries the line, whose links all land on the same page,
    or carries the index instead; none carries both, and none with changes carries neither."""
    pages = [
        path
        for path in GOLDEN.glob("acts/*/*/index.html")
        if '<div class="version-masthead"' in path.read_text(encoding="utf-8")
    ]
    assert pages
    for path in pages:
        rendered = path.read_text(encoding="utf-8")
        lines = _LINE.findall(rendered)
        indexed = 'class="touched"' in rendered
        assert len(lines) + indexed == 1, path
        ids = set(_IDS.findall(rendered))
        for line in lines:
            assert all(fragment in ids for fragment in _HREFS.findall(line)), path
