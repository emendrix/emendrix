"""How one event is named, once, for every surface that has to name it.

An event's `<title>`, the sentence a feed reader shows in its list, and nothing else: the count,
the instrument that made it and the date with its clock. Two surfaces state it, the event page's
head and the Atom entry, and they used to state it differently, which meant a subscriber and a
search result could disagree about what an event was. So the words are composed here and both
read them.

It is a module of its own rather than a helper on either surface because the two already point
at each other: `pages/event.py` asks `feeds` where an act's feed lives, so a title living there
and read by `feeds` would close the loop. One small module both may read is the smaller answer.

Nothing here escapes: a `<title>` is escaped by `chrome.page` and a feed entry by `feeds`, and a
string that arrives pre-escaped would be escaped twice.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amenders, by_words
from emendrix.site_.clocks import event_date
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import count
from emendrix.site_.untouched import UNTOUCHED_CARD, untouched

__all__ = ["SUFFIX", "event_title", "event_words"]

SUFFIX = " — emendrix"
"""What a page's `<title>` ends with and a feed entry's does not: inside a feed already titled
`emendrix — <act>`, the site's own name on every entry is the one word a reader never needs."""


def event_words(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> str:
    """`AI Act: 45 provisions changed by Digital Omnibus on AI, in force 2026-07-27`.

    The short label leads, not the headline: the count, the instrument and the date are the
    news, and a long form in front of them pushes all three past where a result snippet cuts.
    The clock is named by the one helper every dated line on the site reads, so a detection
    date can never be set as an in-force date. An event that touched nothing is said in words,
    because "0 provisions changed" reads as a counter that failed. An event naming no amending
    act carries no clause at all, which is the same sentence this has always been.
    """
    touched = count(entry.counts.touched, "provision")
    counted = UNTOUCHED_CARD if untouched(entry) else f"{touched} changed"
    named = by_words(amenders(site.amending, entry))
    return f"{act.label}: {counted}{' ' + named if named else ''}, {event_date(entry).words}"


def event_title(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> str:
    """The same words as the page's `<title>`, which is the feed entry's title plus the suffix."""
    return f"{event_words(site, act, entry)}{SUFFIX}"
