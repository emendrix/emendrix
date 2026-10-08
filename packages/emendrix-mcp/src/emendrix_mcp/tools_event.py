"""One act, one provision's history, one event in full, and the disputes grouped by reason.

An event is answered from its index row and its payload's `corroboration`, both as stored: the
counts are the payload's own, and the units only one signal names are listed by name, never
as changes. The disputed rows are grouped by the `dispute_reason` code the index stores, each
group carrying the sentence the site prints beside that code.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.models import EventRow
from emendrix_mcp.payload import Corroboration
from emendrix_mcp.reads import Unavailable
from emendrix_mcp.reasons import REASON_SENTENCES
from emendrix_mcp.record import Record
from emendrix_mcp.tools import ChangeRow, Links, Window, reason_sentence, rows_of, window

__all__ = [
    "ActDetail",
    "DisputeGroup",
    "DisputesResult",
    "EventDetail",
    "EventResult",
    "EventView",
    "HistoryResult",
    "describe_act",
    "get_event",
    "list_disputed",
    "provision_history",
]

_FROZEN = ConfigDict(frozen=True)

DISPUTED_LIMIT_MAX: Final = 2000

_TOP_LEVEL: Final = (
    "History is filed by top-level provision (`AR 5`, `AN I`), so a sub-provision or a "
    "location the index does not name returns nothing here."
)


class EventView(BaseModel):
    """One event's index row as stored, with its page."""

    model_config = _FROZEN

    event: EventRow = Field(
        description="The act index's event row as stored: versions, dates, `path`, `sha256`, "
        "counts, repairs, `metadata_only_units` and `instruction_only_units`."
    )
    url: str | None = Field(description="The event's page from the catalogue; null if unknown.")
    url_unavailable: str | None = Field(description="Why `url` is null; null when it is given.")

    @classmethod
    def of(cls, event: EventRow, links: Links) -> EventView:
        url, why = links.event(event)
        return cls(event=event, url=url, url_unavailable=why)


class ActDetail(BaseModel):
    """One act's events newest first, the provisions it touched, and its window."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    corpus: str | None = Field(description="The act's corpus namespace; null if unreadable.")
    key: str | None = Field(description="The act's key; null if unreadable.")
    title: str | None = Field(description="The act index's title for the act.")
    index: str | None = Field(description="The act index's path in the changelogs repository.")
    index_sha256: str | None = Field(description="That file's hash, as the root index states.")
    window: Window | None = Field(description="What the record covers for the act.")
    events: tuple[EventView, ...] = Field(description="Every event, newest first.")
    provisions: tuple[str, ...] = Field(description="Every touched top-level location.")


def _no_act(reason: str) -> ActDetail:
    return ActDetail(
        unavailable=(reason,),
        corpus=None,
        key=None,
        title=None,
        index=None,
        index_sha256=None,
        window=None,
        events=(),
        provisions=(),
    )


def describe_act(record: Record, act: str) -> ActDetail:
    """One act as its indexes state it."""
    row = record.act_row(act)
    if isinstance(row, Unavailable):
        return _no_act(row.reason)
    index = record.act(act)
    if isinstance(index, Unavailable):
        return _no_act(index.reason)
    links = Links(record, index.corpus, index.key)
    return ActDetail(
        unavailable=(),
        corpus=index.corpus,
        key=index.key,
        title=index.title,
        index=row.index,
        index_sha256=row.index_sha256,
        window=window(row, index),
        events=tuple(EventView.of(event, links) for event in index.events),
        provisions=tuple(index.provisions),
    )


class EventDetail(BaseModel):
    """One event: its index row, its payload's corroboration, and its rows."""

    model_config = _FROZEN

    view: EventView = Field(description="The event's index row as stored, with its page.")
    sha256: str | None = Field(description="Hex sha256 of the payload bytes read now.")
    matches_index: bool | None = Field(
        description="False when the payload's bytes differ from what the index states: the "
        "repository is being rewritten. Null when the payload could not be read."
    )
    corroboration: Corroboration | None = Field(
        description="The payload's corroboration as stored: each signal's units, the pairwise "
        "agreements, the disagreements and the units only one signal names; null when the "
        "payload records none or could not be read."
    )
    rows: tuple[ChangeRow, ...] = Field(description="The event's index rows.")


