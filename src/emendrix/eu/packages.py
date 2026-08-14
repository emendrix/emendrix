"""A fetched Formex 4 package: the zip's members, its provenance, and nothing interpreted.

This module stops at *bytes of the right document, cached, with provenance*. The parser decides
what to parse — and it will need all of it, because a Formex package is a bag of documents,
not one file (measured 2026-08-05):

| Package | Members |
|---|---|
| `02024R1689-20260727` consolidated | 2 — the act, annexes inline as `CONS.ANNEX` |
| `32024R1689` as published in the OJ | 16 — the act plus one `ANNEX` document per annex |
| `32008R1272` as published | 98 — 9 XML, 89 `.tif` scans, and its biggest XML is an annex |

So `FormexPackage` keeps every member and ranks none of them.

**Provenance.** Neither the tree notice nor the branch notice carries a build timestamp for a
manifestation (checked 2026-08-06). The provenance is inside the consolidated document itself
and is richer: the root `CONS.ACT` carries

```xml
<INFO.CONSLEG CONSLEG.REF="2024R1689" CONSLEG.DATE="20260715" DATE.LAST.MOD="20260724"
              PROD.SEQ="001.001.0" START.DATE="20260727" END.DATE="99999999" …/>
<INFO.PROD PRODUCER="ES" PROD.SYSTEM="CONSLEG.NEW" PROD.DATE="20260715"/>
```

which is where the ≈10-day consolidation lag is actually measurable: `START.DATE`
2026-07-27 (in force) against `PROD.DATE` 2026-07-15/`DATE.LAST.MOD` 2026-07-24 (built).
`END.DATE="99999999"` means "still current" and is carried as `None`.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from datetime import date, datetime
from typing import Final, Self, cast
from xml.etree.ElementTree import Element, ParseError, XMLPullParser

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, VersionId
from emendrix.eu.dates import compact_date

__all__ = [
    "MAX_PACKAGE_BYTES",
    "ConsolidationInfo",
    "FormexMember",
    "FormexPackage",
    "PackageTooLarge",
    "check_package_size",
    "read_package",
]

_OPEN_ENDED: Final = "99999999"
_HEAD_BYTES: Final = 8192
"""`INFO.CONSLEG` is the first child of the root, so the head of the file is enough."""

MAX_PACKAGE_BYTES: Final = 256 * 1024 * 1024
"""Uncompressed ceiling for one package, summed over its members.

A package is decompressed straight into memory here (`FormexMember.data` holds every member),
so an archive that expands far beyond its transfer size would take the poller out. The largest
real one the corpus serves is 8.9 MB over 98 members (`32008R1272`, measured 2026-08-05, table
above); this sits far enough above that no legitimate act approaches it, and far enough below a
machine's memory that hitting it is a refusal rather than a crash. "It is normally small" is
not a bound, which is why there is a number here.

`ZipInfo.file_size` is the archive's own claim about itself, so this is a cheap first gate and
not a proof. It is aimed squarely at the classic bomb, whose whole trick is a few kilobytes
declaring gigabytes.
"""


def _end_of_validity(raw: str | None) -> date | None:
    """`END.DATE`, where `99999999` means "still current" and is carried as `None`.

    The sentinel is read here rather than in `eu/dates.py` because it means something only to
    `INFO.CONSLEG`: the other four dates in this block never carry it, and a shared parser that
    knew about it would be answering a question nobody else asks. It would parse as `None` in
    any case — this says *why* it is `None`.
    """
    return None if raw == _OPEN_ENDED else compact_date(raw)


class ConsolidationInfo(BaseModel):
    """`INFO.CONSLEG` / `INFO.PROD` — when this consolidated text was built, and for when."""

    model_config = ConfigDict(frozen=True)

    reference: str | None = None
    consolidation_date: date | None = Field(
        default=None, description="`CONSLEG.DATE` — when the consolidation was drawn up."
    )
    last_modified: date | None = None
    produced_on: date | None = Field(default=None, description="`INFO.PROD/PROD.DATE`.")
    start_of_validity: date | None = Field(
        default=None, description="`START.DATE` — the date this text speaks as of."
    )
    end_of_validity: date | None = Field(
        default=None, description="`END.DATE`, or `None` when the text is still current."
    )
    production_sequence: str | None = None


class FormexMember(BaseModel):
    """One file inside the package, byte for byte as the archive holds it."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    data: bytes

    @property
    def is_xml(self) -> bool:
        return self.name.lower().endswith(".xml")


