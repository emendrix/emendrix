"""What every tool result shares: the sentences a caller is told, the row view, the links.

A tool hands over what the loop decided, so the shapes here wrap stored values rather than
restate them. An index row travels as the `ProvisionRow` the act index stores, whole, with its
event's provenance, its page addresses and its reason's sentence beside it. Every address is a
value read out of the catalogue; without one the field is null and a sentence says why.

The tools themselves are in `tools_read.py` (the acts, provisions by name, changes since a
date), `tools_event.py` (one act, one provision's history, one event, the disputes) and
`tools_text.py` (one change with its paged text), split by the question each answers.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.models import ActIndex, ActRow, CatalogueAct, EventRow, ProvisionRow
from emendrix_mcp.reads import Unavailable
from emendrix_mcp.reasons import REASON_SENTENCES
from emendrix_mcp.record import Record, entry_key

__all__ = [
    "APPLIES_FROM_SENTENCE",
    "DISPUTED_SENTENCE",
    "ONE_SIGNAL_SENTENCE",
    "WINDOW_SENTENCE",
    "ChangeRow",
    "EventRef",
    "Links",
    "Window",
    "describe",
    "reason_sentence",
    "rows_of",
    "window",
]

_FROZEN = ConfigDict(frozen=True)

WINDOW_SENTENCE: Final = (
    "Every list is complete for the watch window the record covers, from the oldest version "
    "an act was watched from to its newest, and says nothing about anything outside it."
)
DISPUTED_SENTENCE: Final = (
    "`disputed` means one of three independent signals (the text comparison, the EU's own "
    "amendment metadata, the amending act's instructions) disagreed; `dispute_reason` says "
    "which and how, and a dispute is a reading of the sources, not a judgement about the law."
)
APPLIES_FROM_SENTENCE: Final = (
    "`applies_from: unknown` means no application date could be read deterministically, "
    "never that no date applies."
)
ONE_SIGNAL_SENTENCE: Final = (
    "Units named by only one signal are listed by name on their event "
    "(`metadata_only_units`, `instruction_only_units`), never as changes."
)
_COMMON: Final = " ".join(
    (WINDOW_SENTENCE, DISPUTED_SENTENCE, APPLIES_FROM_SENTENCE, ONE_SIGNAL_SENTENCE, DISCLAIMER)
)
_NO_SENTENCE: Final = "no sentence is published for this dispute_reason code"


def describe(purpose: str) -> str:
    """A tool's description: what it does, then what every answer means."""
    return f"{purpose} {_COMMON}"


def reason_sentence(reason: str | None) -> str | None:
    """The published sentence for a `dispute_reason` code; null when there is no code."""
    if reason is None:
        return None
    return REASON_SENTENCES.get(reason, _NO_SENTENCE)


class Links:
    """One act's page addresses, read out of the catalogue once per call."""

    def __init__(self, record: Record, corpus: str, key: str) -> None:
        self._listing: CatalogueAct | Unavailable = record.listing(corpus, key)

    def _missing(self, what: str) -> tuple[None, str]:
        if isinstance(self._listing, Unavailable):
            return None, self._listing.reason
        return None, f"permalink unavailable: the catalogue lists no page for {what}"

    @property
    def listing(self) -> CatalogueAct | None:
        """The catalogue's row for the act, when there is one."""
        return None if isinstance(self._listing, Unavailable) else self._listing

    def act(self) -> tuple[str | None, str | None]:
        """`(url, why not)` for the act's page."""
        if isinstance(self._listing, Unavailable):
            return None, self._listing.reason
        return self._listing.url, None

    def event(self, event: EventRow) -> tuple[str | None, str | None]:
        """`(url, why not)` for an event's page."""
        url = None if self.listing is None else self.listing.events.get(entry_key(event))
        return (url, None) if url is not None else self._missing(event.to_version)

    def provision(self, location: str) -> tuple[str | None, str | None]:
        """`(url, why not)` for a top-level provision's page."""
        url = None if self.listing is None else self.listing.provisions.get(location)
        return (url, None) if url is not None else self._missing(location)


