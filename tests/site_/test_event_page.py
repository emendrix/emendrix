"""One event's page: every change with its anchor, and the honesty markers it may never lose.

These assertions lived beside the act page's until the evidence moved to each event's own
page; what a change block owes a reader did not move with the address, so the tests moved
whole: the stable anchor, the disagreement marker in a newcomer's words, the gate's
provenance marker, and a stated reason wherever prose is absent.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from helpers import text_of

from emendrix.core import (
    ActId,
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionText,
    ProvisionTree,
    Signal,
    SignalClaim,
    SignalReport,
    VersionId,
)
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange, EmittedDelta, EmittedSentence
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.clocks import version_heading
from emendrix.site_.inputs import ActSite, SiteInputs, collect_site
from emendrix.site_.markup import escape
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.event_index import INDEX_ABOVE
from emendrix.site_.pages.prose import applies_line
from emendrix.site_.pages.texts import text_blocks
from emendrix.site_.style import STYLE
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)

_SCRIPT = re.compile(r"<script\b.*?</script>", re.DOTALL)
"""Tags and their contents, for a check about words: `text_of` strips only the tags, and the
inline JSON-LD block every page carries would otherwise be read as part of the prose."""


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _site(*entries: ChangelogEntry, changelogs_url: str = "") -> SiteInputs:
    return collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=entries,
        changelogs_url=changelogs_url,
    )


def _rendered(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> str:
    """One event page through the builder's own signature: the evidence blocks arrive with it."""
    return render_event_page(site, act, entry, text_blocks(entry))


def _page(entry: ChangelogEntry) -> str:
    site = _site(entry)
    return _rendered(site, site.acts[0], site.acts[0].entries[0])


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
    assert f"<h1>{version_heading(entry)}</h1>" in rendered
    assert f"<h1>{site.acts[0].headline}</h1>" not in rendered
    assert f'href="../../../acts/{site.acts[0].slug}/"' in rendered


def test_the_context_bar_is_there_exactly_when_the_index_is() -> None:
    """Pinned while a long page scrolls, it names the act as a link to the act's page, the
    version by its name, and links the index; a short page, with no index, has neither."""
    from site_entries import some_textless_entry

    short = diff_only_entry(_delta(), detected_on=OBSERVED)
    assert 'class="context"' not in _page(short)
    assert '<nav class="touched"' not in _page(short)

    mixed = some_textless_entry()
    entry = mixed.model_copy(update={"changes": (*mixed.changes, mixed.changes[0])})
    assert len(entry.changes) >= INDEX_ABOVE
    site = _site(entry)
    act = site.acts[0]
    rendered = _rendered(site, act, act.entries[0])
    bar = (
        f'<div class="context"><p><a href="../../../acts/{act.slug}/">{escape(act.label)}</a> · '
        f'{version_heading(entry)} · <a href="#changes-index">Index</a></p></div>'
    )
    assert rendered.count(bar) == 1
    assert rendered.count('<nav class="touched" id="changes-index"') == 1
    # After the version's masthead, so a keyboard reader meets it once the page has said what
    # it is, and before the index it links.
    assert rendered.index('<div class="version-masthead"') < rendered.index(bar)
    assert rendered.index(bar) < rendered.index('<nav class="touched"')


