"""Where a CAS or EC number appears: the entries that print it now, and every change to them.

A typed value is read by the record's identifier rules (shape and check digit, hyphens
optional), and every reading that passes is answered; one that does not is answered with the
reason, never a guess. A CLP Index No is answered with the CAS or EC number whose page its entry
lands on, as the site build's list states it. Each reading is answered from that number's file,
which the site build derived from the committed registers and payloads, and each recorded change
in it is traced to its payload in the changelogs repository through the act's index, so the
answer names the file it was read from and that file's `sha256`.

It says where a number appears and nothing else. A number no entry prints is answered with one
sentence, `ABSENCE`, because many entries name a group of substances and print no number.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix_mcp import DISCLAIMER
from emendrix_record.identifiers import SCHEME_NAMES, parse_identifier
from emendrix_record.models import ActIndex
from emendrix_record.payload import IdentifierRecord
from emendrix_record.reads import Unavailable
from emendrix_record.record import Record
from emendrix_record.substances import SubstanceChange, SubstanceEntry, SubstanceIndex

__all__ = [
    "ABSENCE",
    "FIND_SUBSTANCE",
    "NumberAnswer",
    "SubstanceAnswer",
    "TracedChange",
    "find_substance",
]

_FROZEN = ConfigDict(frozen=True)

FIND_SUBSTANCE: Final = (
    "Find the entries that print a CAS or EC number, given with or without hyphens, in the "
    "newest version of each act the record holds, and every recorded change to them, each with "
    "its date, the amending act the change names and the file it was read from. It reports "
    "where a number appears and decides nothing about legal status; many entries name a group "
    "and print no number."
)
"""The tool's own purpose, as its description opens."""

ABSENCE: Final = (
    "No entry in the record prints this number. Many entries name a group of substances and "
    "print no number, so absence here is not absence from the law."
)
"""The one form an absence takes."""

_NAMES: Final = (
    "`amending_acts` on a change are the amending acts the change names, which may be fewer "
    "than made it."
)


class TracedChange(BaseModel):
    """One recorded change to an entry printing the number, with the payload it was read from."""

    model_config = _FROZEN

    change: SubstanceChange = Field(
        description="The change as the substance file states it: act, version, date, kind, key "
        "label, header, the entry before and after, the amending acts the change names, the "
        "event permalink and the payload's address on the site."
    )
    payload: str | None = Field(
        description="The payload's path in the changelogs repository; null if unresolved."
    )
    payload_sha256: str | None = Field(
        description="Hex sha256 of the payload's bytes, as the act index states it."
    )
    payload_unavailable: str | None = Field(description="Why `payload` is null; else null.")


class NumberAnswer(BaseModel):
    """One reading of the typed value, and what the record holds for it."""

    model_config = _FROZEN

    scheme: str = Field(description="`cas`, `ec` or `index`.")
    value: str = Field(description="The canonical value read.")
    lands_on: IdentifierRecord | None = Field(
        description="For an Index No, the CAS or EC number whose page its entry lands on."
    )
    file: str | None = Field(
        description="The number's file, relative to the site catalogue's directory (`api/v1/` "
        "in a site build); null when none was read."
    )
    sha256: str | None = Field(description="Hex sha256 of that file's bytes as read now.")
    page: str | None = Field(description="The number's page, as its file states it.")
    identifiers: tuple[IdentifierRecord, ...] = Field(
        description="Every identifier the entries' rows carry, this one included."
    )
    entries: tuple[SubstanceEntry, ...] = Field(
        description="Each entry of an act's newest version the record holds that prints the "
        "number, rows verbatim, act order then document order."
    )
    history: tuple[TracedChange, ...] = Field(description="Every recorded change, newest first.")
    sentence: str = Field(description="What the reading's answer, or its absence, means.")


class SubstanceAnswer(BaseModel):
    """What `find_substance` returns."""

    model_config = _FROZEN

    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    unavailable: tuple[str, ...] = Field(description="What could not be read, in words.")
    query: str = Field(description="The value as typed.")
    readings: tuple[NumberAnswer, ...] = Field(
        description="One answer per reading whose check digit passes; empty when none does."
    )
    sentence: str = Field(description="The answer, or the reason the value is no number.")


class _Lookup:
    """What one call reads: the list of numbers when it is needed, and each act index once."""

    def __init__(self, record: Record) -> None:
        self.record = record
        self._acts: dict[str, ActIndex | Unavailable] = {}
        self._listed: SubstanceIndex | Unavailable | None = None

    def listed(self) -> SubstanceIndex | Unavailable:
        """The site build's list of numbers, read on first use: a file read needs it only for
        an Index No and to tell an absent number from an unreadable one."""
        if self._listed is None:
            self._listed = self.record.substances()
        return self._listed

    def trace(self, change: SubstanceChange) -> TracedChange:
        name = f"{change.corpus}/{change.act}"
        if name not in self._acts:
            self._acts[name] = self.record.act(name)
        index = self._acts[name]
        event = index if isinstance(index, Unavailable) else Record.event(index, change.version)
        if isinstance(event, Unavailable):
            return TracedChange(
                change=change, payload=None, payload_sha256=None, payload_unavailable=event.reason
            )
        return TracedChange(
            change=change, payload=event.path, payload_sha256=event.sha256, payload_unavailable=None
        )


