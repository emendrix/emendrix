"""Every date the watched texts name that has not arrived yet, across all of them at once.

The rest of the site looks back: an act's timeline, an event's changes, an instrument's reach.
This is the one page built out of what the corpus says about days that have not come, and it is
still a page about documents rather than about the law.

**What the data holds and what it does not.** `Change.dates_added` and `Change.dates_removed`
are a set difference over the source's own `<DATE ISO>` markup in one provision's subtree: the
new text names this date, the old one did not, or the other way round. Nothing in that says what
the sentence around the date does. The corpus carries restriction-table cut-offs, one half of a
range written "between 1 January and 31 December", and prohibition dates in a column of a
mercury annex, all in the same field. *A date was added to this provision's text* is strictly
weaker than *this provision applies from that date*, and only the weaker claim is in the data.

**So the page puts the two on screen as two blocks.** The stronger claim exists in exactly one
field, `Change.applies_from`, read deterministically from a date change in the act's own
application article. Those rows get their own block above the list; the list below them is
mentions, gathered by sector and then by year in `pages.dates_list`, and every count on it
counts mentions. Two headings draw the line for a reader who
skips the lede. `tests/site_/test_dates_page.py` holds the vocabulary that keeps it there.

**One class of row would otherwise be wrong rather than merely thin.** A date one amendment put
into a provision and a later one took back out reads, in a naive list built from `dates_added`,
as if the text still named it. `history.cross_act_mentions` carries the later change and the row
says what it did, in the register of the record: it removed the date from that provision's text.

Most committed changes carry no machine-readable date at all, so the panel under the list says
how small a corner of the corpus this is, with the build date and why the applies-from date could
not be read elsewhere. The content comes first and the diagnostics after it; the lede that says
what the list is and is not stays first of all, because it is the line the page may not cross.
Every number in the panel is counted at build time by `site_.date_coverage`; none is typed here.

"Ahead" is `mention.on > site.generated_on`, and `generated_on` arrives from the command line
like every other date in this project. There is no clock in this module and no countdown on the
page: a countdown is the strongest available framing of a date as something owed, and it would
read a clock in the render path as well. Two builds of one corpus on one date are byte-identical;
a build made on another day divides the list at another date, which the page says out loud.

No cross-act list of what has passed: complete, it is an order of magnitude more rows than any
page the site serves, for content every act page already holds in full. The recent window is
folded here, the remainder is counted rather than dropped, and the route to it is a link.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.chrome import page
from emendrix.site_.date_coverage import DateCoverage, applies_ahead, coverage
from emendrix.site_.entries import counted, share
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.history import (
    IS_NOT_A_SCHEDULE,
    CrossActMention,
    ahead,
    cross_act_mentions,
    passed_within,
)
from emendrix.site_.identity import page_masthead
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.pages.dates_list import (
    RANGE_ANCHOR,
    by_sector,
    event_link,
    row,
    sector_nav,
)
from emendrix.site_.urls import act_href, dates_href, depth_of, provision_href, up

__all__ = ["render_dates"]

_PATH: Final = dates_href()
_DEPTH: Final = depth_of(_PATH)
"""One directory down from the site root, so every internal link on it climbs once."""

RECENT_DAYS: Final = 90
"""How far back the folded window of dates that have passed reaches.

