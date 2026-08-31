"""One act's page: the timeline of cards, the sidebar, and the anchor it may never lose.

The evidence itself, the per-change blocks and the verbatim text, lives on each event's own
page and is asserted in `test_event_page.py`; what this page owes a reader is the act's
identity, a card per event that still answers to the fragment every feed entry published,
and links that land where the evidence went.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from site_entries import unattributed_entry

from emendrix.core import Delta, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.pages.act import render_act
from emendrix.site_.urls import event_href
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


def _site(*entries: ChangelogEntry) -> SiteInputs:
    return collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries)


def test_the_header_dates_the_newest_amendment_by_its_own_clock() -> None:
    """The header names the clock behind its date instead of claiming a version date.

    "reflects the consolidated version of" once dressed `event_dated`'s fallback, a
    detection date, as a fact about the official text.
    """
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    assert f"newest amendment detected {OBSERVED.isoformat()}" in rendered
    assert "reflects the consolidated version" not in rendered
    stated = entry.model_copy(update={"in_force": (date(2024, 6, 1),)})
    site = _site(stated)
    rendered = render_act(site, site.acts[0])
    assert "newest amendment in force 2024-06-01" in rendered


def test_the_timeline_keeps_the_event_anchor_and_links_the_evidence() -> None:
    """The card still answers to the fragment every feed entry was published under, and the
    per-change evidence is one link away rather than on this page: a long history was
    shipping megabytes of collapsed text here, and the anchor is the one part of that page
    an address outside the site holds on to."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    assert f'id="{entry.key}"' in rendered
    assert f'href="../../{event_href(site.acts[0].slug, entry.key)}"' in rendered
    assert "with the text before and after" in rendered
    assert '<div class="chg"' not in rendered
    assert 'class="verbatim"' not in rendered
    # The one fold left on the page is the sidebar's own, not a change's evidence.
    assert rendered.count("<details") == 1


def _quiet() -> str:
    from emendrix.watch.config import Watchlist

    watchlist = Watchlist.model_validate({"acts": [{"celex": "32016R0679", "name": "GDPR"}]})
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    return render_act(site, site.acts[0])


def test_a_quiet_act_gets_a_page_that_says_so() -> None:
    assert "A quiet act is a real answer" in _quiet()


def test_a_quiet_act_gets_no_index_of_nothing() -> None:
    """An index with two empty lists indexes nothing, and the grid would misplace the page.

    The sidebar is one column of a two-column grid, so shipping it empty costs the reader a
    heading pair with no entries under it, and dropping it while keeping the grid would push
    the whole page into the narrow column instead.
    """
    rendered = _quiet()
    assert "<aside" not in rendered
    assert "Touched provisions" not in rendered
    assert '<div class="layout">' not in rendered


def test_a_quiet_act_does_not_repeat_its_name_as_an_official_title() -> None:
    """No entry has been recorded, so no official title is known; saying the label twice
    would present a watchlist name as the title the legislation publishes for itself."""
    rendered = _quiet()
    assert rendered.count("GDPR</") == 1
    assert 'class="official"' not in rendered


def test_the_sidebar_lists_touched_provisions_and_amendments() -> None:
    """Both lists now link into event pages, since that is where the evidence lives."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    sidebar = rendered.split('<aside class="sidebar">')[1].split("</aside>")[0]
    target = f"../../{event_href(site.acts[0].slug, entry.key)}"
    assert f'href="{target}"' in sidebar
    assert f'href="{target}#' in sidebar
    first = entry.changes[0].change
    assert first.location.human in sidebar


def test_an_event_naming_no_amending_act_is_labelled_and_explained_once() -> None:
    """The card carries the label and one sentence about the corpus's records; the header
    states the same fact instead of falling silent over a timeline the reader can see."""
    site = _site(unattributed_entry())
    rendered = render_act(site, site.acts[0])
    assert '<span class="pill">no amending act named</span>' in rendered
    assert rendered.count("No amending act is named for this event") == 1
    assert "recorded events name no amending act" in rendered
    assert "newest amendment" not in rendered


def test_an_ordinary_event_carries_no_attribution_label() -> None:
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    assert "no amending act named" not in rendered
    assert "No amending act is named" not in rendered


def test_the_facts_line_counts_one_touched_provision_in_the_singular() -> None:
    """The counts are read off the entry, and one of them being 1 must still read as English."""
    delta = _delta()
    single = delta.model_copy(update={"changes": delta.changes[:1]})
    entry = diff_only_entry(single, detected_on=OBSERVED)
    assert entry.counts.touched == 1
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    assert "1 provision touched" in rendered
    assert "1 provisions" not in rendered


def test_a_diff_only_entry_says_the_stage_never_ran_once() -> None:
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    assert "No explanation shipped" not in rendered
    assert rendered.count("the explain stage did not run for this event") == 1
