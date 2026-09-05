"""The whole tree, written out. One table of files, one loop, no decisions.

```
index.html                      the front door
404.html                        what an address that matches nothing gets
style.<digest>.css              the one stylesheet every page links, named for its bytes
search.<digest>.js              the one script, copied from the package as committed
icon.svg                        the favicon every head links
og.png                          the link-preview card, the one binary published
robots.txt                      the crawl policy, and where the sitemap is
search-index.json               what that script fetches, prebuilt
sitemap.xml                     every page, with the date its content last moved
acts/index.html                 the roster
acts/<slug>/index.html          one page per watched act: its timeline and index
acts/<slug>/<key>/index.html    one page per event: the changes and the verbatim text
acts/<slug>/<prov>/index.html   one page per touched provision: its history, newest first
amendments/index.html           every instrument a committed event names, newest first
amendments/<slug>/index.html    one page per instrument: every watched act it amended
dates/index.html                every date the amended texts name that is still ahead
methodology/index.html          what the numbers mean
about/index.html                who runs the site, and what it does on the reader's machine
feeds/index.html                what feeds exist
feeds/all.xml                   every event, newest first
feeds/<slug>.xml                one feed per act, quiet acts included
```

The stylesheet, the script and the icon live at the site root because `chrome.page` links them
relative to it, and the script reads the index back from the root it was handed; move any of
them and every page below the root loads nothing. The first two carry a digest of their own
bytes in the name, and `fingerprint` is the module that says why; both names are read from
there rather than spelled again here, so what a page links and what this table writes cannot
be two strings. `robots.txt` and `sitemap.xml` sit at the root because that is the only place a
crawler looks for either.

The feeds and the sitemap are the one conditional, and it is one rule rather than two: a feed's
links and a sitemap's locations are both absolute, so without a site URL `render_feed` and
`sitemap_xml` refuse and no `.xml` is written at all. The feeds page then says so in words rather
than listing files that are not there, and `robots.txt` loses only its `Sitemap:` line, because a
crawl policy is about paths and needs no base to state one. The icon and the card are written
unconditionally: what needs a base address is the reference to an asset, never the asset, and an
unreferenced image costs a few kilobytes where a conditional costs a rule a reader has to hold.

Determinism is the property this module exists to keep. The table is written in sorted path
order, every string arrives already newline-terminated from the renderer that made it, and
`newline="\\n"` pins the line ending so a build on Windows produces the bytes a build on Linux
produces. Nothing here reads a clock, a socket or a model: `generated_on` came in at the CLI
boundary, and everything else is a pure function of the committed artifacts.

Nothing already in `out` is read, moved or deleted. The directory belongs to the operator, who
may well keep a `CNAME`, a `.nojekyll` or the leftovers of another build in it; a generator that
tidies is a generator that eventually deletes something it did not write. So a build into a
directory a previous build wrote leaves the previous stylesheet and script sitting beside the
new ones, unreferenced by any page and a few kilobytes each. That is the deliberate cost of the
rule above, and it is also what lets a reader who is mid-request keep loading the file the page
they already have names; `docs/site.md` tells the operator when to sweep them.
"""

from __future__ import annotations

from pathlib import Path

from emendrix.site_.amending import resolve
from emendrix.site_.assets import icon_svg, og_png, search_js
from emendrix.site_.discovery import ROBOTS, SITEMAP, robots_txt, sitemap_xml
from emendrix.site_.feeds import feed_path, render_feed, render_feeds_page
from emendrix.site_.fingerprint import SCRIPT, STYLESHEET
from emendrix.site_.history import histories
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.instruments import amended_by
from emendrix.site_.pages.about import render_about
from emendrix.site_.pages.act import render_act
from emendrix.site_.pages.acts_index import render_acts_index
from emendrix.site_.pages.amendment import render_amendment_page
from emendrix.site_.pages.amendments_index import render_amendments_index
from emendrix.site_.pages.dates import render_dates
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.home import render_home
from emendrix.site_.pages.methodology import render_methodology
from emendrix.site_.pages.not_found import render_not_found
from emendrix.site_.pages.provision import render_provision_page
from emendrix.site_.pages.texts import text_blocks
from emendrix.site_.search_index import search_index_json
from emendrix.site_.style import STYLE
from emendrix.site_.urls import (
    act_href,
    amendment_href,
    amendments_href,
    dates_href,
    event_href,
    provision_href,
)

