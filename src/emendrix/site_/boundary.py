"""The one module under `site_/` that knows which corpus published a document.

Every function here turns an identifier the changelog repository recorded into a label or a
URL, at the command-line boundary, so that everything below it is a pure function of plain
strings. Which act has an EUR-Lex address is a corpus capability, not something the pages may
know, so the URL is resolved here from the newest version each act has been consolidated to
and handed down as a plain string, the same way the pipeline's root hands down an adapter.

The date each consolidated version speaks as of is read here for the same reason: only this
module may read a version tag, and that date is what every newest-first list on the site sorts
by. So is the official number of an amending act, `Regulation (EU) 2026/1744`: it is a reading
of a CELEX by the convention of its year, and the pages are handed the words and the address
rather than the identifier grammar. So are the address of each watched act as it was published
and the word for what kind of act each one is, which are the two facts a page about an act
nothing has happened to is otherwise built without.

The seam against `cli.py` is that this module reads identifiers and composes nothing: it is
handed the entries and the watchlist that module resolved, and returns the labels and URLs it
passes on. Nothing here reads a clock, a file or a network.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import ActId, VersionId
from emendrix.eu.identifiers import Celex, ConsolidatedId, parse_version_id
from emendrix.eu.links import document_url
from emendrix.output import ChangelogEntry
from emendrix.output.json_out import slug
from emendrix.site_.amending import mentioned_keys
from emendrix.site_.clocks import VersionDates, sort_date
from emendrix.watch.config import Watchlist

__all__ = ["amending", "eurlex_urls", "kinds", "published_urls", "version_dates"]

_EU = "eu"
"""The one corpus with a published document URL scheme. Others simply get no link."""

_KINDS = {"R": "Regulation", "L": "Directive", "D": "Decision"}
"""What the site calls each CELEX descriptor it has words for. One outside this table keeps its
letter, an identifier a reader can look up, rather than a guess at what the act is; the words go
down to the pages as labels, nothing below here knowing a descriptor was read at all."""


def version_dates(entries: tuple[ChangelogEntry, ...]) -> VersionDates:
    """The date each EU consolidated version speaks as of, read off its own tag.

    `sort_date` orders every newest-first list by these. An entry outside this corpus, one
    whose version is the OJ act itself rather than a consolidation, or one whose tag does
    not parse gets no entry here and falls back to `event_dated`: an unreadable tag is a
    gap to fall back past, not a reason to fail a build over committed data.
    """
    dated: dict[tuple[ActId, VersionId], date] = {}
    for entry in entries:
        if entry.act.corpus != _EU:
            continue
        try:
            parsed = parse_version_id(entry.to_version)
        except ValueError:
            continue
        if isinstance(parsed, ConsolidatedId):
            dated[(entry.act, entry.to_version)] = parsed.version_date
    return dated


def eurlex_urls(entries: tuple[ChangelogEntry, ...], dates: VersionDates) -> dict[str, str]:
    """One EUR-Lex document URL per EU act, for the version `sort_date` ranks newest.

    Keyed by the act's URL slug, which is what `collect_site` matches on, and ranked by the
    same clock every newest-first list uses, so the link an act shows and the event a reader
    sees as newest cannot name two different versions. An act with no committed event yet
    gets no entry here and no link, because the newest consolidation is exactly the thing
    nothing has recorded for it.
    """
    newest: dict[str, tuple[tuple[str, str], str]] = {}
    for entry in entries:
        if entry.act.corpus != _EU:
            continue
        key = slug(entry.act.key)
        ranked = (sort_date(entry, dates).isoformat(), str(entry.to_version))
        if key not in newest or ranked > newest[key][0]:
            newest[key] = (ranked, document_url(entry.to_version))
    return {key: url for key, (_, url) in newest.items()}


def published_urls(watchlist: Watchlist | None) -> dict[str, str]:
    """The EUR-Lex address of each watched act as it was published, keyed by its URL slug.

    A different document from `eurlex_urls`, which names the newest version an act has been
    consolidated to and so can only answer for an act some event recorded. This one is a reading
    of the act's own identifier, known for every watched act including the quiet ones, and the
    one document a page about an act nothing has happened to can send a reader to. Without a
    watchlist there is no declared roster to read an identifier off.
    """
    if watchlist is None:
        return {}
    return {
        slug(watched.act.key): document_url(Celex.parse(watched.celex).version)
        for watched in watchlist.acts
    }


def kinds(watchlist: Watchlist | None) -> tuple[tuple[str, int], ...]:
    """How many acts of each kind the watchlist declares, the largest group first.

    Read off the descriptor of each watched CELEX, a reading only this module may do, and
    handed down as words and counts. The acts index prints them and says what the roster is made
    of; with no watchlist to count there is nothing to say.
    """
    if watchlist is None:
        return ()
    counted: dict[str, int] = {}
    for watched in watchlist.acts:
        descriptor = Celex.parse(watched.celex).descriptor
        name = _KINDS.get(descriptor, descriptor)
        counted[name] = counted.get(name, 0) + 1
    return tuple(sorted(counted.items(), key=lambda item: (-item[1], item[0])))


def amending(entries: tuple[ChangelogEntry, ...]) -> tuple[dict[str, str], dict[str, str]]:
    """The official number and the EUR-Lex address of every amending act the entries name.

    Both are readings of a CELEX, so both are rendered here and handed to `collect_site` as
    plain strings: naming an act's number is corpus vocabulary, and no page may hold any. A key
    that does not parse gets neither and is shown as itself, the same fallback `version_dates`
    follows for a version tag it cannot read; an entry outside this corpus is skipped whole,
    since its keys are not CELEXes and would not be readable as one.

    The number can be empty for a CELEX whose descriptor names neither a regulation nor a
    directive. That is a stated answer rather than a gap: the address still resolves, and the
    key is what the page shows.
    """
    numbers: dict[str, str] = {}
    urls: dict[str, str] = {}
    for key in mentioned_keys(entry for entry in entries if entry.act.corpus == _EU):
        try:
            celex = Celex.parse(key)
        except ValueError:
            continue
        numbers[key] = celex.official_number
        urls[key] = document_url(celex.version)
    return numbers, urls
