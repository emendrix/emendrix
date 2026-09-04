"""One provision's page: its history newest first, and the weight decision that shapes it.

The page exists because the pipeline's unit is a version transition and the reader's unit is
the provision. What is asserted here is that shape and the one rule that makes it affordable:
**the newest step carries its verbatim text and every older step carries a link to the block
that holds its own**. A page that quoted every step would multiply the heaviest page on the
site by the length of its own history, so the absence of those blocks is a property, not an
omission.

The other half is that nothing addressable was minted for this page. Every step id is the
anchor the event page already publishes for that change, which is what lets a reader move
between the two views of one change in either direction.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from site_entries import attributed_entry, unattributed_entry

from emendrix.core import Delta, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange, EmittedSentence
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.history import ProvisionHistory, histories
from emendrix.site_.inputs import ActSite, SiteInputs, collect_site
from emendrix.site_.magnitude import magnitude_html
from emendrix.site_.markup import escape
from emendrix.site_.pages.provision import render_provision_page
from emendrix.site_.pages.texts import text_blocks
from emendrix.site_.urls import entry_anchors
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)
SITE_URL = "https://example.invalid/site"

_STEPS = re.compile(r'<article class="chg step" id="([^"]*)">(.*?)</article>', re.DOTALL)
_LD = re.compile(r'<script type="application/ld\+json">\n(.*?)\n</script>', re.DOTALL)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _entry(index: int) -> ChangelogEntry:
    """The toy transition again on its own version pair and its own detection date."""
    return diff_only_entry(
        _delta().model_copy(
            update={
                "from_version": VersionId(f"v{index}"),
                "to_version": VersionId(f"v{index + 1}"),
            }
        ),
        detected_on=OBSERVED + timedelta(days=index),
    )


def _site(*entries: ChangelogEntry) -> SiteInputs:
    return collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=Path("r.json"),
        entries=entries,
        site_url=SITE_URL,
    )


def _first(act: ActSite) -> ProvisionHistory:
    return histories(act)[0]


def _render(site: SiteInputs, act: ActSite, history: ProvisionHistory) -> str:
    return render_provision_page(site, act, history, text_blocks(history.steps[0].entry))


def _page(*entries: ChangelogEntry) -> tuple[str, ActSite, ProvisionHistory]:
    site = _site(*entries)
    act = site.acts[0]
    history = _first(act)
    return _render(site, act, history), act, history


def test_the_newest_step_carries_its_verbatim_text_and_older_steps_carry_a_link() -> None:
    """The whole weight decision, in one assertion over a three-event history.

    One committed change carries 4.1 million characters of before-and-after text and one
    coordinate has been touched by 47 events, so quoting every step would multiply the
    heaviest page on the site by its own history. The reader who arrives from a search wants
    the current text, so the newest step is open and the rest are one link away.

    An older step names its own anchor twice and the two are different things: the permalink
    every step carries to itself, and the one link out to the block on the event page that
    holds this step's text.
    """
    rendered, _, history = _page(_entry(3), _entry(2), _entry(1))
    steps = _STEPS.findall(rendered)
    assert len(steps) == len(history.steps) == 3
    newest = steps[0][1]
    assert "<details open>" in newest
    assert '<p class="diff">' in newest or 'class="verbatim' in newest
    for anchor, older in steps[1:]:
        assert "<details" not in older
        assert '<p class="diff">' not in older and 'class="verbatim' not in older
        assert older.count(f'/#{anchor}"') == 1
        assert older.count(f'href="#{anchor}"') == 1


def test_every_older_step_links_the_block_on_its_own_event_page() -> None:
    """`../<entry key>/#<anchor>`: a sibling directory under the act, at the fragment that
    event page has always published for this change."""
    rendered, _, history = _page(_entry(2), _entry(1))
    older = history.steps[1]
    assert f'href="../{older.entry.key}/#{older.anchor}"' in rendered


def test_a_one_step_history_carries_no_older_link_at_all() -> None:
    rendered, _, history = _page(_entry(1))
    assert len(history.steps) == 1
    assert "on the event page" not in rendered
    assert "<details open>" in rendered


def test_each_step_id_is_the_anchor_the_event_page_publishes_for_that_change() -> None:
    """Nothing is minted here: a link that worked on the event page works on this one."""
    rendered, act, history = _page(_entry(2), _entry(1))
    for step in history.steps:
        anchors = entry_anchors(
            step.entry.key,
            [emitted.change.location.canonical for emitted in step.entry.changes],
        )
        assert step.anchor == anchors[step.index]
        assert f'id="{step.anchor}"' in rendered
    assert act.entries


def test_the_header_names_the_act_the_coordinate_and_how_much_history_there_is() -> None:
    rendered, act, history = _page(_entry(2), _entry(1))
    assert f"<h1>{history.location.human}</h1>" in rendered
    assert act.headline in rendered
    assert 'href="../"' in rendered
    assert "2 changes recorded across 2 events, newest first." in rendered


def test_the_official_heading_of_the_newest_step_is_printed_verbatim() -> None:
    """The provision's own title in the consolidated text, which can move with the text: the
    newest one is shown and the earlier ones stay visible in the diffs on the event pages."""
    rendered, _, history = _page(_entry(1))
    heading = history.steps[0].change.heading
    assert heading
    assert f'<p class="official">{heading}</p>' in rendered


def test_a_title_that_only_repeats_the_coordinate_is_not_printed_under_it() -> None:
    """The Formex title of an annex is often the words `ANNEX IX`, and printing that under the
    H1 `Annex IX` reads as a rendering accident rather than as the document's own title. Case
    and whitespace are folded for the comparison only: nothing stored is rewritten, and a
    title that says anything more is printed character for character."""
    entry = _entry(1)
    first = entry.changes[0].change
    shouted = entry.model_copy(
        update={
            "changes": (
                entry.changes[0].model_copy(
                    update={
                        "change": first.model_copy(update={"heading": first.location.human.upper()})
                    }
                ),
                *entry.changes[1:],
            )
        }
    )
    rendered, _, _ = _page(shouted)
    assert '<p class="official">' not in rendered


def test_every_step_states_its_date_its_kind_and_when_it_applies() -> None:
    rendered, _, history = _page(_entry(2), _entry(1))
    found = _STEPS.findall(rendered)
    assert [anchor for anchor, _ in found] == [step.anchor for step in history.steps]
    for _, block in found:
        assert '<p class="applies">applies from: ' in block
        assert '<span class="pill' in block
        assert "in force" in block or "detected" in block


def test_a_step_names_the_instrument_that_made_it_and_links_its_page() -> None:
    """The reader scanning a provision's history is asking which instrument did each thing."""
    rendered, _, _ = _page(attributed_entry())
    assert '<p class="amending">Amended by ' in rendered
    assert 'href="../../../amendments/house-rules-amendment-1/"' in rendered