class FormexPackage(BaseModel):
    """The structured text of one version of one act, plus where and when it came from.

    `served_version` is what the corpus actually answered with, which is not always what was
    asked for: when the requested consolidation has no English text the chain falls back to
    the act as published in the OJ (`eu/cellar.py`). The fallback is recorded, never implied.
    """

    model_config = ConfigDict(frozen=True)

    act: ActId
    requested_version: VersionId
    served_version: VersionId
    language: str
    source_url: str
    fetched_at: datetime
    members: tuple[FormexMember, ...] = ()
    consolidation: ConsolidationInfo | None = None

    @property
    def fell_back(self) -> bool:
        return self.requested_version != self.served_version

    @property
    def xml_members(self) -> tuple[FormexMember, ...]:
        return tuple(member for member in self.members if member.is_xml)

    def member(self, name: str) -> FormexMember | None:
        return next((member for member in self.members if member.name == name), None)

    @classmethod
    def from_zip(
        cls,
        blob: bytes,
        *,
        act: ActId,
        requested_version: VersionId,
        served_version: VersionId,
        language: str,
        source_url: str,
        fetched_at: datetime,
    ) -> Self:
        members = read_package(blob)
        return cls(
            act=act,
            requested_version=requested_version,
            served_version=served_version,
            language=language,
            source_url=source_url,
            fetched_at=fetched_at,
            members=members,
            consolidation=consolidation_info(members),
        )


class PackageTooLarge(ValueError):
    """An archive declares more uncompressed bytes than `MAX_PACKAGE_BYTES` allows.

    Loud, like the `BadZipFile` from an archive that is not a zip at all, and for the same
    reason: this is not a first-class state. `EnglishUnavailable` and friends say what the
    corpus answered *about an act*, and "the endpoint served something enormous" is a fault in
    the response, not an answer about the legislation.
    """

    def __init__(self, declared: int) -> None:
        super().__init__(
            f"package declares {declared} uncompressed bytes, over the "
            f"{MAX_PACKAGE_BYTES} ceiling; refusing to read it"
        )
        self.declared = declared


def check_package_size(archive: zipfile.ZipFile) -> None:
    """Refuse an archive that declares more than the ceiling, before anything is decompressed.

    Called by every site that expands a Formex package into memory — `read_package` here and
    `trims.py::trim_formex_zip` — so the number and the reasoning behind it are stated once
    rather than restated per call site.
    """
    declared = sum(info.file_size for info in archive.infolist())
    if declared > MAX_PACKAGE_BYTES:
        raise PackageTooLarge(declared)


def read_package(blob: bytes) -> tuple[FormexMember, ...]:
    """Every member of a Formex zip, in the archive's own order, undecoded and untouched.

    Nothing is extracted to disk — members are held in memory keyed by their archive name — so
    the usual zip finding, path traversal out of the extraction directory, has no target here.
    Size is the exposure that remains, and `check_package_size` is what bounds it.
    """
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        check_package_size(archive)
        return tuple(
            FormexMember(name=info.filename, data=archive.read(info))
            for info in archive.infolist()
            if not info.is_dir()
        )


def consolidation_info(members: tuple[FormexMember, ...]) -> ConsolidationInfo | None:
    """The consolidation provenance block, from whichever member carries one."""
    for member in members:
        if not member.is_xml:
            continue
        found = _read_info(member.data[:_HEAD_BYTES])
        if found is not None:
            return found
    return None


def _read_info(head: bytes) -> ConsolidationInfo | None:
    """Read `INFO.CONSLEG`/`INFO.PROD` attributes without parsing the whole document.

    A consolidated act is a megabyte of XML and this step has no reason to parse it — the
    pull parser is fed the head of the file and stopped at the first start events, so a
    truncated feed is expected and its incompleteness is not an error. Nor is a member that
    is not well-formed XML at all: provenance is best-effort, and whether the document parses
    is the parser's finding to report (`eu/formex/parse.py` counts it), not this function's
    to raise on.

    This is the one parse in the package that `eu/xml_.py` does not cover, because
    `defusedxml` ships no pull-parser wrapper — so the guard below stands in for it. It
    refuses on any `DOCTYPE`, which is deliberately broader than `defusedxml`'s own policy of
    refusing only entity *declarations*: `head` is a truncated 8 KB feed, so an internal
    subset may well be cut off mid-declaration, and a `DOCTYPE` is the only reliable signal
    that there is one here whose end this function cannot see. Nothing is lost — a Formex
    document has no business carrying a DTD, and none of the committed fixtures does.
    """
    if b"<!DOCTYPE" in head:
        return None
    parser: XMLPullParser[Element] = XMLPullParser(events=("start",))
    consleg: dict[str, str] = {}
    prod: dict[str, str] = {}
    # `read_events` is typed for every event kind at once; with `events=("start",)` every
    # event is a `(name, element)` pair.
    events = cast("Iterator[tuple[str, Element]]", parser.read_events())
    try:
        parser.feed(head)
        collected = list(events)
    except ParseError:
        return None
    for _, element in collected:
        if element.tag == "INFO.CONSLEG":
            consleg = dict(element.attrib)
        elif element.tag == "INFO.PROD":
            prod = dict(element.attrib)
    if not consleg and not prod:
        return None
    return ConsolidationInfo(
        reference=consleg.get("CONSLEG.REF"),
        consolidation_date=compact_date(consleg.get("CONSLEG.DATE")),
        last_modified=compact_date(consleg.get("DATE.LAST.MOD")),
        produced_on=compact_date(prod.get("PROD.DATE")),
        start_of_validity=compact_date(consleg.get("START.DATE")),
        end_of_validity=_end_of_validity(consleg.get("END.DATE")),
        production_sequence=consleg.get("PROD.SEQ"),
    )
