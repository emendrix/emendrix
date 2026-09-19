"""The front door: the versions the watched acts took lately, and one measured claim.

A reader arrives with an act in mind, so the first thing under the headline is a way to reach an
act (the search control the script mounts in the header, and the recent-act links that stand in
for it without JavaScript), and the next is the list of what actually moved. The measured claim
follows the list, as a panel of its own: a stranger meets the versions before a measure of the
engine that found them, the way a reference desk shows its holdings before its method, and a
figure set above the facts reads as the page's subject when it is a note about how the facts
were found. It stays on the front page rather than only on the methodology page because the
limitation it carries is the one a reader most needs, and it keeps its sentence, its number and
its caveat whole wherever it sits.

Four things this page will not do:

- **No explanation prose.** A card carries the act, the version, the amending act, the tally
  and the identifiers, all of them read off the committed document. Sentences a model wrote
  live on the version pages, next to the verbatim text they describe.
- **No number without its qualification.** The stat strip publishes the localisation figure in
  the sentence that says what it does not mean, and links straight to the section that says
  the rest.
- **No silence.** An empty changelog repository, or none at all, is a sentence saying which,
  not a page that renders nothing, and every version not shown is counted in words.
- **No tag without the way to what it means.** A card's tags are adjectives in fixed looks, and
  the list prints one link to the glossary that defines every one of them, above the cards.

Depth 0: this page sits at the site root, so its internal links need no prefix. `up(0)` is
still written where a link is built, because the prefix is what makes the tree work from a
subpath and it should be visible at every link rather than assumed here.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amenders, by_words
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, unattributed
from emendrix.site_.chrome import page
from emendrix.site_.clocks import version_heading
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.seo import website_json_ld
from emendrix.site_.tags import LIST_HELP_WORDS, tag, tags_help, tally
from emendrix.site_.urls import act_href, depth_of, event_href, up

__all__ = ["render_home"]

_PATH = ""
_DEPTH = depth_of(_PATH)
"""`index.html`: the site root, so every internal href on this page is already relative."""

_RECENT_ACTS = 6
"""How many acts the hero row names before it stops. The index holds all of them."""

_HEADLINE = "What changed in your regulations?"

_QUIET = (
    "No version is recorded for the watched acts yet: the changelog repository this page was "
    "built from holds none.",
    "No changelog repository was configured for this build, so it has no version to show.",
)
"""Configured and unconfigured are different answers, and neither of them is an empty page."""

_QUIET_TAIL = "A quiet month is a real answer."

_ALL_UNNAMED = (
    "recorded so far named no amending act, so this list has nothing to show; each one is on "
    "its act's page."
)
"""When every recorded event names no amending act: events exist, amendments do not, and the
sentence says both rather than going dark over a non-empty record."""


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
    """The acts with the newest events, each named once, newest first.

    Deliberately unfiltered by attribution: the row names acts as a way in, claims nothing
    about what happened to them, and an act whose newest event names no amending act still
    deserves its link, since its own page carries the labelled picture.
    """
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
    """Headline, pitch, and the no-JavaScript way into the acts: links, not a dead input box.

    Each act is named as its own page's heading names it, the long form where the watchlist
    gives one, so the link and the page it opens say the same name.
    """
    links = [
        Html(f'<a href="{escape(up(_DEPTH) + act_href(act.slug))}">{escape(act.headline)}</a>')
        for act in _recent_acts(site)
    ]
    links.append(Html(f'<a class="go" href="{up(_DEPTH)}acts/">or browse all acts</a>'))
    return [
        Html('<section class="hero">'),
        Html(f'<h1 class="display">{escape(_HEADLINE)}</h1>'),
        Html(f'<p class="lede">{escape(_pitch(site))}</p>'),
        Html(f"<p>{join(links, ' · ')}</p>"),
        Html("</section>"),
    ]


def _card(act: ActSite, entry: ChangelogEntry, named: str) -> Html:
    """One version, led by its act: the act and the version each have one name and one link.

    The caption names the act and goes to the act's page, in the act's colour and shape, and
    the heading names the version the way its own page does and goes there. A card once headed
    by the act's name linked the version page, so one name led two places across the site.
    The act's label is used rather than its long form because a card is a row in a list.

    The heading's date says which clock it came from, through `clocks.version_heading`: a
    detection date printed as an in-force date would be a quiet lie about a fact this project
    treats as first class. `named` is the amending-act clause, `by Digital Omnibus on AI`, in
    plain text: the version's own page links each amending act, and a third link here would
    give the card a third destination. The tally is the one every version card on the site
    prints, so a count read here and on the act page is the same count in the same words. The
    version pair is last, as identifiers one step down.
    """
    if named:
        made = [Html(f'<p class="made">{escape(f"Made {named}")}</p>')]
    elif unattributed(entry):
        made = [Html(f'<p class="made">{tag("unattributed", UNATTRIBUTED_LABEL)}</p>')]
    else:
        made = []
    act_link = escape(up(_DEPTH) + act_href(act.slug))
    href = escape(up(_DEPTH) + event_href(act.slug, entry.key))
    return join(
        (
            Html('<article class="cardrow">'),
            Html(f'<p class="caption"><a href="{act_link}">{escape(act.label)}</a></p>'),
            Html(f'<h3><a href="{href}">{version_heading(entry)}</a></h3>'),
            *made,
            *tally(entry, shapes=False),
            Html(
                f'<p class="ident"><code class="id">{escape(str(entry.from_version))}</code> → '
                f'<code class="id">{escape(str(entry.to_version))}</code></p>'
            ),
            Html("</article>"),
        ),
        "\n",
    )


def _remainder(number: int, noun: str, tail: str) -> Html:
    """One counted line for versions the list does not show, so the window never reads as all."""
    verb = "is" if number == 1 else "are"
    return Html(
        f'<p class="small muted">{escape(count(number, noun))} {tail.format(verb=verb)}</p>'
    )


def _versions(site: SiteInputs, limit: int) -> tuple[list[Html], list[Html]]:
    """The newest versions an amending act is named for, capped, and the lines counting the rest.

    Two kinds of version are pointed at rather than dropped: the ones past the cap, and the
    ones no amending act is named for, whose cards would be made by nothing the list could
    name. Both exclusions are stated with a count, because a silent one would make this window
    read as the whole record. They are returned apart from the list because the stat strip
    sits between the two.
    """
    recent = site.recent
    lines = [Html("<h2>Latest versions</h2>")]
    if not recent:
        where = _QUIET[0] if site.configured else _QUIET[1]
        lines.append(Html(f'<p class="none">{escape(where)} {escape(_QUIET_TAIL)}</p>'))
        return lines, []
    amendments = [(act, entry) for act, entry in recent if not unattributed(entry)]
    unnamed = len(recent) - len(amendments)
    if not amendments:
        lines.append(
            Html(f'<p class="none">{escape(count(unnamed, "version"))} {escape(_ALL_UNNAMED)}</p>')
        )
        return lines, []
    shown = amendments[:limit]
    lines.append(tags_help(up(_DEPTH), LIST_HELP_WORDS))
    lines.extend(
        _card(act, entry, by_words(amenders(site.amending, entry))) for act, entry in shown
    )
    rest: list[Html] = []
    older = len(amendments) - len(shown)
    if older:
        rest.append(_remainder(older, "older version", "{verb} on the act pages."))
    if unnamed:
        rest.append(
            _remainder(
                unnamed,
                "version",
                "naming no amending act {verb} on the act pages, not in this list.",
            )
        )
    return lines, rest


def _strip(site: SiteInputs) -> Html:
    """The measured claim, carrying what it is not, and the link to the section on the rest.

    The qualification is in the same sentence as the number rather than behind the link. A
    figure quoted bare on the busiest page of the site and explained one click away is a figure
    most readers meet without its limitation, and the limitation here is the whole difference
    between finding the right provisions and describing them well. The figure is also set large
    beside the sentence, hidden from assistive technology there, because the sentence already
    reads it out.

    A figure the report does not carry is said to be absent, never rendered as a zero and never
    quietly omitted: the strip is there either way.
    """
    pair = site.run.metrics.localisation
    link = Html(
        f'<a class="go" href="{up(_DEPTH)}methodology/#measured">Measured, not asserted</a>'
    )
    if pair is None:
        return Html(
            f'<aside class="stat"><span>No localisation figure is recorded in the report this '
            f"page was built from, so none is claimed here. {link}</span></aside>"
        )
    figure = f"{pair.micro_f1:.3f}"
    return Html(
        f'<aside class="stat"><strong aria-hidden="true">{figure}</strong><span>Finding '
        f"<em>which</em> provisions an amendment touched scores micro-F1 {figure} over "
        f"{count(pair.cases, 'transition')}, against labels the legislation publishes about "
        f"itself. It is not a measure of whether any explanation is good. {link}</span></aside>"
    )


def render_home(site: SiteInputs, *, limit: int = 20) -> Html:
    """The site's index page. Deterministic: same inputs, same bytes, no clock, no network.

    The pitch is computed once and reaches the reader, the description meta and the structured
    data as one sentence. The `WebSite` block needs the absolute base to name the site by its
    address, so a build without one carries no block rather than an incomplete one.
    """
    listed, rest = _versions(site, limit)
    body = join((*_hero(site), *listed, _strip(site), *rest), "\n")
    description = _pitch(site)
    return page(
        title="emendrix — provision-level changelogs for EU regulations",
        description=description,
        body=body,
        path=_PATH,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
        structured=website_json_ld(site, description=description) if site.site_url else None,
    )
