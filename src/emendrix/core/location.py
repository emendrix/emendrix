"""Where in an act a change lands: the canonical provision location.

A location is a path of `(code, value)` segments (`AR 5 PA 1 ALN 1 PTA (bb)`, `AN III`) parsed
from, and serialised back to, one canonical string. The string is the identity: it is what
changes are keyed by, what goes in sets, and what appears in the JSON output.

This module knows the *grammar* of that path and nothing else. It does not know which corpus
produced it, what a "regulation" is, or how to fetch anything. The vocabulary of codes it is
built from lives in `location_codes.py`; codes outside that vocabulary are carried as
`UnknownCode` rather than rejected, because coverage gaps are counted, not crashed on.
"""

from __future__ import annotations

import re
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from emendrix.core.location_codes import (
    LocationCode,
    LocationSegment,
    SegmentCode,
    UnknownCode,
    is_known_code,
)
from emendrix.core.ordering import SortKey

__all__ = ["ProvisionLocation", "normalize_location"]

# The raw corpus value spells each code as a `{CODE|authority-uri}` template, one per segment:
# the committed notice fixtures carry
# `{AN|http://publications.europa.eu/resource/authority/fd_370/AN} 4` for what this project
# keys as `AN 4` (verified 2026-08-05 against the live notices, and re-checkable in
# `tests/fixtures/eu/`).
_TEMPLATE: Final = re.compile(r"\{(\w+)\|[^}]*\}")


def normalize_location(raw: str) -> str:
    """Canonicalise a raw location string: strip `{CODE|uri}` templates, collapse spaces.

    `'{AR|http://…/fd_370/AR} 52 {PA|…/PA} 4'` → `'AR 52 PA 4'`.
    """
    return " ".join(_TEMPLATE.sub(r"\1", raw).split())


def _parse_segments(raw: str) -> tuple[LocationSegment, ...]:
    """Split a normalised location string into segments.

    The grammar is positional, not lexical: at a segment boundary the next token is the
    code (known, or `UnknownCode`), and the token after it is that code's value unless
    it is itself a known code. That rule alone reproduces every form the live notices
    carried on 2026-08-05, including valueless codes (`AN IX ALN`), stray tokens
    (`AR 3 .20 PO B)`) and values that are not numbers (`PTA (bb)`, `NOTE A`).
    """
    tokens = normalize_location(raw).split()
    segments: list[LocationSegment] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        code: SegmentCode = LocationCode(token) if is_known_code(token) else UnknownCode(raw=token)
        value: str | None = None
        if index + 1 < len(tokens) and not is_known_code(tokens[index + 1]):
            value = tokens[index + 1]
            index += 1
        segments.append(LocationSegment(code=code, value=value))
        index += 1
    return tuple(segments)


# Codes whose value is conventionally written in parentheses when a human reads the
# location aloud: `Art. 5(1)(bb)`. Everything else gets a spelled-out label.
_PARENTHESISED: Final = frozenset(
    {
        LocationCode.PA,
        LocationCode.ALN,
        LocationCode.PTA,
        LocationCode.PO,
        LocationCode.PT,
        LocationCode.PTI,
        LocationCode.TIRE,
        LocationCode.FR,
    }
)
_HUMAN_LABELS: Final[dict[LocationCode, str]] = {
    LocationCode.TIT: "title",
    LocationCode.PRT: "part",
    LocationCode.SCT: "section",
    LocationCode.SECTION: "section",
    LocationCode.SBS: "subsection",
    LocationCode.TXT: "text",
    LocationCode.TEXT: "text",
    LocationCode.TAB: "table",
    LocationCode.TABL: "table",
    LocationCode.COL: "column",
    LocationCode.NOTE: "note",
    LocationCode.FOOTNOTE: "footnote",
    LocationCode.AN: "annex",
    LocationCode.APP: "appendix",
    LocationCode.AR: "article",
}


def _render_head(segment: LocationSegment) -> str:
    if segment.code is LocationCode.AR and segment.value is not None:
        return f"Art. {segment.value}"
    if segment.code is LocationCode.AN and segment.value is not None:
        return f"Annex {segment.value}"
    return str(segment)


def _render_tail(segment: LocationSegment) -> str:
    code = segment.code
    if code in _PARENTHESISED and segment.value is not None:
        return segment.value if segment.value.startswith("(") else f"({segment.value})"
    label = code.raw if isinstance(code, UnknownCode) else _HUMAN_LABELS.get(code, str(code))
    return f" {label}" if segment.value is None else f" {label} {segment.value}"


class ProvisionLocation(BaseModel):
    """A path of segments identifying a provision inside one act.

    The canonical string is the identity: locations are compared, hashed, set-membered and
    serialised by it, so parsing round-trips exactly,
    `ProvisionLocation.parse(s).canonical == normalize_location(s)`.
    """

    model_config = ConfigDict(frozen=True)

    segments: tuple[LocationSegment, ...] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _accept_canonical_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"segments": _parse_segments(data)}
        return data

    @model_serializer
    def _serialize(self) -> str:
        return self.canonical

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Parse a raw or canonical location string. Raises if it holds no segment."""
        return cls(segments=_parse_segments(raw))

    @property
    def canonical(self) -> str:
        """The canonical string form: the identity of this location."""
        return " ".join(str(segment) for segment in self.segments)

    @property
    def top_level(self) -> ProvisionLocation:
        """The top-level unit this location sits in (the unit of change)."""
        return ProvisionLocation(segments=self.segments[:1])

    @property
    def depth(self) -> int:
        return len(self.segments)

    def child(self, code: SegmentCode, value: str | None = None) -> ProvisionLocation:
        """This location extended by one segment."""
        return ProvisionLocation(segments=(*self.segments, LocationSegment(code=code, value=value)))

    def contains(self, other: ProvisionLocation) -> bool:
        """True if `other` is this location or lies within it (`AR 5` contains `AR 5 PA 1`)."""
        return other.segments[: len(self.segments)] == self.segments

    def is_within(self, other: ProvisionLocation) -> bool:
        """True if this location is `other` or lies within it."""
        return other.contains(self)

    @property
    def sort_key(self) -> tuple[tuple[int, str, SortKey], ...]:
        return tuple(segment.sort_key for segment in self.segments)

    def __lt__(self, other: ProvisionLocation) -> bool:
        return self.sort_key < other.sort_key

    @property
    def human(self) -> str:
        """Display form: `Art. 5(1)(bb)`, `Annex III`, `Annex VI part C section 6.6.2`.

        Lossless but not authoritative: every segment is rendered, including structural ones a
        lawyer would leave implicit. The canonical string, not this, is the identity.
        """
        head, *tail = self.segments
        return _render_head(head) + "".join(_render_tail(segment) for segment in tail)

    def __str__(self) -> str:
        return self.canonical
