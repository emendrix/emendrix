"""The committed golden tree, and the properties every page of it keeps.

The tree is built by the whole shipped command chain: `emendrix explain` writes a real
changelog into an output repository under a temporary directory from pinned fixtures and
committed cassettes, and `emendrix site build` renders the site from that repository, from
`watchlist.example.toml` and from the newest committed evaluation report. So the golden
changes exactly when the published artifact changes, which is when a reviewer should be made
to read a diff. It was read file by file on 2026-08-12 against the bar the site is held to:
legible with no context, honest about what is measured, and self-contained.

Read again the same day, when two files moved and nothing else did. The MDR act page carries a
new recording of its nine explanations and, in the collapsed before/after blocks, provision text
that keeps its words apart across block boundaries. The methodology page's provenance line and
its sampled-faithfulness cell follow the newest report, which is what the rule below makes them
do.

Read again on 2026-08-13, when the hand review of the 2026-08-12 recording was published. Two
files moved: the methodology page, whose spot-review cell names a reviewer and a date instead of
`pending` and whose provenance line follows the newest report, and that page's `lastmod` in the
sitemap. No measured figure moved with them.

Read again on 2026-08-14, when the footer grew the sentence naming the public changelog-data
repository. Nine files moved, the nine pages that carry the footer: `404.html`, `index.html`,
`acts/index.html`, `feeds/index.html`, `methodology/index.html`, and the four act pages under
`acts/`. Each moved by that one footer line, which now says the changelog data is public in the
changelog repository, in plain words because the golden build passes no `--changelogs-url`; the
linked form is asserted next to the shell itself. No feed, no `sitemap.xml` and no `style.css`
moved, and no measured figure moved with them.

Read again on 2026-08-14, later the same day, when the methodology page stopped claiming that
the only links leaving the site go to EUR-Lex. One file moved, `methodology/index.html`, by one
sentence: the closing claim now says no link leaves the site except to EUR-Lex and the
repositories the page names, which stays literally true here, where the golden build passes
neither repository URL and the how-built paragraph keeps its old wording, and on a deployment
that configures both links. The footer line of the earlier entry did not move again, no other
page moved, and no measured figure moved with it.

**It is deliberately wired to the newest report**, not to a pinned one, the same rule the
README's metrics table lives under: a new `reports/eval/*.json` breaks this suite until the
site is regenerated, so a figure on a page can never be stale with respect to the numbers the
repository publishes. A golden that fails because a figure moved is a finding to explain, never
a number to adjust.

To regenerate, from the repository root, with the path the failure message names::

    uv run pytest tests/site_/test_golden.py
    rm -rf tests/site_/golden && cp -R <the path the failure named> tests/site_/golden

Then read the diff, because that is the review.

**What the golden is not evidence of.** The act page carries a real model's prose, which makes
it read like the product. Nothing here asserts anything about explanation quality. What it
asserts is that the tree is deterministic, disclaimed, free of third-party requests, free of
the machine that built it, and correct about where law is quoted from.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from helpers import REPO, _tree, build

from emendrix import DISCLAIMER
from emendrix.site_.markup import escape

GOLDEN = Path(__file__).resolve().parent / "golden"

EURLEX = re.compile(
    r"^https://eur-lex\.europa\.eu/legal-content/EN/TXT/HTML/\?uri=CELEX:[0-9A-Za-z_-]+"
    r"(#(art_\d+[a-z]?|anx_[IVXLCDM0-9]+[A-Za-z]?))?$"
)
"""The citation URL shape verified against the live endpoint on 2026-08-06 (`eu/links.py`)."""

SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'
"""The one absolute URL an SVG document must carry. It is an identifier, never fetched."""


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    """One build of the whole tree, shared by every test below.

    Built once because the properties are all properties of one tree and rebuilding it per
    assertion would buy nothing: byte-identity across builds is asserted next to the builder
    itself, over two directories built in the same test.
    """
    return build(tmp_path_factory.mktemp("golden") / "site", changelog_repo)


def _pages(site: Path) -> list[Path]:
    pages = sorted(site.rglob("*.html"))
    assert pages
    return pages


# ------------------------------------------------------------------ the golden


def test_the_committed_golden_tree_is_what_the_command_writes(site: Path) -> None:
    built = _tree(site)
    committed = _tree(GOLDEN)
    assert built == committed, (
        f"the generated tree differs from {GOLDEN}; if the change is intended, run "
        f"`rm -rf {GOLDEN} && cp -R {site} {GOLDEN}` and read the diff"
    )


# ------------------------------------------------------------------ the properties


def test_every_page_carries_the_disclaimer(site: Path) -> None:
    for page in _pages(site):
        text = page.read_text(encoding="utf-8")
        assert escape(DISCLAIMER) in text, page
        assert "Not legal advice" in text, page


def test_external_links_leave_only_for_eur_lex_or_the_configured_repositories(
    tmp_path: Path, changelog_repo: Path
) -> None:
    """Built with both repository URLs, because those are the only other hosts a page may name.

    The two are on distinct hosts here so the allowlist below is exercised prefix by prefix
    rather than one prefix happening to cover both.
    """
    out = build(
        tmp_path / "site",
        changelog_repo,
        "--repo-url",
        "https://example.invalid/emendrix",
        "--changelogs-url",
        "https://data.example.invalid/changelogs",
    )
    for page in _pages(out):
        for link in re.findall(r'href="(https?://[^"]+)"', page.read_text(encoding="utf-8")):
            ok = (
                link.startswith("https://eur-lex.europa.eu/")
                or link.startswith("https://example.invalid/")
                or link.startswith("https://data.example.invalid/")
            )
            assert ok, f"{page}: {link}"


def test_every_citation_url_matches_the_verified_eur_lex_format(site: Path) -> None:
    """Pattern check, offline: the shape verified against the endpoint, not a request to it."""
    seen = 0
    for page in _pages(site):
        for link in re.findall(r'href="([^"]+)"', page.read_text(encoding="utf-8")):
            if "legal-content" in link:
                assert EURLEX.match(link.replace("&amp;", "&")), f"{page}: {link}"
                seen += 1
    assert seen


def test_the_only_script_is_the_committed_search_script(site: Path) -> None:
    """Every executable script on a built page is the one committed file, loaded by `src`.

    `type="application/ld+json"` is the one allowed exception, and it is narrow on purpose. An
    `ld+json` element is inert data: no browser executes it and it cannot fetch anything, which
    is precisely the property this rule exists to protect, so the rule is widened rather than
    broken. `tests/test_architecture.py` holds the same line over the sources and additionally
    pins `site_/seo.py` as the one module allowed to mint such an element.
    """
    for page in _pages(site):
        text = page.read_text(encoding="utf-8")
        scripts = re.findall(r"<script[^>]*>", text)
        assert scripts, page
        for tag in scripts:
            if 'type="application/ld+json"' in tag:
                continue
            assert 'src="' in tag and "search.js" in tag, page


def test_no_page_reaches_a_third_party_or_counts_its_readers(site: Path) -> None:
    """The security story stays one sentence, and that sentence is the only place the word is.

    The footer promises no analytics; a second occurrence of the word on a page would mean
    something on it had grown a tracker, which is why the count is pinned rather than banned.
    """
    for page in _pages(site):
        text = page.read_text(encoding="utf-8")
        for banned in ("http://", "@import", "<iframe", "googleapis", "google-analytics"):
            assert banned not in text, f"{page}: {banned}"
        assert text.count("analytics") == 1, page
        assert "no cookies, no analytics, no third-party requests" in text, page


def test_no_shipped_text_asset_reaches_a_third_party_either(site: Path) -> None:
    """The pages are only half the promise: a web font in the stylesheet is a request too.

    The feeds are excluded on purpose, because the one absolute `http://` in them is the Atom
    namespace, which is an identifier and never fetched. The icon's `xmlns` is stripped before
    the scan for exactly that reason: the SVG namespace names the language the document is
    written in and no browser ever resolves it.
    """
    for name in ("style.css", "search.js", "icon.svg"):
        text = (site / name).read_text(encoding="utf-8").replace(SVG_NS, "")
        for banned in ("http://", "https://", "@import", "url("):
            assert banned not in text, f"{name}: {banned}"


def test_no_absolute_path_of_this_machine_reaches_the_tree(
    site: Path, changelog_repo: Path
) -> None:
    """A build in a checkout and a build in a container must publish the same provenance.

    Every file, not only the pages: an absolute path in the search index or a feed would be
    committed into the golden and would then fail on the next machine that ran the suite. The
    site names the repository-relative place each artifact is committed, and nothing else.

    The comparison is over bytes rather than decoded text, which is strictly stronger and is
    also the only form that works on the link-preview card, the one file the site publishes
    that is not text at all.
    """
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        assert str(REPO).encode() not in data, path
        assert str(changelog_repo).encode() not in data, path
