"""One change in full: its stored facts, its gated sentences and its verbatim sides, paged.

A side can run to megabytes, so each is cut at `max_chars` and the cut is marked in the text
itself, with the count of what was left out and the offset that continues it. The page is a
slice of the stored string and nothing else: no whitespace is touched, and the markers are the
only characters a page holds that the payload does not. Everything a reader needs to judge the
change without the text, `changed_within` and the cited sentences, is returned whole.

`disputed` and `dispute_reason` are the index row's: a payload written before the reason was
stored lacks it, and the row always carries it.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.models import ProvisionRow
from emendrix_mcp.payload import (
    ActRef,
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    Observations,
    Sentence,
)
from emendrix_mcp.reads import Unavailable
from emendrix_mcp.record import Record
from emendrix_mcp.tools import EventRef, Links, reason_sentence

__all__ = [
    "LEADING_MARKER",
    "MAX_CHARS_LIMIT",
    "TRUNCATION_MARKER",
    "ChangeDetail",
    "ChangeResult",
    "TextPage",
    "get_change",
    "page",
]

_FROZEN = ConfigDict(frozen=True)

TRUNCATION_MARKER: Final = "\n[… {omitted} characters omitted, continue with offset={next_offset}]"
"""Appended to a page that stops before the end of its side."""

LEADING_MARKER: Final = "[… {offset} characters before this page, from offset=0]\n"
"""Prepended to a page that starts after the beginning of its side."""

MAX_CHARS_LIMIT: Final = 50_000


class TextPage(BaseModel):
    """One page of one verbatim side: a slice of the stored text, with the cut marked."""

    model_config = _FROZEN

    text: str = Field(
        description="The stored text from `offset`, at most `max_chars` characters of it, with "
        "a marker before it when it starts past the beginning and after it when it stops "
        "before the end. The markers are the only characters not in the stored text."
    )
    offset: int = Field(ge=0, description="Where in the stored text this page starts.")
    returned_chars: int = Field(ge=0, description="Characters of stored text on this page.")
    total_chars: int = Field(ge=0, description="Characters in the whole stored side.")
    next_offset: int | None = Field(
        description="The offset that continues this side; null when this page reaches its end."
    )


def page(text: str, offset: int, max_chars: int) -> TextPage:
    """The page of `text` from `offset`, at most `max_chars` long, both clamped."""
    start = min(max(offset, 0), len(text))
    size = min(max(max_chars, 1), MAX_CHARS_LIMIT)
    end = min(start + size, len(text))
    body = text[start:end]
    if start:
        body = LEADING_MARKER.format(offset=start) + body
    more = end < len(text)
    if more:
        body += TRUNCATION_MARKER.format(omitted=len(text) - end, next_offset=end)
    return TextPage(
        text=body,
        offset=start,
        returned_chars=end - start,
        total_chars=len(text),
        next_offset=end if more else None,
    )


class ChangeDetail(BaseModel):
    """One change: where it comes from, what the index says of it, and what the payload holds."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    location: str = Field(description="The change's own canonical location, as stored.")
    occurrence: int = Field(ge=1, description="Which repeat of that location in the event.")
    event: EventRef = Field(description="The event, with the payload's path and indexed hash.")
    sha256: str = Field(description="Hex sha256 of the payload bytes read now.")
    matches_index: bool = Field(
        description="False when those bytes differ from what the index states: the repository "
        "is being rewritten while it is read."
    )
    row: ProvisionRow | None = Field(
        description="The act index's row for this change, the source of `disputed`, "
        "`dispute_reason` and the signal triple; null when the index files none."
    )
    reason_sentence: str | None = Field(description="What the row's `dispute_reason` means.")
    provision_url: str | None = Field(description="The provision's page from the catalogue.")
    provision_url_unavailable: str | None = Field(description="Why `provision_url` is null.")
    change_type: str = Field(description="The change's type as the structural diff named it.")
    version: str = Field(description="The version the stored provision reference points into.")
    heading: str | None = Field(description="The provision's stored heading, if any.")
    previous_location: str | None = Field(description="Its location before renumbering.")
    before: TextPage | None = Field(description="The verbatim text before; null if none.")
    after: TextPage | None = Field(description="The verbatim text after; null if none.")
    changed_within: tuple[str, ...] = Field(description="Sub-provisions that differ, whole.")
    signals: Observations = Field(description="The three signals with their stored detail.")
    in_force: date | None = Field(description="The change's in-force date, as stored.")
    applies_from: date | ApplicabilityUnknown | ApplicabilityUnchanged = Field(
        description="A date, or `unknown` with its reason (no date could be read "
        "deterministically, never that no date applies), or `unchanged`."
    )
    dates_added: tuple[date, ...] = Field(description="Dates the provision carries after only.")
    dates_removed: tuple[date, ...] = Field(description="Dates it carried before only.")
    amending_acts: tuple[ActRef, ...] = Field(description="Acts named as amending it.")
    outcome: str = Field(description="How the change left the citation gate.")
    sentences: tuple[Sentence, ...] = Field(
        description="The gated explanation, whole, each sentence with its citations' URLs."
    )
    applicability_note: Sentence | None = Field(description="The stored applicability prose.")
    unexplained: str = Field(description="Why there are no sentences, when there are none.")
    unexplained_kind: str = Field(description="The counted kind of that reason, or ''.")


class ChangeResult(BaseModel):
    """What `get_change` returns."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    change: ChangeDetail | None = Field(description="The change; null when it could not be read.")


def _provision_url(links: Links, location: str) -> tuple[str | None, str | None]:
    """The page of the top-level provision `location` sits in, as the catalogue files it."""
    words = location.split(" ")
    for size in range(1, len(words)):
        found = links.provision(" ".join(words[:size]))
        if found[0] is not None:
            return found
    return links.provision(location)


def get_change(
    record: Record,
    act: str,
    version: str,
    location: str,
    occurrence: int = 1,
    max_chars: int = 8000,
    offset: int = 0,
) -> ChangeResult:
    """The `occurrence`-th change at `location` in the event producing `version`, paged."""
    read = record.change(act, version, location, occurrence)
    if isinstance(read, Unavailable):
        return ChangeResult(unavailable=(read.reason,), change=None)
    stored = read.change.change
    corpus, key = stored.provision.act.corpus, stored.provision.act.key
    links = Links(record, corpus, key)
    url, why = _provision_url(links, location)
    detail = ChangeDetail(
        corpus=corpus,
        key=key,
        location=read.location,
        occurrence=read.occurrence,
        event=EventRef.of(read.event, links),
        sha256=read.sha256,
        matches_index=read.matches_index,
        row=read.row,
        reason_sentence=None if read.row is None else reason_sentence(read.row.dispute_reason),
        provision_url=url,
        provision_url_unavailable=why,
        change_type=stored.change_type,
        version=stored.provision.version,
        heading=stored.heading,
        previous_location=stored.previous_location,
        before=None if stored.before is None else page(stored.before, offset, max_chars),
        after=None if stored.after is None else page(stored.after, offset, max_chars),
        changed_within=stored.changed_within,
        signals=stored.signals,
        in_force=stored.in_force,
        applies_from=stored.applies_from,
        dates_added=stored.dates_added,
        dates_removed=stored.dates_removed,
        amending_acts=stored.amending_acts,
        outcome=read.change.outcome,
        sentences=read.change.sentences,
        applicability_note=read.change.applicability_note,
        unexplained=read.change.unexplained,
        unexplained_kind=read.change.unexplained_kind,
    )
    return ChangeResult(unavailable=(), change=detail)