def test_the_label_names_the_act_in_the_caption_and_the_long_name_in_the_snippet() -> None:
    """The version's heading is its own, so the act is named by its short label in the caption,
    linked back to the act, and by its long form in the description a snippet is read under."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry)
    act = site.acts[0].model_copy(update={"long_name": "House Rules of Flat 3B"})
    rendered = _rendered(site, act, act.entries[0])
    assert "<h1>House Rules of Flat 3B</h1>" not in rendered
    assert (
        f'<p class="caption">Version · <a href="../../../acts/{act.slug}/">{act.label}</a></p>'
        in rendered
    )
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


def test_an_event_with_no_text_anywhere_says_that_in_its_title_and_its_description() -> None:
    """Every unit here was named by a source that carries no text, so nothing on the page
    changed in any text this site can show, and `2 provisions changed` would say it did."""
    from site_entries import textless_entry

    rendered = _page(textless_entry())
    assert "2 provisions named with no text to show" in rendered
    assert "2 provisions changed" not in rendered
    assert '<p class="tally">2 provisions named with no text to show</p>' in rendered
    assert '<span class="tag tag--differ">2 where sources differ</span>' in rendered
    assert "without text</span>" not in rendered
    assert "Each provision, with the source that named it, from consolidated" in rendered
    assert "the verbatim text before and after" not in rendered


def test_no_markdown_fence_reaches_the_words_of_a_change_with_no_text() -> None:
    """The reason is stored on the document and escaped into the page, which is correct and
    stays correct, so the sentence itself may carry no markup of any format: a fence would
    reach a reader as two stray characters here and as an element in the changelog."""
    from site_entries import textless_entry

    rendered = _page(textless_entry())
    assert '<p class="none">No explanation shipped — ' in rendered
    assert "another source named the provision, and it is listed where sources differ" in rendered
    assert "disputed" not in text_of(_SCRIPT.sub("", rendered))
    assert "`" not in text_of(_SCRIPT.sub("", rendered))


def _disputed_entry() -> ChangelogEntry:
    """One entry whose changes the metadata signal saw only for `AR 9`, so the rest disagree.

    Five disagreements in two shapes: the four the comparison read and the metadata did not
    list, and `AR 9`, which the metadata named and the comparison never saw, so it carries no
    text at all and is appended by the corroborator.
    """
    metadata = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(SignalClaim(location=ProvisionLocation.parse("AR 9")),),
    )
    return diff_only_entry(corroborate(_delta(), metadata=metadata).delta, detected_on=OBSERVED)


def test_a_disputed_change_says_what_disagreed_without_saying_disputed() -> None:
    """The stored vocabulary is `disputed`; a page that prints it invites the wrong reading.

    A newcomer takes "disputed" for a claim about the law. The claim is about the tool, so the
    marker names the sources and says neither is overruled.

    The lead also says which shape the disagreement has. These changes are the evidenced one:
    the comparison read the text, which is on the page below the marker, and the metadata did
    not list it. The block carries that shape as a class and says it with the shape's tag,
    beside the link to what the tag means.
    """
    rendered = _page(_disputed_entry())
    assert "<strong>Found in the text, but not every source lists it</strong>" in rendered
    assert (
        "the text comparison found this change; the EU&#x27;s own amendment metadata does not "
        "list it. Both are shown; neither is overruled." in rendered
    )
    assert "<strong>Disputed</strong>" not in rendered
    assert rendered.count('<div class="chg differ-text"') == 4
    assert "differ-kind" not in rendered
    assert (
        rendered.count(
            '<p><span class="tag tag--differ-text">Not in every list</span><a class="define" '
            'href="../../../methodology/#sources-differ">What this means</a></p>'
        )
        == 4
    )


def test_the_masthead_tags_say_what_the_sources_differ_count_is_a_count_of() -> None:
    """One number covers three findings, and the tags after it add back up to that number.

    They are read off the same function the site's published rates are counted by, so the tags
    over a version and the methodology table cannot say different things about one corpus. A
    shape with no change in it gets no tag, and the word the stored field is named by is not
    printed.
    """
    rendered = _page(_disputed_entry())
    assert '<span class="tag tag--differ">5 where sources differ</span>' in rendered
    assert '<span class="tag tag--differ-text">4 not in every list</span>' in rendered
    assert '<span class="tag tag--differ-none">1 no text found</span>' in rendered
    assert "tag--differ-kind" not in rendered
    assert "5 disputed" not in rendered


def test_a_version_with_nothing_disputed_gets_no_sources_differ_tag() -> None:
    """There is no shape of a disagreement that did not happen, and no zero is printed for it."""
    rendered = _page(diff_only_entry(_delta(), detected_on=OBSERVED))
    assert "tag--differ" not in rendered
    assert "where sources differ" not in rendered


def test_the_changes_with_no_text_are_gathered_and_every_one_is_still_on_the_page() -> None:
    """A row that can show a reader nothing is one line; nothing about it leaves the page.

    The mixed event is the one that matters here: four changes carrying text and one carrying
    none. The four stay where they are, the fifth moves to the foot under a heading that counts
    them, and it keeps its anchor, its permalink, its disagreement note and its own reason for
    carrying no prose.
    """
    from site_entries import some_textless_entry

    entry = some_textless_entry()
    rendered = _page(entry)
    (quiet,) = [emitted for emitted in entry.changes if emitted.change.textless]
    anchor = f"{entry.key}-{quiet.change.location.canonical.lower().replace(' ', '-')}"
    assert "<h3>1 provision named with no text to show</h3>" in rendered
    assert "None was dropped and every one still counts where sources differ above." in rendered
    section = rendered[rendered.index('<section class="quiet">') :]
    assert f'<div class="chg differ-none" id="{anchor}">' in section
    assert f'<a class="permalink" href="#{anchor}"' in section
    assert "named by the EU&#x27;s own amendment metadata" in section
    assert "A source lists it, but there is no text to show" in section
    assert '<span class="tag tag--differ-none">No text found</span>' in section
    # The four that carry text are blocks above the gathered list, not rows inside it.
    assert rendered.count('<div class="chg') == len(entry.changes)
    assert section.count('<div class="chg') == 1
    # The heading counts rows and calls them provisions, which is only honest because the
    # corroborator appends one such change per top-level unit: the number it prints is the
    # `without text` figure the tally above states, reached by a different route.
    assert entry.counts.textless == 1
    assert '<span class="tag tag--no-text">1 without text</span>' in rendered


def test_a_permalink_into_the_gathered_list_opens_the_row_it_names() -> None:
    """A `§` that scrolled to a row a reader still could not read would be a worse promise.

    The row is collapsed by the sheet and reopened by `:target`, which is exactly what its own
    permalink sets, so the link that names a row is the link that opens it. Both halves are
    asserted: the markup pairs the anchor with the id, and the sheet reveals a targeted row.
    """
    from site_entries import some_textless_entry

    rendered = _page(some_textless_entry())
    section = rendered[rendered.index('<section class="quiet">') :]
    (target,) = re.findall(r'<div class="chg differ-none" id="([^"]+)">', section)
    assert f'href="#{target}"' in section
    assert ".quiet .chg > *:not(h3) { display: none; }" in STYLE
    assert ".quiet .chg:target > *:not(h3) { display: block; }" in STYLE


def test_the_outright_contradiction_about_kind_is_the_one_that_reads_as_an_alert() -> None:
    """The smallest and loudest of the three shapes, on the page and in the sheet.

    Every source that looked found the provision and they named different kinds, so nothing is
    missing and nothing is unlisted: the lead says so, the block carries the kind class, and its
    tag and note are the only ones of the three the sheet draws in the alert colour.
    """
    metadata = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=tuple(
            SignalClaim(location=change.unit, change_type=ChangeType.INSERTED)
            for change in _delta().changes
        ),
    )
    entry = diff_only_entry(corroborate(_delta(), metadata=metadata).delta, detected_on=OBSERVED)
    rendered = _page(entry)
    assert rendered.count('<div class="chg differ-kind"') == 3
    assert "<strong>The sources name different kinds of change</strong>" in rendered
    assert rendered.count('<span class="tag tag--differ-kind">Kinds differ</span>') == 3
    assert '<span class="tag tag--differ">3 where sources differ</span>' in rendered
    assert '<span class="tag tag--differ-kind">3 kinds differ</span>' in rendered
    assert ".differ-kind .differ strong { color: var(--alert); }" in STYLE


def test_the_tags_are_followed_by_one_link_to_the_glossary_that_defines_them() -> None:
    """The three sources are explained once, on the methodology page, where every tag's word is
    defined; the page links there once, under its tags, and never from a tag itself."""
    rendered = _page(_disputed_entry())
    assert (
        rendered.count('<a class="go" href="../../../methodology/#glossary">What these mean</a>')
        == 1
    )
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


def _retitled(location: str, heading: str | None, text: str) -> str:
    """One event page whose first change is moved to `location` and titled and worded anew."""
    delta = _delta()
    first = delta.changes[0]
    moved = first.model_copy(
        update={
            "provision": first.provision.model_copy(
                update={"location": ProvisionLocation.parse(location)}
            ),
            "heading": heading,
            "before": ProvisionText(text),
            "after": ProvisionText(text),
        }
    )
    entry = diff_only_entry(
        delta.model_copy(update={"changes": (moved, *delta.changes[1:])}), detected_on=OBSERVED
    )
    return _page(entry)


def test_an_annex_titled_only_by_its_number_is_headed_by_the_subject_its_text_opens_with() -> None:
    """The FIC Regulation's Annex II stores the heading `ANNEX II` and opens its text with the
    annex's own title and then its subject. The heading prints the subject as the text has it,
    marked for the sheet to set in small capitals, and never in a case the law did not use."""
    subject = "SUBSTANCES OR PRODUCTS CAUSING ALLERGIES OR INTOLERANCES"
    text = f"ANNEX II\n{subject}\n1. Cereals containing gluten, namely: wheat, rye"
    rendered = _retitled("AN II", "ANNEX II", text)
    assert f'Annex II</a> <span class="ttl ttl--caps">{subject}</span>' in rendered


def test_an_article_titled_only_by_its_number_prints_no_title_after_it() -> None:
    rendered = _retitled("AR 1", "Art. 1", "Art. 1\nSUBJECT MATTER\nThis Regulation applies.")
    assert 'Art. 1</a><span class="visually-hidden">,</span>' in rendered
    assert "SUBJECT MATTER</span>" not in rendered


def _headed(**update: object) -> str:
    """One event page, its entry patched, for reading the heading and the dates line off."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED).model_copy(update=update)
    site = _site(entry)
    return _rendered(site, site.acts[0], site.acts[0].entries[0])


