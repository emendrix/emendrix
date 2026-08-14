"""EU identifier grammar: CELEX, consolidated CELEX, and the resource paths they answer on.

Three identifier families matter, and they are not interchangeable: which one resolves
depends on the age of the document (verified 2026-08-05, again 2026-08-06):

| Document | Resource path that answers |
|---|---|
| Act published before the 2023 OJ reform | `celex/32020R0561.ENG.fmx4` |
| Act published from 2023-10 | `oj/L_202401860.ENG.fmx4` (the `celex/` form **404s**) |
| Consolidation built from ~2018 on | `consolidation/2006R1907%2F20221014.ENG.fmx4` |
| Older consolidation | `celex/02006R1907-20081012.ENG.fmx4` (the `consolidation/` form 404s) |

So this module supplies *candidates*, in the order worth trying, and never claims to know
which one is live. The authoritative answer is the tree notice, which publishes the exact
resolvable identifier of every manifestation (`eu/notices.py`); these constructions are the
fallback for when it does not.

ELI appears here as identifier grammar only. It does not resolve at provision level
(`…/eli/reg/2024/1689/oj/art_5` → 404, verified 2026-08-05), so nothing is ever fetched by it.

This is the module that maps EU identifiers onto the corpus-agnostic `ActId`/`VersionId` of
`emendrix.core`. Those two are opaque outside the EU adapter; here is where they are read.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final, Self
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, VersionId

__all__ = [
    "CORPUS",
    "Celex",
    "ConsolidatedId",
    "ResourceRef",
    "VersionKey",
    "act_id",
    "celex_of",
    "parse_identifier",
    "parse_version_id",
]

CORPUS: Final = "eu"
"""The `ActId.corpus` namespace this adapter owns."""

_CELEX: Final = re.compile(r"^(?P<sector>\d)(?P<year>\d{4})(?P<type>[A-Z]{1,2})(?P<number>\d{4})$")
_CONSOLIDATED: Final = re.compile(r"^0(?P<act_code>\d{4}[A-Z]{1,2}\d{4})-(?P<version>\d{8})$")
_CONSOLIDATION_PATH: Final = re.compile(
    r"^(?P<act_code>\d{4}[A-Z]{1,2}\d{4})/(?P<version>\d{8})(?:_\d+)?$"
)
"""The `consolidation:` form the notification feed writes — `2024R1689/20260727`.