About a quarter, which is the shortest window in which "has that one gone by yet" is still a
live question, and the same order of magnitude as the fold `act_dates.FOLD_ABOVE` sets for one
screen. Everything earlier is counted and routed to the act pages, which carry it in full.
"""


def _applies_block(site: SiteInputs, found: DateCoverage, root: str) -> list[Html]:
    """Clock 2's own answers, above the list, with the caption that says how few there are.

    Why the rest could not be read is coverage rather than content, so it is in the panel.

    Rendered even when none of them is ahead. Deleting the block when it is empty would remove
    the page's own demonstration of the distinction it exists to draw, precisely on the build
    where the list below stands alone and is most likely to be read as the stronger claim.
    """
    on = site.generated_on.isoformat()
    rows = [
        Html(
            f'<li><span class="on">{escape(applies.isoformat())}</span> · '
            f'<a href="{escape(root + provision_href(act.slug, step.change.location.canonical))}">'
            f"{escape(step.change.location.human)}</a> of "
            f'<a href="{escape(root + act_href(act.slug))}">{escape(act.label)}</a> '
            f"applies from this date · "
            f"{event_link(step.entry, step.anchor, act, root)}</li>"
        )
        for act, step, applies in applies_ahead(site)
    ]
    listing = (
        [Html("<ul>"), *rows, Html("</ul>")]
        if rows
        else [
            Html(
                f'<p class="none">No change of the committed corpus states an applies-from date '
                f"later than {escape(on)}.</p>"
            )
        ]
    )
    caption = (
        f"Read deterministically from a date change in the act's own application article, which "
        f"is the only place this project reads such a date. It resolves for "
        f"{found.applies_dated:,} of {counted(found.changes, 'committed change')}, with "
        f"{found.dated_ahead:,} of those dates falling after {on}. Everywhere else the answer is "
        f"stated rather than guessed: {counted(found.applies_unchanged, 'change')} saying the "
        f"date did not move, {counted(found.applies_unknown, 'change')} saying none could be "
        f"read. It is never inferred, and no other field on this page carries this claim."
    )
    return [
        Html('<section class="dates-named">'),
        Html("<h2>Dates a change applies from</h2>"),
        *listing,
        Html(f'<p class="small muted">{escape(caption)}</p>'),
        Html("</section>"),
    ]


def _reasons(found: DateCoverage) -> list[Html]:
    """Why no applies-from date could be read, in the corpus's own words, one line per reason.

    A stated non-answer is a value that reaches the output, so it is published rather than
    summed into one silence.
    """
    if not found.unknown_reasons:
        return []
    return [
        Html('<ul class="caveats">'),
        *(
            Html(f"<li>{escape(f'{number:,} · {reason}')}</li>")
            for reason, number in found.unknown_reasons
        ),
        Html("</ul>"),
    ]


def _panel(site: SiteInputs, found: DateCoverage) -> list[Html]:
    """What the forward list is a view of, and what it leaves out. Every number computed.

    It follows the list rather than opening the page: the lede above already says what the list
    is, and the coverage below says how much of the corpus it could have held.
    """
    on = site.generated_on.isoformat()
    without = share(found.without_a_date, found.changes)
    opening = [
        f"{on} is the date this build was made for. It is printed at the foot of every page, "
        f"and a build made on another day divides this list at another date.",
        f"Of the {counted(found.changes, 'change')} this build renders, "
        f"{found.without_a_date:,}"
        + (f" ({without:.3f})" if without is not None else "")
        + f" moved no machine-readable date at all, so this page is a view of the "
        f"{found.with_a_date:,} that did.",
        f"The forward list holds {counted(found.mentions_ahead, 'mention')} dated after {on}, "
        f"from {found.acts_ahead} of the {counted(found.acts_with_events, 'act')} holding a "
        f"committed event, leaving {found.acts_with_nothing_ahead} with nothing ahead. It marks "
        f"{counted(found.superseded_ahead, 'mention')} whose date a later amendment took back "
        f"out of the same provision.",
        f"It leaves out {counted(found.mentions_behind, 'mention')} dated on or before {on}.",
    ]
    closing = [
        f"No applies-from date could be read for "
        f"{counted(found.applies_unknown, 'change')}. This corpus also holds "
        f"{counted(found.textless, 'change')} with no text on either side, where there is "
        f"nothing to read a date out of at all, so part of that block describes the corpus's own "
        f"coverage rather than the second clock's reliability.",
        f"Across the {counted(found.events, 'event')} here, and beyond the opening event of each "
        f"act, the record has {counted(found.gaps, 'hole')} in it: an event reaching back to a "
        f"version no other event of its act produced. A date could have moved in a transition "
        f"this corpus does not hold.",
    ]
    lines = [
        Html("<h2>What this is a view of</h2>"),
        *(Html(f'<p class="small muted">{escape(one)}</p>') for one in opening),
    ]
    first, *rest = closing
    lines.extend((Html(f'<p class="small muted">{escape(first)}</p>'), *_reasons(found)))
    lines.extend(Html(f'<p class="small muted">{escape(one)}</p>') for one in rest)
    if found.earliest is not None and found.latest is not None:
        span = (
            f"The date markup produced readings from {found.earliest.isoformat()} to "
            f"{found.latest.isoformat()}. Both ends are shown as read: nothing here is clipped "
            f"to the range somebody thought a document ought to stay inside."
        )
        lines.append(Html(f'<p class="small muted" id="{RANGE_ANCHOR}">{escape(span)}</p>'))
    return lines


def _past(
    site: SiteInputs, mentions: tuple[CrossActMention, ...], found: DateCoverage, root: str
) -> list[Html]:
    """The recent window folded, and the remainder counted with the route to it.

    The complete cross-act list of what has passed is several times the weight of the largest
    page the site serves, for rows every act page already holds in full. So the window a reader
    might still be checking is on the page, and everything earlier is a number and a link.
    """
    on = site.generated_on.isoformat()
    recent = passed_within(mentions, site.generated_on, RECENT_DAYS)
    lines = [Html("<h2>Dates that have passed</h2>")]
    if recent:
        summary = f"{counted(len(recent), 'date')} in the {RECENT_DAYS} days before {on}"
        lines.extend(
            (
                Html('<section class="dates-named">'),
                Html(f"<details><summary>{escape(summary)}</summary>"),
                Html("<ul>"),
                *(row(one, root) for one in recent),
                Html("</ul>"),
                Html("</details>"),
                Html("</section>"),
            )
        )
    rest = found.mentions_behind - len(recent)
    counts = (
        f"Earlier than that: {counted(rest, 'further mention')}."
        if recent
        else f"No date the committed texts name falls in the {RECENT_DAYS} days before {on}. "
        f"Earlier than that: {counted(rest, 'mention')}."
    )
    lines.append(
        Html(
            f'<p class="small muted">{escape(counts)} Every act\'s own page carries its '
            f'complete list, under "Dates the amended text names": start at '
            f'<a href="{root}acts/">all watched acts</a>.</p>'
        )
    )
    return lines


def render_dates(site: SiteInputs) -> Html:
    """The cross-act list of dates ahead. Deterministic: same inputs and same build date, same
    bytes. No clock is read here; `generated_on` came in at the command line."""
    root = up(_DEPTH)
    on = site.generated_on.isoformat()
    mentions = cross_act_mentions(site)
    forward = ahead(mentions, site.generated_on)
    found = coverage(site, mentions)
    lede = (
        f"Every date an amendment added to or removed from a provision's text, as the parser "
        f"read it off the source's own date markup, that falls after {on}, with the provision "
        f"and the event that moved it. {IS_NOT_A_SCHEDULE}"
    )
    listing = (
        [sector_nav(forward), *by_sector(forward, root, site.generated_on)]
        if forward
        else [
            Html(f'<p class="none">No date the committed texts name falls after {escape(on)}.</p>')
        ]
    )
    body = join(
        (
            *page_masthead(
                "prose", "Across all watched acts", "Dates ahead in the amended texts", _PATH
            ),
            Html(f'<p class="lede">{escape(lede)}</p>'),
            *_applies_block(site, found, root),
            Html('<section class="dates-named">'),
            Html("<h2>Dates the amended texts name</h2>"),
            *listing,
            Html("</section>"),
            *_panel(site, found),
            *_past(site, mentions, found, root),
        ),
        "\n",
    )
    return page(
        title="Dates ahead — emendrix",
        description=(
            "Every date a committed amendment added to or removed from a watched act's text "
            "that has not arrived yet, nearest first, with the provision and the event."
        ),
        body=body,
        path=_PATH,
        chrome=site.chrome,
        section=_PATH,
        feeds=((feed_path(None), feed_title(None)),),
    )