def _gate_tags(**counts: int) -> list[str]:
    """The tag words of an explained version whose gate counts are patched to order."""
    from emendrix.output.counts import EntryCounts
    from emendrix.site_.tags import tally

    entry = diff_only_entry(_delta(), detected_on=OBSERVED).model_copy(
        update={
            "diff_only": False,
            "counts": EntryCounts(touched=4, substantive=4, **counts),
        }
    )
    return re.findall(
        r'<span class="tag tag--[a-z-]+">([^<]*)</span>', "".join(tally(entry, shapes=True))
    )


def test_the_tags_say_what_the_citation_check_found_in_the_readers_words() -> None:
    """The same two fields the summary has always carried, said as what they mean. A reader
    arriving at a version page has never heard of a gate, and "shipped" is a pipeline's word.
    Nothing unexplained and nothing quoted is one tag, not two absences."""
    assert _gate_tags() == ["All explained"]
    assert _gate_tags(unexplained=2) == ["2 without an explanation"]
    assert _gate_tags(quoted=1) == ["1 quoted verbatim"]
    assert _gate_tags(unexplained=2, quoted=1) == ["2 without an explanation", "1 quoted verbatim"]


def test_a_version_the_explain_stage_never_ran_for_says_so_in_its_own_tag() -> None:
    """A diff-only version has no explanations to have checked, which is a different answer
    from every explanation passing."""
    rendered = _headed(in_force=(date(2024, 6, 1),))
    assert '<span class="tag tag--diff-only">No explanations for this version</span>' in rendered
    assert "All explained" not in rendered


