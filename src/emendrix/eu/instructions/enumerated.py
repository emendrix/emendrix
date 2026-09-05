"""A dated statement that writes out every point it defers, read to all of them.

A third module beside `effect.py` and `final_provisions.py`, and not more of either: both are
at the package's size cap, and what this reads is a grammar rather than a rule. The rule it
serves is in `final_provisions.py`, which calls this first and falls back to its own reading
unchanged when this answers nothing.

The shape, read verbatim out of `32021R2117` Article 6 on 2026-09-05:

    Article 1, points (8)(d)(i), (8)(d)(iii), (10)(a)(ii) and (38), shall apply from
    <DATE ISO="20210101">1 January 2021</DATE>.

`eu/references.py` keeps the first coordinate at each nesting depth, which is right for an
instruction clause pointing at one provision and wrong here: this statement names four, and
reading it as `AR 1 PO 8` alone defers one of them and leaves the reader with a doubt about
the whole article. So the subject of the statement is parsed as a list, strictly, and the
coordinates it yields are folded by `effect.marker_segment`, the one notion of what an
enumerator is that this package has.

**Strict means the whole subject or nothing.** Every fragment must parse, nothing may be left
over, and a statement carrying a range (*"points (11) to (14)"*), a second act
(*"as regards Article 104a of Regulation (EU) No 575/2013"*), a description
(*"containing the provisions on own funds"*) or a list written elsewhere
(*"The following points of Article 1 … :"*) parses as nothing at all. The caller then doubts
it exactly as it did before this module existed. Over-scoping deletes a true claim and
under-scoping leaves one where it already is, so the failure direction is the refusal.
"""

from __future__ import annotations

import re
from typing import Final

from emendrix.core import LocationCode, LocationSegment, ProvisionLocation
from emendrix.eu.instructions.effect import marker_segment

__all__ = ["read_enumerated"]

_LEAD_IN: Final = re.compile(
    r"\s*(?:however|additionally|moreover|furthermore|in addition)\s*,\s*", re.IGNORECASE
)
"""A connective the drafting opens the sentence with. It says nothing about a coordinate."""

_UNIT: Final = re.compile(
    r"\s*(?:(?P<article>Articles?)\s+(?P<art>\d+[a-z]?)"
    r"|(?P<annex>Annex(?:es)?)\s+(?P<an>(?-i:[IVXLCDM]+)|\d+[a-z]?))\b",
    re.IGNORECASE,
)
"""A top-level unit of the *amending* act, spelled as `eu/references.py` spells the same one."""

_POINTS: Final = re.compile(r"\s*points?\s+", re.IGNORECASE)
_PATH: Final = re.compile(r"\s*(?:\(\s*[0-9A-Za-z]{1,4}\s*\))+")
"""`(8)(d)(i)`: a point and the enumerators under it, parenthesised, with nothing between."""

_MARKERS: Final = re.compile(r"\(\s*([0-9A-Za-z]{1,4})\s*\)")
_SEPARATOR: Final = re.compile(r"\s*(?:,\s*(?:and\s+)?|and\s+)", re.IGNORECASE)
_COMMA: Final = re.compile(r"\s*,\s*")
_OF: Final = re.compile(r"\s*of\s+", re.IGNORECASE)
_OF_THIS_ACT: Final = re.compile(
    r"\s*of\s+this\s+(?:amending\s+)?(?:Regulation|Directive|Decision)\b", re.IGNORECASE
)
"""The act naming itself. Anything else after `of` is a second act and refuses the read."""

_END: Final = re.compile(r"\s*,?\s*$")


def read_enumerated(subject: str) -> tuple[ProvisionLocation, ...] | None:
    """Every coordinate `subject` names, or `None` where it does not name them all explicitly.

    `subject` is the dated statement's words up to its deferral phrase, quoted text already
    excluded. `None` is the answer to anything this grammar does not cover in full, which is
    the caller's signal to read the statement the way it read it before.
    """
    scanner = _Scanner(subject)
    found = scanner.subject()
    return None if found is None else tuple(dict.fromkeys(found))


class _Scanner:
    """A cursor over the subject. Every rule either advances it or leaves it where it was."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.at = 0

    def subject(self) -> list[ProvisionLocation] | None:
        """`fragment (separator fragment)*`, and every character of the subject consumed."""
        self._take(_LEAD_IN)
        found = self._fragment()
        if found is None:
            return None
        while True:
            mark = self.at
            if not self._take(_SEPARATOR):
                break
            more = self._fragment()
            if more is None:
                self.at = mark
                break
            found.extend(more)
        return found if self._take(_END) else None

    def _fragment(self) -> list[ProvisionLocation] | None:
        """One unit and the points listed under it, in either order the drafting writes them."""
        mark = self.at
        unit = self._unit()
        if unit is not None:
            if self._take(_COMMA):
                paths = self._points()
                if paths is not None:
                    return [ProvisionLocation(segments=(unit, *path)) for path in paths]
            self.at = mark
            return None
        paths = self._points()
        if paths is None or not self._take(_OF):
            self.at = mark
            return None
        unit = self._unit()
        if unit is None:
            self.at = mark
            return None
        self._take(_OF_THIS_ACT)
        return [ProvisionLocation(segments=(unit, *path)) for path in paths]

    def _unit(self) -> LocationSegment | None:
        matched = self._take(_UNIT)
        if matched is None:
            return None
        if matched["article"]:
            return LocationSegment(code=LocationCode.AR, value=matched["art"].lower())
        return LocationSegment(code=LocationCode.AN, value=matched["an"].upper())

    def _points(self) -> list[tuple[LocationSegment, ...]] | None:
        if not self._take(_POINTS):
            return None
        first = self._path()
        if first is None:
            return None
        found = [first]
        while True:
            mark = self.at
            if not self._take(_SEPARATOR):
                break
            more = self._path()
            if more is None:
                self.at = mark
                break
            found.append(more)
        return found

    def _path(self) -> tuple[LocationSegment, ...] | None:
        """`(8)(d)(i)` → `PO 8 PTA (d) PTA (i)`, in the spelling the instruction walk writes."""
        mark = self.at
        matched = self._take(_PATH)
        if matched is None:
            return None
        segments: list[LocationSegment] = []
        for marker in _MARKERS.findall(matched[0]):
            segment = marker_segment(marker)
            if segment is None:
                self.at = mark
                return None
            segments.append(segment)
        return tuple(segments)

    def _take(self, pattern: re.Pattern[str]) -> re.Match[str] | None:
        matched = pattern.match(self.text, self.at)
        if matched is None:
            return None
        self.at = matched.end()
        return matched
