"""The front door and the roster."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from emendrix.core import Delta, ProvisionTree
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


def test_every_act_on_the_index_links_its_page() -> None:
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    rendered = render_acts_index(site)
    assert f'href="../acts/{site.acts[0].slug}/"' in rendered