def _card(**update: object) -> str:
    """One version as the act page's card prints it, its entry patched to order."""
    from emendrix.site_.pages.version_card import version_card

    entry = diff_only_entry(_delta(), detected_on=OBSERVED).model_copy(update=update)
    return "\n".join(version_card(entry, "v/", (), level=2, root="../../"))


_FIRST_SEEN = (
    '<p class="dates">First seen by emendrix on <time datetime="2026-08-09">9 August 2026</time>, '
    "when it first read this version; that is not a legal date.</p>"
)


def test_the_version_is_headed_by_its_date_and_the_dates_line_carries_the_other_clock() -> None:
    """The H1 is the version by the date its own clock answers with, and the line below states
    the clock the heading did not, in words that say what that date is. The act page's card is
    headed by the same name, as a link to this page."""
    rendered = _headed(in_force=(date(2024, 6, 1),))
    assert '<h1>Version in force <time datetime="2024-06-01">1 June 2024</time></h1>' in rendered
    assert (
        '<h2><a href="v/">Version in force <time datetime="2024-06-01">1 June 2024</time></a></h2>'
        in _card(in_force=(date(2024, 6, 1),))
    )
    assert _FIRST_SEEN in rendered
    # The title and the meta description name the dated words too, and should. What must not
    # happen is the line under the heading restating the heading.
    assert '<p class="dates">In force' not in rendered


def test_a_version_with_no_in_force_date_is_headed_by_detection_and_says_so_below() -> None:
    """The heading names the only clock there is, so the line below is what is missing rather
    than the detection date a second time."""
    rendered = _headed(in_force=())
    assert '<h1>Version detected <time datetime="2026-08-09">9 August 2026</time></h1>' in rendered
    assert 'Version detected <time datetime="2026-08-09">9 August 2026</time></a></h2>' in _card(
        in_force=()
    )
    assert '<p class="dates">In force date not stated.</p>' in rendered
    assert "First seen by emendrix" not in rendered


def test_a_version_with_several_in_force_dates_lists_them_all_below_its_heading() -> None:
    """The heading can name only one date. Where the corpus states more, the line below is the
    whole set, which is more than the heading said and so is not a repetition of it."""
    rendered = _headed(in_force=(date(2024, 6, 1), date(2025, 1, 2)))
    assert '<h1>Version in force <time datetime="2025-01-02">2 January 2025</time></h1>' in rendered
    assert (
        '<p class="dates">In force <time datetime="2024-06-01">1 June 2024</time>, '
        '<time datetime="2025-01-02">2 January 2025</time>. First seen by emendrix on' in rendered
    )


