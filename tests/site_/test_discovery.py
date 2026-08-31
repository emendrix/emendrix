"""What the site tells a crawler: the sitemap and the crawl policy, checked against the tree.

Every assertion walks the built tree rather than calling a renderer, for the reason the head's
own suite gives: the property that matters is a relationship between what the sitemap says and
what the builder actually wrote, and only a walk can see both.

Parsing with `xml.etree.ElementTree` here does not touch the hardened-parser rule. That rule is
about documents that came off a socket; these bytes were produced by this same process moments
earlier, and reading them back with the stdlib parser is how the test checks that what was
assembled is a well-formed sitemap rather than a string that merely looks like one. The rule
could not be honoured on the production side in any case: no module under `site_/` may import
`emendrix.eu`, which is where the hardened parser lives.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import pytest
from helpers import REPORTS, SITE_URL, WATCHLIST, build, runner
from site_entries import unattributed_entry

from emendrix.cli import app
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.discovery import robots_txt, sitemap_xml
from emendrix.site_.inputs import SiteInputs, collect_site
from eu_pins import OBSERVED_ON

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

UNUSED_DATE = date(2019, 3, 4)
"""A build date that is no event date and no report date, so a `lastmod` cannot equal it by luck."""


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """One build with a site URL, shared by every test that needs a sitemap to exist."""
    return build(tmp_path_factory.mktemp("discovery") / "site", changelog_repo)


def _urls(site: Path) -> list[tuple[str, str | None]]:
    """Every `<url>` in the built sitemap as `(loc, lastmod or None)`, in document order."""
    root = ElementTree.fromstring((site / "sitemap.xml").read_text(encoding="utf-8"))
    assert root.tag == f"{SITEMAP_NS}urlset"
    found = []
    for url in root.findall(f"{SITEMAP_NS}url"):
        loc = url.findtext(f"{SITEMAP_NS}loc")
        assert loc is not None
        found.append((loc, url.findtext(f"{SITEMAP_NS}lastmod")))
    assert found
    return found


def _addresses(site: Path) -> set[str]:
    """Where every page the build wrote is served from, as its site-root-relative address."""
    pages = sorted(site.rglob("*.html"))
    assert pages
    return {page.relative_to(site).as_posix().removesuffix("index.html") for page in pages}


def _empty_site(*, site_url: str = SITE_URL) -> SiteInputs:
    """A watched-nothing site: no acts, no events, and the newest committed report."""
    return SiteInputs(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report="r.json",
        site_url=site_url,
    )


def _canonicals(site: Path) -> dict[str, str]:
    """Each built page's declared canonical, keyed by its address. The 404 page is left out."""
    found: dict[str, str] = {}
    for page in sorted(site.rglob("*.html")):
        address = page.relative_to(site).as_posix().removesuffix("index.html")
        if address == "404.html":
            continue
        text = page.read_text(encoding="utf-8")
        marker = '<link rel="canonical" href="'
        start = text.index(marker) + len(marker)
        found[address] = text[start : text.index('"', start)]
    return found


# ------------------------------------------------------------------ the sitemap


def test_every_page_but_the_not_found_one_is_listed_and_every_location_is_a_page(
    site: Path,
) -> None:
    """Both directions, so a failure says which one broke.

    Add an act and forget the sitemap and the first comparison fails; rename a page or list one
    the builder never writes and the second does. A membership loop in one direction would let
    the sitemap rot in the other.
    """
    listed = {loc.removeprefix(f"{SITE_URL}/") for loc, _ in _urls(site)}
    written = _addresses(site) - {"404.html"}
    assert not written - listed, "pages the build wrote that the sitemap does not list"
    assert not listed - written, "locations the sitemap lists that the build did not write"


def test_the_not_found_page_is_written_and_deliberately_absent_from_the_sitemap(
    site: Path,
) -> None:
    """It asks to be kept out of results, and listing it would contradict that in the same tree."""
    assert '<meta name="robots" content="noindex">' in (site / "404.html").read_text(
        encoding="utf-8"
    )
    assert all("404" not in loc for loc, _ in _urls(site))


def test_a_location_is_the_same_string_as_the_canonical_on_the_page_it_names(site: Path) -> None:
    """One join builds both, and this is what makes that shared function load-bearing.

    Two addresses for one page is exactly the confusion a canonical exists to end, so a sitemap
    that disagreed with one would be worse than no sitemap.
    """
    assert {loc for loc, _ in _urls(site)} == set(_canonicals(site).values())


def test_only_pages_are_listed_and_no_feed_or_asset_is(site: Path) -> None:
    """A sitemap indexes pages. The feeds are advertised in every head as `rel="alternate"`."""
    for loc, _ in _urls(site):
        for asset in (".xml", ".css", ".js", ".json", ".png", ".svg"):
            assert not loc.endswith(asset), loc


def test_no_changefreq_and_no_priority_are_published(site: Path) -> None:
    """Google ignores both, so publishing them would be invented precision it then discards."""
    text = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "changefreq" not in text
    assert "priority" not in text


# ------------------------------------------------------------------ where lastmod comes from


def test_every_published_lastmod_is_an_iso_date(site: Path) -> None:
    """A day, not a timestamp: the corpus dates events to the day and this invents no more."""
    for loc, lastmod in _urls(site):
        if lastmod is not None:
            assert date.fromisoformat(lastmod).isoformat() == lastmod, loc


def test_the_methodology_page_is_dated_by_the_report_its_figures_came_from(site: Path) -> None:
    run = EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())
    dates = dict(_urls(site))
    assert dates[f"{SITE_URL}/methodology/"] == run.run_date.isoformat()


