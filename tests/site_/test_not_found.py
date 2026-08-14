"""`404.html`: a real page rather than the host's generic one, and the one page kept unindexed.

The properties every other page keeps are asserted over the whole tree in `test_golden.py`,
which walks `*.html` and therefore covers this file for free: the disclaimer, the single
committed script, no third-party request. What is left to check here is what makes this page
different from the other four, and that nothing about it depends on where the site is deployed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import build

ROBOTS = '<meta name="robots" content="noindex">'


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("not_found") / "site", changelog_repo)


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
    assert '<header class="bar">' in text
    assert '<div id="search" data-root="">' in text
    assert "Not legal advice" in text


def test_its_links_climb_no_directory_because_the_file_sits_at_the_root(site: Path) -> None:
    """`404.html` is at the site root, so a `../` on it would leave the site entirely."""
    text = (site / "404.html").read_text(encoding="utf-8")
    assert "../" not in text
    for destination in ('href="acts/"', 'href="methodology/"', 'href="feeds/"'):
        assert destination in text, destination


def test_every_page_links_the_committed_icon_relative_to_its_own_depth(site: Path) -> None:
    """The icon needs no base address, which is why it is written whatever the site URL is."""
    for page in sorted(site.rglob("*.html")):
        prefix = "../" * len(page.relative_to(site).parts[:-1])
        expected = f'<link rel="icon" href="{prefix}icon.svg" type="image/svg+xml">'
        assert expected in page.read_text(encoding="utf-8"), page
