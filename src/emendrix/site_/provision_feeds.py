"""Atom for one provision, and one OPML file per act that lists every such feed.

A reader who cares about one article of a long act would otherwise subscribe to the act and read
every version for the one change in it they wanted. Each provision with a recorded change gets a
feed of its own, rendered from the same `ProvisionHistory` its page renders, so the feed is that
page's subscription form and says nothing the page does not.

**An entry's `<id>` is the change's own address on its version page**,
`{site_url}/acts/{slug}/{key}/#{anchor}`, where `anchor` is `ProvisionStep.anchor`, the fragment
`urls.entry_anchors` counts once for the version page, the provision page and this feed alike.
The act feed's id is `{site_url}/acts/{slug}/#{key}`, an address on the act page with no
version directory in it, so the two can never be equal: a reader subscribed to both sees one
item for the version and one for each change it made, which is what they are. Like the act
feed's, the id moves only when `--site-url` does.

The framing is written again here rather than shared with `feeds.py`, whose ids are a public
promise that no edit made for this module may risk; a test holds the two framings to the same
declaration, namespace and author lines.

No entry carries verbatim text or a cited sentence. A provision touched by many versions would
repeat the heaviest part of the site once per step, and the version page the entry links holds
both. Nothing here reads a clock: an entry is dated by `event_dated`, as the act feed's are.

The OPML file is OPML 2.0 with no `dateCreated`, which would be either a clock read or a date
that is not when the file was made. The disclaimer is both an XML comment, for a reader of the
file, and the first outline, for a reader of whatever the file is imported into. An XML comment
may not hold `--`, which the disclaimer does not, and a test holds it to that.
"""

from __future__ import annotations

from datetime import date

from emendrix import DISCLAIMER
from emendrix.output.markdown import applies_text
from emendrix.site_.amending import amenders
from emendrix.site_.clocks import event_date, event_dated
from emendrix.site_.dispute import REASON_SENTENCES
from emendrix.site_.feeds import feed_title
from emendrix.site_.history import ProvisionHistory, ProvisionStep, histories
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.urls import event_href, location_slug, provision_href

__all__ = [
    "opml_path",
    "provision_feed_files",
    "provision_feed_path",
    "provision_feed_title",
    "render_opml",
    "render_provision_feed",
]

_DIRECTORY = "feeds/acts"
_OPML = "provisions.opml"


def provision_feed_path(act: ActSite, canonical: str) -> str:
    """`feeds/acts/<slug>/<location slug>.xml`, relative to the site root."""
    return f"{_DIRECTORY}/{act.slug}/{location_slug(canonical)}.xml"


def opml_path(act: ActSite) -> str:
    """`feeds/acts/<slug>/provisions.opml`. No location slug can be it: it has no `.xml`."""
    return f"{_DIRECTORY}/{act.slug}/{_OPML}"


def provision_feed_title(act: ActSite, history: ProvisionHistory) -> str:
    """The act feed's title followed by the coordinate as the provision page names it."""
    return f"{feed_title(act)} {history.location.human}"


def _stamp(value: date) -> str:
    """Midnight UTC of the day the corpus named, the act feed's rule."""
    return f"{value.isoformat()}T00:00:00Z"


def _change_url(site: SiteInputs, act: ActSite, step: ProvisionStep) -> str:
    """The change's block on its version page: the entry's id and its link at once."""
    return f"{site.site_url}/{event_href(act.slug, step.entry.key)}#{step.anchor}"


def _applies(step: ProvisionStep) -> str:
    """`applies_text`'s answer, with `unknown` said as what it is: a date not read."""
    value = applies_text(step.change.applies_from)
    return "not read" + value.removeprefix("unknown") if value.startswith("unknown") else value


def _summary(site: SiteInputs, step: ProvisionStep) -> str:
    """What the step's block on the provision page states, in sentences, then the disclaimer."""
    change = step.change
    in_force = change.in_force.isoformat() if change.in_force else "not stated"
    parts = [f"{change.change_type.value.capitalize()}.", f"In force {in_force}."]
    parts.append(f"Applies from: {_applies(step)}.")
    for label, dates in (
        ("Dates added to the text", change.dates_added),
        ("Dates removed", change.dates_removed),
    ):
        if dates:
            parts.append(f"{label}: {', '.join(value.isoformat() for value in dates)}.")
    if change.disputed:
        reason = change.dispute_reason
        parts.append(
            f"Sources differ: {REASON_SENTENCES[reason]}"
            if reason is not None
            else "Sources differ."
        )
    numbers = ", ".join(act.number or act.key for act in amenders(site.amending, step.entry))
    if numbers:
        parts.append(f"Amended by {numbers}.")
    parts.extend(("The text is on the version's page.", DISCLAIMER))
    return " ".join(parts)


