"""CELLAR modification annotations: the reference label set, and the `in_force` clock.

The Publications Office publishes, in the amended act's *branch notice*, structured
per-amendment provision-level modification coordinates: one
`RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL` link per amending act, each holding `ANNOTATION`
elements of `ROLE2` (`{J|http://…/authority/fd_375/J}`), `REFERENCE_TO_MODIFIED_LOCATION`
(`{AR|…/fd_370/AR} 5 {PA|…} 1 {ALN|…} 1 {PTA|…} (bb)`) and `START_OF_VALIDITY`. This module
reads them.

Four facts about that markup, each of which costs correctness if assumed away. All were
verified against the pinned branch notices on 2026-08-06, and `tests/eu/test_modmeta.py`
re-asserts the counts every run: the AI Act's 88 annotations and their R=45 / J=39 / DEL=4
histogram among them.

1. **A branch notice carries every amending act in the act's history**: 1 link for the AI
   Act, 10 for the MDR, **85** for REACH. Filtering by the `SAMEAS` CELEX of the link, or by
   the date window of the version pair, is load-bearing.
2. **Both fields are `{CODE|authority-uri}` templates**, and legacy notices mix expanded and
   bare codes in one location value. `core.normalize_location` strips the template; the role
   is stripped here by the same rule.
3. **The role vocabulary has no published English labels**, so it is empirical and lives in
   `eu/mod_roles.py` with the evidence for each reading. Anything outside it is carried as
   `UnknownRole` and counted.
4. **Dates are inconsistently formatted**: `START_OF_VALIDITY` is `2008-10-12` in some notices
   and `2007/11/23` in 27 of REACH's 391 (the 391 is asserted by `tests/eu/test_modmeta.py`).
   Both spellings are read by `eu/dates.py`, which is also where the reason an unreadable one
   answers `None` rather than raising is written down.

**This is a reference set, never an oracle.** CELLAR annotates a blanket amendment once and
does not enumerate the provisions it lands in: the CLP Regulation's "the word 'preparation' …
shall be replaced by 'mixture' … throughout the text" is 28 annotations naming 8 units against
the 40 the structural diff finds, and the diff is the one that is right. Disagreement
is information, and it ships as `disputed`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # types only; parsing goes through `eu/xml_.py`
from collections.abc import Iterable
from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import (
    ActId,
    ChangeType,
    ProvisionLocation,
    Signal,
    SignalClaim,
    SignalReport,
    normalize_location,
)
from emendrix.eu.dates import iso_date
from emendrix.eu.identifiers import CORPUS
from emendrix.eu.mod_roles import RoleCode, UnknownRole, change_type_of, parse_role
from emendrix.eu.xml_ import fromstring

__all__ = [
    "ModificationRecord",
    "ModificationSet",
    "metadata_signal",
    "parse_branch_modifications",
    "touched_units",
]

_LINK: Final = "RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL"


class ModificationRecord(BaseModel):
    """One `ANNOTATION`: which amending act changed which location, in what way, from when."""

    model_config = ConfigDict(frozen=True)

    amending_celex: str | None = Field(
        default=None, description="The `SAMEAS` CELEX of the link this annotation hangs off."
    )
    location: ProvisionLocation
    role: RoleCode | None = Field(default=None, union_mode="left_to_right")
    start_of_validity: date | None = None

    @property
    def unit(self) -> ProvisionLocation:
        """The top-level provision this modification is counted under."""
        return self.location.top_level

    @property
    def change_type(self) -> ChangeType | None:
        """The change type this role means, at this record's own location. `None` if unknown."""
        return change_type_of(self.role)

    def to_claim(self) -> SignalClaim:
        """The corroboration-shaped claim, with the amending act as an identifier of its own.

        The CELEX is carried straight into `ActId.key` rather than parsed: it is an
        unvalidated string read off a remote notice, `Celex.parse` raises on an unexpected
        shape, and this path counts coverage gaps instead of crashing on them. `source` keeps
        its flattened audit form, `'?'` placeholder and all, because an audit string may say
        "unknown" where an identifier may not.
        """
        return SignalClaim(
            location=self.location,
            change_type=self.change_type,
            in_force=self.start_of_validity,
            source=f"{self.amending_celex or '?'} {self.role or 'UNKNOWN()'}",
            amending_act=(
                None
                if self.amending_celex is None
                else ActId(corpus=CORPUS, key=self.amending_celex)
            ),
        )


class ModificationSet(BaseModel):
    """Every modification annotation of one act, with what could not be read counted.

    Coverage gaps are counted, never crashed on. An annotation whose role or date is unreadable
    still becomes a record, with that field absent, and is tallied here. One whose *location* is
    unreadable cannot: a modification with nowhere to put it is not a record of anything, so it
    is counted in `unreadable_locations` and nothing else. All three counts were zero on the
    pinned notices except the one unknown role (measured 2026-08-06).
    """

    model_config = ConfigDict(frozen=True)

    act: str = Field(description="The CELEX of the amended act these annotations hang off.")
    records: tuple[ModificationRecord, ...] = ()
    unknown_roles: tuple[tuple[str, int], ...] = Field(
        default=(), description="Role code → count, for codes outside `ModRole`."
    )
    missing_roles: int = Field(default=0, ge=0, description="Annotations with no `ROLE2` at all.")
    unreadable_locations: int = Field(
        default=0, ge=0, description="`REFERENCE_TO_MODIFIED_LOCATION` values that held no segment."
    )
    unreadable_dates: int = Field(
        default=0, ge=0, description="`START_OF_VALIDITY` values no date rule accepted."
    )
    amending_acts: tuple[str, ...] = Field(
        default=(), description="Every amending CELEX the notice links, in document order."
    )

    @property
    def clean(self) -> bool:
        return not (self.unknown_roles or self.unreadable_locations or self.unreadable_dates)

    def by_amending_act(self, celex: str) -> tuple[ModificationRecord, ...]:
        """Only the annotations of one amending act — the notice carries every one of them."""
        return tuple(record for record in self.records if record.amending_celex == celex)

    def between(self, after: date | None, until: date) -> tuple[ModificationRecord, ...]:
        """Annotations whose `START_OF_VALIDITY` falls in `(after, until]`.

        The window, not the amending act, is what a version pair asks for: a pair can fold in
        several amending acts, and one amending act's changes can be split across several
        dates — the CLP Regulation amends REACH from its entry into force, from 2010-12-01 and
        from 2015-06-01, and CELLAR dates each annotation accordingly.
        """
        return tuple(
            record
            for record in self.records
            if record.start_of_validity is not None
            and (after is None or record.start_of_validity > after)
            and record.start_of_validity <= until
        )


