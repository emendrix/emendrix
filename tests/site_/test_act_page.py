"""One act's page: the timeline of cards, the sidebar, and the anchor it may never lose.

The evidence itself, the per-change blocks and the verbatim text, lives on each event's own
page and is asserted in `test_event_page.py`; what this page owes a reader is the act's
identity, a card per event that still answers to the fragment every feed entry published,
and links that land where the evidence went.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from site_entries import unattributed_entry

from emendrix.core import Delta, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.markup import escape
from emendrix.site_.pages.act import render_act
from emendrix.site_.pages.act_dates import FOLD_ABOVE, LEDE
from emendrix.site_.urls import event_href, provision_href
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


def _quiet(*, published: str = "", site_url: str = "") -> str:
    """One watched act with nothing recorded for it, under the two facts a build may have."""
    from emendrix.watch.config import Watchlist

    watchlist = Watchlist.model_validate({"acts": [{"celex": "32016R0679", "name": "GDPR"}]})
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        watchlist=watchlist,
        published_urls={"32016R0679": published} if published else None,
        site_url=site_url,
    )
    return render_act(site, site.acts[0])


def test_a_quiet_act_gets_a_page_that_says_so() -> None:
    """The sentence is about the record, not about time: the site has no "last checked" date
    and never invents one, and a backfill can still write an older transition tomorrow."""
    rendered = _quiet()
    assert "No amendment event is recorded for this act" in rendered
    assert "A quiet act is a real answer" in rendered
    assert "since watching began" not in rendered
    assert "checked" not in rendered


def test_a_quiet_act_offers_only_what_this_build_actually_has() -> None:
    """Each half of the middle sentence is guarded by the thing it points at, so a page never
    promises a feed a build did not write or a document that has no address."""
    bare = _quiet()
    assert "as published" not in bare
    assert "the feed above" not in bare
    published = _quiet(published="https://eur-lex.europa.eu/x")
    assert "Its text as published is on EUR-Lex." in published
    assert "the feed above" not in published
    both = _quiet(published="https://eur-lex.europa.eu/x", site_url="https://example.invalid/site")
    assert (
        "Its text as published is on EUR-Lex, and the feed above will carry the first event "
        "the day one is recorded." in both
    )
    feed_only = _quiet(site_url="https://example.invalid/site")
    assert "The feed above will carry the first event the day one is recorded." in feed_only


def test_a_quiet_act_links_the_act_as_published_and_says_which_document_it_is() -> None:
    """Two labels, because the newest consolidation and the act as published are two
    documents; an act with events shows the first and never offers the second."""
    published = _quiet(published="https://eur-lex.europa.eu/x")
    assert '<a href="https://eur-lex.europa.eu/x">as published, ' in published
    assert ">on EUR-Lex</span></a>" in published
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(entry,),
        eurlex_urls={"house-rules": "https://eur-lex.europa.eu/consolidated"},
        published_urls={"house-rules": "https://eur-lex.europa.eu/x"},
    )
    rendered = render_act(site, site.acts[0])
    assert '<a class="nowrap" href="https://eur-lex.europa.eu/consolidated">on EUR-Lex</a>' in (
        rendered
    )
    assert "as published" not in rendered


def _grouped(count: int, domain: str = "Digital") -> str:
    """One act page from a watchlist of `count` acts, all in one domain. The first is rendered."""
    from emendrix.watch.config import Watchlist

    watchlist = Watchlist.model_validate(
        {
            "acts": [
                {"celex": f"32016R{700 + index:04d}", "name": f"Act {index}", "domain": domain}
                for index in range(count)
            ]
        }
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    return render_act(site, site.acts[0])


def test_an_act_links_the_others_the_watchlist_puts_in_its_group() -> None:
    """The domain is the watchlist's own label, so the line infers nothing; the order is
    `collect_site`'s, which is the acts index's, so the two agree without a second sort."""
    rendered = _grouped(3)
    line = rendered.split('<p class="related">')[1].split("</p>")[0]
    assert line.startswith("Also watched in Digital: ")
    assert '<a href="../../acts/32016R0701/">Act 1</a>' in line
    assert '<a href="../../acts/32016R0702/">Act 2</a>' in line
    assert "Act 0" not in line


def test_the_related_line_stops_at_six_and_links_the_group_instead() -> None:
    """A domain of forty acts is a page of its own, and this is a line under a header."""
    six = _grouped(7)
    assert six.count('<a href="../../acts/32016R0') == 6
    assert "all 7 →" not in six
    seven = _grouped(8)
    assert seven.count('<a href="../../acts/32016R0') == 6
    assert '<a href="../../acts/#Digital">all 8 →</a>' in seven


def test_an_act_alone_or_ungrouped_gets_no_related_line() -> None:
    """ "Also watched in Health" over no names is a heading with nothing under it, and an act
    the watchlist put in no group has no group to point at."""
    assert 'class="related"' not in _grouped(1)
    assert 'class="related"' not in _quiet()


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
    assert "<title>GDPR: every amendment — emendrix</title>" in rendered


def test_a_long_name_heads_the_page_and_the_label_stays_on_the_facts_line() -> None:
    """The H1 says the act the way a person types it; the short label and the key move one
    step down, to the facts line, so nothing a reader used to find the act is gone."""
    from emendrix.watch.config import Watchlist

    watchlist = Watchlist.model_validate(
        {
            "acts": [
                {
                    "celex": "32016R0679",
                    "name": "GDPR",
                    "long_name": "General Data Protection Regulation",
                }
            ]
        }
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    rendered = render_act(site, site.acts[0])
    assert "<h1>General Data Protection Regulation</h1>" in rendered
    assert '<p class="facts">GDPR · <code>32016R0679</code>' in rendered
    assert (
        "<title>General Data Protection Regulation (GDPR): every amendment — emendrix</title>"
        in rendered
    )
    assert "seen for General Data Protection Regulation." in rendered
    assert 'class="official"' not in rendered


def test_the_official_title_is_rendered_whole_however_long_it_is() -> None:
    """The cut at the changelog's cap stays for headings in a list; this is the one page whose
    job is to be the act, and the words past the cap are the ones a reader searched for."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    long_title = "House Rules of Flat 3B, " + "as agreed by every tenant of the building, " * 4
    assert len(long_title) > 120
    renamed = entry.model_copy(
        update={"act": entry.act.model_copy(update={"display_name": long_title})}
    )
    site = _site(renamed)
    rendered = render_act(site, site.acts[0])
    assert f'<p class="official">{long_title}</p>' in rendered
    assert "[…]" not in rendered


