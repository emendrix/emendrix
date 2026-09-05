"""When an amending act's own instructions take effect: the four answers and the clause reader.

The date an instruction takes effect is in the amending act's own text, in two representations,
which is why reading it is two modules rather than more of `read.py` (already at the package's
size cap). An instruction states its own deferral in **prose**, inside the clause the walk
already builds: `32019R2033` Article 62(14) reads *"… Section 2 (Articles 95 to 98) is deleted
with effect from 26 June 2026;"*. The act's final-provisions article states one in **markup**,
where `<DATE ISO="20250110">` is the attribute `eu/dates.py` already reads; that reader is
`final_provisions.py`, and flattening it into this one would throw away the one date the
Publications Office tags for exactly this purpose.

Four answers, in this order, and the fourth is a counted gap rather than a guess:

1. the clause's own effect date;
2. the final-provisions article, where it names the coordinate the clause was drafted at;
3. the act's own date of application, for every instruction the first two do not reach;
4. nothing, counted as `EffectDateSource.UNREAD`.

**Only a date attached to a coordinate the parser itself wrote may scope that coordinate.**
A date loose in the act names no instruction and is never attached to one; the act's date of
application is the one act-wide answer, and `final_provisions.py` withdraws it the moment it
meets a deferral it cannot attribute. A record with no effect date is claimed exactly as it was
before this module existed, which is the safe direction of every failure here.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Final
from xml.etree.ElementTree import Element

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import LocationCode, LocationSegment, ProvisionLocation
from emendrix.core import normalize_for_comparison as _normalize
from emendrix.eu.formex.locations import decode_identifier

__all__ = [
    "Deferral",
    "EffectDateSource",
    "EffectDates",
    "clause_effect_date",
    "prose",
    "source_location",
]

_MONTHS: Final[dict[str, int]] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_WRITTEN_DATE: Final = re.compile(
    rf"(\d{{1,2}})\s+({'|'.join(_MONTHS)})\s+(\d{{4}})", re.IGNORECASE
)
"""A date as the drafting writes it in a sentence. The markup spelling is `eu/dates.py`."""

_CLAUSE_EFFECT: Final = re.compile(r"\bwith effect (?:as )?from\s+(?:the\s+)?", re.IGNORECASE)
"""The one phrase that defers an instruction inside its own clause, verified on `32019R2033`.

Deliberately not *"shall apply from"*: a clause carries the amended act's words as well as its
own, and that phrase belongs to the text being replaced as often as to the instruction.
"""

QUOTED: Final = frozenset({"QUOT.S"})
"""What an act quotes is another act's prose, and never a statement about this act's dates."""

_MARKER: Final = re.compile(r"^\(?([0-9A-Za-z]{1,4})\)?\.?$")


class EffectDateSource(StrEnum):
    """Which of the four answers a record's effect date came from. `UNREAD` is the gap."""

    CLAUSE = "clause"
    FINAL_PROVISIONS = "final provisions"
    ACT_DEFAULT = "act default"
    UNREAD = "unread"


class Deferral(BaseModel):
    """One coordinate of the amending act, and the date the instructions under it take effect."""

    model_config = ConfigDict(frozen=True)

    location: ProvisionLocation = Field(
        description="Where in the *amending* act, e.g. `AR 1 PO 1` for `Article 1, point (1)`."
    )
    effective: date


