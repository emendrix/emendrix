"""The shell every page shares: disclaimer, relative links, no third-party requests."""

from __future__ import annotations

from datetime import date

from emendrix import DISCLAIMER
from emendrix.site_.chrome import nav_links, page
from emendrix.site_.markup import Html, escape

GENERATED = date(2026, 8, 9)


def _page(path: str = "", repo_url: str = "") -> str:
    return page(
        title="t",
        description="d",
        body=Html("<p>body</p>"),
        path=path,
        generated_on=GENERATED,
        repo_url=repo_url,
    )


def test_every_page_carries_the_disclaimer_and_the_generated_date() -> None:
    rendered = _page()
    assert escape(DISCLAIMER) in rendered
    assert "Not legal advice" in rendered
    assert "2026-08-09" in rendered


def test_the_path_prefixes_every_internal_link_and_asset() -> None:
    rendered = _page(path="acts/x/")
    assert '<link rel="stylesheet" href="../../style.css">' in rendered
    assert '<script defer src="../../search.js"></script>' in rendered
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
    linked = _page(repo_url="https://example.invalid/emendrix")
    assert '<a href="https://example.invalid/emendrix">' in linked