def test_the_sidebar_lists_touched_provisions_and_amendments() -> None:
    """The amendments list links event pages; a provision links its own history.

    The provision index pointed at the newest change's fragment on an event page until those
    pages existed. It asks "has anything ever touched Article 13?", and the answer to that is
    now a page rather than one arbitrary version transition, so no link in that list carries a
    fragment at all any more.
    """
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    act = site.acts[0]
    rendered = render_act(site, act)
    sidebar = rendered.split('<aside class="sidebar">')[1].split("</aside>")[0]
    assert f'href="../../{event_href(act.slug, entry.key)}"' in sidebar
    first = entry.changes[0].change
    assert f'href="../../{provision_href(act.slug, first.location.canonical)}"' in sidebar
    assert first.location.human in sidebar
    provisions = sidebar.split("Touched provisions")[1].split("<h2>Amendments</h2>")[0]
    assert "#" not in provisions


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


def test_the_header_states_the_act_before_it_offers_anything_to_do() -> None:
    """Four lines in one order: the name, the title the legislation publishes for itself, the
    facts that identify it elsewhere, and the two things a reader can do about it.

    The feed and the EUR-Lex link used to sit inside the facts chain, between a domain and a
    date, where an action read as another fact about the legislation.
    """
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    long_title = "House Rules of Flat 3B, as agreed by every tenant of the building"
    renamed = entry.model_copy(
        update={"act": entry.act.model_copy(update={"display_name": long_title})}
    )
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(renamed,),
        site_url="https://example.invalid/site",
    )
    rendered = render_act(site, site.acts[0])
    assert rendered.index("<h1>") < rendered.index('<p class="official">')
    assert rendered.index('<p class="official">') < rendered.index('<p class="facts">')
    assert rendered.index('<p class="facts">') < rendered.index('<p class="links">')
    links = rendered.split('<p class="links">')[1].split("</p>")[0]
    assert "Atom feed" in links
    facts = rendered.split('<p class="facts">')[1].split("</p>")[0]
    assert "Atom feed" not in facts
    assert "newest amendment" in facts