def test_the_version_names_its_consolidated_versions_once_with_v1_and_v2_mapped() -> None:
    """The identifiers are secondary, and the one place the citation mapping is stated."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    stated = entry.model_copy(update={"in_force": (date(2024, 6, 1),)})
    site = _site(stated)
    rendered = _rendered(site, site.acts[0], site.acts[0].entries[0])
    assert f"<h1>{version_heading(stated)}</h1>" in rendered
    assert (
        f'<p class="ident">Consolidated versions <code class="id">{stated.from_version}</code> → '
        f'<code class="id">{stated.to_version}</code>. v1 is the previous version, v2 this one.</p>'
        in rendered
    )
    assert rendered.count("v1 is the previous version") == 1


def test_the_masthead_says_where_the_version_sits_in_the_act_s_history() -> None:
    site = _timeline(3)
    act = site.acts[0]
    newest, middle, oldest = act.entries
    label = act.label
    assert f"Version 3 of 3 recorded for {label}, the newest." in _rendered(site, act, newest)
    assert f"Version 2 of 3 recorded for {label}.</p>" in _rendered(site, act, middle)
    assert f"Version 1 of 3 recorded for {label}, the oldest recorded." in (
        _rendered(site, act, oldest)
    )


def test_the_title_and_the_description_name_the_instrument_that_made_the_event() -> None:
    """The name a reader searched for, in the two strings a result is drawn from. It is the
    short name the site knows: no watchlist label and no number for the toy act, so the key."""
    from site_entries import attributed_entry

    rendered = _page(attributed_entry())
    assert "changed by house-rules-amendment-1, " in rendered
    assert "— emendrix</title>" in rendered


def test_the_version_says_which_amending_act_made_it_and_links_its_page_here() -> None:
    """No number and no address for a key that is not a CELEX, so the key is the whole name,
    and it goes to the amending act's page on this site rather than off it."""
    from site_entries import attributed_entry

    rendered = _page(attributed_entry())
    assert (
        '<p class="amending">Made by <a href="../../../amendments/house-rules-amendment-1/">'
        "house-rules-amendment-1</a></p>" in rendered
    )


def test_the_recorded_official_title_is_printed_on_the_page_and_only_when_known() -> None:
    """The words a reader searched for are in the official title, and this is the one surface
    with room for one. A mention carrying no title prints no empty line."""
    from site_entries import attributed_entry

    entry = attributed_entry()
    assert '<p class="lede">Rule change, June</p>' in _page(entry)
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
    assert '<p class="lede">' not in rendered


def test_an_event_naming_no_amending_act_says_so_and_gains_no_line() -> None:
    """Unchanged from before this page could name an instrument: one answer, not two."""
    from site_entries import unattributed_entry

    site = _site(unattributed_entry())
    rendered = _rendered(site, site.acts[0], site.acts[0].entries[0])
    assert "Made by" not in rendered
    assert (
        '<p class="amending"><span class="tag tag--unattributed">no amending act named</span></p>'
        in rendered
    )
    assert "No amending act is named for this version" in rendered
    label = site.acts[0].label
    assert f"<title>{label}: 4 provisions changed, detected 2026-08-09 — emendrix</title>" in (
        rendered
    )


def _timeline(count: int) -> SiteInputs:
    """One act with `count` events, oldest to newest, each on its own version and detection day."""
    delta = _delta()
    entries = tuple(
        diff_only_entry(
            delta.model_copy(
                update={"from_version": VersionId(f"v{n}"), "to_version": VersionId(f"v{n + 1}")}
            ),
            detected_on=OBSERVED + timedelta(days=n),
        )
        for n in range(1, count + 1)
    )
    return _site(*entries)


def test_the_pager_links_the_versions_either_side_by_direction_with_each_date_under_it() -> None:
    """Older is `prev`, the act's timeline running newest first, and the words now say so. The
    pager is printed at the top and at the foot, and the two landmarks have different names."""
    site = _timeline(3)
    act = site.acts[0]
    newest, middle, oldest = act.entries
    rendered = _rendered(site, act, middle)
    assert '<nav class="pager" aria-label="Versions of this act (top)">' in rendered
    assert '<nav class="pager pager--foot" aria-label="Versions of this act">' in rendered
    older = (
        f'<a rel="prev" href="../{oldest.key}/"><span class="back">Previous version</span> '
        '<span class="small">detected <time datetime="2026-08-10">10 August 2026</time></span></a>'
    )
    newer = (
        f'<a rel="next" href="../{newest.key}/"><span class="go">Next version</span> '
        '<span class="small">detected <time datetime="2026-08-12">12 August 2026</time></span></a>'
    )
    assert rendered.count(older) == 2
    assert rendered.count(newer) == 2


