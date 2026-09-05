"""The cross-act list of dates the amended texts name, and the line it may not cross.

The corpus's dates are a set difference over the source's own date markup and nothing more, so
the page that gathers them across acts is one sentence away from claiming that an obligation
begins on one of them. Most of what is asserted here is about that sentence: which words the
page may not contain, that the two kinds of date sit in two blocks, and that a date a later
amendment took back out says so on its own row.

The input is the toy corpus with dates patched onto its changes, because that corpus writes no
date markup of its own. Two acts, so the ordering has a tie to break at the act; one date equal
to the build date, so the strict comparison has something to get wrong; and one date added by an
older event and removed by a newer one, which is the shape a naive list renders as still current.

The build date arrives as a value in every one of these, which is the property the page rests
on: it is a pure function of the committed corpus and that one date, and nothing in the render
path may read a clock.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from helpers import build, text_of

from emendrix.core import ActId, Delta, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.date_coverage import applies_ahead, coverage
from emendrix.site_.history import ahead, cross_act_mentions, passed_within
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.pages.dates import RECENT_DAYS, render_dates
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"

BUILT_ON = date(2026, 9, 5)
"""The build date every case here passes in. Never a clock read, on either side of the seam."""

ALPHA = ActId(corpus="toy", key="alpha")
BETA = ActId(corpus="toy", key="beta")

AHEAD = date(2027, 6, 1)
"""One date two acts both name, which is the tie the ordering key has to break at the act."""

TAKEN_BACK = date(2030, 3, 3)
ON_THE_DAY = BUILT_ON
JUST_PASSED = BUILT_ON - timedelta(days=10)
LONG_PASSED = BUILT_ON - timedelta(days=400)

BANNED = (
    "deadline",
    "obligation",
    "duty",
    "requirement",
    "comes into effect",
    "takes effect",
    "enters into application",
    "becomes applicable",
    "compliance date",
    "calendar",
    "schedule",
    "milestone",
    "due",
    "starts",
    "begins to apply",
)
"""Words that would turn a mention into a claim about when something is owed.

