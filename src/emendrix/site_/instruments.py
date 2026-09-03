"""The amending instrument read the other way round: which watched acts it moved, and when.

`site_.amending` answers "what made this event?"; this module answers the reader's other
question, "what else did that instrument do?". It is the same committed attribution inverted,
nothing more: an act appears under an instrument because a change of one of its events names
that instrument, and the order is the order the site already publishes events in.

It is a module of its own for two reasons. `amending.py` deliberately does not know what
`SiteInputs` is, which is what keeps `inputs.py` free to import from it, and the inversion is
read by the builder, the sitemap, the search index and three pages alike, so it cannot live in
any one of them.

Nothing here re-derives an order. `site.recent` is already every event of every watched act,
newest first by `sort_date`, so walking it once puts each instrument's events in that same
order and puts the instruments themselves in the order of their newest event. A `dict` keeps
insertion order, which is what makes that true of the mapping as a whole.

An instrument with no page is a real state and a common one: the watchlist may declare a short
name for an instrument no committed event names, and an event of an act nobody watches names
instruments the site never shows. Only what this mapping holds gets a page, which is why the
builder, the sitemap and the search index all read it rather than `SiteInputs.amending`.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amending_keys
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.urls import amendment_href

__all__ = ["Amended", "amended_by"]

Amended = tuple[tuple[ActSite, ChangelogEntry], ...]
"""One instrument's work: every `(act, event)` pair a change of that event attributes to it."""


def amended_by(site: SiteInputs) -> dict[str, Amended]:
    """Every amending instrument a committed event names, to the events it made, newest first.

    Keyed by the instrument's own key, in the order of each one's newest event, so a caller
    that wants the roster order has it without sorting anything a second time. A pair appears
    once per instrument however many of the event's changes name it, `amending_keys` having
    already reduced one event's mentions to a set in document order.

    The path each key would be written to is checked here rather than left to the builder's
    file table, where two keys slugging alike would silently write one page and list two.
    """
    found: dict[str, Amended] = {}
    paths: dict[str, str] = {}
    for act, entry in site.recent:
        for key in amending_keys(entry):
            path = amendment_href(key)
            if paths.setdefault(path, key) != key:
                raise ValueError(
                    f"amending acts {paths[path]} and {key} share the URL path {path!r}"
                )
            found[key] = (*found.get(key, ()), (act, entry))
    return found
