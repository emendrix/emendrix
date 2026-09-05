"""The shell every page shares: disclaimer, relative links, no third-party requests."""

from __future__ import annotations

from datetime import date

from helpers import text_of

from emendrix import DISCLAIMER
from emendrix.site_.chrome import nav_links, page
from emendrix.site_.fingerprint import SCRIPT, STYLESHEET
from emendrix.site_.inputs import PageChrome
from emendrix.site_.markup import Html, escape

GENERATED = date(2026, 8, 9)


def _page(path: str = "", repo_url: str = "", changelogs_url: str = "") -> str:
    return page(
        title="t",
        description="d",
        body=Html("<p>body</p>"),
        path=path,
        chrome=PageChrome(generated_on=GENERATED, repo_url=repo_url, changelogs_url=changelogs_url),
    )


def test_every_page_carries_the_disclaimer_and_the_generated_date() -> None:
    rendered = _page()
    assert escape(DISCLAIMER) in text_of(rendered)
    assert "Not legal advice" in rendered
    assert "2026-08-09" in rendered


def test_the_disclaimer_says_not_legal_advice_once_with_its_lead_in_bold() -> None:
    """The paragraph led with a bolded `Not legal advice.` and then printed the constant,
    which itself opens `Not legal advice:`, so a reader met the phrase twice in one line.
    Only the emphasis moved: the words are the constant's own, in its own order.
    """
    paragraph = _page().split('<p class="disclaimer">')[1].split("</p>")[0]
    assert paragraph.count("Not legal advice") == 1
    assert "<strong>Not legal advice:</strong>" in paragraph
    assert escape(DISCLAIMER) in text_of(paragraph)


def test_the_header_carries_the_six_destinations_in_one_order() -> None:
    """Two rosters, the list of dates ahead, the two prose pages and the feeds.

    Pinned as one string because the order is the decision: `Amendments` sits beside `All
    acts` because the two are the site's two rosters, and a reader who has just met an
    instrument's name on an event page looks for it next to where the acts are. `Dates ahead`
    follows them because it is the third view of the corpus and the only one facing forward;
    everything after it is about the site rather than about the corpus.
    """
    assert (
        '<nav aria-label="Site"><a href="acts/">All acts</a> '
        '<a href="amendments/">Amendments</a> '
        '<a href="dates/">Dates ahead</a> '
        '<a href="methodology/">Methodology</a> '
        '<a href="about/">About</a> '
        '<a href="feeds/">Feeds</a></nav>' in nav_links(0)
    )


def test_the_footer_links_the_about_page_from_whatever_depth_the_page_sits_at() -> None:
    assert 'href="about/">About this site</a>' in _page()
    assert 'href="../../about/">About this site</a>' in _page(path="acts/x/")
    assert 'href="../about/">About</a>' in nav_links(1)


def test_the_path_prefixes_every_internal_link_and_asset() -> None:
    """The two content-addressed names come from `fingerprint`, never from a literal here.

    A hard-coded digest would be a second spelling of the one name the builder writes, and it
    would pass on the day somebody changed the naming and forgot this file.
    """
    rendered = _page(path="acts/x/")
    assert f'<link rel="stylesheet" href="../../{STYLESHEET}">' in rendered
    assert f'<script defer src="../../{SCRIPT}"></script>' in rendered
    assert 'href="../../acts/"' in rendered
    assert 'data-root="../../"' in nav_links(2)


def test_no_external_asset_and_no_analytics() -> None:
    rendered = _page()
    for banned in ("http://", "@import", "<iframe", "googleapis", "google-analytics"):
        assert banned not in rendered
    # The word itself does appear, exactly once, in the footer's promise that there is none
    # of it; a second occurrence would mean something on the page had grown a tracker.
    assert rendered.count("analytics") == 1
    assert "no cookies, no analytics, no third-party requests" in rendered


def test_repo_url_is_a_link_only_when_configured() -> None:
    assert "<a href" not in _page().split("<footer>")[1].split("Not legal advice")[0]
    assert "the emendrix repository" in _page()
    linked = _page(repo_url="https://example.invalid/emendrix")
    assert '<a href="https://example.invalid/emendrix">' in linked


def test_changelogs_url_is_a_link_only_when_configured() -> None:
    assert "<a href" not in _page().split("<footer>")[1].split("Not legal advice")[0]
    assert "the changelog repository" in _page()
    linked = _page(changelogs_url="https://example.invalid/changelogs")
    assert '<a href="https://example.invalid/changelogs">' in linked