def test_a_step_of_an_event_naming_no_instrument_says_so_in_the_sites_own_words() -> None:
    """The label the rest of the site uses for the class, not a sentence per step: on a long
    history the sentence would be repeated per step and it is one link away on each event."""
    rendered, _, _ = _page(unattributed_entry())
    assert '<p class="amending">no amending act named</p>' in rendered


def test_the_title_and_description_carry_the_human_coordinate() -> None:
    """`Annex XVII`, not `AN XVII`: what ranks is what a reader types, and the canonical
    string is already in the address."""
    rendered, act, history = _page(_entry(1))
    human = history.location.human
    assert f"<title>{act.label} {human}: every consolidated version and what changed" in rendered
    assert f'content="{human} of {act.headline}: 1 change across 1 event' in rendered


def test_the_structured_data_names_the_provision_as_a_part_of_the_act() -> None:
    """Four rungs, and one `hasPart` carrying a name and nothing else: a provision has no
    address at EUR-Lex that resolves and no identifier outside this corpus's vocabulary."""
    rendered, act, history = _page(_entry(1))
    (payload,) = _LD.findall(rendered)
    breadcrumb, webpage = json.loads(payload)
    rungs = [item["name"] for item in breadcrumb["itemListElement"]]
    assert rungs == ["emendrix", "All watched acts", act.label, history.location.human]
    assert webpage["about"]["hasPart"] == {
        "@type": "Legislation",
        "name": history.location.human,
    }
    assert webpage["@id"].startswith(f"{SITE_URL}/acts/{act.slug}/")