def _entry_xml(
    site: SiteInputs, act: ActSite, history: ProvisionHistory, step: ProvisionStep
) -> str:
    """One change to this provision as one Atom entry, titled as its page heads the step: the
    coordinate, the kind in the words its tag uses, and the version by its clock and date."""
    url = escape(_change_url(site, act, step))
    words = step.change.change_type.value.capitalize()
    dated = event_date(step.entry).human
    title = escape(f"{act.label} {history.location.human}: {words}, version {dated}")
    return join(
        (
            Html("<entry>"),
            Html(f"<title>{title}</title>"),
            Html(f"<id>{url}</id>"),
            Html(f'<link rel="alternate" href="{url}"/>'),
            Html(f"<updated>{_stamp(event_dated(step.entry))}</updated>"),
            Html(f"<summary>{escape(_summary(site, step))}</summary>"),
            Html("</entry>"),
        ),
        "\n",
    )


def _require_base(site: SiteInputs) -> str:
    if not site.site_url:
        raise ValueError(
            "a feed's links are absolute, so rendering one needs a site URL; "
            "check `site.site_url` before asking for a feed"
        )
    return site.site_url


def render_provision_feed(site: SiteInputs, act: ActSite, history: ProvisionHistory) -> str:
    """One provision's Atom document, newest step first, newline-terminated."""
    base = _require_base(site)
    canonical = history.location.canonical
    self_url = escape(f"{base}/{provision_feed_path(act, canonical)}")
    alternate = escape(f"{base}/{provision_href(act.slug, canonical)}")
    updated = max(event_dated(step.entry) for step in history.steps)
    lines = [
        Html('<?xml version="1.0" encoding="utf-8"?>'),
        Html('<feed xmlns="http://www.w3.org/2005/Atom">'),
        Html(f"<title>{escape(provision_feed_title(act, history))}</title>"),
        Html(f"<id>{self_url}</id>"),
        Html(f'<link rel="self" href="{self_url}"/>'),
        Html(f'<link rel="alternate" href="{alternate}"/>'),
        Html(f"<updated>{_stamp(updated)}</updated>"),
        Html("<author><name>emendrix</name></author>"),
        *(Html(_entry_xml(site, act, history, step)) for step in history.steps),
        Html("</feed>"),
        Html(""),
    ]
    return join(lines, "\n")


def _outline(base: str, act: ActSite, history: ProvisionHistory) -> Html:
    """One provision feed as an OPML outline, named as the feed names itself."""
    canonical = history.location.canonical
    title = escape(provision_feed_title(act, history))
    feed = escape(f"{base}/{provision_feed_path(act, canonical)}")
    page = escape(f"{base}/{provision_href(act.slug, canonical)}")
    return Html(
        f'<outline type="rss" text="{title}" title="{title}" xmlUrl="{feed}" htmlUrl="{page}"/>'
    )


def render_opml(
    site: SiteInputs, act: ActSite, found: tuple[ProvisionHistory, ...] | None = None
) -> str:
    """Every provision feed of one act, in `histories(act)` order, as one OPML 2.0 file.

    `found` is that act's histories where the caller already holds them.
    """
    base = _require_base(site)
    outlines = [
        _outline(base, act, history) for history in (histories(act) if found is None else found)
    ]
    lines = [
        Html('<?xml version="1.0" encoding="utf-8"?>'),
        Html(f"<!-- {DISCLAIMER} -->"),
        Html('<opml version="2.0">'),
        Html("<head>"),
        Html(f"<title>{escape(feed_title(act))} provisions</title>"),
        Html("</head>"),
        Html("<body>"),
        Html(f'<outline text="{escape(DISCLAIMER)}"/>'),
        *outlines,
        Html("</body>"),
        Html("</opml>"),
        Html(""),
    ]
    return join(lines, "\n")


def provision_feed_files(site: SiteInputs) -> dict[str, str]:
    """Every provision feed and every act's OPML file, path -> contents; `{}` without a base.

    An act with no recorded change has no provision to follow, so it gets neither.
    """
    if not site.site_url:
        return {}
    files: dict[str, str] = {}
    for act in site.acts:
        found = histories(act)
        if not found:
            continue
        for history in found:
            path = provision_feed_path(act, history.location.canonical)
            files[path] = render_provision_feed(site, act, history)
        files[opml_path(act)] = render_opml(site, act, found)
    return files
