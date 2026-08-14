"""Reading a CELLAR *tree notice*: what versions of an act exist and how to fetch each one.

The tree notice is the adapter's routing table, and it is better than guessing. For every
version, the act as published in the OJ and each consolidation alike, it publishes under
`EXPRESSION_MANIFESTED_BY_MANIFESTATION/SAMEAS/URI` the exact resolvable `IDENTIFIER` of every
manifestation (`2024R1689/20260727.ENG.fmx4`) tagged with the `TYPE` it answers on
(`consolidation`), verified 2026-08-06 on `32024R1689`. So `eu/cellar.py` does not have to
know that pre-2018 consolidations answer on `celex/` and later ones on `consolidation/`: it
asks the notice and falls back to constructed candidates.

Four traps, all met on real notices on 2026-08-06:

1. **Two relations carry consolidations, and neither is complete.** Versions hang off the
   amended act's WORK under `RESOURCE_LEGAL_CONSOLIDATED_BY_ACT_CONSOLIDATED` *and* under
   `RESOURCE_LEGAL_BASIS_FOR_ACT_CONSOLIDATED`. Usually both; not always. REACH's
   `02006R1907-20190107` appears **only** under the second, so reading the first alone finds
   67 of its 68 consolidated versions, and 68 is the number measured by a different route and
   asserted every run by `tests/eu/test_cellar.py`. Both
   relations are read and the union deduplicated.
2. `RESOURCE_LEGAL_CONSOLIDATED_BY_ACT_CONSOLIDATED` on the AI Act's WORK lists **23** links,
   and only 6 are consolidations *of the AI Act*. The rest are consolidations of the nine
   regulations the AI Act amends. Filtering by the act's own code is mandatory; without it
   this act appears to have versions dated by other acts' amendments.
3. Some of those links address a *part* of a consolidation (`2024R1689/20260727_0010010`) and
   carry no consolidated CELEX. Requiring `ID_CELEX` to match `0<act code>-<date>` drops them.
4. The notice is decoded in one language (`Accept-Language: eng`). For a version with no
   English expression it embeds another one: `02024R1689-20240712` comes back with `FRA`
   only, which is the eleven-languages-no-English case the fallback chain exists for. So the
   language list here is *what the notice offered*, never a promise, and `fetch_formex` still
   asks.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # types only; parsing goes through `eu/xml_.py`
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from emendrix.core import ActId, VersionDescriptor, VersionId
from emendrix.eu.dates import iso_date
from emendrix.eu.identifiers import Celex, ConsolidatedId, ResourceRef, act_id
from emendrix.eu.xml_ import fromstring

__all__ = [
    "Manifestation",
    "TreeNotice",
    "VersionRecord",
    "WorkMetadata",
    "parse_tree_notice",
]

_MANIFESTATION_ID: Final = re.compile(r"^(?P<stem>.+)\.(?P<language>[A-Z]{3})\.(?P<format>\w+)$")
FORMEX_FORMAT: Final = "fmx4"
"""The structured manifestation. No `akn` manifestation exists for these acts (2026-08-05)."""

CONSOLIDATION_RELATIONS: Final = (
    "RESOURCE_LEGAL_CONSOLIDATED_BY_ACT_CONSOLIDATED",
    "RESOURCE_LEGAL_BASIS_FOR_ACT_CONSOLIDATED",
)
"""Both relations under which a consolidated version hangs off the act (trap 1 above)."""


def _text(element: ET.Element | None, path: str) -> str | None:
    if element is None:
        return None
    found = element.findtext(path)
    return found.strip() if found and found.strip() else None


def _same_as(element: ET.Element) -> tuple[ResourceRef, ...]:
    """The `SAMEAS` references of one element — the readable ones.

    A URI missing either half names nothing, and a `<TYPE>` outside the shape `ResourceRef`
    accepts is not a system this adapter can address (it would reach a path segment
    unencoded). Both are dropped here, for the same reason: this function answers *what can be
    fetched*, and an unreadable reference is one fewer candidate, never an exception out of the
    version inventory.
    """
    refs = []
    for uri in element.findall("SAMEAS/URI"):
        identifier, system = _text(uri, "IDENTIFIER"), _text(uri, "TYPE")
        if not (identifier and system):
            continue
        try:
            refs.append(ResourceRef(system=system, identifier=identifier))
        except ValidationError:
            continue
    return tuple(refs)


class Manifestation(BaseModel):
    """One (language, format) rendition of one version, and where it answers."""

    model_config = ConfigDict(frozen=True)

    language: str = Field(min_length=1)
    format: str = Field(min_length=1)
    ref: ResourceRef


class WorkMetadata(BaseModel):
    """What the notice says about the act itself — identity, title, dates."""

    model_config = ConfigDict(frozen=True)

    celex: Celex
    act: ActId
    title: str | None = None
    document_date: date | None = None
    entry_into_force: tuple[date, ...] = ()
    identifiers: tuple[ResourceRef, ...] = ()
    cellar_uri: str | None = None

    def identifier(self, system: str) -> str | None:
        """The act's identifier in one system (`oj`, `eli`, `celex`), if the notice has it."""
        return next((ref.identifier for ref in self.identifiers if ref.system == system), None)