def test_an_act_with_nothing_to_link_gets_no_empty_line_of_links() -> None:
    """A build with no site URL mints no feed, and the toy corpus renders no official page."""
    rendered = _quiet()
    assert 'class="links"' not in rendered


def test_a_timeline_card_is_headed_by_its_date_with_the_version_pair_below() -> None:
    """A reader arriving at a timeline is asking when, so the date is the heading and the
    version pair sits one step down, where an identifier belongs. The `id` does not move."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    assert f'<article class="event" id="{entry.key}">' in rendered
    assert f"<h2>detected {OBSERVED.isoformat()}</h2>" in rendered
    assert (
        f'<p class="ident"><code>{entry.from_version} → {entry.to_version}</code></p>' in rendered
    )


_SECTION = re.compile(r'<section class="dates-named" id="dates-named">(.*?)</section>', re.DOTALL)
"""The dates section alone, so an assertion about it cannot be answered by the rest of the page."""


def _dated(added: tuple[date, ...] = (), removed: tuple[date, ...] = ()) -> str:
    """The act page for one event whose first change moved the dates handed in.

    Patched onto a real change because the toy corpus writes no date markup: it moves none,
    which is what makes the plain toy entry the input for the absent case below.
    """
    delta = _delta()
    changes = (
        delta.changes[0].model_copy(update={"dates_added": added, "dates_removed": removed}),
        *delta.changes[1:],
    )
    entry = diff_only_entry(delta.model_copy(update={"changes": changes}), detected_on=OBSERVED)
    site = _site(entry)
    return render_act(site, site.acts[0])


def test_the_act_lists_the_dates_its_amended_text_names() -> None:
    """One row per mention, sorted by the date, each saying which way the date moved and
    linking the two places a reader can check it: the provision's own history and the change
    block that moved it."""
    rendered = _dated((date(2027, 12, 2),), (date(2026, 8, 2),))
    (section,) = _SECTION.findall(rendered)
    assert "<h2>Dates the amended text names</h2>" in rendered
    assert escape(LEDE) in section
    assert '<span class="on">2026-08-02</span> removed from' in section
    assert '<span class="on">2027-12-02</span> added to' in section
    assert section.index("2026-08-02") < section.index("2027-12-02")
    assert 'href="../../acts/house-rules/ar-2/">Art. 2</a>' in section
    assert 'href="../../acts/house-rules/v2/#v2-ar-2">detected 2026-08-09</a>' in section


def test_the_list_says_what_it_is_and_never_calls_a_date_a_deadline() -> None:
    """The lede is the whole of the care taken: it says the list is dates the text contains,
    says where the other question is answered, and the words for that reading appear nowhere."""
    (section,) = _SECTION.findall(_dated((date(2027, 12, 2),)))
    assert "This is a list of dates the text contains." in escape(LEDE)
    assert "&quot;applies from&quot;, and nowhere else." in section
    for word in ("deadline", "obligation", "compliance date", "timeline of obligations"):
        assert word not in section


def test_an_act_whose_changes_moved_no_date_gets_no_section_and_no_index_link() -> None:
    """Most acts are this one: a heading over an empty list is a page inventing a subject."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = render_act(site, site.acts[0])
    assert "dates-named" not in rendered


def test_the_index_links_the_section_wherever_it_exists() -> None:
    rendered = _dated((date(2027, 12, 2),))
    assert '<p class="small"><a href="#dates-named">Dates named</a></p>' in rendered
    assert rendered.index('href="#dates-named"') < rendered.index('id="dates-named"')


def test_the_list_folds_once_it_is_longer_than_a_screenful() -> None:
    """A list of scores of dates standing in front of the timeline would be the section
    answering a question nobody asked; the fold says how many rows it holds."""
    dates = tuple(date(2027, 1, 1) + timedelta(days=day) for day in range(FOLD_ABOVE))
    (section,) = _SECTION.findall(_dated(dates))
    assert "<summary>" not in section
    (longer,) = _SECTION.findall(_dated((*dates, date(2028, 1, 1))))
    assert f"<details><summary>{FOLD_ABOVE + 1} dates</summary>" in longer
