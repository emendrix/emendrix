"""What one page publishes as machine-readable data: its breadcrumb trail and what it is about.

The JSON-LD half of a page's head. What that head states in meta tags, the canonical address,
the Open Graph preview and the feed links, moved to `head.py` on 2026-09-03, when a provision
page's structured data pushed this module past the size cap; the seam is the one this docstring
already drew. The blocks here follow that module's rule rather than restating it: they are
written only under an absolute base, because a JSON-LD `@id` that does not resolve identifies
nothing.

**`markup.escape` is wrong inside a JSON-LD element and must not be used there.** A browser
decodes no HTML entities inside it, so an escaped `&amp;` reaches a consumer as those five
characters and corrupts the JSON, while a literal end tag in any value ends the element early,
which is the injection escaping exists to stop. `_ld_block` is the one correct path and the only
place in the package that mints such an element: it rewrites `<`, `>` and `&` as JSON string
escapes, which keeps the document valid JSON and cannot break out of the element. `indent=2`
rather than compact separators, because the published tree is diffed in git and reviewed as a
golden; Python dicts are insertion-ordered, so the bytes are deterministic without sorting keys.

Nothing is declared that the inputs do not hold. **No `SearchAction` on the `WebSite`**, because
the search runs in the reader's browser over a prebuilt index and there is no `?q=` route to
hand anyone; a search endpoint that does not exist would be a false claim in a machine-readable
field. Every breadcrumb is derived from the URL trail itself, so no page invents a rung its own
address does not carry, and no type is claimed for a thing schema.org has no honest type for.
"""

from __future__ import annotations

import json
from typing import Final

from emendrix.core import ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct
from emendrix.site_.head import SITE_NAME, canonical_url
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html
from emendrix.site_.urls import (
    act_href,
    amendment_href,
    amendments_href,
    event_href,
    provision_href,
)

__all__ = [
    "act_json_ld",
    "amendment_json_ld",
    "event_json_ld",
    "provision_json_ld",
    "website_json_ld",
]

_SCHEMA: Final = "https://schema.org"
"""The `https` spelling, never `http`: the site publishes no `http://` string anywhere."""

_ACTS_INDEX: Final = "acts/"
"""The roster's own path, which is also the directory `act_href` puts every act page under.

Named here for the breadcrumb's middle rung; `test_seo.py` pins it to a file the build wrote,
so the two cannot drift apart silently.
"""

_INSTRUMENTS: Final = "Amending instruments"
"""The middle rung of an amendment page's breadcrumb, and that index page's own heading."""


def _ld_block(payload: object) -> Html:
    """A JSON-LD element. `markup.escape` is wrong here, and this is the whole reason why.

    Inside `<script type="application/ld+json">` the browser decodes no HTML entities, so an
    escaped `&amp;` corrupts the JSON, while a literal `</script>` in any value ends the element
    early. Escaping those three characters as JSON string escapes instead keeps the document
    valid JSON and cannot break out of the element, which is what justifies the `Html` mint.
    """
    body = (
        json.dumps(payload, ensure_ascii=False, indent=2)
        .replace("<", "\\u003C")
        .replace(">", "\\u003E")
        .replace("&", "\\u0026")
    )
    return Html(f'<script type="application/ld+json">\n{body}\n</script>')


def website_json_ld(site: SiteInputs, *, description: str) -> Html:
    """The home page's `WebSite`, and the one place the publisher is named.

    The publisher is an `Organization` called `emendrix` whose address is the site's own. No
    person is named, because nothing in the build knows one and a machine-readable field is
    the last place to guess. `description` is the page's own description meta, passed in so the
    two say the same thing rather than being written twice.
    """
    home = canonical_url(site.site_url, "")
    payload: dict[str, object] = {
        "@context": _SCHEMA,
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": home,
        "description": description,
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": home},
    }
    return _ld_block(payload)


def _breadcrumb(rungs: tuple[tuple[str, str], ...]) -> dict[str, object]:
    """One `BreadcrumbList` from `(name, absolute url)` pairs in trail order.

    Shared by every page whose breadcrumb is the URL trail itself, so a rung's position and
    its address are computed in one place however many rungs the URL actually has, and no
    page can invent a rung its address does not carry.
    """
    return {
        "@context": _SCHEMA,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": position, "name": name, "item": item}
            for position, (name, item) in enumerate(rungs, start=1)
        ],
    }


def _legislation(act: ActSite) -> dict[str, object]:
    """The `about` object every page describing this act shares.

    A `Legislation`, schema.org's ELI-derived type, and ELI is the vocabulary EU legislation
    is actually published under, so it is the honest label even though no engine renders
    anything from it. `sameAs` points at the official document the act page links, which is
    the newest consolidated version where an event resolved one and otherwise the act as
    published, and is omitted rather than emitted empty when the page links neither; the page
    and the payload name the same document or neither does. The act's own key belongs here: it
    is core vocabulary rather than the vocabulary of any one corpus, and it is what identifies
    the act everywhere else.

    `name` is the headline, the long form where the watchlist gives one, because that is what
    the page's own H1 says and a machine-readable name that disagreed with the visible one
    would be the kind of mismatch an engine discounts. The short label then rides as
    `alternateName`, omitted rather than emitted equal when there is no long form. The
    breadcrumb rungs keep the short label on purpose: a breadcrumb is the trail printed under
    a search result, and the long form would not fit in it.
    """
    about: dict[str, object] = {"@type": "Legislation", "name": act.headline}
    if act.headline != act.label:
        about["alternateName"] = act.label
    about["identifier"] = act.act.key
    if act.eurlex_url or act.published_url:
        about["sameAs"] = act.eurlex_url or act.published_url
    return about