class VersionRecord(BaseModel):
    """One version of an act: the OJ text, or a consolidation, with its manifestations."""

    model_config = ConfigDict(frozen=True)

    version: VersionId
    kind: Literal["original", "consolidated"]
    version_date: date | None = None
    manifestations: tuple[Manifestation, ...] = ()

    @property
    def languages(self) -> tuple[str, ...]:
        """Languages the *notice* offered — not a promise that fetching succeeds (see above)."""
        return tuple(sorted({item.language for item in self.manifestations}))

    def formats(self, language: str) -> tuple[str, ...]:
        wanted = language.upper()
        return tuple(
            sorted({item.format for item in self.manifestations if item.language == wanted})
        )

    def manifestation(self, language: str, format: str) -> Manifestation | None:
        wanted = language.upper()
        return next(
            (
                item
                for item in self.manifestations
                if item.language == wanted and item.format == format
            ),
            None,
        )

    def to_descriptor(self, act: ActId) -> VersionDescriptor:
        return VersionDescriptor(
            act=act,
            version=self.version,
            version_date=self.version_date,
            languages=self.languages,
        )


class TreeNotice(BaseModel):
    """A parsed tree notice: the act, and every version of it the notice lists."""

    model_config = ConfigDict(frozen=True)

    work: WorkMetadata
    versions: tuple[VersionRecord, ...] = ()

    def version(self, version: VersionId) -> VersionRecord | None:
        return next((item for item in self.versions if item.version == version), None)

    @property
    def consolidated(self) -> tuple[VersionRecord, ...]:
        return tuple(item for item in self.versions if item.kind == "consolidated")


def _manifestations(expression: ET.Element) -> tuple[Manifestation, ...]:
    """Manifestations of one expression, read off its `SAMEAS` identifiers.

    The language is taken from the manifestation identifier itself
    (`L_202401689.ENG.fmx4`) rather than from `EXPRESSION_USES_LANGUAGE`, so that a notice
    whose expression block is missing the language concept still yields usable rows.
    """
    declared = _text(expression, "EXPRESSION_USES_LANGUAGE/IDENTIFIER")
    found: list[Manifestation] = []
    for link in expression.findall("EXPRESSION_MANIFESTED_BY_MANIFESTATION"):
        for ref in _same_as(link):
            matched = _MANIFESTATION_ID.fullmatch(ref.identifier)
            if matched is None:
                continue
            language = matched["language"] if matched["language"] else declared
            if language is None:
                continue
            found.append(
                Manifestation(language=language.upper(), format=matched["format"], ref=ref)
            )
    return tuple(found)


def _work_metadata(notice: ET.Element, work: ET.Element, celex: Celex) -> WorkMetadata:
    title = next(
        (
            _text(expression, "EXPRESSION_TITLE/VALUE")
            for expression in notice.findall("EXPRESSION")
            if _text(expression, "EXPRESSION_USES_LANGUAGE/IDENTIFIER") == "ENG"
        ),
        None,
    )
    entry_into_force = tuple(
        sorted(
            {
                parsed
                for element in work.findall("RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE")
                if (parsed := iso_date(_text(element, "VALUE"))) is not None
            }
        )
    )
    return WorkMetadata(
        celex=celex,
        act=act_id(celex, display_name=title),
        title=title,
        document_date=iso_date(_text(work, "WORK_DATE_DOCUMENT/VALUE")),
        entry_into_force=entry_into_force,
        identifiers=_same_as(work),
        cellar_uri=_text(work, "URI/VALUE"),
    )


def _original_version(notice: ET.Element, celex: Celex) -> VersionRecord:
    """The act as published in the OJ — the notice's own top-level expressions."""
    manifestations = tuple(
        item for expression in notice.findall("EXPRESSION") for item in _manifestations(expression)
    )
    return VersionRecord(
        version=celex.version,
        kind="original",
        version_date=iso_date(_text(notice.find("WORK"), "WORK_DATE_DOCUMENT/VALUE")),
        manifestations=manifestations,
    )


def _consolidated_version(link: ET.Element, celex: Celex) -> VersionRecord | None:
    """One `RESOURCE_LEGAL_CONSOLIDATED_BY_ACT_CONSOLIDATED` link, if it is this act's."""
    embedded = link.find("EMBEDDED_NOTICE")
    if embedded is None:
        return None
    consolidated_celex = _text(embedded.find("WORK"), "ID_CELEX/VALUE")
    if consolidated_celex is None:
        return None
    try:
        parsed = ConsolidatedId.parse(consolidated_celex)
    except ValueError:
        return None
    if parsed.act_code != celex.act_code:  # trap 1: other acts' consolidations ride along
        return None
    manifestations = tuple(
        item
        for expression in embedded.findall("EXPRESSION")
        for item in _manifestations(expression)
    )
    return VersionRecord(
        version=parsed.version,
        kind="consolidated",
        version_date=parsed.version_date,
        manifestations=manifestations,
    )


def parse_tree_notice(xml: bytes, celex: Celex) -> TreeNotice:
    """Parse a `notice=tree` response into the act's metadata and its versions, oldest first."""
    notice = fromstring(xml)
    work = notice.find("WORK")
    if work is None:
        raise ValueError(f"tree notice for {celex} has no WORK element")

    merged: dict[VersionId, VersionRecord] = {}
    for relation in CONSOLIDATION_RELATIONS:
        for link in work.findall(relation):
            record = _consolidated_version(link, celex)
            if record is None:
                continue
            found = merged.get(record.version)
            merged[record.version] = record if found is None else _merge(found, record)

    versions = [_original_version(notice, celex), *merged.values()]
    versions.sort(key=lambda item: (item.version_date or date.min, str(item.version)))
    return TreeNotice(work=_work_metadata(notice, work, celex), versions=tuple(versions))


def _merge(first: VersionRecord, second: VersionRecord) -> VersionRecord:
    """One version seen under both relations: keep every manifestation either one listed."""
    known = {(item.language, item.format) for item in first.manifestations}
    extra = tuple(
        item for item in second.manifestations if (item.language, item.format) not in known
    )
    return first.model_copy(update={"manifestations": (*first.manifestations, *extra)})