def parse_branch_modifications(
    branch_xml: bytes, *, amending_celex: str | None = None
) -> ModificationSet:
    """Read every modification annotation out of a branch notice.

    `amending_celex` narrows to one amending act by the `SAMEAS` CELEX of its link — the
    filtering gotcha of the module docstring. Left `None`, every link is read and each record
    remembers which one it came from.
    """
    notice = fromstring(branch_xml)
    work = notice.find("WORK")
    if work is None:
        raise ValueError("branch notice has no WORK element")
    act = (work.findtext("ID_CELEX/VALUE") or "").strip()

    records: list[ModificationRecord] = []
    linked: list[str] = []
    unknown: dict[str, int] = {}
    missing_roles = unreadable_locations = unreadable_dates = 0

    for link in work.findall(_LINK):
        celex = _link_celex(link)
        if celex is not None and celex not in linked:
            linked.append(celex)
        if amending_celex is not None and celex != amending_celex:
            continue
        for annotation in link.findall("ANNOTATION"):
            raw_location = annotation.findtext("REFERENCE_TO_MODIFIED_LOCATION")
            if not normalize_location(raw_location or ""):
                unreadable_locations += 1
                continue
            role = parse_role(annotation.findtext("ROLE2"))
            if role is None:
                missing_roles += 1
            elif isinstance(role, UnknownRole):
                unknown[role.raw] = unknown.get(role.raw, 0) + 1
            raw_date = annotation.findtext("START_OF_VALIDITY")
            validity = iso_date(raw_date)
            if validity is None and raw_date is not None:
                unreadable_dates += 1
            records.append(
                ModificationRecord(
                    amending_celex=celex,
                    location=ProvisionLocation.parse(raw_location or ""),
                    role=role,
                    start_of_validity=validity,
                )
            )

    return ModificationSet(
        act=act,
        records=tuple(records),
        unknown_roles=tuple(sorted(unknown.items())),
        missing_roles=missing_roles,
        unreadable_locations=unreadable_locations,
        unreadable_dates=unreadable_dates,
        amending_acts=tuple(linked),
    )


def _link_celex(link: ET.Element) -> str | None:
    for uri in link.findall("SAMEAS/URI"):
        if (uri.findtext("TYPE") or "").strip() == "celex":
            identifier = (uri.findtext("IDENTIFIER") or "").strip()
            if identifier:
                return identifier
    return None


def touched_units(records: Iterable[ModificationRecord]) -> tuple[ProvisionLocation, ...]:
    """The distinct top-level units these annotations name, in canonical order.

    Comparison with the diff happens here and not deeper: the metadata elides segments the
    markup keeps (`AR 3 PO 14` for `AR 3 ALN 1 PO 14`), so the two vocabularies agree
    on the unit and not always below it.
    """
    seen = {record.unit.canonical: record.unit for record in records}
    return tuple(sorted(seen.values(), key=lambda unit: unit.sort_key))


def metadata_signal(
    records: Iterable[ModificationRecord], *, note: str | None = None
) -> SignalReport:
    """The corpus-metadata signal, in the corpus-agnostic shape corroboration takes.

    **No annotation at all means the signal is unavailable, not that it saw nothing.** A window
    the corpus annotated nowhere carries no reference set, so there is nothing for the diff to
    disagree with. Reported as available it would leave every unit the diff found `ABSENT`, and
    `OBSERVED` against `ABSENT` is a dispute, so a whole transition would ship disputed on the
    strength of silence. Where the corpus *did* annotate the window there is a reference set,
    and a unit missing from it is a real disagreement that still ships `disputed`: that is the
    REACH blanket-amendment finding, and it is not what this rule touches.

    The commonest empty window is a consolidation carrying only a corrigendum. A corrigendum is
    not an amendment and no amending act annotates it, so the metadata has nothing to say about
    that pair by construction. Measured 2026-08-12 over the 30 transitions the watcher had
    emitted: all 7 empty windows were of this shape, each one the act as published in the
    Official Journal against the consolidation dated the same day, where no amending act can
    exist yet. `32017R0745@20170505` in the eval corpus is that case, and the eval report names
    the class where it lists it: a transition with no reference set to score against.

    Nothing about the act's other windows enters the decision. A claim dated 2020 is not
    evidence about what happened in 2022, so annotations outside the window cannot turn silence
    inside it into dissent. This is also the answer the instruction signal built from the same
    records gives, so the two second opinions of one pair agree about when they have nothing to
    say.
    """
    claims = tuple(record.to_claim() for record in records)
    if not claims:
        return SignalReport.unavailable(Signal.CORPUS_METADATA, note=note)
    return SignalReport(signal=Signal.CORPUS_METADATA, claims=claims, note=note)