def test_the_pager_is_half_missing_at_each_end_and_absent_for_a_lone_event() -> None:
    site = _timeline(3)
    act = site.acts[0]
    newest, _, oldest = act.entries
    assert 'rel="next"' not in _rendered(site, act, newest)
    assert 'rel="prev"' in _rendered(site, act, newest)
    assert 'rel="prev"' not in _rendered(site, act, oldest)
    assert 'rel="next"' in _rendered(site, act, oldest)
    lone = _timeline(1)
    assert 'class="pager' not in _rendered(lone, lone.acts[0], lone.acts[0].entries[0])


def test_the_event_links_the_page_of_every_instrument_it_names() -> None:
    from site_entries import attributed_entry

    rendered = _page(attributed_entry())
    assert (
        '<a href="../../../amendments/house-rules-amendment-1/">'
        "Everything house-rules-amendment-1 changed</a>" in rendered
    )


def test_the_other_acts_an_instrument_amended_are_named_only_when_there_are_some() -> None:
    """The act the reader is already on is never in that list, so one act alone says nothing."""
    from site_entries import attributed_entry

    entry = attributed_entry()
    site = _site(entry)
    assert "also changed" not in _rendered(site, site.acts[0], site.acts[0].entries[0])
    second = ActId(corpus="toy", key="second-house")
    shared = _site(entry, entry.model_copy(update={"act": second}))
    here = next(act for act in shared.acts if act.act != second)
    rendered = _rendered(shared, here, here.entries[0])
    assert f'also changed <a href="../../../acts/{second.key}/">{second.key}</a>' in rendered


def test_an_event_naming_no_instrument_gains_no_link_line() -> None:
    from site_entries import unattributed_entry

    site = _site(unattributed_entry())
    rendered = _rendered(site, site.acts[0], site.acts[0].entries[0])
    assert "amendments/" not in rendered.split("<main")[1]


def _explained(count: int, *, note: bool = False) -> ChangelogEntry:
    """The toy entry with `count` sentences on every change, each citing both versions.

    The citation pair is the same on every sentence of a change, which is the shape the
    committed corpus produces and the one a row per change exists for: a model writing two
    sentences about one provision cites the before and the after in both of them.
    """
    delta = _delta()
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)

    def explained(emitted: EmittedChange) -> EmittedChange:
        ref = emitted.change.provision
        cited = tuple(
            adapter.render_citation(ref.model_copy(update={"version": version}))
            for version in (delta.from_version, delta.to_version)
        )
        shipped = tuple(
            EmittedSentence(text=f"Sentence {index} about this provision.", citations=cited)
            for index in range(1, count + 1)
        )
        return emitted.model_copy(
            update={
                "outcome": GateOutcome.PASSED,
                "sentences": shipped,
                "applicability_note": (
                    EmittedSentence(text="It applies from the date stated.", citations=cited[-1:])
                    if note
                    else None
                ),
            }
        )

    entry = diff_only_entry(delta, detected_on=OBSERVED)
    return entry.model_copy(
        update={"changes": tuple(explained(emitted) for emitted in entry.changes)}
    )


def test_a_change_cites_its_provisions_once_however_many_sentences_named_them() -> None:
    """The distinct citations of a change, in first-mention order, in one row under its prose.

    Two sentences about one provision cite the same before-and-after pair, and printing that
    pair under each of them put the same two links on the page as many times as the model had
    sentences. What the reader needs is the pair, once. Nothing below the page moves: the
    committed JSON and Markdown keep every citation on the sentence that carried it, which is
    the form the citation gate resolves.
    """
    rendered = _page(_explained(2))
    entry = _explained(2)
    assert rendered.count('<p class="cites">Cited: ') == len(entry.changes)
    assert rendered.count("Sentence 2 about this provision.") == len(entry.changes)
    for emitted in entry.changes:
        for item in emitted.sentences[0].citations:
            assert rendered.count(f'href="{escape(item.url)}"') == 1
    row = re.search(r'<p class="cites">.*?</p>', rendered)
    assert row is not None
    assert row.group().count("<a ") == 2
    assert row.group().count('class="ext"') == 2
    assert rendered.count(
        '<p class="cites-key small">v1 is the previous version, v2 this one.</p>'
    ) == (len(entry.changes))


