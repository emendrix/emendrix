"""The committed golden tree, and the properties every page of it keeps.

The tree is built by the whole shipped command chain: `emendrix explain` writes a real
changelog into an output repository under a temporary directory from pinned fixtures and
committed cassettes, and `emendrix site build` renders the site from that repository, from
`watchlist.example.toml` and from the newest committed evaluation report. So the golden
changes exactly when the published artifact changes, which is when a reviewer should be made
to read a diff. It was read file by file on 2026-08-12 against the bar the site is held to:
legible with no context, honest about what is measured, and self-contained.

The dated record of every regeneration since, which files moved and by what, is the module
docstring of `golden_record.py`, split off on 2026-09-02 when it had grown to half of this
module and pushed it past the size cap. It stays a record: nothing is trimmed from it, and
every regeneration still adds one paragraph there, in the same form.

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
from helpers import REPO, _tree, build, text_of

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


def _asset(site: Path, suffix: str) -> str:
    """The one root-level file of that kind, under whatever name the build wrote it under.

    The stylesheet and the script carry a digest of their own bytes, so their names move with
    their content and nothing may pin one as a literal. Read off the tree rather than imported
    from the builder, because what these tests are about is the file the tree actually holds.
    """
    names = sorted(path.name for path in site.glob(f"*{suffix}"))
    assert len(names) == 1, names
    return names[0]


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
    """The words, not the markup: the lead is bold, so the constant spans two nodes.

    Read over the tag-stripped page for that reason and no other. What is asserted is still
    the escaped constant, character for character, which is what stops the sentence being
    reworded on a page while the source of truth stays where every other output reads it.
    """
    for page in _pages(site):
        text = page.read_text(encoding="utf-8")
        assert escape(DISCLAIMER) in text_of(text), page
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

    The name is read off the tree, so this stays an assertion that every page loads the one
    script the build wrote and cannot pass by matching a string nothing on disk answers to.
    """
    script = _asset(site, ".js")
    for page in _pages(site):
        text = page.read_text(encoding="utf-8")
        scripts = re.findall(r"<script[^>]*>", text)
        assert scripts, page
        for tag in scripts:
            if 'type="application/ld+json"' in tag:
                continue
            assert 'src="' in tag and script in tag, page


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
    for name in (_asset(site, ".css"), _asset(site, ".js"), "icon.svg"):
        text = (site / name).read_text(encoding="utf-8").replace(SVG_NS, "")
        for banned in ("http://", "https://", "@import", "url("):
            assert banned not in text, f"{name}: {banned}"


