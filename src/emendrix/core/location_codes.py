"""The location-code vocabulary and one step of a location path.

Split out of `location.py` along a real seam. This module is the *vocabulary*: which codes
exist, how they rank, and what happens to a code nobody has seen before. `location.py` is the
*path* built out of it.

It knows nothing about which corpus emits these codes or how their values are written.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from emendrix.core.ordering import SortKey, natural_key

__all__ = [
    "LocationCode",
    "LocationSegment",
    "SegmentCode",
    "UnknownCode",
    "is_known_code",
]


class LocationCode(StrEnum):
    """The location-code vocabulary, as observed in real corpus metadata.

    Members are declared in rough document order (articles before annexes), and that
    order is the ordering rank used when two sibling segments carry different codes.

    Readings are empirical: the authority tables that publish these codes carry no
    English labels. This set is every code seen across 540 modification annotations of
    three acts spanning 2006 to 2026, counted on 2026-08-05; see
    `scripts/validation/results/*-annotations.txt`.
    Note the three legacy spelling pairs (`TXT`/`TEXT`, `SCT`/`SECTION`, `TAB`/`TABL`),
    kept distinct so that parsing round-trips, and folded by `preferred`.
    """

    AR = "AR"  # article
    TIT = "TIT"  # title
    PRT = "PRT"  # part
    SCT = "SCT"  # section
    SECTION = "SECTION"  # section (legacy long spelling of SCT)
    SBS = "SBS"  # subsection
    PA = "PA"  # paragraph
    ALN = "ALN"  # alinea (unnumbered sub-paragraph)
    PTA = "PTA"  # lettered point, e.g. (bb)
    PO = "PO"  # numbered point
    PT = "PT"  # point (alternative spelling seen in annex numbering)
    PTI = "PTI"  # sub-point, e.g. (ii)
    TIRE = "TIRE"  # indent
    FR = "FR"  # sentence/fragment
    TXT = "TXT"  # the text of the enclosing unit
    TEXT = "TEXT"  # text (legacy long spelling of TXT)
    TAB = "TAB"  # table
    TABL = "TABL"  # table (legacy long spelling of TAB)
    COL = "COL"  # table column
    NOTE = "NOTE"  # note
    FOOTNOTE = "FOOTNOTE"  # footnote
    AN = "AN"  # annex
    APP = "APP"  # appendix

    @property
    def preferred(self) -> LocationCode:
        """The preferred spelling of this code (`TEXT` → `TXT`, `SECTION` → `SCT`, …).

        Use it when comparing codes for meaning. Never use it when building a canonical
        string: the canonical form preserves the spelling the corpus actually used.
        """
        return _SPELLING_ALIASES.get(self, self)


_SPELLING_ALIASES: Final[dict[LocationCode, LocationCode]] = {
    LocationCode.TEXT: LocationCode.TXT,
    LocationCode.SECTION: LocationCode.SCT,
    LocationCode.TABL: LocationCode.TAB,
}

_CODE_RANK: Final[dict[str, int]] = {code.value: rank for rank, code in enumerate(LocationCode)}
_UNKNOWN_RANK: Final = len(_CODE_RANK)

_UNKNOWN_WRAPPER: Final = re.compile(r"^UNKNOWN\((.+)\)$")


def is_known_code(token: str) -> bool:
    """True if `token` is a code in the vocabulary: the one lexical test the parser makes."""
    return token in _CODE_RANK


class UnknownCode(BaseModel):
    """A location code outside `LocationCode`: the `UNKNOWN(str)` escape hatch.

    Real corpora emit codes no vocabulary anticipated (`CONSID 61`, `TIS IV`) and the
    occasional malformed value (`A02P1LB`). Those are carried through as data so they
    can be counted in coverage statistics, never dropped and never raised on.
    """

    model_config = ConfigDict(frozen=True)

    # No whitespace: a code is one token, and a canonical string that re-parsed into a
    # different path would break the round-trip guarantee locations are identified by.
    raw: str = Field(min_length=1, pattern=r"^\S+$")

    @model_validator(mode="before")
    @classmethod
    def _accept_plain_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            wrapped = _UNKNOWN_WRAPPER.match(data)
            return {"raw": wrapped.group(1) if wrapped else data}
        return data

    @model_serializer
    def _serialize(self) -> str:
        return f"UNKNOWN({self.raw})"

    def __str__(self) -> str:
        return self.raw


SegmentCode = LocationCode | UnknownCode
"""A code, known or not. Nothing downstream may assume it is in the vocabulary."""


class LocationSegment(BaseModel):
    """One `(code, value)` step of a location path. The value may be absent (`AR 65 TXT`)."""

    model_config = ConfigDict(frozen=True)

    code: SegmentCode = Field(union_mode="left_to_right")
    value: str | None = Field(default=None, pattern=r"^\S+$")

    def __str__(self) -> str:
        return str(self.code) if self.value is None else f"{self.code} {self.value}"

    @property
    def sort_key(self) -> tuple[int, str, SortKey]:
        rank = _CODE_RANK.get(str(self.code), _UNKNOWN_RANK)
        return (rank, str(self.code), natural_key(self.value or ""))