The optional `_0010010` suffix is a manifestation discriminator the feed emits beside the
bare form (seen on the AI Act's own consolidation notifications, 2026-08-06); it names the
same version, so it is read and dropped rather than counted as an unknown identifier.
"""


def _iso(compact: str) -> date:
    return date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))


class ResourceRef(BaseModel):
    """One addressable CELLAR resource: a `system` and an identifier within it.

    `system` is CELLAR's own word for the identifier family — `celex`, `oj`, `consolidation`,
    `cellar` — and it is the first path segment. The identifier is percent-encoded whole, `/`
    included: `2024R1689/20260727.ENG.fmx4` must reach the server as `2024R1689%2F20260727…`,
    and httpx will not do that for a path built naively (verified 2026-08-06).

    `system` is constrained rather than escaped, because it is *read off the notice* — a tree
    notice's `<TYPE>` element, i.e. a value the server chooses — and it lands in a path segment
    unencoded. A `<TYPE>` of `../..` would have httpx resolve the dot segments and fetch a
    different path; a `?` or `#` would split the URL. The word family is small and closed
    (`celex`, `oj`, `consolidation`, `cellar`, `eli`, `uriserv`, `language`, `immc`, `planjo` —
    the nine seen across the pinned notices, 2026-08-06), so a notice announcing something
    outside its shape is a finding, not a URL worth constructing. `eu/notices.py` counts it as
    an unreadable reference rather than letting it end a version inventory.
    """

    model_config = ConfigDict(frozen=True)

    system: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    identifier: str = Field(min_length=1)

    @property
    def path(self) -> str:
        """The path this resource answers on, relative to the CELLAR base URL."""
        return f"/resource/{self.system}/{quote(self.identifier, safe='')}"

    def __str__(self) -> str:
        return f"{self.system}:{self.identifier}"


class Celex(BaseModel):
    """A CELEX number of an act as published — `32024R1689`.

    Sector, year, descriptor and number, kept as the strings the corpus writes them as: the
    leading zeros of the number are part of the identifier (`0745`, not `745`).
    """

    model_config = ConfigDict(frozen=True)

    sector: str = Field(pattern=r"^\d$")
    year: str = Field(pattern=r"^\d{4}$")
    descriptor: str = Field(pattern=r"^[A-Z]{1,2}$")
    number: str = Field(pattern=r"^\d{4}$")

    @classmethod
    def parse(cls, raw: str) -> Self:
        matched = _CELEX.fullmatch(raw.strip().upper())
        if matched is None:
            raise ValueError(f"not a CELEX number: {raw!r}")
        return cls(
            sector=matched["sector"],
            year=matched["year"],
            descriptor=matched["type"],
            number=matched["number"],
        )

    @property
    def value(self) -> str:
        """`32024R1689` — the identity of this act."""
        return f"{self.sector}{self.year}{self.descriptor}{self.number}"

    @property
    def act_code(self) -> str:
        """`2024R1689` — the CELEX without its sector, as consolidation ids write it."""
        return f"{self.year}{self.descriptor}{self.number}"

    @property
    def oj_identifier(self) -> str:
        """`L_202401689` — the reformed-OJ identifier, constructed.

        A guess with one input (the act number) and no way to know the OJ series from the
        CELEX alone: acts in the C series, and pre-reform acts (whose OJ ids look like
        `JOL_2020_130_R_0004`), do not follow it. Verified to be right for `32024R1689` and
        `32026R1744` on 2026-08-06; use the tree notice's `oj` SAMEAS identifier when there
        is one, and treat this only as the last candidate.
        """
        return f"L_{self.year}{int(self.number):05d}"

    @property
    def version(self) -> VersionId:
        """The `VersionId` of the act as published in the OJ, i.e. its own CELEX."""
        return VersionId(self.value)

    def resource_refs(self, suffix: str = "") -> tuple[ResourceRef, ...]:
        """Resource candidates for this act, best guess first (see the module docstring)."""
        return (
            ResourceRef(system="celex", identifier=f"{self.value}{suffix}"),
            ResourceRef(system="oj", identifier=f"{self.oj_identifier}{suffix}"),
        )

    def __str__(self) -> str:
        return self.value


class ConsolidatedId(BaseModel):
    """A consolidated version of an act — `02024R1689-20260727`.

    Note what this deliberately does *not* do: reconstruct the amended act's CELEX. A
    consolidation is published in sector 0 and its identifier keeps only the act code, so
    inverting it would require assuming the act's sector. Nothing needs that — a consolidated
    id is always minted from a `Celex` that is already known.
    """

    model_config = ConfigDict(frozen=True)

    act_code: str = Field(pattern=r"^\d{4}[A-Z]{1,2}\d{4}$")
    version_date: date

    @classmethod
    def parse(cls, raw: str) -> Self:
        matched = _CONSOLIDATED.fullmatch(raw.strip().upper())
        if matched is None:
            raise ValueError(f"not a consolidated CELEX number: {raw!r}")
        return cls(act_code=matched["act_code"], version_date=_iso(matched["version"]))

    @classmethod
    def for_act(cls, act: Celex, version_date: date) -> Self:
        return cls(act_code=act.act_code, version_date=version_date)

    @property
    def compact_date(self) -> str:
        """`20260727` — the date as both identifier forms write it."""
        return self.version_date.strftime("%Y%m%d")

    @property
    def value(self) -> str:
        """`02024R1689-20260727` — the consolidated CELEX, which is also its `VersionId`."""
        return f"0{self.act_code}-{self.compact_date}"

    @property
    def consolidation_identifier(self) -> str:
        """`2024R1689/20260727` — the same version in the `consolidation` system."""
        return f"{self.act_code}/{self.compact_date}"

    @property
    def version(self) -> VersionId:
        return VersionId(self.value)

    def resource_refs(self, suffix: str = "") -> tuple[ResourceRef, ...]:
        """Resource candidates for this version, best guess first (see the module docstring)."""
        return (
            ResourceRef(
                system="consolidation", identifier=f"{self.consolidation_identifier}{suffix}"
            ),
            ResourceRef(system="celex", identifier=f"{self.value}{suffix}"),
        )

    def __str__(self) -> str:
        return self.value


VersionKey = Celex | ConsolidatedId
"""What a `VersionId` of this corpus parses back into: an OJ act, or a consolidation of one."""


def act_id(celex: Celex, *, display_name: str | None = None) -> ActId:
    """The corpus-agnostic handle for an act. `key` is its CELEX, and nothing else reads it."""
    return ActId(corpus=CORPUS, key=celex.value, display_name=display_name)


def celex_of(act: ActId) -> Celex:
    """Read an `ActId` minted by this adapter back into a CELEX."""
    if act.corpus != CORPUS:
        raise ValueError(f"not an EU act: {act}")
    return Celex.parse(act.key)


def parse_version_id(version: VersionId) -> VersionKey:
    """Read a `VersionId` minted by this adapter: consolidated version, or the OJ act itself."""
    raw = str(version)
    if _CONSOLIDATED.fullmatch(raw):
        return ConsolidatedId.parse(raw)
    return Celex.parse(raw)


def parse_identifier(raw: str) -> VersionKey | None:
    """Read any identifier the corpus writes, or answer `None` — never raise.

    Three forms resolve, and they are the three the notification feed puts on one entry for
    one consolidated act (verified 2026-08-06):

    | Written as | Reads as |
    |---|---|
    | `32024R1689`, `celex:32024R1689` | `Celex` |
    | `02024R1689-20260727`, `celex:02024R1689-20260727` | `ConsolidatedId` |
    | `consolidation:2024R1689/20260727`, with or without a `_0010010` suffix | `ConsolidatedId` |

    Everything else the feed carries — `eli:reg:2024:1689:2026-07-27`, `oj:L_202601913`,
    `ep:`, `ecli:`, `immc:` — answers `None`. That is not a gap to fix: those families name
    the same works through vocabularies this adapter does not fetch by, and an identifier it
    cannot read is a value the caller counts, not an error.
    """
    text = raw.strip().upper()
    _, _, rest = text.partition(":")
    candidate = rest if rest else text
    if _CONSOLIDATED.fullmatch(candidate):
        return ConsolidatedId.parse(candidate)
    matched = _CONSOLIDATION_PATH.fullmatch(candidate)
    if matched is not None:
        return ConsolidatedId(act_code=matched["act_code"], version_date=_iso(matched["version"]))
    if _CELEX.fullmatch(candidate):
        return Celex.parse(candidate)
    return None