def test_an_act_is_dated_by_its_newest_event_and_a_quiet_one_is_not_dated_at_all(
    site: Path,
) -> None:
    """The act's own feed is the second record of the same fact, so the two are compared.

    An act nothing has happened to yet has no content date and gets no `<lastmod>` element: a
    guessed one would tell a crawler something the corpus never said.
    """
    dates = dict(_urls(site))
    quiet = busy = 0
    for feed in sorted((site / "feeds").glob("*.xml")):
        if feed.name == "all.xml":
            continue
        root = ElementTree.fromstring(feed.read_text(encoding="utf-8"))
        updated = [entry.findtext(f"{ATOM_NS}updated") for entry in root.findall(f"{ATOM_NS}entry")]
        lastmod = dates[f"{SITE_URL}/acts/{feed.stem}/"]
        if not updated:
            assert lastmod is None, feed
            quiet += 1
        else:
            newest = max(stamp for stamp in updated if stamp is not None)
            assert lastmod == newest[:10], feed
            busy += 1
    assert quiet and busy, f"{quiet} quiet and {busy} amended acts; both cases must be covered"


def test_an_act_with_only_unnamed_events_still_dates_its_page() -> None:
    """`<lastmod>` answers when the page's content last moved, and an event naming no
    amending act moved it like any other; only the human-facing "newest amendment" line
    skips such events. A crawler told this page never changed would be told a lie."""
    entry = unattributed_entry()
    inputs = collect_site(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry,),
        site_url=SITE_URL,
    )
    assert inputs.acts[0].dated is None
    rendered = sitemap_xml(inputs)
    slug = inputs.acts[0].slug
    block_start = rendered.index(f"{SITE_URL}/acts/{slug}/")
    block = rendered[block_start : rendered.index("</url>", block_start)]
    assert f"<lastmod>{entry.detected_on.isoformat()}</lastmod>" in block


def test_the_build_date_reaches_no_lastmod(tmp_path: Path, changelog_repo: Path) -> None:
    """A rebuild must not restamp every URL and tell a crawler the whole site changed.

    Built on a date that is neither an event date nor the report's, so the absence is evidence
    rather than a coincidence of two dates agreeing.
    """
    out = build(tmp_path / "site", changelog_repo, "--generated-on", UNUSED_DATE.isoformat())
    assert UNUSED_DATE.isoformat() in (out / "index.html").read_text(encoding="utf-8")
    assert UNUSED_DATE.isoformat() not in (out / "sitemap.xml").read_text(encoding="utf-8")


# ------------------------------------------------------------------ without a base address


def _bare(out: Path, changelog_repo: Path) -> Path:
    """The same build with no `--site-url`, which is the mode that publishes no absolute URL."""
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


def test_no_sitemap_is_written_without_a_base_address(tmp_path: Path, changelog_repo: Path) -> None:
    out = _bare(tmp_path / "site", changelog_repo)
    assert not (out / "sitemap.xml").exists()


def test_rendering_a_sitemap_without_a_base_address_refuses() -> None:
    """A location is absolute by definition, so there is no partial answer to give."""
    with pytest.raises(ValueError, match="needs a site URL"):
        sitemap_xml(_empty_site(site_url=""))


# ------------------------------------------------------------------ robots.txt


def test_the_crawl_policy_is_written_on_every_build_and_allows_everything(
    site: Path, tmp_path: Path, changelog_repo: Path
) -> None:
    """It is about paths, so it needs no base address and is published either way."""
    bare = _bare(tmp_path / "bare", changelog_repo)
    for out in (site, bare):
        text = (out / "robots.txt").read_text(encoding="utf-8")
        assert text.startswith("User-agent: *\nAllow: /\n"), out
        assert text.endswith("\n"), out
        assert "Disallow" not in text, out


def test_the_sitemap_line_appears_only_with_a_base_address_and_is_absolute(
    site: Path, tmp_path: Path, changelog_repo: Path
) -> None:
    assert f"Sitemap: {SITE_URL}/sitemap.xml\n" in (site / "robots.txt").read_text(encoding="utf-8")
    bare = _bare(tmp_path / "bare", changelog_repo)
    assert "Sitemap" not in (bare / "robots.txt").read_text(encoding="utf-8")


def test_the_crawl_policy_states_no_ai_crawler_directive(site: Path) -> None:
    """One policy for every crawler: the site is published to be found."""
    text = (site / "robots.txt").read_text(encoding="utf-8")
    assert text.count("User-agent") == 1
    for named in ("GPTBot", "CCBot", "Google-Extended", "ClaudeBot"):
        assert named not in text


def test_the_crawl_policy_carries_no_comment_of_its_own(site: Path) -> None:
    """A host may append a managed comment block of its own, and two of them is noise."""
    assert "#" not in (site / "robots.txt").read_text(encoding="utf-8")


# ------------------------------------------------------------------ determinism


def test_a_site_with_no_events_at_all_still_has_a_sitemap() -> None:
    """A checkout with a watchlist and an empty changelog repository is a real state.

    The four fixed pages are still published, so they are still listed, and the only date
    anything has is the report's. Two renderings of one input agree, which is the module's half
    of the byte-stability the whole tree is held to.
    """
    inputs = _empty_site()
    document = sitemap_xml(inputs)
    assert document == sitemap_xml(inputs)
    assert robots_txt(inputs) == robots_txt(inputs)
    root = ElementTree.fromstring(document)
    locations = [url.findtext(f"{SITEMAP_NS}loc") for url in root.findall(f"{SITEMAP_NS}url")]
    assert locations == [
        f"{SITE_URL}/",
        f"{SITE_URL}/acts/",
        f"{SITE_URL}/methodology/",
        f"{SITE_URL}/feeds/",
    ]
    assert document.count("<lastmod>") == 1