Every one of them names the stronger fact the data does not hold: what the sentence around a
date does is prose nothing in this project parses. `applies from` is the one licensed phrase and
appears in exactly two places, the block that renders clock 2's own answers and the disclaimer
sentence that sends a reader to the applies line on a change.
"""


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=BUILT_ON)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _event(
    act: ActId,
    tag: str,
    previous: str,
    in_force: date,
    moved: dict[int, tuple[tuple[date, ...], tuple[date, ...]]],
) -> ChangelogEntry:
    """One committed event of `act`, with dates hung on the changes `moved` names.

    The toy corpus writes no date markup, so every date on this page's fixtures is patched on
    here rather than parsed. `previous` is the version this event continues, which is what keeps
    the coverage panel's chain count at zero for an act whose events form a chain.
    """
    delta = _delta()
    changes = list(delta.changes)
    for index, (added, removed) in moved.items():
        changes[index] = changes[index].model_copy(
            update={"dates_added": added, "dates_removed": removed, "in_force": in_force}
        )
    entry = diff_only_entry(
        delta.model_copy(update={"changes": tuple(changes)}), detected_on=BUILT_ON
    )
    return entry.model_copy(
        update={
            "act": act,
            "from_version": VersionId(previous),
            "to_version": VersionId(tag),
            "in_force": (in_force,),
        }
    )


def _entries() -> tuple[ChangelogEntry, ...]:
    """Two acts: one whose newest event takes a date back out, and one that shares a date."""
    return (
        _event(ALPHA, "alpha-2", "alpha-1", date(2026, 2, 2), {0: ((), (TAKEN_BACK,))}),
        _event(
            ALPHA,
            "alpha-1",
            "alpha-0",
            date(2026, 1, 1),
            {0: ((AHEAD, TAKEN_BACK), ()), 3: ((ON_THE_DAY, JUST_PASSED, LONG_PASSED), ())},
        ),
        _event(BETA, "beta-1", "beta-0", date(2026, 1, 3), {0: ((AHEAD,), ())}),
    )


def _site(*entries: ChangelogEntry, on: date = BUILT_ON) -> SiteInputs:
    return collect_site(
        generated_on=on, run=_run(), report=Path("r.json"), entries=entries or _entries()
    )


def _mentions(site: SiteInputs) -> str:
    return render_dates(site)


def _rows(rendered: str) -> list[str]:
    return re.findall(r"<li>.*?</li>", rendered, re.DOTALL)


def _forward_rows(rendered: str) -> list[str]:
    """The rows of the forward list alone, without the applies-from block or the recent window."""
    listing = rendered.split("<h2>Dates the amended texts name</h2>")[1]
    return _rows(listing.split("<h2>What this is a view of</h2>")[0])


# ------------------------------------------------------------------ the fold


def test_the_forward_list_holds_every_date_after_the_build_date_and_none_on_it() -> None:
    """The comparison is strict: a date equal to the build date has arrived, so it is behind.

    Asserted on the fold rather than on the page, because this is the one decision the whole
    view rests on and it is worth reading without markup around it.
    """
    site = _site()
    forward = ahead(cross_act_mentions(site), site.generated_on)
    assert [one.mention.on for one in forward] == [AHEAD, AHEAD, TAKEN_BACK, TAKEN_BACK]
    assert ON_THE_DAY not in {one.mention.on for one in forward}


def test_two_acts_naming_one_date_are_ordered_by_the_act_the_roster_orders_by() -> None:
    """The date is the sort key and the act breaks the tie, in the roster's own order, so the
    list and the acts index cannot disagree about which act comes first."""
    forward = ahead(cross_act_mentions(_site()), BUILT_ON)
    tied = [one.act.act.key for one in forward if one.mention.on == AHEAD]
    assert tied == ["alpha", "beta"]


def test_a_date_a_later_amendment_removed_carries_the_change_that_removed_it() -> None:
    """The one place a straightforward list would be wrong rather than merely thin.

    `TAKEN_BACK` was added by the older event and removed by the newer one, so its added
    mention names the change that removed it; `AHEAD` was never taken out and names nothing.
    """
    forward = ahead(cross_act_mentions(_site()), BUILT_ON)
    marked = {one.mention.on: one.superseded_by for one in forward if one.mention.added}
    assert marked[AHEAD] is None
    removed = marked[TAKEN_BACK]
    assert removed is not None and removed.entry.key == "alpha-2"


def test_the_recent_window_holds_what_passed_inside_it_and_not_what_passed_before() -> None:
    recent = passed_within(cross_act_mentions(_site()), BUILT_ON, RECENT_DAYS)
    assert [one.mention.on for one in recent] == [JUST_PASSED, ON_THE_DAY]


# ------------------------------------------------------------------ the page


def test_the_page_never_calls_a_mention_something_that_is_owed() -> None:
    """The enforceable form of the whole design: the words that would make a date a deadline.

    Matched on whole words over the page's own text, so `produced` does not read as `due`. If a
    future edit needs one of these words, that edit is the moment to argue the boundary again
    rather than to widen this list.
    """
    words = text_of(_mentions(_site())).lower()
    for banned in BANNED:
        assert not re.search(rf"(?<![a-z]){re.escape(banned)}(?![a-z])", words), banned


def test_the_two_kinds_of_date_are_two_blocks_and_only_one_says_applies_from() -> None:
    """The stronger claim lives in one field and gets its own heading; the list is mentions.

    `applies from` is licensed inside that block and in the shared disclaimer sentence, and
    nowhere else, so a reader who reads only the headings still meets the distinction.
    """
    rendered = _mentions(_site())
    assert "<h2>Dates a change applies from</h2>" in rendered
    assert "<h2>Dates the amended texts name</h2>" in rendered
    applies = rendered.index("<h2>Dates a change applies from</h2>")
    listing = rendered.index("<h2>Dates the amended texts name</h2>")
    assert applies < listing
    assert "applies from this date" not in rendered[listing:]


def test_the_applies_from_block_renders_its_caption_when_no_such_date_is_ahead() -> None:
    """Deleting the empty block would drop the page's own demonstration of the distinction on
    exactly the build where the list below it stands alone."""
    site = _site()
    assert applies_ahead(site) == ()
    rendered = _mentions(site)
    assert "No change of the committed corpus states an applies-from date later than" in rendered
    assert "the only place this project reads such a date" in rendered


def test_a_superseded_row_says_what_the_later_change_did_and_links_it() -> None:
    """In the register of the committed record: the text no longer names the date. Nothing on
    the row says anything about what applies, which is the claim that is not in the data."""
    rendered = _mentions(_site())
    marked = [row for row in _rows(rendered) if "a later amendment" in row]
    assert len(marked) == 1
    assert "removed it from that provision's text" in marked[0]
    assert "#alpha-2-ar-2" in marked[0]
    assert sum("a later amendment" in row for row in _rows(rendered)) == 1


def test_every_year_present_gets_its_own_heading_and_none_is_folded_away() -> None:
    rendered = _mentions(_site())
    assert re.findall(r"<h3>(\d{4})</h3>", rendered) == ["2027", "2030"]


def test_a_corpus_with_nothing_ahead_says_so_and_still_publishes_the_panel() -> None:
    """Thin is published as thin. The panel is what stops a short list reading as the whole
    corpus, so it is exactly the build with no rows that must not lose it."""
    site = _site(on=date(2031, 1, 1))
    rendered = _mentions(site)
    assert "No date the committed texts name falls after 2031-01-01." in rendered
    assert "<h2>What this is a view of</h2>" in rendered


def test_an_empty_corpus_renders_the_page_rather_than_raising() -> None:
    """A checkout with no changelog repository is a real state, and every share over it is a
    stated non-answer rather than a zero nobody measured."""
    rendered = render_dates(collect_site(generated_on=BUILT_ON, run=_run(), report=Path("r.json")))
    assert "<h1>Dates ahead in the amended texts</h1>" in rendered
    assert "The forward list holds 0 mentions dated after 2026-09-05" in text_of(rendered)


# ------------------------------------------------------------------ the numbers


def test_the_panel_prints_the_numbers_the_counters_returned() -> None:
    """The page may not carry a figure it worked out for itself, which is the whole reason the
    counters are a frozen model and not a handful of locals in a renderer."""
    site = _site()
    found = coverage(site, cross_act_mentions(site))
    words = text_of(_mentions(site))
    assert found.changes == 12 and found.without_a_date == 8
    assert f"Of the {found.changes:,} changes this build renders" in words
    assert f"holds {found.mentions_ahead} mentions dated after 2026-09-05" in words
    assert f"{found.acts_ahead} of the {found.acts_with_events} acts" in words
    assert f"It leaves out {found.mentions_behind} mentions dated on or before" in words


def test_the_out_of_range_readings_are_published_as_the_markup_gave_them() -> None:
    """Both ends of the corpus's own range, shown rather than clipped: a page that quietly
    dropped a reading it found implausible would be curating its own evidence."""
    site = _site()
    found = coverage(site, cross_act_mentions(site))
    assert (found.earliest, found.latest) == (LONG_PASSED, TAKEN_BACK)
    assert f"readings from {LONG_PASSED.isoformat()} to {TAKEN_BACK.isoformat()}" in text_of(
        _mentions(site)
    )


def test_an_act_whose_chain_is_complete_reports_no_hole_and_a_broken_one_does() -> None:
    """One event per act legitimately reaches back to a version the corpus does not hold, its
    own first; the count is what is left after that one, so a chain reads zero."""
    assert coverage(_site(), cross_act_mentions(_site())).gaps == 0
    orphan = _event(ALPHA, "alpha-9", "alpha-7", date(2026, 3, 3), {})
    broken = _site(*_entries(), orphan)
    assert coverage(broken, cross_act_mentions(broken)).gaps == 1


# ------------------------------------------------------------------ the build date


def test_the_split_is_decided_by_the_build_date_and_by_nothing_else() -> None:
    """Two builds of one corpus, one day apart, move exactly the rows that crossed the pivot.

    This is what "no clock in the render path" buys: the same committed documents produce a
    different list only because a different date was passed in, and the page says which one.
    """
    entries = _entries()
    before = _mentions(_site(*entries, on=ON_THE_DAY - timedelta(days=1)))
    after = _mentions(_site(*entries, on=ON_THE_DAY))
    assert ON_THE_DAY.isoformat() in text_of(before).split("What this is a view of")[0]
    assert f"{(ON_THE_DAY - timedelta(days=1)).isoformat()} is the date this build" in before
    assert f"{ON_THE_DAY.isoformat()} is the date this build" in after
    assert len(_forward_rows(before)) == len(_forward_rows(after)) + 1


def test_two_renderings_of_one_corpus_and_one_date_are_byte_identical() -> None:
    """The ordering is total and explicit, so nothing here depends on a dictionary or a set."""
    entries = _entries()
    assert _mentions(_site(*entries)) == _mentions(_site(*entries))


# ------------------------------------------------------------------ the built tree


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("dates") / "site", changelog_repo)


def test_the_page_is_written_where_the_navigation_points(site: Path) -> None:
    assert (site / "dates" / "index.html").is_file()
    assert '<a href="dates/">Dates ahead</a>' in (site / "index.html").read_text(encoding="utf-8")


def test_every_link_on_the_page_lands_on_a_file_the_same_build_wrote(site: Path) -> None:
    """The round trip is the property the whole site is built on: a row is checkable against
    the verbatim text in two clicks, and a row whose links go nowhere is not a row."""
    page = (site / "dates" / "index.html").read_text(encoding="utf-8")
    for href in re.findall(r'href="(\.\./[^"#]*)', page):
        target = site / "dates" / href
        assert (target if target.suffix else target / "index.html").exists(), href
