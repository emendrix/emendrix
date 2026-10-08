"""The listing tools: the acts, one act's provisions by name, and the changes since a date.

Each reads the indexes and, for headings only, the payloads; none searches a provision's text.
A filter selects stored rows and a sort orders them by stored dates and keys; nothing ranks,
merges or classifies. An act named in a request that the record does not hold is reported in
`unavailable` in words, and the rest of the answer still stands.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.models import ActIndex, ActRow, EventRow
from emendrix_mcp.reads import Unavailable
from emendrix_mcp.record import Record
from emendrix_mcp.tools import ChangeRow, Links, rows_of

__all__ = [
    "ActSummary",
    "ActsResult",
    "Basis",
    "ChangesResult",
    "ProvisionMatch",
    "ProvisionsResult",
    "changes_since",
    "find_provisions",
    "list_acts",
]

_FROZEN = ConfigDict(frozen=True)

Basis = Literal["updated_on", "detected_on", "in_force"]

LIMIT_MAX: Final = 500


def _fold(text: str) -> str:
    return " ".join(text.casefold().split())


def _matches(query: str, *names: str) -> bool:
    wanted = _fold(query)
    return any(wanted in _fold(name) for name in names)


class ActSummary(BaseModel):
    """One act: its root index row as stored, and the catalogue's names and page for it."""

    model_config = _FROZEN

    row: ActRow = Field(
        description="The root index row as stored: title, counts, newest version, `updated_on`, "
        "and the act index's `index` path and `index_sha256`."
    )
    label: str | None = Field(description="The catalogue's label; null without a catalogue.")
    long_name: str | None = Field(description="The catalogue's long form; null without one.")
    aliases: tuple[str, ...] = Field(description="The catalogue's other names for the act.")
    domain: str | None = Field(description="The catalogue's sector; null without a catalogue.")
    url: str | None = Field(description="The act's page from the catalogue; null if unknown.")
    url_unavailable: str | None = Field(description="Why `url` is null; null when it is given.")
    feed: str | None = Field(description="The act's Atom feed from the catalogue, when named.")


class ActsResult(BaseModel):
    """The acts the record holds that match the request."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    acts: tuple[ActSummary, ...] = Field(description="Matching acts, sorted by corpus and key.")


def _summary(record: Record, row: ActRow) -> ActSummary:
    links = Links(record, row.corpus, row.key)
    listing = links.listing
    url, why = links.act()
    return ActSummary(
        row=row,
        label=None if listing is None else listing.label,
        long_name=None if listing is None else listing.long_name,
        aliases=() if listing is None else listing.aliases,
        domain=None if listing is None else listing.domain,
        url=url,
        url_unavailable=why,
        feed=None if listing is None else listing.feed,
    )


def list_acts(record: Record, query: str | None = None, domain: str | None = None) -> ActsResult:
    """Every act the record holds, filtered by a name and by the catalogue's sector."""
    root = record.root()
    if isinstance(root, Unavailable):
        return ActsResult(unavailable=(root.reason,), acts=())
    acts = [_summary(record, row) for row in root.acts]
    unavailable: tuple[str, ...] = ()
    if query:
        acts = [
            act
            for act in acts
            if _matches(
                query,
                act.row.key,
                f"{act.row.corpus}/{act.row.key}",
                act.row.title,
                act.label or "",
                act.long_name or "",
                *act.aliases,
            )
        ]
    if domain:
        unavailable = tuple(
            f"{act.row.corpus}/{act.row.key} has no sector here: {act.url_unavailable}"
            for act in acts
            if act.domain is None
        )
        acts = [
            act for act in acts if act.domain is not None and _fold(act.domain) == _fold(domain)
        ]
    return ActsResult(unavailable=unavailable, acts=tuple(acts))


class ProvisionMatch(BaseModel):
    """One touched provision whose name matched, with its newest row."""

    model_config = _FROZEN

    location: str = Field(description="The canonical top-level location, as the index files it.")
    heading: str | None = Field(description="The newest heading a payload stores for it, if any.")
    heading_version: str | None = Field(description="The version that heading was read from.")
    newest: ChangeRow = Field(description="The provision's newest row in the act index.")


