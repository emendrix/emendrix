"""The site's side of an account service: links to it, and the shell it renders into.

Walked over built trees, like the discovery checks, because each property is a relationship
between pages: every provision page links its own provision, every act page its own act, and a
build that was not told a service exists links none at all. The service itself is not here and
nothing below imports it; what is checked is the published contract it reads, the markers in
`account-shell.html` and the query of a "Watch this" link.
"""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from helpers import REPORTS, SITE_URL, WATCHLIST, build, runner

from emendrix.cli import app
from emendrix.site_.api_files import CATALOGUE
from emendrix.site_.pages.account_shell import (
    ACCOUNT_MARKER,
    CONTENT_MARKER,
    FOOTER_NOTE_MARKER,
    SHELL,
    TITLE_MARKER,
)
from eu_pins import OBSERVED_ON

ROOT = urlsplit(SITE_URL).path + "/"
"""Where the shell's references start: the path of the site URL the helper builds with."""


@pytest.fixture(scope="module")
def plain(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("plain") / "site", changelog_repo)


@pytest.fixture(scope="module")
def linked(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("linked") / "site", changelog_repo, "--accounts")


def _pages(site: Path) -> list[Path]:
    pages = sorted(site.rglob("*.html"))
    assert pages
    return pages


def _catalogue(site: Path) -> list[dict[str, Any]]:
    acts: list[dict[str, Any]] = json.loads((site / CATALOGUE).read_text(encoding="utf-8"))["acts"]
    return acts


def _page(site: Path, url: str) -> str:
    return (site / url.removeprefix(f"{SITE_URL}/") / "index.html").read_text(encoding="utf-8")


def _watch_links(text: str, words: str) -> list[dict[str, list[str]]]:
    """The decoded query of every link on the page whose words are `words`."""
    hrefs = re.findall(rf'<a href="([^"]*account/watch\?[^"]*)">{re.escape(words)}</a>', text)
    return [parse_qs(urlsplit(unescape(href)).query) for href in hrefs]


# ------------------------------------------------------------------ without the flag


def test_without_the_flag_nothing_links_an_account_service(plain: Path) -> None:
    assert not (plain / SHELL).exists()
    for page in _pages(plain):
        assert "account/" not in page.read_text(encoding="utf-8"), page


# ------------------------------------------------------------------ the links


def test_every_provision_page_links_its_own_provision_once(linked: Path) -> None:
    seen = 0
    for act in _catalogue(linked):
        for canonical, url in act["provisions"].items():
            found = _watch_links(_page(linked, url), "Watch this provision")
            assert found == [{"act": [act["key"]], "loc": [canonical]}], url
            seen += 1
    assert seen


def test_every_act_page_links_its_own_act_once_quiet_ones_included(linked: Path) -> None:
    acts = _catalogue(linked)
    assert any(not act["events"] for act in acts), "no quiet act in the build"
    for act in acts:
        assert _watch_links(_page(linked, act["url"]), "Watch this act") == [{"act": [act["key"]]}]


def test_every_page_ends_its_header_bar_with_the_account_link(linked: Path) -> None:
    """After the search mount and outside the navigation, so a service can fill that one slot.

    The shell is the one page holding the account marker there instead, checked below.
    """
    for page in _pages(linked):
        if page.name == SHELL:
            continue
        text = page.read_text(encoding="utf-8")
        nav = text.split('<nav aria-label="Site">', 1)[1].split("</nav>", 1)[0]
        assert "account/" not in nav, page
        header = text.split('<header class="bar">', 1)[1].split("</header>", 1)[0] + "</header>"
        assert re.search(
            r'<div id="search" data-root="[^"]*"></div>'
            r'<a class="account" href="[^"]*account/">Account</a></header>$',
            header,
        ), page


def test_about_names_the_service_and_its_privacy_notice(linked: Path, plain: Path) -> None:
    about = (linked / "about" / "index.html").read_text(encoding="utf-8")
    assert '<a href="../account/privacy">/account/privacy</a>' in about
    assert "sets one cookie to keep them signed in" in about
    assert "Nothing about a reader is stored anywhere." in about
    assert "account service" not in (plain / "about" / "index.html").read_text(encoding="utf-8")


# ------------------------------------------------------------------ the shell


def test_the_shell_carries_each_marker_once_and_nothing_of_its_own(linked: Path) -> None:
    shell = (linked / SHELL).read_text(encoding="utf-8")
    markers = (TITLE_MARKER, ACCOUNT_MARKER, CONTENT_MARKER, FOOTER_NOTE_MARKER)
    for marker in markers:
        assert shell.count(marker) == 1, marker
    places = [shell.index(marker) for marker in markers]
    assert places == sorted(places), "title, account, content, footer-note, in file order"
    assert f'<div id="search" data-root="{ROOT}"></div>{ACCOUNT_MARKER}</header>' in shell
    assert 'class="account"' not in shell
    assert f"<title>{TITLE_MARKER}</title>" in shell
    assert '<meta name="description" content="">' in shell
    assert f'<main id="content">\n{CONTENT_MARKER}\n</main>' in shell
    footer = shell.split("<footer>", 1)[1]
    assert footer.index('class="disclaimer"') < footer.index(FOOTER_NOTE_MARKER)
    assert '<meta name="robots" content="noindex">' in shell
    assert "no cookies" not in shell
    assert "og:" not in shell and 'rel="canonical"' not in shell


def test_every_reference_in_the_shell_starts_from_the_site_root(linked: Path) -> None:
    """The service serves these bytes under `/account/...`, where a relative link would miss."""
    shell = (linked / SHELL).read_text(encoding="utf-8")
    references = re.findall(r'(?:href|src|data-root)="([^"]*)"', shell)
    assert references
    for reference in references:
        assert reference.startswith((ROOT, "https://", "#")), reference
    assert f'<link rel="stylesheet" href="{ROOT}style.' in shell
    assert ACCOUNT_MARKER in shell


def test_the_shell_is_byte_identical_across_two_builds(
    tmp_path: Path, changelog_repo: Path, linked: Path
) -> None:
    again = build(tmp_path / "site", changelog_repo, "--accounts")
    assert (again / SHELL).read_bytes() == (linked / SHELL).read_bytes()


# ------------------------------------------------------------------ the command line


def test_the_flag_without_a_site_url_is_refused(tmp_path: Path, changelog_repo: Path) -> None:
    """Without a base, the shell has no root to start its references from."""
    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--out",
            str(tmp_path / "site"),
            "--report-dir",
            str(REPORTS),
            "--watchlist",
            str(WATCHLIST),
            "--generated-on",
            OBSERVED_ON.isoformat(),
            "--changelogs",
            str(changelog_repo),
            "--accounts",
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 2
    assert "--accounts needs --site-url" in result.output
    assert not (tmp_path / "site").exists()
