"""One event's page: every change with its anchor, and the honesty markers it may never lose.

These assertions lived beside the act page's until the evidence moved to each event's own
page; what a change block owes a reader did not move with the address, so the tests moved
whole: the stable anchor, the disagreement marker in a newcomer's words, the gate's
provenance marker, and a stated reason wherever prose is absent.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from emendrix.core import Delta, ProvisionLocation, ProvisionTree, Signal, SignalClaim, SignalReport
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange, EmittedDelta, EmittedSentence
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.pages.event import render_event_page
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


def _page(entry: ChangelogEntry) -> str:
    site = _site(entry)
    return render_event_page(site, site.acts[0], site.acts[0].entries[0])


def test_the_page_shows_every_change_with_a_stable_anchor() -> None:
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    rendered = _page(entry)
    assert f'id="{entry.key}"' in rendered
    for emitted in entry.changes:
        assert emitted.change.location.human in rendered
    assert rendered.count('<div class="chg"') == len(entry.changes)
    assert "<details" in rendered


def test_the_page_names_its_act_and_links_back_to_the_timeline() -> None:
    """A reader lands here from a feed or a search result, so the act's identity and the way
    to the rest of its history cannot be assumed to have been seen already."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    rendered = _page(entry)
    assert f"<h1>{site.acts[0].headline}</h1>" in rendered
    assert f'href="../../../acts/{site.acts[0].slug}/"' in rendered
    assert "every event for this act" in rendered


def test_a_long_name_heads_the_page_and_the_label_opens_the_facts_line() -> None:
    """The act page's rule, held on the event page: the long form is the H1, and the short
    label a reader may have searched for stays visible beside the key."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    act = site.acts[0].model_copy(update={"long_name": "House Rules of Flat 3B"})
    rendered = render_event_page(site, act, act.entries[0])
    assert "<h1>House Rules of Flat 3B</h1>" in rendered
    assert f'<p class="facts">{act.label} · <code>{act.act.key}</code>' in rendered
    assert f"<title>{act.label}: " in rendered
    assert 'content="House Rules of Flat 3B: 4 provisions changed, detected' in rendered


def test_the_title_names_the_count_and_the_clock_rather_than_the_version_pair() -> None:
    """What a reader learns by opening the page, said in the title: how much changed and when,
    with the clock named as every dated line on the site names it. The toy entry carries no
    in-force date, so the clock is the detection one."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    assert not entry.in_force
    assert entry.counts.touched == 4
    site = _site(entry)
    rendered = _page(entry)
    label = site.acts[0].label
    assert f"<title>{label}: 4 provisions changed, detected 2026-08-09 — emendrix</title>" in (
        rendered
    )
    assert "4 provisions changed, detected 2026-08-09. Every changed provision, with" in rendered
    assert "from consolidated version v2." in rendered
    stated = entry.model_copy(update={"in_force": (date(2024, 6, 1),)})
    rendered = _page(stated)
    assert f"<title>{label}: 4 provisions changed, in force 2024-06-01 — emendrix</title>" in (
        rendered
    )


def test_an_event_that_touched_nothing_is_titled_in_words_not_as_a_zero() -> None:
    """`0 provisions changed` reads as a counter that failed; the finding is a sentence."""
    from site_entries import untouched_entry

    rendered = _page(untouched_entry())
    assert "no provisions differ, detected 2026-08-09 — emendrix</title>" in rendered
    assert "0 provisions changed" not in rendered


def _disputed_entry() -> ChangelogEntry:
    """One entry whose changes the metadata signal saw only for `AR 9`, so the rest disagree."""
    metadata = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(SignalClaim(location=ProvisionLocation.parse("AR 9")),),
    )
    return diff_only_entry(corroborate(_delta(), metadata=metadata).delta, detected_on=OBSERVED)


def test_a_disputed_change_says_what_disagreed_without_saying_disputed() -> None:
    """The stored vocabulary is `disputed`; a page that prints it invites the wrong reading.

    A newcomer takes "disputed" for a claim about the law. The claim is about the tool, so the
    marker names the sources and says neither is overruled.
    """
    rendered = _page(_disputed_entry())
    assert "<strong>Sources disagree</strong>" in rendered
    assert (
        "the text comparison found this change; the EU&#x27;s own amendment metadata does not "
        "list it. Both are shown; neither is overruled." in rendered
    )
    assert "<strong>Disputed</strong>" not in rendered


def test_the_three_sources_explainer_is_said_once_above_the_first_disagreement() -> None:
    rendered = _page(_disputed_entry())
    assert rendered.count("Emendrix checks every change against three independent sources") == 1
    assert rendered.index("three independent sources") < rendered.index("Sources disagree")