class EventRef(BaseModel):
    """The event a row belongs to: the payload's path and hash, and the event's page."""

    model_config = _FROZEN

    to_version: str = Field(description="The version the event produced, as stored.")
    from_version: str = Field(description="The version it was computed from, as stored.")
    detected_on: date = Field(description="The date the run observed the event.")
    updated_on: date = Field(description="The latest of `detected_on` and every repair's date.")
    path: str = Field(description="The payload's path relative to the changelogs repository.")
    sha256: str = Field(description="Hex sha256 of the payload's bytes, as the index states.")
    url: str | None = Field(description="The event's page from the catalogue; null if unknown.")
    url_unavailable: str | None = Field(description="Why `url` is null; null when it is given.")

    @classmethod
    def of(cls, event: EventRow, links: Links) -> EventRef:
        url, why = links.event(event)
        return cls(
            to_version=event.to_version,
            from_version=event.from_version,
            detected_on=event.detected_on,
            updated_on=event.updated_on,
            path=event.path,
            sha256=event.sha256,
            url=url,
            url_unavailable=why,
        )


class ChangeRow(BaseModel):
    """One index row, whole, with where it comes from and what its reason code means."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    location: str = Field(description="The canonical top-level location the row is filed under.")
    row: ProvisionRow = Field(
        description="The act index's row as stored: change type, `disputed`, `dispute_reason`, "
        "the three signals, dates, gate outcome, `changed_within`, `occurrence`."
    )
    reason_sentence: str | None = Field(
        description="What the row's `dispute_reason` means; null when the row is not disputed."
    )
    event: EventRef = Field(description="The event the row belongs to, with its provenance.")
    provision_url: str | None = Field(description="The provision's page from the catalogue.")
    provision_url_unavailable: str | None = Field(description="Why `provision_url` is null.")

    @classmethod
    def of(
        cls, index: ActIndex, event: EventRow, location: str, row: ProvisionRow, links: Links
    ) -> ChangeRow:
        url, why = links.provision(location)
        return cls(
            corpus=index.corpus,
            key=index.key,
            location=location,
            row=row,
            reason_sentence=reason_sentence(row.dispute_reason),
            event=EventRef.of(event, links),
            provision_url=url,
            provision_url_unavailable=why,
        )


def rows_of(index: ActIndex, links: Links) -> list[ChangeRow]:
    """Every row of an act, events newest first, then by location and occurrence."""
    rows: list[ChangeRow] = []
    for event in index.events:
        for location, filed in index.provisions.items():
            rows.extend(
                ChangeRow.of(index, event, location, row, links)
                for row in filed
                if row.version == event.to_version
            )
    return rows


class Window(BaseModel):
    """What the record covers for one act, as its indexes state it."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    from_version: str = Field(description="The `from_version` of the act's oldest event.")
    to_version: str = Field(description="The act's newest version, as the root index states.")
    first_detected_on: date = Field(description="The earliest `detected_on` over its events.")
    updated_on: date = Field(description="The latest `updated_on` over its events.")
    sentence: str = Field(description="The window, said in words.")


def window(row: ActRow, index: ActIndex) -> Window:
    """The window of one act, read off its root row and its oldest event."""
    oldest = index.events[-1].from_version if index.events else row.newest_version
    return Window(
        corpus=row.corpus,
        key=row.key,
        from_version=oldest,
        to_version=row.newest_version,
        first_detected_on=row.first_detected_on,
        updated_on=row.updated_on,
        sentence=f"The record covers {row.corpus}/{row.key} from version {oldest} to version "
        f"{row.newest_version}, over events detected from {row.first_detected_on} and last "
        f"updated on {row.updated_on}; it says nothing about any change outside that window.",
    )
