"""Every watched act, grouped, with the one fact that decides where a reader goes next.

The roster page. It answers "is this act watched at all?" and "has anything happened to it?",
and it is the whole navigation for a reader without JavaScript, so it lists everything rather
than the recent slice the home page shows.

Grouping comes from the watchlist's `domain` field and nowhere else. Nothing here infers a
subject area from an act's title or its identifier: an operator who has not said which group an
act belongs in gets `Other`, which is honest, while a guess would be a claim this project has
no evidence for. `Other` sorts last for the same reason it exists, that it is the absence of an
answer rather than a group.

An act with no events says so in words. A row that simply had no date would read as a rendering
bug; "no amendments seen" is the actual state, and it is a real answer.
"""

from __future__ import annotations

from emendrix.output.markdown import short_title
from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.urls import act_href, depth_of, up

__all__ = ["render_acts_index"]

_PATH = "acts/"
_DEPTH = depth_of(_PATH)
"""`acts/index.html`: every internal link on this page climbs one directory first."""

_UNGROUPED = "Other"
"""Where an act with no declared domain lands, and the group that always sorts last."""

_QUIET = "no amendments seen"


def _groups(site: SiteInputs) -> list[tuple[str, list[ActSite]]]:
    """The acts by domain, groups alphabetical with the ungrouped bucket last.

    Insertion order inside a group is `collect_site`'s, which is already sorted by label, so
    the whole page is a total order over one repository state and two builds agree by
    construction.
    """
    grouped: dict[str, list[ActSite]] = {}
    for act in site.acts:
        grouped.setdefault(act.domain or _UNGROUPED, []).append(act)
    return sorted(
        grouped.items(), key=lambda item: (item[0] == _UNGROUPED, item[0].casefold(), item[0])
    )


def _row(act: ActSite) -> Html:
    """One act: the link, what the official text calls it, and when it last moved."""
    facts = [Html(f'<a href="{escape(up(_DEPTH) + act_href(act.slug))}">{escape(act.label)}</a>')]
    if act.entries:
        facts.append(escape(short_title(act.entries[0].title)))
    dated = act.dated
    last = f"last amended {dated.isoformat()}" if dated is not None else _QUIET
    facts.append(Html(f'<span class="muted">{escape(last)}</span>'))
    return Html(f"<li>{join(facts, ' · ')}</li>")


def render_acts_index(site: SiteInputs) -> Html:
    """The roster page. Deterministic: same inputs, same bytes, no clock, no network."""
    events = sum(len(act.entries) for act in site.acts)
    lines = [
        Html("<h1>All watched acts</h1>"),
        Html(
            f'<p class="lede muted">{escape(count(len(site.acts), "act"))} watched, '
            f"{escape(count(events, 'amendment event'))} recorded. Grouping comes from the "
            f"watchlist; nothing here is inferred.</p>"
        ),
    ]
    for domain, acts in _groups(site):
        lines.append(Html(f"<h2>{escape(domain)}</h2>"))
        lines.append(Html("<ul>"))
        lines.extend(_row(act) for act in acts)
        lines.append(Html("</ul>"))
    return page(
        title="All watched acts — emendrix",
        description=(
            "Every act emendrix watches, grouped by the domain the watchlist declares, with "
            "the date each one was last amended."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        generated_on=site.generated_on,
        repo_url=site.repo_url,
        site_url=site.site_url,
        feeds=((feed_path(None), feed_title(None)),),
    )
