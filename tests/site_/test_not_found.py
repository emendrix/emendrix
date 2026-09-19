"""`404.html`: a real page rather than the host's generic one, and the one page kept unindexed.

The properties every other page keeps are asserted over the whole tree in `test_golden.py`,
which walks `*.html` and therefore covers this file for free: the disclaimer, the single
committed script, no third-party request. What is left to check here is what makes this page
different from the other pages: it asks not to be indexed, and with a site URL it is the one
page whose references start from the site's own path rather than from its own directory, because
a host serves it under whatever address a reader mistyped.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from helpers import build

from emendrix.site_.fingerprint import SCRIPT, STYLESHEET
from emendrix.site_.pages.not_found import not_found_root

ROBOTS = '<meta name="robots" content="noindex">'
SUBPATH = "https://example.org/sub"
_REFERENCE = re.compile(r'(?:href|src|data-root)="([^"]*)"')


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("not_found") / "site", changelog_repo)


@pytest.fixture(scope="module")
def subpath(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> str:
    out = tmp_path_factory.mktemp("not_found_sub") / "site"
    build(out, changelog_repo, "--site-url", SUBPATH)
    return (out / "404.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def unaddressed(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> str:
    out = tmp_path_factory.mktemp("not_found_bare") / "site"
    build(out, changelog_repo, "--site-url", "")
    return (out / "404.html").read_text(encoding="utf-8")


def _on_site(text: str) -> list[str]:
    """Every href, src and data-root that stays on the site: not a fragment, not another host."""
    return [
        ref
        for ref in _REFERENCE.findall(text)
        if not ref.startswith(("#", "https://", "http://", "mailto:"))
    ]


def test_the_not_found_page_asks_not_to_be_indexed_and_no_other_page_does(site: Path) -> None:
    """A result reading "page not found" tells a reader nothing about what this site is."""
    assert ROBOTS in (site / "404.html").read_text(encoding="utf-8")
    for page in sorted(site.rglob("*.html")):
        if page.name == "404.html":
            continue
        assert ROBOTS not in page.read_text(encoding="utf-8"), page


def test_it_is_a_whole_page_with_the_shell_and_the_disclaimer(site: Path) -> None:
    """The point of shipping one at all is the way back: the header bar and the search box."""
    text = (site / "404.html").read_text(encoding="utf-8")
    assert "<h1>Page not found</h1>" in text
    # An address that matches nothing has no place in the tree, so the masthead has no trail.
    assert '<header class="masthead masthead--prose">' in text
    assert 'class="trail"' not in text
    assert '<header class="bar">' in text
    assert '<div id="search" data-root="/site/">' in text
    assert "Not legal advice" in text


def test_with_a_site_url_every_reference_starts_from_the_site_urls_path(subpath: str) -> None:
    """Served under `/acts/nope/deeper/`, a relative stylesheet would resolve three directories
    too deep and the page would render unstyled; the URL's path is right from any address."""
    references = _on_site(subpath)
    assert references
    for ref in references:
        assert ref.startswith("/sub/"), ref
    for expected in (
        f'<link rel="stylesheet" href="/sub/{STYLESHEET}">',
        f'<script defer src="/sub/{SCRIPT}"></script>',
        '<link rel="icon" href="/sub/icon.svg" type="image/svg+xml">',
        '<a class="wordmark" href="/sub/">emendrix</a>',
        '<a href="/sub/acts/">All acts</a>',
        '<div id="search" data-root="/sub/">',
        '<a href="/sub/acts/">All watched acts</a>',
        '<a href="/sub/about/">About this site</a>',
    ):
        assert expected in subpath, expected
    # The canonical address is absolute either way and does not move.
    assert '<link rel="canonical" href="https://example.org/sub/404.html">' in subpath


def test_without_a_site_url_its_references_stay_relative_and_climb_no_directory(
    unaddressed: str,
) -> None:
    """A build with no base has nothing to write a root path against, and from `file://` a
    leading `/` would leave the tree; `404.html` sits at the root, so nothing climbs either."""
    assert "../" not in unaddressed
    for ref in _on_site(unaddressed):
        assert not ref.startswith("/"), ref
    for expected in (
        f'<link rel="stylesheet" href="{STYLESHEET}">',
        f'<script defer src="{SCRIPT}"></script>',
        '<link rel="icon" href="icon.svg" type="image/svg+xml">',
        '<a class="wordmark" href="./">emendrix</a>',
        '<div id="search" data-root="">',
        'href="acts/"',
        'href="methodology/"',
        'href="feeds/"',
    ):
        assert expected in unaddressed, expected
    assert 'rel="canonical"' not in unaddressed


@pytest.mark.parametrize(
    ("site_url", "root"),
    [
        ("", ""),
        ("https://emendrix.eu", "/"),
        ("https://emendrix.eu/", "/"),
        ("https://example.org/sub", "/sub/"),
        ("https://example.org/a b/", "/a%20b/"),
        ('https://example.org/"x&y', "/%22x%26y/"),
    ],
)
def test_the_root_is_the_site_urls_path_encoded_for_an_attribute(site_url: str, root: str) -> None:
    assert not_found_root(site_url) == root


def test_every_page_links_the_committed_icon_relative_to_its_own_depth(site: Path) -> None:
    """The icon needs no base address, which is why it is written whatever the site URL is.
    The not-found page alone writes it from the site URL's path, for the reason above."""
    for page in sorted(site.rglob("*.html")):
        if page.name == "404.html":
            continue
        prefix = "../" * len(page.relative_to(site).parts[:-1])
        expected = f'<link rel="icon" href="{prefix}icon.svg" type="image/svg+xml">'
        assert expected in page.read_text(encoding="utf-8"), page


def test_no_page_but_the_not_found_page_writes_a_root_relative_reference(site: Path) -> None:
    """Relative is what lets the tree work from `file://` and from a subpath; the exception is
    the one page a host serves under addresses it does not own, and it must stay one page.
    Walked over the same build the committed golden is compared against."""
    pages = sorted(site.rglob("*.html"))
    assert len(pages) > 1
    for page in pages:
        text = page.read_text(encoding="utf-8")
        rooted = [ref for ref in _on_site(text) if ref.startswith("/")]
        if page.name == "404.html" and page.parent == site:
            assert rooted, page
        else:
            assert rooted == [], (page, rooted)
