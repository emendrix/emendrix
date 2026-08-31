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
from site_entries import unattributed_entry

from emendrix import DISCLAIMER
from emendrix.core import ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import diff_only_entry
from emendrix.site_.feeds import feed_path, render_feed, render_feeds_page
from emendrix.site_.inputs import SiteInputs, collect_site
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
    site = _site()
    assert render_feed(site, None) == render_feed(site, None)
    key = site.acts[0].entries[0].key
    assert f"#{key}</id>" in render_feed(site, None)


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
    its id and link are the same permalink any entry gets, so no reader is re-notified."""
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


def test_the_feeds_page_lists_the_global_feed_and_every_watched_act() -> None:
    site = _site()
    rendered = render_feeds_page(site)
    assert 'href="../feeds/all.xml"' in rendered
    assert f'href="../feeds/{site.acts[0].slug}.xml"' in rendered
    assert "Not legal advice." in rendered


def test_without_a_site_url_the_feeds_page_says_so_and_no_feed_is_rendered() -> None:
    site = _site().model_copy(update={"site_url": ""})
    rendered = render_feeds_page(site)
    assert "no site URL was configured" in rendered
    assert ".xml" not in rendered
    with pytest.raises(ValueError, match="site URL"):
        render_feed(site, None)
