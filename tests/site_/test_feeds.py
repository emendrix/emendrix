"""Atom feeds: stable ids, absolute links, and the disclaimer in every summary.

Parsing with `xml.etree.ElementTree` here does not touch the hardened-parser rule. That rule
is about documents that came off a socket; these bytes were produced by this same process one
line earlier, and reading them back with the stdlib parser is how the test checks that what
was assembled is well-formed Atom rather than a string that merely looks like it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import pytest
from site_entries import some_textless_entry, textless_entry, unattributed_entry

from emendrix import DISCLAIMER
from emendrix.core import ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.feeds import feed_path, render_feed, render_feeds_page
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.titles import SUFFIX, event_title, event_words
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)
ATOM = "{http://www.w3.org/2005/Atom}"


def _site() -> SiteInputs:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    entry = diff_only_entry(compute_delta(before, after), detected_on=OBSERVED)
    return collect_site(
        generated_on=OBSERVED,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry,),
        site_url="https://example.invalid/site",
    )


def test_the_global_feed_is_valid_atom_with_one_entry_per_event() -> None:
    site = _site()
    root = ElementTree.fromstring(render_feed(site, None))
    assert root.tag == f"{ATOM}feed"
    entries = root.findall(f"{ATOM}entry")
    assert len(entries) == 1
    entry_id = entries[0].findtext(f"{ATOM}id")
    assert entry_id is not None and entry_id.startswith("https://example.invalid/site/acts/")


def test_entry_ids_are_permalinks_and_stable_across_builds() -> None:
    """The id is the act page's fragment under the site base, and the base is the one part of
    it that can move: it survived the event getting a page of its own, because minting a fresh
    id that day would have renotified every subscriber about events none of them missed."""
    site = _site()
    assert render_feed(site, None) == render_feed(site, None)
    key = site.acts[0].entries[0].key
    slug = site.acts[0].slug
    assert f"<id>https://example.invalid/site/acts/{slug}/#{key}</id>" in render_feed(site, None)


def test_the_site_base_is_the_one_thing_whose_move_reissues_an_entry() -> None:
    """The id embeds the base by design, so a build at another base mints another id for the
    same event. That is the whole cost of moving the site, and it is stated on `/feeds/` with
    its date rather than left to a subscriber to work out from a poll."""
    site = _site()
    moved = site.model_copy(update={"site_url": "https://example.invalid/moved"})
    key = site.acts[0].entries[0].key
    slug = site.acts[0].slug
    assert f"<id>https://example.invalid/moved/acts/{slug}/#{key}</id>" in render_feed(moved, None)
    assert render_feed(moved, None) != render_feed(site, None)


def test_the_alternate_link_points_at_the_events_own_page() -> None:
    """An id identifies and a link locates: the link follows the content to the event page."""
    site = _site()
    act = site.acts[0]
    entry = act.entries[0]
    root = ElementTree.fromstring(render_feed(site, None))
    (found,) = root.findall(f"{ATOM}entry/{ATOM}link")
    href = found.get("href")
    assert href == f"https://example.invalid/site/acts/{act.slug}/{entry.key}/"
    ident = root.findtext(f"{ATOM}entry/{ATOM}id")
    assert ident is not None and ident != href


def test_the_per_act_feed_carries_only_that_acts_events_and_its_path_is_the_slug() -> None:
    site = _site()
    act = site.acts[0]
    assert feed_path(act) == f"feeds/{act.slug}.xml"
    root = ElementTree.fromstring(render_feed(site, act))
    assert len(root.findall(f"{ATOM}entry")) == len(act.entries)


def test_every_summary_carries_the_disclaimer() -> None:
    site = _site()
    root = ElementTree.fromstring(render_feed(site, None))
    summary = root.find(f"{ATOM}entry/{ATOM}summary")
    assert summary is not None and summary.text is not None
    assert DISCLAIMER in summary.text


def test_an_event_naming_no_amending_act_keeps_its_entry_and_says_so_first() -> None:
    """The feed carries every event; this one is worded as what it is, and only worded:
    its id is the same permalink any entry gets, so no reader is re-notified."""
    site = collect_site(
        generated_on=OBSERVED,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(unattributed_entry(),),
        site_url="https://example.invalid/site",
    )
    root = ElementTree.fromstring(render_feed(site, None))
    entries = root.findall(f"{ATOM}entry")
    assert len(entries) == 1
    summary = entries[0].findtext(f"{ATOM}summary")
    assert summary is not None
    assert summary.startswith("No amending act is named for this event. ")
    entry_id = entries[0].findtext(f"{ATOM}id")
    assert entry_id is not None and entry_id.startswith("https://example.invalid/site/acts/")


def _summary_of(entry: ChangelogEntry) -> tuple[str, str]:
    """One entry's Atom summary and its id, which is the promise a rewording may not move."""
    site = collect_site(
        generated_on=OBSERVED,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry,),
        site_url="https://example.invalid/site",
    )
    element = ElementTree.fromstring(render_feed(site, None)).find(f"{ATOM}entry")
    assert element is not None
    summary, ident = element.findtext(f"{ATOM}summary"), element.findtext(f"{ATOM}id")
    assert summary is not None and ident is not None
    return summary, ident


