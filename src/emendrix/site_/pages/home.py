"""The front door: what changed lately, and one measured claim about how well it is found.

A reader arrives with an act in mind, so the first thing under the headline is a way to reach an
act (the search control the script mounts in the header, and the recent-act links that stand in
for it without JavaScript), and the second is the list of what actually moved. The argument for
trusting any of it lives on the methodology page instead, where a reader who wants it finds all
of it at once rather than scrolling past it to get to the facts.

Three things this page will not do:

- **No explanation prose.** A card carries the act, the version pair, the counts and the date,
  all of them read off the committed document. Sentences a model wrote live on the act page,
  next to the verbatim text they describe.
- **No number without its qualification.** The credibility strip publishes the localisation
  figure and links straight to the row that says what it does not mean.
- **No silence.** An empty changelog repository, or none at all, is a sentence saying which,
  not a page that renders nothing.

Depth 0: this page sits at the site root, so its internal links need no prefix. `up(0)` is
still written where a link is built, because the prefix is what makes the tree work from a
subpath and it should be visible at every link rather than assumed here.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.seo import website_json_ld
from emendrix.site_.urls import act_href, depth_of, up

__all__ = ["render_home"]

_PATH = ""
_DEPTH = depth_of(_PATH)
"""`index.html`: the site root, so every internal href on this page is already relative."""

_RECENT_ACTS = 6
"""How many acts the hero row names before it stops. The index holds all of them."""

_HEADLINE = "What changed in your regulations?"

_QUIET = (
    "The changelog repository this page was built from holds no amendment events for the "
    "watched acts yet.",
    "No changelog repository was configured for this build, so it had no amendment events to show.",
)
"""Configured and unconfigured are different answers, and neither of them is an empty page."""

_QUIET_TAIL = "A quiet month is a real answer."


def _pitch(site: SiteInputs) -> str:
    """The one-line claim, and the roster size it is made over.

    With a watchlist that count is the whole roster, quiet acts included, which is the intended
    meaning: an act is watched whether or not anything has happened to it yet.
    """
    return (
        f"Provision-level changelogs for {count(len(site.acts), 'watched act')}. Every explanation "
        f"cites the provision it describes; every change carries its verbatim text."
    )


def _recent_acts(site: SiteInputs) -> list[ActSite]:
    """The most recently amended acts, each named once, newest first."""
    named: list[ActSite] = []
    seen: set[str] = set()
    for act, _ in site.recent:
        if act.slug not in seen:
            seen.add(act.slug)
            named.append(act)
        if len(named) == _RECENT_ACTS:
            break
    return named


def _hero(site: SiteInputs) -> list[Html]:
    """Headline, pitch, and the no-JavaScript way into the acts: links, not a dead input box."""
    links = [
        Html(f'<a href="{escape(up(_DEPTH) + act_href(act.slug))}">{escape(act.label)}</a>')
        for act in _recent_acts(site)
    ]
    links.append(Html(f'<a href="{up(_DEPTH)}acts/">or browse all acts →</a>'))
    return [
        Html('<section class="hero">'),
        Html(f'<h1 class="display">{escape(_HEADLINE)}</h1>'),
        Html(f'<p class="lede">{escape(_pitch(site))}</p>'),
        Html(f"<p>{join(links, ' · ')}</p>"),
        Html("</section>"),
    ]


def _card(act: ActSite, entry: ChangelogEntry) -> Html:
    """One event, in two lines: which act moved, by how much, and from when.

    The date says which clock it came from. `in_force` is the corpus's own answer and is
    absent on plenty of events, and a detection date printed as an in-force date would be a
    quiet lie about a fact this project treats as first class.
    """
    counts = entry.counts
    touched = count(counts.touched, "provision")
    if counts.disputed:
        touched += f", {counts.disputed} disputed"
    dated = (
        f"in force {max(entry.in_force).isoformat()}"
        if entry.in_force
        else f"detected {entry.detected_on.isoformat()}"
    )
    href = f"{up(_DEPTH)}{act_href(act.slug)}#{entry.key}"
    return Html(
        f'<div class="cardrow">'
        f'<h3><a href="{escape(href)}">{escape(act.label)}</a> '
        f"<code>{escape(str(entry.from_version))} → {escape(str(entry.to_version))}</code></h3>"
        f"<p>{escape(touched)} · {escape(dated)}</p>"
        f"</div>"
    )


def _amendments(site: SiteInputs, limit: int) -> list[Html]:
    """The newest events, capped, with the remainder pointed at rather than dropped."""
    recent = site.recent
    lines = [Html("<h2>Latest amendments</h2>")]
    if not recent:
        where = _QUIET[0] if site.configured else _QUIET[1]
        lines.append(Html(f'<p class="none">{escape(where)} {escape(_QUIET_TAIL)}</p>'))
        return lines
    shown = recent[:limit]
    lines.extend(_card(act, entry) for act, entry in shown)
    older = len(recent) - len(shown)
    if older:
        verb = "is" if older == 1 else "are"
        lines.append(
            Html(
                f'<p class="small muted">{escape(count(older, "older event"))} {verb} on the '
                f"act pages.</p>"
            )
        )
    return lines


def _strip(site: SiteInputs) -> Html:
    """The measured claim, carrying what it is not, and the link to the row that says the rest.

    The qualification is in the same sentence as the number rather than behind the link. A
    figure quoted bare on the busiest page of the site and explained one click away is a figure
    most readers meet without its limitation, and the limitation here is the whole difference
    between finding the right provisions and describing them well.

    A figure the report does not carry is said to be absent, never rendered as a zero and never
    quietly omitted: the strip is the same width either way.
    """
    pair = site.run.metrics.localisation
    link = Html(f'<a href="{up(_DEPTH)}methodology/">Measured, not asserted →</a>')
    if pair is None:
        return Html(
            f'<p class="strip">No localisation figure is recorded in the report this page was '
            f"built from, so none is claimed here. {link}</p>"
        )
    return Html(
        f'<p class="strip">Finding <em>which</em> provisions an amendment touched scores micro-F1 '
        f"<strong>{pair.micro_f1:.3f}</strong> over {count(pair.cases, 'transition')}, against "
        f"labels the legislation publishes about itself. It is not a measure of whether any "
        f"explanation is good. {link}</p>"
    )


def render_home(site: SiteInputs, *, limit: int = 20) -> Html:
    """The site's index page. Deterministic: same inputs, same bytes, no clock, no network.

    The pitch is computed once and reaches the reader, the description meta and the structured
    data as one sentence. The `WebSite` block needs the absolute base to name the site by its
    address, so a build without one carries no block rather than an incomplete one.
    """
    body = join(
        (
            *_hero(site),
            *_amendments(site, limit),
            _strip(site),
        ),
        "\n",
    )
    description = _pitch(site)
    return page(
        title="emendrix — what changed in your regulations",
        description=description,
        body=body,
        path=_PATH,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
        structured=website_json_ld(site, description=description) if site.site_url else None,
    )