def _webpage(
    here: str, *, title: str, description: str, about: dict[str, object]
) -> dict[str, object]:
    """The `WebPage` object every described page carries, its `@id` its canonical address."""
    return {
        "@context": _SCHEMA,
        "@type": "WebPage",
        "@id": here,
        "name": title,
        "description": description,
        "about": about,
    }


def act_json_ld(site: SiteInputs, act: ActSite, *, title: str, description: str) -> Html:
    """One act page's breadcrumb trail and the page itself, as one element holding two things.

    The breadcrumb is derived entirely from the URL structure, which is the one shape here that
    earns a real search result: the trail a reader sees under the link. It is three rungs deep
    because that is how deep the site is here, and no rung is invented.
    """
    home = canonical_url(site.site_url, "")
    roster = canonical_url(site.site_url, _ACTS_INDEX)
    here = canonical_url(site.site_url, act_href(act.slug))
    payload: list[dict[str, object]] = [
        _breadcrumb(((SITE_NAME, home), ("All watched acts", roster), (act.label, here))),
        _webpage(here, title=title, description=description, about=_legislation(act)),
    ]
    return _ld_block(payload)


def event_json_ld(
    site: SiteInputs, act: ActSite, entry: ChangelogEntry, *, title: str, description: str
) -> Html:
    """One event page's breadcrumb trail and the page itself. Four rungs, because the site is
    four deep here: home, the roster, the act, this event, the same no-invented-rung rule
    `act_json_ld` holds at three.

    `about` is the same `Legislation` the act page names, because this page still describes
    that act; which transition it describes is stated by the fourth rung and by
    `title`/`description`, and schema.org has no honest type for one amendment event, so no
    machine-readable field pretends to one.
    """
    home = canonical_url(site.site_url, "")
    roster = canonical_url(site.site_url, _ACTS_INDEX)
    act_page = canonical_url(site.site_url, act_href(act.slug))
    here = canonical_url(site.site_url, event_href(act.slug, entry.key))
    event = f"{entry.from_version} → {entry.to_version}"
    payload: list[dict[str, object]] = [
        _breadcrumb(
            ((SITE_NAME, home), ("All watched acts", roster), (act.label, act_page), (event, here))
        ),
        _webpage(here, title=title, description=description, about=_legislation(act)),
    ]
    return _ld_block(payload)


def amendment_json_ld(
    site: SiteInputs,
    instrument: AmendingAct,
    amended: tuple[ActSite, ...],
    *,
    title: str,
    description: str,
) -> Html:
    """One amending instrument's page: three rungs, and what it changed named as legislation.

    `legislationChanges` is schema.org's own property for "another legislation that this
    legislation changes", which is what an amending act does and the only machine-readable
    claim this page has to make. Its members are the same `Legislation` objects the act pages
    declare about themselves, so an act is described identically wherever it is named.

    Nothing else is declared. The instrument has no date and no type in the site's inputs, and
    a `legislationType` or a `datePublished` invented here would be a guess in the one place a
    reader cannot see it. `alternateName` carries the official number only where it is not
    already the name, the same omission `_legislation` makes for an act's short label.
    """
    home = canonical_url(site.site_url, "")
    index = canonical_url(site.site_url, amendments_href())
    here = canonical_url(site.site_url, amendment_href(instrument.key))
    about: dict[str, object] = {
        "@type": "Legislation",
        "name": instrument.short,
        "legislationIdentifier": instrument.key,
    }
    if instrument.number and instrument.number != instrument.short:
        about["alternateName"] = instrument.number
    if instrument.eurlex_url:
        about["sameAs"] = instrument.eurlex_url
    about["legislationChanges"] = [_legislation(act) for act in amended]
    payload: list[dict[str, object]] = [
        _breadcrumb(((SITE_NAME, home), (_INSTRUMENTS, index), (instrument.short, here))),
        _webpage(here, title=title, description=description, about=about),
    ]
    return _ld_block(payload)


def provision_json_ld(
    site: SiteInputs,
    act: ActSite,
    location: ProvisionLocation,
    *,
    title: str,
    description: str,
) -> Html:
    """One provision page's breadcrumb trail and the page itself. Four rungs, like an event's.

    The site is four deep here too, and the fourth rung is the provision in its human form,
    which is what the page's own H1 says. `about` is the act this provision belongs to, the
    same `Legislation` every other page describing that act declares, extended by one
    `hasPart`: schema.org's own property for a component of a work, and a provision is one.
    That part carries a name and nothing else, because a name is all the site has for it. It
    has no address of its own at EUR-Lex that resolves (provision-level ELI 404s, verified
    2026-08-05), no date, and no identifier outside this corpus's location vocabulary, so
    nothing else is claimed for it.
    """
    home = canonical_url(site.site_url, "")
    roster = canonical_url(site.site_url, _ACTS_INDEX)
    act_page = canonical_url(site.site_url, act_href(act.slug))
    here = canonical_url(site.site_url, provision_href(act.slug, location.canonical))
    about = _legislation(act)
    about["hasPart"] = {"@type": "Legislation", "name": location.human}
    payload: list[dict[str, object]] = [
        _breadcrumb(
            (
                (SITE_NAME, home),
                ("All watched acts", roster),
                (act.label, act_page),
                (location.human, here),
            )
        ),
        _webpage(here, title=title, description=description, about=about),
    ]
    return _ld_block(payload)