class EffectDates(BaseModel):
    """What one amending act says about when its own instructions take effect.

    `default` is already `None` where the reader met a deferral it could not attribute, so a
    caller never has to know that rule in order to apply this safely.
    """

    model_config = ConfigDict(frozen=True)

    default: date | None = Field(
        default=None, description="The act's own date of application, where it states one."
    )
    deferrals: tuple[Deferral, ...] = ()
    guarded: tuple[ProvisionLocation, ...] = Field(
        default=(),
        description="Coordinates whose deferral was read in part; the default is withdrawn there.",
    )
    unread: int = Field(
        default=0,
        description="Dated statements about this act's own coordinates that it could not use.",
    )

    def for_clause(self, clause: str, source_ref: str) -> tuple[date | None, EffectDateSource]:
        """The effect date of one instruction, in the four-tier order, and where it came from."""
        stated = clause_effect_date(clause)
        if stated is not None:
            return stated, EffectDateSource.CLAUSE
        return self._for_source(source_location(source_ref))

    def _for_source(self, source: ProvisionLocation | None) -> tuple[date | None, EffectDateSource]:
        if source is not None:
            deferred = self._deferred(source)
            if deferred is not None:
                return deferred, EffectDateSource.FINAL_PROVISIONS
            if self._doubted(source):
                return None, EffectDateSource.UNREAD
        if self.default is None:
            return None, EffectDateSource.UNREAD
        return self.default, EffectDateSource.ACT_DEFAULT

    def _deferred(self, source: ProvisionLocation) -> date | None:
        """The date of the most specific deferral covering `source`, where those agree."""
        covering = [item for item in self.deferrals if item.location.contains(source)]
        if not covering:
            return None
        deepest = max(item.location.depth for item in covering)
        dates = {item.effective for item in covering if item.location.depth == deepest}
        return dates.pop() if len(dates) == 1 else None

    def _doubted(self, source: ProvisionLocation) -> bool:
        """True where a deferral reaches inside `source`, or one covering it was read in part.

        Either way the act's default is the wrong answer for part of what this coordinate
        drafted, and the reader cannot say which part, so it answers nothing at all.
        """
        return any(where.contains(source) for where in self.guarded) or any(
            source.contains(item.location) for item in self.deferrals
        )


def prose(node: Element, *, skipped: frozenset[str] = QUOTED) -> str:
    """The element's own words, with the named subtrees left out.

    A separator at every element boundary, exactly as `eu/formex/text.py` builds a comparison
    form: the reference grammar reads words, and a lost boundary is a lost reference.
    """
    parts: list[str] = []

    def walk(element: Element) -> None:
        if element.text:
            parts.append(element.text)
        for child in element:
            if child.tag not in skipped:
                walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(node)
    return _normalize(" ".join(parts))


def clause_effect_date(clause: str) -> date | None:
    """The date an instruction clause defers itself to, or `None` when it states none.

    Two effect phrases naming two dates is a clause this cannot attribute, and it answers
    `None` rather than picking one of them.
    """
    found: set[date] = set()
    for phrase in _CLAUSE_EFFECT.finditer(clause):
        written = _WRITTEN_DATE.match(clause, phrase.end())
        if written is None:
            continue
        stated = _written_date(written)
        if stated is not None:
            found.add(stated)
    return found.pop() if len(found) == 1 else None


def source_location(source_ref: str) -> ProvisionLocation | None:
    """`'AR 001 (1) (b)'` → `AR 1 PO 1 PTA (b)`: the coordinate in the *amending* act.

    The instruction walk writes the amending article's own `IDENTIFIER` and the enumerators
    below it; the reference grammar spells the same coordinate `AR 1 PO 1` when the act's own
    final provisions name it. The two are folded onto one form here and compared as locations
    rather than as strings. A marker this cannot read ends the path, which is a coarser
    coordinate and never a wrong one.
    """
    tokens = source_ref.split()
    if len(tokens) < 2 or tokens[0] != str(LocationCode.AR):
        return None
    article = decode_identifier(tokens[1])
    if article is None:
        return None
    segments = [LocationSegment(code=LocationCode.AR, value=article)]
    for token in tokens[2:]:
        segment = _marker_segment(token)
        if segment is None:
            break
        segments.append(segment)
    return ProvisionLocation(segments=tuple(segments))


def _written_date(matched: re.Match[str]) -> date | None:
    try:
        return date(int(matched[3]), _MONTHS[matched[2].lower()], int(matched[1]))
    except ValueError:
        return None


def _marker_segment(token: str) -> LocationSegment | None:
    """An enumerator as the instruction walk wrote it, in the grammar's own spelling.

    Numbered points are `PO 14` and lettered ones `PTA (g)`, which is what `eu/references.py`
    produces for the same enumerator in prose. The markup vocabulary's `PTI` is not used here,
    because a deferral is only ever compared against a coordinate read out of prose.
    """
    matched = _MARKER.fullmatch(token)
    if matched is None:
        return None
    value = matched[1]
    if value.isdigit():
        return LocationSegment(code=LocationCode.PO, value=value)
    return LocationSegment(code=LocationCode.PTA, value=f"({value.lower()})")