def test_no_citation_link_sits_inside_a_sentence_any_more() -> None:
    """The row is the only place a citation is linked on the page, so a sentence reads as one.

    Asserted as the whole paragraph, character for character: a sentence that still carried
    its links would be a longer element than this and the equality would say so.
    """
    rendered = _page(_explained(2))
    for index in (1, 2):
        assert f"<p>Sentence {index} about this provision.</p>" in rendered


def test_the_applicability_note_s_citation_is_in_the_row_with_the_sentences() -> None:
    """The note is prose the gate resolved like any other, so its citation is the change's."""
    rendered = _page(_explained(1, note=True))
    assert "It applies from the date stated." in rendered
    row = re.search(r'<p class="cites">.*?</p>', rendered)
    assert row is not None
    assert row.group().count("<a ") == 2


def test_a_change_with_nothing_cited_carries_no_citation_row() -> None:
    """An empty row would be a label with nothing under it; a diff-only entry cites nothing."""
    assert 'class="cites"' not in _page(diff_only_entry(_delta(), detected_on=OBSERVED))


_DATES = re.compile(r'<p class="meta">.*</p>\n<p class="dates">([^<]*)</p>')
"""The dates line, captured only where it sits directly under the line it qualifies.

The applies line above it is matched loosely because it carries markup of its own: a real date
is wrapped so the stylesheet can lift it, and a pattern that stopped at the first `<` would
quietly stop finding the pair on exactly the changes that moved a date."""


def _dated_page(**moved: object) -> str:
    """One event page whose first change carries the dates the test hands it.

    Patched onto a real change rather than built from a fixture with dates in it, because the
    toy corpus writes no date markup at all: every change of it moves nothing, which is what
    makes it the right input for the absent case below and the wrong one for the present case.
    """
    delta = _delta()
    changes = (delta.changes[0].model_copy(update=moved), *delta.changes[1:])
    entry = diff_only_entry(delta.model_copy(update={"changes": changes}), detected_on=OBSERVED)
    site = _site(entry)
    return _rendered(site, site.acts[0], site.acts[0].entries[0])


def test_a_change_that_moved_dates_names_them_under_the_applies_line() -> None:
    """Both clauses, in the ISO form every date on the site is printed in, added first.

    Under the applies line and never above it: that line answers whether one of these dates
    governs the provision, and this one only says which dates the text stopped and started
    naming.
    """
    rendered = _dated_page(
        dates_added=(date(2027, 12, 2), date(2028, 8, 2)), dates_removed=(date(2026, 8, 2),)
    )
    assert _DATES.findall(rendered) == [
        "dates added to the text: 2027-12-02, 2028-08-02 · dates removed: 2026-08-02"
    ]


def test_the_applies_line_labels_its_value_and_marks_only_a_real_date() -> None:
    """Three values share this line and only one of them is a date.

    The colon is what makes it a label. The two non-answers are the site's own words:
    `unchanged` beside a changed provision read as "the provision did not change", so it says no
    date changed, and `unknown` says not readable, keeps its reason and links the definition.

    The span is on the date alone. It is what lets the stylesheet lift a date out of the
    colour the two non-answers keep, and marking a non-answer with it would style a stated
    absence as a fact a reader can act on.
    """
    unchanged = _delta().changes[0]
    assert isinstance(unchanged.applies_from, ApplicabilityUnchanged)
    assert applies_line(unchanged, "../") == '<p class="meta">Applies from: no date changed</p>'

    deferred = unchanged.model_copy(update={"applies_from": date(2021, 5, 26)})
    assert applies_line(deferred, "../") == (
        '<p class="meta">Applies from: <span class="date">2021-05-26</span></p>'
    )

    reason = "the text changed beyond its dates"
    unknown = unchanged.model_copy(update={"applies_from": ApplicabilityUnknown(reason=reason)})
    assert applies_line(unknown, "../") == (
        f'<p class="meta">Applies from: not readable ({reason}) <a class="define" '
        'href="../methodology/#applies-from">why</a></p>'
    )


def test_a_change_that_moved_no_date_prints_no_dates_line() -> None:
    """Nine hundred committed changes moved none, and a paragraph saying so on each of them
    would be markup carrying the absence of a fact."""
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    assert not any(
        emitted.change.dates_added or emitted.change.dates_removed for emitted in entry.changes
    )
    changes = _page(entry).split('<h2 class="section">What changed</h2>')[1]
    assert 'class="dates"' not in changes


