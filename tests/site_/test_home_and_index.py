"""The front door and the roster."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from site_entries import unattributed_entry

from emendrix.core import Delta, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import collect_site
from emendrix.site_.pages.acts_index import render_acts_index
from emendrix.site_.pages.home import render_home
from emendrix.watch.config import Watchlist
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _entry() -> ChangelogEntry:
    return diff_only_entry(_delta(), detected_on=OBSERVED)


def test_home_leads_with_search_hero_and_recent_events() -> None:
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(_entry(),),
        configured=True,
    )
    rendered = render_home(site)
    entry = site.acts[0].entries[0]
    assert "What changed in your regulations?" in rendered
    assert f'#{entry.key}"' in rendered
    assert "Latest amendments" in rendered


def test_home_credibility_strip_reads_from_the_report_and_links_methodology() -> None:
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    rendered = render_home(site)
    pair = _run().metrics.localisation
    assert pair is not None
    assert f"{pair.micro_f1:.3f}" in rendered
    assert 'href="methodology/"' in rendered


def test_home_without_events_says_so_instead_of_going_dark() -> None:
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    rendered = render_home(site)
    assert "No changelog repository was configured" in rendered
    assert "A quiet month is a real answer" in rendered


def test_more_events_than_the_limit_are_counted_rather_than_hidden() -> None:
    """The front page is a window on the timeline, and it says so where it stops.

    A capped list that ends silently reads as the whole history, which is the one thing the
    home page must not imply on a site whose act pages carry the rest.
    """
    entries = tuple(
        _entry().model_copy(update={"in_force": (date(2020, 1, day),)}) for day in (1, 2, 3)
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries, configured=True
    )
    rendered = render_home(site, limit=2)
    assert rendered.count('<div class="cardrow">') == 2
    assert "1 older event is on the act pages" in rendered


def test_a_card_for_one_touched_provision_says_provision_not_provisions() -> None:
    """One is the count a bare plural gets wrong, and the card is where a reader meets it first.

    The event is a real one with its changes cut to a single change, so the count comes out of
    the same computation the shipped entry uses rather than being written into the fixture.
    """
    delta = _delta()
    single = delta.model_copy(update={"changes": delta.changes[:1]})
    entry = diff_only_entry(single, detected_on=OBSERVED)
    assert entry.counts.touched == 1
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(entry,),
        configured=True,
    )
    rendered = render_home(site)
    assert "1 provisions" not in rendered
    assert "1 provision ·" in rendered


def test_home_excludes_events_naming_no_amending_act_and_says_how_many() -> None:
    """The list is titled "Latest amendments", and an event no amending act is named for is
    not shown under that word; the exclusion is counted in words, never silent."""
    unnamed = unattributed_entry().model_copy(update={"to_version": VersionId("v9")})
    entries = (_entry().model_copy(update={"in_force": (date(2024, 6, 1),)}), unnamed)
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries, configured=True
    )
    rendered = render_home(site)
    assert rendered.count('<div class="cardrow">') == 1
    assert "1 event naming no amending act is on the act pages, not in this list." in rendered
    assert f'#{unnamed.key}"' not in rendered


def test_home_with_only_events_naming_no_amending_act_says_so() -> None:
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(unattributed_entry(),),
        configured=True,
    )
    rendered = render_home(site)
    assert '<div class="cardrow">' not in rendered
    assert "1 event recorded so far named no amending act" in rendered


def test_the_index_groups_by_domain_with_other_last() -> None:
    watchlist = Watchlist.model_validate(
        {
            "acts": [
                {"celex": "32016R0679", "name": "GDPR", "domain": "Data & privacy"},
                {"celex": "32024R1689", "name": "AI Act"},
            ]
        }
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    rendered = render_acts_index(site)
    assert rendered.index("Data &amp; privacy") < rendered.index("Other")
    assert "no amendments seen" in rendered


def test_the_index_dates_a_row_by_the_clock_that_produced_the_date() -> None:
    """An in-force date reads "in force", never "last amended".

    "last amended" over `event_dated`'s fallback branch once printed the day a backfill ran
    as an amendment date, so the label is gone from the page entirely, meta description
    included.
    """
    stated = _entry().model_copy(update={"in_force": (date(2024, 6, 1),)})
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(stated,))
    rendered = render_acts_index(site)
    assert "in force 2024-06-01" in rendered
    assert "last amended" not in rendered


def test_the_index_calls_a_detection_date_detected() -> None:
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    rendered = render_acts_index(site)
    assert f"detected {OBSERVED.isoformat()}" in rendered
    assert "last amended" not in rendered


def test_the_index_counts_events_naming_no_amending_act_apart() -> None:
    """Both numbers always render, zeros included: one figure over both kinds would call
    every recorded event an amendment."""
    unnamed = unattributed_entry().model_copy(update={"to_version": VersionId("v9")})
    entries = (_entry().model_copy(update={"in_force": (date(2024, 6, 1),)}), unnamed)
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries)
    rendered = render_acts_index(site)
    assert "1 amendment event recorded, plus 1 event naming no amending act." in rendered
    bare = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    assert "1 amendment event recorded, plus 0 events naming no amending act." in render_acts_index(
        bare
    )


def test_the_index_row_for_an_act_with_only_unnamed_events_says_so() -> None:
    """Neither a date (nothing was amended) nor "no amendments seen" (events exist and the
    act's page shows them): the third state gets its own words."""
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(unattributed_entry(),)
    )
    rendered = render_acts_index(site)
    assert "events recorded, none names an amending act" in rendered
    assert "no amendments seen" not in rendered
    assert "in force 2" not in rendered and "detected 2" not in rendered


def test_every_act_on_the_index_links_its_page() -> None:
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    rendered = render_acts_index(site)
    assert f'href="../acts/{site.acts[0].slug}/"' in rendered
