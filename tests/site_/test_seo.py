"""What each built page declares about itself, checked against the tree it was written into.

Every assertion here walks the built tree rather than calling a renderer, because the property
that matters is a relationship between a page's own address and what the page says its address
is. Walking the tree is also what makes a new page impossible to add without a canonical: the
page appears in the walk the moment the builder writes it, and the canonical is checked against
where it landed.

The second build, without `--site-url`, is the degradation case. Canonical, Open Graph and
JSON-LD are absolute by definition, so without a base they are absent in their entirety rather
than in part, and the feed links go with them because no feed file is written either. The head
that build produces carries no blank line where those blocks would have gone, which is what the
last test pins.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from helpers import REPORTS, SITE_URL, WATCHLIST, build, runner

from emendrix.cli import app
from eu_pins import OBSERVED_ON

CANONICAL = re.compile(r'<link rel="canonical" href="([^"]*)">')
ALTERNATE = re.compile(
    r'<link rel="alternate" type="application/atom\+xml" title="([^"]*)" href="([^"]*)">'
)
OG_URL = re.compile(r'<meta property="og:url" content="([^"]*)">')
OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]*)">')
LD = re.compile(r'<script type="application/ld\+json">\n(.*?)\n</script>', re.DOTALL)


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """One build with a site URL, shared by every test that needs the declared form."""
    return build(tmp_path_factory.mktemp("seo") / "site", changelog_repo)


@pytest.fixture(scope="module")
def bare(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """The same inputs with no `--site-url`, which is the mode that declares nothing."""
    out = tmp_path_factory.mktemp("seo_bare") / "site"
    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--out",
            str(out),
            "--report-dir",
            str(REPORTS),
            "--watchlist",
            str(WATCHLIST),
            "--generated-on",
            OBSERVED_ON.isoformat(),
            "--changelogs",
            str(changelog_repo),
        ],
        env={"EMENDRIX_OUTPUT_REPO": ""},
    )
    assert result.exit_code == 0, result.output
    return out


def _pages(site: Path) -> list[Path]:
    pages = sorted(site.rglob("*.html"))
    assert pages
    return pages


def _address(page: Path, site: Path) -> str:
    """Where a written file actually sits, as the site-root-relative path it is served under."""
    return page.relative_to(site).as_posix().removesuffix("index.html")


def _act_pages(site: Path) -> list[Path]:
    return sorted((site / "acts").glob("*/index.html"))


def _payloads(page: Path) -> list[Any]:
    """Every JSON-LD block on one page, parsed, having first checked it cannot break out."""
    found: list[Any] = []
    for body in LD.findall(page.read_text(encoding="utf-8")):
        assert "<" not in body, page
        assert ">" not in body, page
        found.append(json.loads(body))
    return found


def test_every_page_states_its_own_address_as_its_canonical(site: Path) -> None:
    """The one assertion that makes a page impossible to add without a correct canonical."""
    for page in _pages(site):
        found = CANONICAL.findall(page.read_text(encoding="utf-8"))
        assert found == [f"{SITE_URL}/{_address(page, site)}"], page


def test_a_page_declares_exactly_one_canonical(site: Path) -> None:
    """Two of them is the duplicate the canonical exists to resolve, stated twice."""
    for page in _pages(site):
        assert page.read_text(encoding="utf-8").count('rel="canonical"') == 1, page


def test_the_preview_url_is_the_canonical_and_the_card_is_absolute(site: Path) -> None:
    """A scraper resolves neither a relative `og:url` nor a relative `og:image`."""
    assert (site / "og.png").is_file()
    for page in _pages(site):
        text = page.read_text(encoding="utf-8")
        assert OG_URL.findall(text) == CANONICAL.findall(text), page
        assert OG_IMAGE.findall(text) == [f"{SITE_URL}/og.png"], page


def test_the_home_page_is_the_one_website_and_it_claims_no_search_endpoint(site: Path) -> None:
    """The site's search is client-side with no `?q=` route, so none is declared."""
    payloads = _payloads(site / "index.html")
    assert len(payloads) == 1
    website = payloads[0]
    assert website["@context"] == "https://schema.org"
    assert website["@type"] == "WebSite"
    assert website["url"] == f"{SITE_URL}/"
    assert website["publisher"] == {
        "@type": "Organization",
        "name": "emendrix",
        "url": f"{SITE_URL}/",
    }
    assert "potentialAction" not in website