def _named(scheme: str, value: str) -> str:
    return f"{SCHEME_NAMES.get(scheme, scheme)} {value}"


def _empty(scheme: str, value: str, sentence: str) -> NumberAnswer:
    return NumberAnswer(
        scheme=scheme,
        value=value,
        lands_on=None,
        file=None,
        sha256=None,
        page=None,
        identifiers=(),
        entries=(),
        history=(),
        sentence=sentence,
    )


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _found_sentence(name: str, entries: int, acts: int, changes: int) -> str:
    where = (
        f"{name} appears in {_plural(entries, 'entry', 'entries')} of "
        f"{_plural(acts, 'act', 'acts')}, in the newest version of each act the record holds"
        if entries
        else f"No entry in the newest version of any act the record holds prints {name}"
    )
    moved = (
        f"{_plural(changes, 'recorded change names', 'recorded changes name')} it, newest first"
        if changes
        else "no recorded change names it"
    )
    return f"{where}; {moved}. {_NAMES}"


def _answer(lookup: _Lookup, scheme: str, value: str) -> tuple[NumberAnswer, str | None]:
    """One reading's answer, and what could not be read for it."""
    target, lands_on = (scheme, value), None
    if scheme not in ("cas", "ec"):
        listed = lookup.listed()
        if isinstance(listed, Unavailable):
            sentence = (
                f"Nothing could be read for {_named(scheme, value)}, so nothing is said of it."
            )
            return _empty(scheme, value, sentence), listed.reason
        row = next((r for r in listed.substances if (r.scheme, r.value) == target), None)
        page = (
            None
            if row is None
            else next(
                (r for r in listed.substances if r.scheme in ("cas", "ec") and r.file == row.file),
                None,
            )
        )
        if page is None:
            return _empty(
                scheme,
                value,
                f"{_named(scheme, value)} lands on no CAS or EC page: no entry in the record "
                f"prints it beside a CAS or EC number, and an Index No has no page of its own.",
            ), None
        target = (page.scheme, page.value)
        lands_on = IdentifierRecord(scheme=page.scheme, value=page.value)
    read = lookup.record.substance(*target)
    if isinstance(read, Unavailable):
        listed = lookup.listed()
        if not isinstance(listed, Unavailable) and not any(
            (r.scheme, r.value) == target for r in listed.substances
        ):
            return _empty(scheme, value, f"{_named(scheme, value)}: {ABSENCE}"), None
        sentence = f"Nothing could be read for {_named(scheme, value)}, so nothing is said of it."
        return _empty(scheme, value, sentence), read.reason
    document = read.document
    history = tuple(lookup.trace(change) for change in document.history)
    shown = _named(*target) if lands_on is None else f"{_named(scheme, value)} ({_named(*target)})"
    held = {(entry.corpus, entry.act) for entry in document.entries}
    sentence = _found_sentence(shown, len(document.entries), len(held), len(history))
    answer = NumberAnswer(
        scheme=scheme,
        value=value,
        lands_on=lands_on,
        file=read.path,
        sha256=read.sha256,
        page=document.page,
        identifiers=document.identifiers,
        entries=document.entries,
        history=history,
        sentence=sentence,
    )
    return answer, None


def find_substance(record: Record, identifier: str) -> SubstanceAnswer:
    """Every passing reading of `identifier`, each answered from the record's substance files."""
    parsed = parse_identifier(identifier)
    if isinstance(parsed, str):
        return SubstanceAnswer(
            unavailable=(),
            query=identifier,
            readings=(),
            sentence=f"{parsed} Nothing was looked up.",
        )
    lookup = _Lookup(record)
    unavailable: list[str] = []
    readings: list[NumberAnswer] = []
    for scheme, value in parsed:
        answer, missing = _answer(lookup, scheme, value)
        readings.append(answer)
        if missing is not None and missing not in unavailable:
            unavailable.append(missing)
    sentence = " ".join(answer.sentence for answer in readings)
    if len(readings) > 1:
        sentence = (
            f"{identifier.strip()!r} reads as more than one number, each answered. {sentence}"
        )
    return SubstanceAnswer(
        unavailable=tuple(unavailable),
        query=identifier,
        readings=tuple(readings),
        sentence=sentence,
    )
