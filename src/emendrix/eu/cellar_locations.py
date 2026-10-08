"""CELLAR location codes read as the units the Formex markup names.

The modification annotations of a branch notice key a change by a location code, and three
shapes of that code do not name the unit the structural diff keys the same provision by:

- a dotted article, `AR 3.1`, which is Article 3 with a sub-provision written into its number;
- an annex numbered in Arabic, `AN 4`, which legacy notices write where the markup and the newer
  notices write `AN IV`;
- a container or a recital, `CHA III`, `PRT 2`, `TIT XI`, `CONSID 5` or a bare `AN`, which names
  no article or annex at all.

The first two are notations and are rewritten to the markup's spelling. The third is not a unit
of change and is returned as a `ContainerKey`, for the caller to count as a coverage gap rather
than claim. An Arabic annex number outside the converter's range is returned as an
`UnconvertedAnnex` and counted the same way, never guessed at.

Only the head of the code is read; a sub-provision tail rides along unchanged
(`AR 3.1 PA 2` is `AR 3 PA 2`). The function is pure and idempotent, so it can be applied to the
raw notice value as it is read and again to a location already stored in a published claim.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import normalize_location
from emendrix.core.location_codes import is_known_code

__all__ = [
    "ROMAN_LIMIT",
    "CodeGap",
    "ContainerKey",
    "ContainerKind",
    "UnconvertedAnnex",
    "gap_note",
    "roman",
    "unit_code",
]

ROMAN_LIMIT: Final = 50
"""The largest annex number converted; a larger one is counted as a gap, not guessed at."""


class ContainerKind(StrEnum):
    """A CELLAR head code that names a container or a recital, never an article or an annex."""

    PART = "PRT"
    CHAPTER = "CHA"
    TITLE = "TIT"
    SUBTITLE = "TIS"
    SECTION = "SCT"
    SECTION_LONG = "SECTION"
    P = "P"
    RECITAL = "CONSID"
    UNNUMBERED_ANNEX = "AN"


# Every head code found keying a modification annotation in the 446 entries of the published
# changelog on 2026-10-08 that names neither an article nor an annex. A bare `AN` is the annexes
# as a whole and is matched only when it carries no number.
_CONTAINERS: Final = frozenset(kind.value for kind in ContainerKind) - {"AN"}


class ContainerKey(BaseModel):
    """A location that names a container or a recital: counted, never a unit of change."""

    model_config = ConfigDict(frozen=True)

    kind: ContainerKind = Field(description="The container the head code names.")
    raw: str = Field(description="The normalised location as the corpus wrote it.")


class UnconvertedAnnex(BaseModel):
    """An annex numbered in Arabic beyond `ROMAN_LIMIT`: counted, never guessed at."""

    model_config = ConfigDict(frozen=True)

    raw: str = Field(description="The normalised location as the corpus wrote it.")


CodeGap = ContainerKey | UnconvertedAnnex
"""A location code that names no unit of change, for the caller to count."""

_DOTTED: Final = re.compile(r"^(\d+[a-z]*)\.\d")
_ARABIC: Final = re.compile(r"^\d+$")
_NUMERALS: Final = (
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


def roman(number: int) -> str | None:
    """`4` is `IV`; `None` outside 1 to `ROMAN_LIMIT`, where this reader does not convert."""
    if not 1 <= number <= ROMAN_LIMIT:
        return None
    digits: list[str] = []
    for value, numeral in _NUMERALS:
        while number >= value:
            digits.append(numeral)
            number -= value
    return "".join(digits)


def unit_code(raw: str) -> str | CodeGap:
    """The location in the markup's spelling, or the gap it is when it names no unit.

    `AR 3.1` is `AR 3`, `AN 4` is `AN IV`, and every other unit comes back normalised and
    otherwise as written. `CHA III` is a `ContainerKey`; `AN 51` is an `UnconvertedAnnex`.
    """
    location = normalize_location(raw)
    tokens = location.split()
    if not tokens:
        return location
    head = tokens[0]
    value = tokens[1] if len(tokens) > 1 and not is_known_code(tokens[1]) else None
    tail = tokens[2:] if value is not None else tokens[1:]
    if head in _CONTAINERS or (head == "AN" and value is None):
        return ContainerKey(kind=ContainerKind(head), raw=location)
    if value is None:
        return location
    if head == "AR" and (dotted := _DOTTED.match(value)):
        return " ".join(("AR", dotted.group(1), *tail))
    if head == "AN" and _ARABIC.match(value):
        numeral = roman(int(value))
        if numeral is None:
            return UnconvertedAnnex(raw=location)
        return " ".join(("AN", numeral, *tail))
    return location


def gap_note(note: str | None, gaps: Iterable[CodeGap | None]) -> str | None:
    """`note`, extended by how many annotations of a window named no unit, when any did."""
    found = tuple(gap for gap in gaps if gap is not None)
    containers = sum(isinstance(gap, ContainerKey) for gap in found)
    clauses = [note] if note else []
    if containers:
        clauses.append(
            f"{containers} annotations named a part, chapter, title or recital "
            "and are not counted as units"
        )
    if unconverted := len(found) - containers:
        clauses.append(f"{unconverted} annotations named an annex by a number not converted")
    return "; ".join(clauses) if found else note