def test_an_act_page_carries_its_breadcrumb_and_the_page_itself(site: Path) -> None:
    """Three rungs because the site is three deep, and the last one is this page's address."""
    for page in _act_pages(site):
        payloads = _payloads(page)
        assert len(payloads) == 1, page
        crumbs, described = payloads[0]
        assert crumbs["@type"] == "BreadcrumbList", page
        items = crumbs["itemListElement"]
        assert [item["position"] for item in items] == [1, 2, 3], page
        assert items[0]["item"] == f"{SITE_URL}/", page
        assert items[1]["item"] == f"{SITE_URL}/acts/", page
        assert (site / "acts" / "index.html").is_file()
        canonical = CANONICAL.findall(page.read_text(encoding="utf-8"))
        assert [items[2]["item"]] == canonical, page
        assert described["@type"] == "WebPage", page
        assert [described["@id"]] == canonical, page
        assert described["about"]["@type"] == "Legislation", page


def test_the_official_document_is_named_only_where_one_was_resolved(site: Path) -> None:
    """An act with no committed event has no resolved address, and says nothing rather than ''."""
    seen = 0
    for page in _act_pages(site):
        text = page.read_text(encoding="utf-8")
        about = _payloads(page)[0][1]["about"]
        assert ("sameAs" in about) == ("on EUR-Lex" in text), page
        if "sameAs" in about:
            assert about["sameAs"].startswith("https://eur-lex.europa.eu/"), page
            seen += 1
    assert seen, "no act page linked an official document, so the omission proves nothing"


def test_the_pages_that_describe_nothing_a_type_names_declare_nothing(site: Path) -> None:
    """A one-rung breadcrumb on `/acts/` restates the URL, and the other three have no type."""
    described = {"index.html", *(str(page.relative_to(site)) for page in _act_pages(site))}
    for page in _pages(site):
        if str(page.relative_to(site)) in described:
            continue
        assert _payloads(page) == [], page


def test_every_advertised_feed_resolves_to_a_file_the_build_wrote(site: Path) -> None:
    """A `rel="alternate"` a reader's client cannot fetch is worse than no advertisement."""
    for page in _pages(site):
        found = ALTERNATE.findall(page.read_text(encoding="utf-8"))
        assert found, page
        for title, href in found:
            assert title.startswith("emendrix"), page
            assert (page.parent / href).resolve().is_file(), f"{page}: {href}"


def test_an_act_page_offers_its_own_feed_before_the_global_one(site: Path) -> None:
    """A reader subscribing from an act's page is asking for that act, not for everything."""
    for page in _act_pages(site):
        found = ALTERNATE.findall(page.read_text(encoding="utf-8"))
        assert len(found) == 2, page
        assert found[0][1].endswith(f"feeds/{page.parent.name}.xml"), page
        assert found[1][1].endswith("feeds/all.xml"), page


def test_without_a_site_url_a_page_declares_nothing_at_all(bare: Path) -> None:
    """All or nothing: `og:title` with no `og:url` renders a preview that is wrong."""
    for page in _pages(bare):
        text = page.read_text(encoding="utf-8")
        for absent in ('rel="canonical"', "og:", "ld+json", 'rel="alternate"', "schema.org"):
            assert absent not in text, f"{page}: {absent}"


def test_without_a_site_url_the_icon_stays_and_the_head_gains_no_blank_line(bare: Path) -> None:
    """What needs a base address is a reference to an address, never a relative asset link.

    A block that renders as an empty string into the head's newline join would put a blank line
    on every page of every base-less build, which is a formatting change nobody asked for. The
    icon link following its predecessor immediately is what proves no such line was inserted.
    """
    for page in _pages(bare):
        text = page.read_text(encoding="utf-8")
        prefix = "../" * len(page.relative_to(bare).parts[:-1])
        assert f'<link rel="icon" href="{prefix}icon.svg" type="image/svg+xml">' in text, page
        assert f'>\n<link rel="icon" href="{prefix}icon.svg"' in text, page
        assert "\n\n" not in text, page