def test_a_page_with_no_disagreement_does_not_explain_one() -> None:
    """An explanation of something absent from the page reads as a warning about it."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    assert entry.counts.disputed == 0
    rendered = _page(entry)
    assert "three independent sources" not in rendered


def test_a_gate_written_sentence_keeps_its_marker_and_is_not_capped() -> None:
    delta = _delta()
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    long_text = "A sentence the gate quoted verbatim from the rule. " * 20
    entry = ChangelogEntry.of(
        EmittedDelta(
            act=delta.act,
            from_version=delta.from_version,
            to_version=delta.to_version,
            summary=delta.summary,
            changes=tuple(
                EmittedChange(
                    change=change,
                    outcome=GateOutcome.FALLBACK,
                    sentences=(
                        EmittedSentence(
                            text=long_text,
                            fallback=True,
                            citations=(adapter.render_citation(change.provision),),
                        ),
                    ),
                )
                for change in delta.changes
            ),
        ),
        detected_on=OBSERVED,
    )
    rendered = _page(entry)
    assert "Quoted verbatim by the citation gate" in rendered
    assert "truncated by emendrix" not in rendered
    assert " ".join(long_text.split()) in rendered


def test_a_change_with_no_prose_says_why_rather_than_showing_nothing() -> None:
    """The stage ran and produced nothing for this change; the block says which of the two."""
    delta = _delta()
    entry = ChangelogEntry.of(
        EmittedDelta(
            act=delta.act,
            from_version=delta.from_version,
            to_version=delta.to_version,
            summary=delta.summary,
            changes=tuple(
                EmittedChange(
                    change=change,
                    outcome=GateOutcome.UNEXPLAINED,
                    unexplained="the model returned no sentence for this change",
                )
                for change in delta.changes
            ),
        ),
        detected_on=OBSERVED,
    )
    rendered = _page(entry)
    assert "the model returned no sentence for this change" in rendered


def _headed(**update: object) -> str:
    """One event page, its entry patched, for reading the heading and the dates line off."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED).model_copy(update=update)
    site = _site(entry)
    return render_event_page(site, site.acts[0], site.acts[0].entries[0])


def test_the_event_is_headed_by_its_date_and_the_dates_line_carries_the_other_clock() -> None:
    """The H1 names the act, the H2 the date the event's own clock answers with, and the line
    below states the clock the heading did not, never the one it did."""
    rendered = _headed(in_force=(date(2024, 6, 1),))
    assert "<h2>in force 2024-06-01</h2>" in rendered
    assert '<p class="facts">detected 2026-08-09</p>' in rendered
    # The title and the meta description name the dated words too, and should. What must not
    # happen is the line under the heading restating the heading.
    assert '<p class="facts">in force' not in rendered


def test_an_event_with_no_in_force_date_is_headed_by_detection_and_says_so_below() -> None:
    """The heading names the only clock there is, so the line below is what is missing rather
    than the detection date a second time."""
    rendered = _headed(in_force=())
    assert "<h2>detected 2026-08-09</h2>" in rendered
    assert '<p class="facts">in force not stated</p>' in rendered
    assert '<p class="facts">detected' not in rendered


def test_an_event_with_several_in_force_dates_lists_them_all_below_its_heading() -> None:
    """The heading can name only one date. Where the corpus states more, the line below is the
    whole set, which is more than the heading said and so is not a repetition of it."""
    rendered = _headed(in_force=(date(2024, 6, 1), date(2025, 1, 2)))
    assert "<h2>in force 2025-01-02</h2>" in rendered
    assert '<p class="facts">in force 2024-06-01, 2025-01-02 · detected 2026-08-09</p>' in rendered


def test_the_event_page_names_the_act_and_the_version_pair_under_the_heading() -> None:
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    stated = entry.model_copy(update={"in_force": (date(2024, 6, 1),)})
    site = _site(stated)
    rendered = render_event_page(site, site.acts[0], site.acts[0].entries[0])
    assert f"<h1>{site.acts[0].headline}</h1>" in rendered
    assert (
        f'<p class="ident"><code>{stated.from_version} → {stated.to_version}</code></p>' in rendered
    )


def test_the_title_and_the_description_name_the_instrument_that_made_the_event() -> None:
    """The name a reader searched for, in the two strings a result is drawn from. It is the
    short name the site knows: no watchlist label and no number for the toy act, so the key."""
    from site_entries import attributed_entry

    rendered = _page(attributed_entry())
    assert "changed by house-rules-amendment-1, " in rendered
    assert "— emendrix</title>" in rendered


def test_the_event_says_which_instrument_amended_it_with_the_identifier_beside_the_name() -> None:
    """No number and no address for a key that is not a CELEX, so the key is the whole name."""
    from site_entries import attributed_entry

    rendered = _page(attributed_entry())
    assert '<p class="amending">Amended by house-rules-amendment-1</p>' in rendered


def test_the_recorded_official_title_is_printed_on_the_page_and_only_when_known() -> None:
    """The words a reader searched for are in the official title, and this is the one surface
    with room for one. A mention carrying no title prints no empty line."""
    from site_entries import attributed_entry

    entry = attributed_entry()
    assert '<p class="official">Rule change, June</p>' in _page(entry)
    untitled = entry.model_copy(
        update={
            "changes": tuple(
                emitted.model_copy(
                    update={
                        "change": emitted.change.model_copy(
                            update={
                                "amending_acts": tuple(
                                    act.model_copy(update={"display_name": None})
                                    for act in emitted.change.amending_acts
                                )
                            }
                        )
                    }
                )
                for emitted in entry.changes
            ),
            "corroboration": None,
        }
    )
    rendered = _page(untitled)
    assert '<p class="amending">' in rendered
    assert '<p class="official">' not in rendered


def test_an_event_naming_no_amending_act_says_so_and_gains_no_line() -> None:
    """Unchanged from before this page could name an instrument: one answer, not two."""
    from site_entries import unattributed_entry

    site = _site(unattributed_entry())
    rendered = render_event_page(site, site.acts[0], site.acts[0].entries[0])
    assert 'class="amending"' not in rendered
    assert "no amending act named" in rendered
    label = site.acts[0].label
    assert f"<title>{label}: 4 provisions changed, detected 2026-08-09 — emendrix</title>" in (
        rendered
    )