_LARGEST_PAGE = ("acts/32017R0745/02017R0745-20200424/index.html", 42020)
"""The heaviest page in the committed golden, path and exact bytes, read off the tree the day
the act page split into a timeline and one page per event (2026-08-31). It is the MDR event
page, the one place the golden's verbatim text now lives. The full-tree comparison above
already pins every byte; this pins the one number that grew tenfold unnoticed on the live site,
so a page regaining that shape is a stated finding rather than a diff nobody weighs.

41 bytes lighter on 2026-09-01, when a footnote stopped being run into the sentence citing it
(`eu/formex/text.py`, `DETACHED_ELEMENTS`). Two of those bytes are the line breaks the fix
inserts into the verbatim text this page quotes; the page still lost weight overall because the
one explanation on it moved key and its re-recording is shorter prose. Neither number is a
measurement of anything, which is why only the total is pinned.

75 bytes heavier on 2026-09-02, when the event page's title stopped restating the version pair
the H2 already carries and started saying what the page holds, `9 provisions changed, in force
2020-04-24`, with the description saying the same in a sentence. The title is written three
times in the head (`<title>`, `og:title` and the JSON-LD `WebPage` name, with the description
beside each), which is where all 75 bytes went; nothing below the head moved.

1120 bytes heavier on 2026-09-02, later the same day, when each of the nine change blocks
opened with an `<h3>` of three spans and its own applies paragraph, and the page gained the
`nav.touched` list above them: nine items of a fragment link and a pill, which is most of the
growth. Nothing inside a `<details>` moved.

65 bytes heavier on 2026-09-03, when the site gained an about page. The header bar's fourth
link costs 36 bytes at this depth and the footer's closing one 47, and the disclaimer gave 18
back by no longer printing `Not legal advice` twice. Every page on the site moved by those
same three edits; only the relative paths differ, and this page is three directories down.

28 bytes heavier on 2026-09-03, later the same day, when the event's opening became its date.
The `<h2>` held the version pair in two `<code>` elements and now holds the dated words, with
the pair below it in `<p class="ident">` inside one `<code>`: 78 bytes of heading became 28,
and the new paragraph costs 78 including the line break. It is the whole markup change of that
pass on this page, paid once for the event rather than once for each of its nine blocks, which
is why the page grew by less than the heading of a single change block cost it the day before.
Nothing inside a `<details>` moved, and no anchor did.

102 bytes heavier on 2026-09-03, later again: 82 of chrome that every page on the site gained,
a skip link, the header navigation's name and the id it skips to, plus 43 for the class that
keeps `EUR-Lex` off a line break at 390px, less 23 given back by a dates line that no longer
restates the clock its own heading names.

618 bytes heavier on 2026-09-03, later again, when the event started naming the instrument
that made it. 233 of those are the `p.amending` line, the number linked to EUR-Lex with the
CELEX beside it, and 224 the recorded official title of `32020R0561` printed verbatim under it,
which is the one place on the site the words of that title appear. The rest is the head: the
title and the description each name the instrument now, and each is written three times there
(`<title>`, `og:title` and the JSON-LD `WebPage` name, with the description beside each). No
change block moved and nothing inside a `<details>` did.

157 bytes heavier on 2026-09-03, later again, when the instrument that made the event gained a
page of its own. 111 of those are the line under the act's facts, one link per named
instrument to everything that instrument amended, and 46 are the header bar's fifth link, to
the roster of those instruments, which every page on the site gained at whatever its own depth
costs. This event is the act's only one, so it carries no pager; an act with a history gains
two dated links at the foot of each of its event pages.

102 bytes heavier on 2026-09-03, later again, when each of the nine coordinates in a change
heading became a link to that provision's own page: about 11 bytes a block, a span traded for
an anchor and a relative path one directory up. This page is still the largest in the golden
and by a wide margin, which is the shape the provision pages were designed to keep: the nine
new pages weigh 6124 to 11 225 bytes each, because a provision page carries the verbatim text
of its newest step only. Nothing inside a `<details>` moved and no anchor did.

491 bytes heavier on 2026-09-03, later again, and it is two changes pulling against each
other. The page gained about 1050 bytes of wayfinding: a permalink on each of the nine change
headings (69 bytes plus the anchor it repeats), the grid wrapper and the section that holds
the blocks, the count line above the index, and the link back to the top. It gave back about
559, because the citations moved out of the sentences and into one row per change: eighteen
inline pairs became nine rows of the distinct citations, and Art. 59, whose three sentences
each cited the same single anchor, now prints that anchor once. The saving grows with the
prose, so the pages this pin exists to watch, the ones carrying hundreds of explained
changes, pay proportionally less of the 1053 than this one does.

2310 bytes heavier on 2026-09-03, later again, when every change started saying how much of
its provision moved. Eighteen figures at about 128 bytes each: one in each of the nine change
headings and one in each of the nine index items, the bulk of it the `title` sentence saying
what the characters are, repeated per figure because a title is where a reader asks. The index
items carry a weight class as well, and the count line above them gained the event's totals.
This is the most expensive markup per change the page has ever gained, and it is spent on the
one fact the type pill cannot carry: six of these nine changes are date moves of 4 to 50
characters and three are prose, which a reader could previously tell apart only by opening
nine `<details>`. Nothing inside one moved and no anchor did.

769 bytes heavier on 2026-09-04, when every change whose text moved a machine-readable date
started printing those dates under its applies line. All nine of this event's changes moved
one, so the page pays nine paragraphs of about 85 bytes: this is the postponement, and the
dates are the whole of what it did. The line is a fact about the text and never a schedule,
which is the wording `pages/prose.py` holds and the act page's own list repeats at length. No
measured figure moved with it; nothing inside a `<details>` and no anchor moved.

18 bytes heavier on 2026-09-04, when the stylesheet and the script gained a digest of their own
bytes in their names: nine characters in each of the two asset links, paid identically by every
page on the site. It buys a cache that cannot serve yesterday's stylesheet beside today's
markup, which is what the edge did serve that day, holding 14 424 bytes of it against the
origin's 22 056 under a one-day asset lifetime. No measured figure moved with it, and on this
page nothing else moved at all."""


def test_the_largest_page_is_a_reviewed_number() -> None:
    """The heaviest page, named and weighed, updated only with the golden itself.

    Asserted over the committed tree rather than the built one because the two are already
    asserted equal above, and a reviewer updating the golden should see this number move in
    the same diff.
    """
    pages = [(page.relative_to(GOLDEN).as_posix(), page.stat().st_size) for page in _pages(GOLDEN)]
    heaviest = max(pages, key=lambda item: (item[1], item[0]))
    assert heaviest == _LARGEST_PAGE, (
        f"the largest page is now {heaviest[0]} at {heaviest[1]} bytes; if the change is "
        "intended, update _LARGEST_PAGE with the golden and say why in the docstring above"
    )


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
