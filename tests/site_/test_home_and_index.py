"""The front door and the roster."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from site_entries import attributed_entry, disputed_entry, unattributed_entry

from emendrix.core import Delta, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.dispute import DISPUTED_GLOSS
from emendrix.site_.inputs import collect_site
from emendrix.site_.markup import escape
from emendrix.site_.pages.acts_index import render_acts_index
from emendrix.site_.pages.home import render_home
from emendrix.site_.pitch import SCOPE
from emendrix.site_.urls import domain_anchor, event_href
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
    assert f'href="{event_href(site.acts[0].slug, entry.key)}"' in rendered
    assert "Latest amendments" in rendered


def test_home_credibility_strip_reads_from_the_report_and_links_methodology() -> None:
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    rendered = render_home(site)
    pair = _run().metrics.localisation
    assert pair is not None
    assert f"{pair.micro_f1:.3f}" in rendered
    assert 'href="methodology/"' in rendered


def test_the_measured_claim_is_read_before_the_list_it_qualifies() -> None:
    """One line between the hero and the amendments, not a footnote under them.

    A stranger decides whether to believe a machine-computed legal tool before reading its
    output. The strip moved above the list on 2026-09-03 for that reason, and the order is
    asserted rather than left to the sequence of calls in `render_home`.
    """
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    rendered = render_home(site)
    assert rendered.index('<p class="strip">') < rendered.index("<h2>Latest amendments</h2>")


def test_a_card_leads_with_the_act_and_carries_the_version_pair_below_it() -> None:
    """The heading is the name and the link; the identifier is a line of its own, one step down."""
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(_entry(),),
        configured=True,
    )
    act = site.acts[0]
    entry = act.entries[0]
    href = event_href(act.slug, entry.key)
    rendered = render_home(site)
    assert f'<h3><a href="{href}">{escape(act.label)}</a></h3>' in rendered
    assert (
        f'<p class="ident"><code class="id">{entry.from_version} → {entry.to_version}</code></p>'
        in rendered
    )


def test_the_home_title_names_the_category_a_reader_searches_for() -> None:
    """The one place the category words are spelled out. The headline and the pitch keep
    their own voice: a title is what a search result shows, and the page is what it opens."""
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    rendered = render_home(site)
    assert "<title>emendrix — provision-level changelogs for EU regulations</title>" in rendered
    assert "What changed in your regulations?" in rendered


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
    assert rendered.count('<article class="cardrow">') == 2
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
    assert rendered.count('<article class="cardrow">') == 1
    assert "1 event naming no amending act is on the act pages, not in this list." in rendered
    assert f"/{unnamed.key}/" not in rendered


def test_home_with_only_events_naming_no_amending_act_says_so() -> None:
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(unattributed_entry(),),
        configured=True,
    )
    rendered = render_home(site)
    assert '<article class="cardrow">' not in rendered
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
    assert "no amendment recorded" in rendered


def test_the_lede_says_what_kinds_of_act_the_roster_holds() -> None:
    """ "67 acts" says nothing about whether the act a reader came for could be here at all.
    The words and the counts are the composition root's; this page prints them."""
    watchlist = Watchlist.model_validate(
        {"acts": [{"celex": f"32016R{700 + index:04d}"} for index in range(4)]}
    )
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        watchlist=watchlist,
        kinds=(("Regulation", 4),),
    )
    assert "4 acts watched, all of them Regulations." in render_acts_index(site)
    one = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), kinds=(("Decision", 1),)
    )
    assert "watched, a Decision." in render_acts_index(one)
    two = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        kinds=(("Regulation", 60), ("Directive", 7)),
    )
    assert "watched, 60 Regulations and 7 Directives." in render_acts_index(two)
    bare = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    assert "0 acts watched. " in render_acts_index(bare)


def test_the_scope_paragraph_is_printed_only_while_the_roster_makes_it_true() -> None:
    """It claims no Directive is watched. The day one is, the sentence would be the site being
    wrong about itself, so it is rendered from the roster's own kinds rather than standing."""
    regulations = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), kinds=(("Regulation", 4),)
    )
    assert escape(SCOPE) in render_acts_index(regulations)
    mixed = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        kinds=(("Regulation", 60), ("Directive", 7)),
    )
    assert escape(SCOPE) not in render_acts_index(mixed)
    bare = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    assert escape(SCOPE) not in render_acts_index(bare)