def test_a_summary_counts_the_units_with_no_text_beside_the_other_two() -> None:
    """The split the count line prints, printed here too, so the two cannot disagree."""
    summary, _ = _summary_of(some_textless_entry())
    assert "5 provisions touched: 4 substantive, 0 date-only, 1 with no text, 1 disputed." in (
        summary
    )


def test_an_event_with_no_text_anywhere_says_so_and_keeps_its_id() -> None:
    """Three zeros and a count would say less than the clause does, and nothing is dropped:
    the touched count and the disputed count are still either side of it, and the id, which is
    what would renotify a subscriber, is the permalink it always was."""
    entry = textless_entry()
    summary, ident = _summary_of(entry)
    assert "2 provisions touched: none with text to show, 2 disputed." in summary
    assert "0 substantive" not in summary
    assert ident.startswith("https://example.invalid/site/acts/")
    assert ident.endswith(f"#{entry.key}")


def test_the_feeds_page_lists_the_global_feed_and_every_watched_act() -> None:
    site = _site()
    rendered = render_feeds_page(site)
    assert 'href="../feeds/all.xml"' in rendered
    assert f'href="../feeds/{site.acts[0].slug}.xml"' in rendered
    assert "Not legal advice:" in rendered


def test_the_feeds_page_dates_the_one_reissue_and_promises_no_other() -> None:
    """Published copy. The page whose subject is the durability of these ids states the day
    they moved and what a subscriber paid for it, rather than dropping a claim it cannot
    make. A reader who was handed every entry twice is owed the reason here.

    The sentence does not spell the hostname, because `test_architecture.py` refuses the string
    `emendrix.eu` anywhere under `site_/`, that being the import path of the EU adapter, and a
    reader of this page is already on the domain the sentence is about."""
    rendered = render_feeds_page(_site())
    assert "Moving this site to its own domain on 2026-09-05" in rendered
    assert "saw every entry a second time" in rendered
    assert "Nothing else reissues an entry." in rendered
    assert "never reissued" not in rendered


def test_without_a_site_url_the_feeds_page_says_so_and_no_feed_is_rendered() -> None:
    site = _site().model_copy(update={"site_url": ""})
    rendered = render_feeds_page(site)
    assert "no site URL was configured" in rendered
    assert ".xml" not in rendered
    with pytest.raises(ValueError, match="site URL"):
        render_feed(site, None)


def _attributed_site() -> SiteInputs:
    from site_entries import attributed_entry

    return collect_site(
        generated_on=OBSERVED,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(attributed_entry(),),
        site_url="https://example.invalid/site",
    )


def test_an_entry_is_titled_exactly_as_the_event_page_is_minus_the_sites_own_name() -> None:
    """One reader meets the event in a feed reader and one in a search result; they read the
    same words. Inside a feed already titled `emendrix — <act>`, the site's name on every
    entry is the one word nobody needs."""
    site = _attributed_site()
    act = site.acts[0]
    entry = act.entries[0]
    root = ElementTree.fromstring(render_feed(site, None))
    title = root.findtext(f"{ATOM}entry/{ATOM}title")
    assert title == event_words(site, act, entry)
    assert title == event_title(site, act, entry).removesuffix(SUFFIX)
    assert "house-rules-amendment-1" in (title or "")


def test_a_summary_names_the_instrument_by_its_number_after_the_counts() -> None:
    """A summary is where a subscriber checks which instrument this was, so it is named by the
    number; with no number to render, by the key it is identified as."""
    root = ElementTree.fromstring(render_feed(_attributed_site(), None))
    summary = root.findtext(f"{ATOM}entry/{ATOM}summary")
    assert summary is not None
    assert " Amended by house-rules-amendment-1. In force " in summary


def test_a_reworded_title_is_not_a_new_event() -> None:
    """The id is the promise and it did not move when the title started naming the act."""
    site = _attributed_site()
    act = site.acts[0]
    entry = act.entries[0]
    rendered = render_feed(site, None)
    assert f"<id>https://example.invalid/site/acts/{act.slug}/#{entry.key}</id>" in rendered