class EventResult(BaseModel):
    """What `get_event` returns."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    event: EventDetail | None = Field(description="The event; null when it could not be read.")


def get_event(record: Record, act: str, version: str) -> EventResult:
    """The event of `act` that produced `version`, named by version or by entry key."""
    index = record.act(act)
    if isinstance(index, Unavailable):
        return EventResult(unavailable=(index.reason,), event=None)
    event = Record.event(index, version)
    if isinstance(event, Unavailable):
        return EventResult(unavailable=(event.reason,), event=None)
    links = Links(record, index.corpus, index.key)
    view = EventView.of(event, links)
    rows = tuple(row for row in rows_of(index, links) if row.event.to_version == event.to_version)
    read = record.payload(event.path, event.sha256)
    if isinstance(read, Unavailable):
        unread = EventDetail(
            view=view, sha256=None, matches_index=None, corroboration=None, rows=rows
        )
        return EventResult(unavailable=(read.reason,), event=unread)
    detail = EventDetail(
        view=view,
        sha256=read.sha256,
        matches_index=read.matches_index,
        corroboration=read.payload.corroboration,
        rows=rows,
    )
    return EventResult(unavailable=(), event=detail)


class DisputeGroup(BaseModel):
    """The disputed rows that share one `dispute_reason` code."""

    model_config = _FROZEN

    reason: str | None = Field(description="The stored `dispute_reason` code.")
    sentence: str | None = Field(description="What that code means, as the site prints it.")
    rows: tuple[ChangeRow, ...] = Field(description="The rows, by act, newest event first.")


class DisputesResult(BaseModel):
    """Disputed rows grouped by reason."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    groups: tuple[DisputeGroup, ...] = Field(description="One group per reason code, by code.")
    omitted: int = Field(ge=0, description="Disputed rows left out because of `limit`.")


def list_disputed(
    record: Record, act: str | None = None, reason: str | None = None, limit: int = 200
) -> DisputesResult:
    """Every disputed row, optionally of one act or one reason, grouped by `dispute_reason`."""
    if reason is not None and reason not in REASON_SENTENCES:
        codes = ", ".join(sorted(REASON_SENTENCES))
        return DisputesResult(
            unavailable=(f"no dispute_reason {reason!r} is published; the codes are {codes}",),
            groups=(),
            omitted=0,
        )
    names: list[str]
    if act is not None:
        names = [act]
    else:
        root = record.root()
        if isinstance(root, Unavailable):
            return DisputesResult(unavailable=(root.reason,), groups=(), omitted=0)
        names = [f"{row.corpus}/{row.key}" for row in root.acts]
    unavailable: list[str] = []
    disputed: list[ChangeRow] = []
    for name in names:
        index = record.act(name)
        if isinstance(index, Unavailable):
            unavailable.append(index.reason)
            continue
        disputed.extend(
            row
            for row in rows_of(index, Links(record, index.corpus, index.key))
            if row.row.disputed and (reason is None or row.row.dispute_reason == reason)
        )
    size = min(max(limit, 1), DISPUTED_LIMIT_MAX)
    kept = disputed[:size]
    codes_seen = sorted({row.row.dispute_reason for row in kept}, key=lambda code: code or "")
    groups = tuple(
        DisputeGroup(
            reason=code,
            sentence=reason_sentence(code),
            rows=tuple(row for row in kept if row.row.dispute_reason == code),
        )
        for code in codes_seen
    )
    return DisputesResult(
        unavailable=tuple(unavailable), groups=groups, omitted=max(len(disputed) - size, 0)
    )


class HistoryResult(BaseModel):
    """Every row of one provision, newest first, and the window they are complete for."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    location: str = Field(description="The canonical top-level location asked for.")
    window: Window | None = Field(description="What the record covers; null if unreadable.")
    rows: tuple[ChangeRow, ...] = Field(description="The provision's rows, newest first.")
    sentence: str = Field(description="What the rows, or their absence, mean, in words.")


def _no_history(act: str, location: str, reason: str) -> HistoryResult:
    return HistoryResult(
        unavailable=(reason,),
        location=location,
        window=None,
        rows=(),
        sentence=f"Nothing could be read for {act!r}, so nothing is said about {location}.",
    )


def provision_history(record: Record, act: str, location: str) -> HistoryResult:
    """Every recorded change to one top-level provision of one act, newest first."""
    act_row = record.act_row(act)
    if isinstance(act_row, Unavailable):
        return _no_history(act, location, act_row.reason)
    index = record.act(act)
    if isinstance(index, Unavailable):
        return _no_history(act, location, index.reason)
    links = Links(record, index.corpus, index.key)
    rows = tuple(row for row in rows_of(index, links) if row.location == location)
    span = window(act_row, index)
    name = f"{location} of {index.corpus}/{index.key}"
    sentence = (
        f"These are the recorded changes to {name}, newest first, complete for the window."
        if rows
        else f"No recorded change to {name} in the window: {span.sentence}"
    )
    if location not in index.provisions:
        sentence += f" {_TOP_LEVEL}"
    return HistoryResult(
        unavailable=(), location=location, window=span, rows=rows, sentence=sentence
    )