def test_every_domain_heading_carries_the_id_an_act_page_links_to() -> None:
    """The act pages link `acts/#<domain>`; without the id that link lands at the top."""
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
    assert f'<h2 id="{domain_anchor("Data & privacy")}">Data &amp; privacy</h2>' in rendered
    assert f'<h2 id="{domain_anchor("Other")}">Other</h2>' in rendered


def test_the_index_row_links_the_long_form_and_keeps_the_label_beside_it() -> None:
    """A reader scanning the roster for an initialism still finds the row.

    The label rides in the identity span with the key, and is absent when it would only
    repeat the link: a row reading `AI Act · AI Act` says nothing twice.
    """
    watchlist = Watchlist.model_validate(
        {
            "acts": [
                {
                    "celex": "32016R0679",
                    "name": "GDPR",
                    "long_name": "General Data Protection Regulation",
                },
                {"celex": "32024R1689", "name": "AI Act"},
            ]
        }
    )
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), watchlist=watchlist
    )
    rendered = render_acts_index(site)
    assert (
        '<a href="../acts/32016R0679/">General Data Protection Regulation</a> '
        '<span class="ident">GDPR · <code class="id">32016R0679</code></span>' in rendered
    )
    assert (
        '<a href="../acts/32024R1689/">AI Act</a> '
        '<span class="ident"><code class="id">32024R1689</code></span>' in rendered
    )


def test_every_index_row_carries_the_act_key() -> None:
    """The identifier is on every row, one step down: it is what a reader pastes elsewhere."""
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"))
    rendered = render_acts_index(site)
    for act in site.acts:
        assert f'<code class="id">{act.act.key}</code>' in rendered


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
    """Neither a date (nothing was amended) nor "no amendment recorded" (events exist and the
    act's page shows them): the third state gets its own words."""
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(unattributed_entry(),)
    )
    rendered = render_acts_index(site)
    assert "events recorded, none names an amending act" in rendered
    assert "no amendment recorded" not in rendered
    assert "in force 2" not in rendered and "detected 2" not in rendered


def test_every_act_on_the_index_links_its_page() -> None:
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    rendered = render_acts_index(site)
    assert f'href="../acts/{site.acts[0].slug}/"' in rendered


def test_a_disputed_count_never_stands_without_the_sentence_saying_what_it_means() -> None:
    """`36 provisions, 36 disputed` reads as a failure rate to a reader who has met no other
    page. The count stays, because the mark is the project's own promise not to drop the
    change; what travels with it is the sentence saying the disagreement is between the
    sources and not about the law.
    """
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(disputed_entry(),),
        configured=True,
    )
    rendered = render_home(site)
    assert rendered.count(escape(DISPUTED_GLOSS)) == 2
    assert f'<span class="disp" title="{escape(DISPUTED_GLOSS)}">1 disputed change</span>' in (
        rendered
    )


def test_a_home_page_with_nothing_disputed_carries_neither_the_gloss_nor_the_span() -> None:
    """A sentence explaining a mark that is nowhere on the page reads as a warning about it."""
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(attributed_entry(),),
        configured=True,
    )
    rendered = render_home(site)
    assert "disputed" not in rendered
    assert 'class="disp"' not in rendered


def test_a_card_names_the_instrument_beside_the_count_it_is_a_count_of() -> None:
    """The clause rides with the provision count, not in a segment of its own: it says what
    the count is a count of. The toy act's key is not a CELEX, so the key is the name."""
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(attributed_entry(),)
    )
    rendered = render_home(site)
    assert "4 provisions by house-rules-amendment-1 ·" in rendered


def test_a_card_for_an_event_naming_no_instrument_reads_as_it_always_did() -> None:
    """Nothing on the card grew a blank: an event with no name to print prints none. Such an
    event never reaches this list at all, so the assertion is over the act page's card."""
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    rendered = render_home(site)
    assert "4 provisions ·" in rendered
    assert "provisions by" not in rendered


def test_the_roster_row_names_the_instrument_behind_the_newest_amendment() -> None:
    """The date fact answers "when", and now also "by what": the fact a reader scanning the
    roster for one act is looking for."""
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(attributed_entry(),)
    )
    rendered = render_acts_index(site)
    assert "in force 2026-06-01 by house-rules-amendment-1</span>" in rendered


def test_the_roster_row_for_an_act_with_no_named_instrument_keeps_its_bare_date() -> None:
    site = collect_site(
        generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(_entry(),)
    )
    rendered = render_acts_index(site)
    assert f"detected {OBSERVED.isoformat()}</span>" in rendered