class ProvisionsResult(BaseModel):
    """The touched provisions of one act whose canonical string or heading matched."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    provisions: tuple[ProvisionMatch, ...] = Field(description="Matches, by canonical location.")


def _headings(record: Record, index: ActIndex) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """The newest stored heading of each top-level location, with the version it came from."""
    headings: dict[str, tuple[str, str]] = {}
    unreadable: list[str] = []
    for event in index.events:
        read = record.payload(event.path, event.sha256)
        if isinstance(read, Unavailable):
            unreadable.append(read.reason)
            continue
        for emitted in read.payload.changes:
            change = emitted.change
            location = change.provision.location
            if change.heading and location in index.provisions and location not in headings:
                headings[location] = (change.heading, event.to_version)
    return headings, unreadable


def find_provisions(record: Record, act: str, query: str) -> ProvisionsResult:
    """Touched provisions of `act` whose canonical string or stored heading contains `query`."""
    index = record.act(act)
    if isinstance(index, Unavailable):
        return ProvisionsResult(unavailable=(index.reason,), provisions=())
    links = Links(record, index.corpus, index.key)
    headings, unreadable = _headings(record, index)
    events = {event.to_version: event for event in index.events}
    matches: list[ProvisionMatch] = []
    for location, filed in index.provisions.items():
        heading, version = headings.get(location, (None, None))
        if not filed or not _matches(query, location, heading or ""):
            continue
        newest = filed[0]
        matches.append(
            ProvisionMatch(
                location=location,
                heading=heading,
                heading_version=version,
                newest=ChangeRow.of(index, events[newest.version], location, newest, links),
            )
        )
    return ProvisionsResult(unavailable=tuple(unreadable), provisions=tuple(matches))


class ChangesResult(BaseModel):
    """Index rows on or after a date, newest first."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    basis: Basis = Field(description="Which stored date was compared with `since`.")
    since: date = Field(description="The earliest date a row's basis date may carry.")
    rows: tuple[ChangeRow, ...] = Field(description="Matching rows, newest first.")
    omitted: int = Field(ge=0, description="Matching rows left out because of `limit`.")


def _basis(basis: Basis, event: EventRow, row: ChangeRow) -> date | None:
    if basis == "in_force":
        return row.row.in_force
    return event.detected_on if basis == "detected_on" else event.updated_on


def changes_since(
    record: Record,
    since: date,
    acts: tuple[str, ...] | None = None,
    basis: Basis = "updated_on",
    include_disputed: bool = True,
    limit: int = 50,
) -> ChangesResult:
    """Every row whose `basis` date is on or after `since`, newest first, at most `limit`."""
    names: tuple[str, ...]
    unavailable: list[str] = []
    if acts is None:
        root = record.root()
        if isinstance(root, Unavailable):
            return ChangesResult(
                unavailable=(root.reason,), basis=basis, since=since, rows=(), omitted=0
            )
        names = tuple(f"{row.corpus}/{row.key}" for row in root.acts)
    else:
        names = acts
    picked: list[tuple[tuple[int, str, str, int], ChangeRow]] = []
    for name in names:
        index = record.act(name)
        if isinstance(index, Unavailable):
            unavailable.append(index.reason)
            continue
        positions = {event.to_version: n for n, event in enumerate(index.events)}
        events = {event.to_version: event for event in index.events}
        for row in rows_of(index, Links(record, index.corpus, index.key)):
            when = _basis(basis, events[row.event.to_version], row)
            if when is None or when < since or (row.row.disputed and not include_disputed):
                continue
            order = (-when.toordinal(), index.corpus, index.key, positions[row.event.to_version])
            picked.append((order, row))
    picked.sort(key=lambda pair: pair[0])
    size = min(max(limit, 1), LIMIT_MAX)
    return ChangesResult(
        unavailable=tuple(unavailable),
        basis=basis,
        since=since,
        rows=tuple(row for _, row in picked[:size]),
        omitted=max(len(picked) - size, 0),
    )