__all__ = ["act_pages", "write_site"]

INDEX = "search-index.json"
"""What the script fetches, at the root the script is handed as `data-root`. A fixed name: it
changes on every build and is served with the short lifetime the pages carry."""

ICON = "icon.svg"
CARD = "og.png"
"""The favicon and the link-preview card, both at the root every page links relative to."""


def act_pages(site: SiteInputs, act: ActSite) -> dict[str, str]:
    """One act's whole page tree, path -> contents: its timeline, its events, its provisions.

    Factored out of `_files` because the scale suite needs exactly this slice, one act's index
    beside the pages it links into, without assembling the rest of the site around it, for the
    reason `entry_anchors` is one function rather than one counter per caller: the pages that
    must agree are built by the one code path the builder itself runs.

    The evidence blocks are computed here, once per entry, and handed to both kinds of page.
    An event page shows every one of its entry's blocks and a provision page shows the one
    belonging to its newest step, so a diff that would otherwise be built twice is built once
    however many pages carry it. That is the whole reason the cache exists: the texts are the
    expensive part of this tree by orders of magnitude.
    """
    blocks = {entry.key: text_blocks(entry) for entry in act.entries}
    files: dict[str, str] = {f"{act_href(act.slug)}index.html": render_act(site, act)}
    for entry in act.entries:
        files[f"{event_href(act.slug, entry.key)}index.html"] = render_event_page(
            site, act, entry, blocks[entry.key]
        )
    for history in histories(act):
        path = provision_href(act.slug, history.location.canonical)
        files[f"{path}index.html"] = render_provision_page(
            site, act, history, blocks[history.steps[0].entry.key]
        )
    return files


def _files(site: SiteInputs, home_limit: int) -> dict[str, str | bytes]:
    """Every file the site is, as `relative path -> contents`. Pure; writes nothing."""
    files: dict[str, str | bytes] = {
        "index.html": render_home(site, limit=home_limit),
        "404.html": render_not_found(site),
        STYLESHEET: STYLE,
        SCRIPT: search_js(),
        ICON: icon_svg(),
        CARD: og_png(),
        ROBOTS: robots_txt(site),
        INDEX: search_index_json(site),
        "acts/index.html": render_acts_index(site),
        f"{amendments_href()}index.html": render_amendments_index(site),
        f"{dates_href()}index.html": render_dates(site),
        "methodology/index.html": render_methodology(site),
        "about/index.html": render_about(site),
        "feeds/index.html": render_feeds_page(site),
    }
    for act in site.acts:
        files.update(act_pages(site, act))
    # Only an instrument a committed event names gets a page: a declared short name for one
    # nothing has been attributed to would be a page about work the corpus has not recorded.
    for key, amended in amended_by(site).items():
        files[f"{amendment_href(key)}index.html"] = render_amendment_page(
            site, resolve(site.amending, key), amended
        )
    if site.site_url:
        files[SITEMAP] = sitemap_xml(site)
        files[feed_path(None)] = render_feed(site, None)
        for act in site.acts:
            files[feed_path(act)] = render_feed(site, act)
    return files


def write_site(out: Path, site: SiteInputs, *, home_limit: int = 20) -> tuple[Path, ...]:
    """Write the site into `out` and return the relative paths written, sorted.

    Directories are created as needed and nothing else in `out` is touched: the operator owns
    that directory. Two calls with one `SiteInputs` write byte-identical files.

    Bytes and text take separate branches because `write_bytes` accepts no newline argument and
    the card must reach the tree exactly as it was committed, neither decoded nor re-encoded.
    """
    written: list[Path] = []
    for name, content in sorted(_files(site, home_limit).items()):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")
        written.append(Path(name))
    return tuple(written)