def test_two_renderings_of_one_history_are_byte_identical() -> None:
    site = _site(_entry(2), _entry(1))
    act = site.acts[0]
    history = _first(act)
    assert _render(site, act, history) == _render(site, act, history)


def test_every_step_heading_ends_with_a_permalink_to_that_step() -> None:
    """A history of many steps is a page where a reader wants to hand somebody one of them.

    It is the same link and the same anchor a change block carries on its event page, so one
    change can be linked from either view of it.
    """
    rendered, _, history = _page(_entry(2), _entry(1))
    for step in history.steps:
        assert (
            f'<a class="permalink" href="#{step.anchor}" '
            'aria-label="Link to this change">§</a></h2>' in rendered
        )


def _explained(entry: ChangelogEntry) -> ChangelogEntry:
    """The entry with two sentences on every change, both citing the same before-and-after."""
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)

    def explained(emitted: EmittedChange) -> EmittedChange:
        ref = emitted.change.provision
        cited = tuple(
            adapter.render_citation(ref.model_copy(update={"version": version}))
            for version in (entry.from_version, entry.to_version)
        )
        return emitted.model_copy(
            update={
                "outcome": GateOutcome.PASSED,
                "sentences": tuple(
                    EmittedSentence(text=f"Sentence {index}.", citations=cited) for index in (1, 2)
                ),
            }
        )

    return entry.model_copy(
        update={"changes": tuple(explained(emitted) for emitted in entry.changes)}
    )


def test_a_step_carries_the_change_s_citations_as_one_row() -> None:
    """The step states a change through the same renderer an event page does, so the row a
    change gained there is here for the same reason and in the same words."""
    entry = _explained(_entry(1))
    cited = entry.changes[0].sentences[0].citations
    assert len(cited) == 2
    rendered, _, history = _page(entry)
    assert len(history.steps) == 1
    assert rendered.count('<p class="cites">Cited: ') == 1
    for item in cited:
        assert rendered.count(f'href="{escape(item.url)}"') == 1
    assert "<p>Sentence 2.</p>" in rendered


def test_only_the_step_showing_its_evidence_says_how_much_moved() -> None:
    """The count belongs to the comparison a page renders, and one step here renders one.

    An older step's evidence is on its event page, and so is its count; a figure printed here
    beside a link would be a measurement of markup the reader cannot see from this page.
    """
    site = _site(_entry(2), _entry(1))
    act = site.acts[0]
    history = _first(act)
    rendered = _render(site, act, history)
    assert len(history.steps) > 1
    newest = text_blocks(history.steps[0].entry)[history.steps[0].index]
    headings = re.findall(r"<h2>.*?</h2>", rendered, re.DOTALL)
    magnitudes = [heading for heading in headings if '<span class="mag"' in heading]
    assert len(magnitudes) == 1
    assert magnitude_html(newest) in magnitudes[0]
    assert magnitudes[0].index('<span class="pill') < magnitudes[0].index('<span class="mag"')


def test_a_step_carries_the_dates_its_own_change_moved() -> None:
    """The same line the event page prints under the same applies line, from the one renderer
    both pages read: a change stated two ways on its two pages is the thing that module exists
    to prevent. The toy corpus writes no date markup, so the dates are patched onto a real
    change and every other step of the page still carries none."""
    delta = _delta()
    changes = (
        delta.changes[0].model_copy(update={"dates_added": (date(2027, 12, 2),)}),
        *delta.changes[1:],
    )
    entry = diff_only_entry(delta.model_copy(update={"changes": changes}), detected_on=OBSERVED)
    site = _site(entry)
    act = site.acts[0]
    moved = next(one for one in histories(act) if one.location.canonical == "AR 2")
    rendered = _render(site, act, moved)
    ((_, body),) = _STEPS.findall(rendered)
    assert '<p class="dates">dates added to the text: 2027-12-02</p>' in body
    assert body.index('<p class="applies">') < body.index('<p class="dates">')
    untouched = next(one for one in histories(act) if one.location.canonical == "AN I")
    assert 'class="dates"' not in _render(site, act, untouched)
