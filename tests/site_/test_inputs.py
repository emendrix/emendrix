"""Resolving committed artifacts into what the site renders. Pure and total."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from emendrix.core import ActId
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import ActSite, collect_site, event_dated
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