def test_the_dates_line_states_dates_and_never_calls_one_a_deadline() -> None:
    """The words are the whole risk. A date in a provision's text is a fact about the text;
    what it governs is prose nothing in this project parses, and the words for that reading
    are the ones that may never appear here."""
    rendered = _dated_page(dates_removed=(date(2026, 8, 2),))
    (line,) = _DATES.findall(rendered)
    assert line == "dates removed: 2026-08-02"
    for word in ("deadline", "application", "applies", "obligation", "compliance"):
        assert word not in line


def _closing_path(entry: ChangelogEntry) -> str:
    """The changelog document this entry was committed to, as the sentence names it."""
    return f"{entry.act_dir}/CHANGELOG.md"


def _closed_with(changelogs_url: str) -> tuple[str, str]:
    entry = diff_only_entry(_delta(), detected_on=OBSERVED)
    site = _site(entry, changelogs_url=changelogs_url)
    return _rendered(site, site.acts[0], site.acts[0].entries[0]), _closing_path(entry)


def test_the_closing_path_links_into_a_public_changelog_repository() -> None:
    """A deployment that publishes the changelog data says where the entry is, in a link.

    GitHub serves a committed file under `blob/<ref>/`, verified against a changelog
    repository's own `CHANGELOG.md` on 2026-09-04. The link is to the file and never to a
    heading inside it: that host derives a heading anchor from the heading's text, so a deeper
    link would break silently the day the heading is reworded.
    """
    rendered, path = _closed_with("https://github.com/o/changelogs")
    assert (
        f'is committed at <a href="https://github.com/o/changelogs/blob/main/{path}">'
        f"<code>{path}</code></a>." in rendered
    )


def test_a_changelog_home_of_unknown_shape_leaves_the_closing_path_as_text() -> None:
    """A forge whose file layout nobody has checked gets no guessed link, only the path."""
    rendered, path = _closed_with("https://data.example.invalid/changelogs")
    assert f"is committed at <code>{path}</code>." in rendered
    assert f"https://data.example.invalid/changelogs/{path}" not in rendered


def test_a_build_with_no_public_changelog_home_prints_the_closing_path_plainly() -> None:
    """The honest answer where the repository is the operator's own: the stable path inside
    it, for a reader who has the checkout, and no host named."""
    rendered, path = _closed_with("")
    assert f'<p class="small muted">The full entry is committed at <code>{path}</code>.</p>' in (
        rendered
    )
    assert "citation mapping" not in rendered
    assert "github.com" not in rendered


def _coded_pair() -> tuple[SiteInputs, ChangelogEntry]:
    """Two versions of one act, the older one's code carrying a date it is not in force from."""
    from emendrix.core import VersionId

    template = diff_only_entry(_delta(), detected_on=OBSERVED)
    older = template.model_copy(
        update={
            "from_version": VersionId("v0"),
            "to_version": VersionId("v1"),
            "in_force": (date(2015, 12, 31),),
        }
    )
    newer = template.model_copy(
        update={
            "from_version": VersionId("v1"),
            "to_version": VersionId("v2"),
            "in_force": (date(2025, 4, 1),),
        }
    )
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=(older, newer),
        version_dates={
            (newer.act, VersionId("v1")): date(2018, 1, 1),
            (newer.act, VersionId("v2")): date(2025, 4, 1),
        },
    )
    return site, newer


def test_a_coded_date_that_is_not_the_in_force_date_is_explained_where_the_codes_are() -> None:
    """A version coded 20180101 and in force from 31 December 2015 reads as a mistake unless
    the page says what the code's date is. Said once, beside the codes, and only where a
    version this page names differs; this version's own code matches and is not mentioned
    on the newer page, and the older page names the code as its own."""
    site, newer = _coded_pair()
    act = site.acts[0]
    rendered = render_event_page(site, act, newer, text_blocks(newer, act.entries))
    assert (
        '<span class="note">The date in a version&#x27;s code is the date EUR-Lex gives that '
        "consolidated text, which can differ from its in-force date: the previous version, "
        "coded 20180101, is in force from 31 December 2015.</span>"
    ) in rendered
    assert "this version, coded" not in rendered
    # The diff's sides are named by role and dated by the versions that produced them.
    assert '<span class="side-before">Previous version, in force 31 December 2015</span>' in (
        rendered
    )
    assert '<span class="side-after">this version, in force 1 April 2025</span>' in rendered
    # The older page names the same code as its own, and its previous version has no record.
    older = act.entries[1]
    page = render_event_page(site, act, older, text_blocks(older, act.entries))
    assert "this version, coded 20180101, is in force from 31 December 2015." in page
    assert "the previous version, coded" not in page
    assert '<span class="side-before">Previous version</span>' in page
