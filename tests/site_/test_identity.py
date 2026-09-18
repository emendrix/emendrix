"""Every page below home says what it is and where it sits, in one masthead.

Walked over a built tree, like the golden, because what matters is a relationship between
pages: a trail link resolves only if the page it names was written, and the visible trail is
honest only if it is the one the page's JSON-LD publishes.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
from helpers import build
from site_entries import unattributed_entry

from emendrix.site_.clocks import human_date, version_name

MASTHEAD = re.compile(r'<header class="masthead masthead--([a-z]+)">\n(.*?)\n</header>', re.DOTALL)
TRAIL = re.compile(r'<nav class="trail" aria-label="Breadcrumb"><ol>(.*?)</ol></nav>')
RUNG = re.compile(r'<li(?: aria-current="page")?>(?:<a href="([^"]*)">)?([^<]*)(?:</a>)?</li>')
LD = re.compile(r'<script type="application/ld\+json">\n(.*?)\n</script>', re.DOTALL)

_KINDS = {
    "acts/32017R0745/index.html": "act",
    "acts/32017R0745/02017R0745-20200424/index.html": "version",
    "acts/32017R0745/ar-1/index.html": "provision",
    "amendments/32020R0561/index.html": "amending",
    "acts/index.html": "index",
    "amendments/index.html": "index",
    "dates/index.html": "prose",
    "methodology/index.html": "prose",
    "about/index.html": "prose",
    "feeds/index.html": "prose",
    "404.html": "prose",
}
"""One page of every type the golden tree holds, and the masthead kind it must open with."""

_TRAILED = (
    "acts/32017R0745/index.html",
    "acts/32017R0745/02017R0745-20200424/index.html",
    "acts/32017R0745/ar-1/index.html",
    "amendments/32020R0561/index.html",
)
"""The pages whose trail is also published as a `BreadcrumbList`."""


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("identity") / "site", changelog_repo)


def _read(site: Path, name: str) -> str:
    return (site / name).read_text(encoding="utf-8")


def _rungs(text: str) -> list[tuple[str, str]]:
    """The visible trail as `(href, name)` pairs, the last one with no href."""
    found = TRAIL.search(text)
    assert found is not None
    return RUNG.findall(found.group(1))


@pytest.mark.parametrize(("name", "kind"), sorted(_KINDS.items()))
def test_every_page_below_home_opens_with_one_masthead_of_its_kind(
    site: Path, name: str, kind: str
) -> None:
    text = _read(site, name)
    found = MASTHEAD.findall(text)
    assert [found_kind for found_kind, _ in found] == [kind], name
    inside = found[0][1]
    assert inside.count('<p class="caption">') == 1, name
    assert inside.count("<h1>") == 1, name
    assert text.count("<h1>") == 1, name
    assert '<main id="content">\n<header class="masthead' in text, name


def test_home_keeps_its_hero_and_gets_no_masthead_or_trail(site: Path) -> None:
    text = _read(site, "index.html")
    assert "masthead" not in text
    assert 'class="trail"' not in text


def test_every_trailed_page_but_the_not_found_one_ends_on_itself(site: Path) -> None:
    """The last crumb is the page, unlinked and marked current; every other one is a link."""
    for name in _KINDS:
        text = _read(site, name)
        if name == "404.html":
            assert 'class="trail"' not in text
            continue
        rungs = _rungs(text)
        assert len(rungs) >= 2, name
        assert all(href for href, _ in rungs[:-1]), name
        assert rungs[-1][0] == "", name
        assert f'<li aria-current="page">{rungs[-1][1]}</li>' in text, name


@pytest.mark.parametrize("name", _TRAILED)
def test_the_visible_trail_is_the_one_the_json_ld_publishes(site: Path, name: str) -> None:
    text = _read(site, name)
    crumbs = json.loads(LD.findall(text)[0])[0]
    published = [item["name"] for item in crumbs["itemListElement"]]
    assert [rung for _, rung in _rungs(text)] == published


def test_every_trail_link_resolves_to_a_file_the_build_wrote(site: Path) -> None:
    for name in _KINDS:
        if name == "404.html":
            continue
        here = (site / name).parent
        for href, _ in _rungs(_read(site, name))[:-1]:
            assert not href.startswith(("/", "http")), (name, href)
            target = (here / href).resolve()
            assert (target / "index.html").is_file(), (name, href)


def test_the_header_marks_the_section_each_page_belongs_to(site: Path) -> None:
    sections = {
        "acts/32017R0745/02017R0745-20200424/index.html": "All acts",
        "acts/32017R0745/ar-1/index.html": "All acts",
        "amendments/32020R0561/index.html": "Amending acts",
        "amendments/index.html": "Amending acts",
        "methodology/index.html": "Methodology",
    }
    for name, section in sections.items():
        marked = re.findall(r'aria-current="page">([^<]*)</a>', _read(site, name))
        assert marked == [section], name
    for name in ("index.html", "404.html"):
        assert 'aria-current="page"' not in _read(site, name), name


def test_a_human_date_names_every_month_without_a_locale() -> None:
    months = [human_date(date(2025, month, 1)) for month in range(1, 13)]
    assert months == [
        "1 January 2025",
        "1 February 2025",
        "1 March 2025",
        "1 April 2025",
        "1 May 2025",
        "1 June 2025",
        "1 July 2025",
        "1 August 2025",
        "1 September 2025",
        "1 October 2025",
        "1 November 2025",
        "1 December 2025",
    ]
    assert human_date(date(2024, 2, 29)) == "29 February 2024"


def test_a_version_is_named_by_its_clock_and_its_date() -> None:
    """The clock is part of the name: a detection date is never named as the version's own."""
    detected = unattributed_entry().model_copy(update={"in_force": ()})
    assert version_name(detected) == f"Version detected {human_date(detected.detected_on)}"
    in_force = detected.model_copy(update={"in_force": (date(2025, 4, 1),)})
    assert version_name(in_force) == "Version in force 1 April 2025"
