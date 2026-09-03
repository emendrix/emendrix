"""Resolving committed artifacts into what the site renders. Pure and total."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from site_entries import unattributed_entry

from emendrix.core import ActId, VersionId
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.clocks import event_dated, sort_date
from emendrix.site_.inputs import ActSite, collect_site
from emendrix.watch.config import Watchlist
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _entry(in_force: date) -> ChangelogEntry:
    from emendrix.core import ProvisionTree
    from emendrix.diff import compute_delta

    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    entry = diff_only_entry(compute_delta(before, after), detected_on=OBSERVED)
    return entry.model_copy(update={"in_force": (in_force,)})


def test_event_dated_prefers_in_force_and_falls_back_to_detected() -> None:
    entry = _entry(date(2024, 6, 1))
    assert event_dated(entry) == date(2024, 6, 1)
    bare = entry.model_copy(update={"in_force": ()})
    assert event_dated(bare) == OBSERVED


def test_sort_date_prefers_a_resolved_version_date_and_falls_back() -> None:
    entry = _entry(date(2024, 6, 1))
    dated = {(entry.act, entry.to_version): date(2020, 4, 24)}
    assert sort_date(entry, dated) == date(2020, 4, 24)
    assert sort_date(entry, {}) == event_dated(entry)


def test_a_dated_backfill_does_not_outrank_a_version_dated_amendment() -> None:
    """A backfill stamps old events with one recent detection date; the order ignores it.

    Without version dates the backfilled event would sort first, because its detection date
    is later than the amendment's in-force date and `event_dated` compares the two clocks
    as one. The front page once did exactly that under "Latest amendments".
    """
    amendment = _entry(date(2026, 7, 27))
    backfill = _entry(date(2020, 1, 1)).model_copy(
        update={
            "act": ActId(corpus=amendment.act.corpus, key="older-act"),
            "in_force": (),
            "detected_on": date(2026, 8, 13),
        }
    )
    dated = {
        (amendment.act, amendment.to_version): date(2026, 7, 27),
        (backfill.act, backfill.to_version): date(2013, 6, 28),
    }
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(amendment, backfill),
        version_dates=dated,
    )
    assert [pair[1].act for pair in site.recent] == [amendment.act, backfill.act]


def test_one_acts_entries_order_by_the_version_date_not_the_detection_date() -> None:
    newest = _entry(date(2024, 6, 1))
    older = newest.model_copy(
        update={"to_version": VersionId("v9"), "in_force": (), "detected_on": date(2026, 8, 13)}
    )
    dated = {
        (newest.act, newest.to_version): date(2024, 6, 1),
        (older.act, older.to_version): date(2013, 6, 28),
    }
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(newest, older),
        version_dates=dated,
    )
    versions = [entry.to_version for entry in site.acts[0].entries]
    assert versions == [newest.to_version, older.to_version]


def test_dated_carries_the_clock_that_produced_it() -> None:
    """A page reading `dated` gets the date and which clock it came from, inseparably.

    The date alone once let the acts index print a detection date under "last amended";
    a value that names its clock makes that misreading a type error rather than a review
    finding.
    """
    entry = _entry(date(2024, 6, 1))
    stated = ActSite(act=entry.act, label="x", entries=(entry,)).dated
    assert stated is not None
    assert (stated.on, stated.in_force) == (date(2024, 6, 1), True)
    bare = entry.model_copy(update={"in_force": ()})
    fallen = ActSite(act=bare.act, label="x", entries=(bare,)).dated
    assert fallen is not None
    assert (fallen.on, fallen.in_force) == (OBSERVED, False)
    assert ActSite(act=entry.act, label="x").dated is None


def test_dated_is_never_an_event_naming_no_amending_act() -> None:
    """`dated` backs every "newest amendment" line, and an event no amending act is named
    for must not date one: it is skipped past, and an act with only such events answers
    `None` over a non-empty history, which each caller says in its own words."""
    unnamed = unattributed_entry()
    only = ActSite(act=unnamed.act, label="x", entries=(unnamed,))
    assert only.entries and only.dated is None
    amended = _entry(date(2024, 6, 1)).model_copy(update={"to_version": VersionId("v9")})
    mixed = ActSite(act=unnamed.act, label="x", entries=(unnamed, amended))
    stated = mixed.dated
    assert stated is not None
    assert (stated.on, stated.in_force) == (date(2024, 6, 1), True)


def test_entries_group_under_their_act_newest_first() -> None:
    entries = tuple(_entry(day) for day in (date(2020, 1, 1), date(2024, 6, 1)))
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries)
    assert len(site.acts) == 1
    dates = [event_dated(entry) for entry in site.acts[0].entries]
    assert dates == [date(2024, 6, 1), date(2020, 1, 1)]


def test_recent_is_every_event_across_acts_newest_first() -> None:
    entries = tuple(_entry(day) for day in (date(2020, 1, 1), date(2024, 6, 1)))
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries)
    assert [event_dated(e).isoformat() for _, e in site.recent] == ["2024-06-01", "2020-01-01"]


def test_a_watched_act_with_no_entries_still_gets_a_page() -> None:
    watchlist = Watchlist.model_validate(
        {"acts": [{"celex": "32016R0679", "name": "GDPR", "domain": "Data & privacy"}]}
    )
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(),
        watchlist=watchlist,
    )
    assert [act.label for act in site.acts] == ["GDPR"]
    assert site.acts[0].domain == "Data & privacy"
    assert site.acts[0].entries == ()


def test_an_unwatched_act_is_excluded_when_a_watchlist_exists() -> None:
    watchlist = Watchlist.model_validate({"acts": [{"celex": "32016R0679"}]})
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(_entry(date(2024, 6, 1)),),
        watchlist=watchlist,
    )
    assert [act.label for act in site.acts] == ["32016R0679"]
    assert site.acts[0].entries == ()


def test_eurlex_urls_ride_in_by_act_slug() -> None:
    entries = (_entry(date(2024, 6, 1)),)
    act_slug = ActSite(act=entries[0].act, label="x", entries=entries).slug
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=entries,
        eurlex_urls={act_slug: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:x"},
    )
    assert site.acts[0].eurlex_url.startswith("https://eur-lex.europa.eu/")


def test_the_amending_acts_arrive_resolved_and_keyed_by_their_own_key() -> None:
    """What the documents name, what the watchlist calls it and what the boundary rendered,
    joined once. The watchlist's amending labels are read here and nowhere else, the same rule
    every other label follows."""
    from site_entries import attributed_entry

    entry = attributed_entry()
    key = "house-rules-amendment-1"
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(entry,),
        amending_numbers={key: "Rule change no. 1"},
        amending_urls={key: "https://example.invalid/amendment"},
    )
    resolved = site.amending[key]
    assert resolved.title == "Rule change, June"
    assert resolved.number == "Rule change no. 1"
    assert resolved.eurlex_url == "https://example.invalid/amendment"
    assert resolved.label == ""


def test_an_act_nothing_names_never_reaches_the_amending_mapping() -> None:
    """A label with no mention is a line in a config file, not a fact about the corpus. The
    watchlist's amending labels are read in `collect_site` and nowhere else, the same rule
    every other label follows; what one does to a name is `collect_amending`'s own test."""
    watchlist = Watchlist.model_validate(
        {
            "acts": [{"celex": "32024R1689", "name": "AI Act"}],
            "amending_acts": [{"celex": "32026R1744", "name": "Digital Omnibus on AI"}],
        }
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    assert site.amending == {}


def test_acts_sort_by_label_case_insensitively() -> None:
    watchlist = Watchlist.model_validate(
        {
            "acts": [
                {"celex": "32024R1689", "name": "ai act"},
                {"celex": "32016R0679", "name": "GDPR"},
            ]
        }
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    assert [act.label for act in site.acts] == ["ai act", "GDPR"]


def test_two_acts_sharing_one_url_slug_are_refused() -> None:
    mine = _entry(date(2024, 6, 1))
    theirs = mine.model_copy(update={"act": ActId(corpus="other", key=mine.act.key)})
    with pytest.raises(ValueError, match="share the URL slug"):
        collect_site(
            generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(mine, theirs)
        )


def test_the_report_is_named_by_its_file_and_the_committed_convention() -> None:
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=REPORTS / "2026-08-11-abc1234.json"
    )
    assert site.report == "2026-08-11-abc1234.json"
    assert site.report_markdown == "reports/eval/2026-08-11-abc1234.md"
    assert site.acts == () and site.configured is False
