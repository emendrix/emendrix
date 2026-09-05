"""The markup reader: what an act's final-provisions article says about its own dates.

The companion of the prose reader in `effect.py`, and a separate module because it reads a
separate representation. *"Article 1, point (1), and Article 2, point (1), shall apply from
`<DATE ISO="20250110">`10 January 2025`</DATE>`"* (`32024R1860` Article 3) is markup: the date
is a tagged attribute and the deferred instructions are named by coordinate, which the
reference grammar resolves to `AR 1 PO 1`, the same coordinate the instruction walk writes as
`AR 001 (1)`. Reading that as a sentence would lose the tag and gain a date format problem.

Three rules carry the safety of the whole read, and all three answer *"nothing"* rather than
guessing:

- **The article has to be speaking about the act itself.** A final-provisions article says
  *"This Regulation shall apply from …"*; a scope article says *"This Regulation shall apply to
  intermediary services"* and an instruction article says what another act shall do, in that
  act's own words. Only the first is read, and quoted text is excluded everywhere.
- **A deferral scopes only the coordinate the grammar resolved.** The grammar keeps the first
  coordinate at each depth, so *"Article 1, point (1), and Article 2, point (1)"* yields
  `AR 1 PO 1` and says nothing about Article 2.
- **Every other unit a deferral names is guarded rather than dated.** Article 2 above carries
  no date at all, and neither does the whole of Article 1 where the deferral is written as an
  enumeration the grammar cannot separate (*"The following points of Article 1 … shall apply
  from 27 June 2019:"*). The act's default would be the wrong answer for part of what those
  articles drafted and this cannot say which part, so it answers nothing and those instructions
  are claimed exactly as they were before.

The act's default itself is withdrawn only where a dated statement names no unit this can read
at all, which is doubt with nowhere narrower to put it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from typing import Final
from xml.etree.ElementTree import Element

from emendrix.core import LocationCode, LocationSegment, ProvisionLocation
from emendrix.eu.dates import compact_date
from emendrix.eu.instructions.effect import QUOTED, Deferral, EffectDates, prose
from emendrix.eu.references import parse_reference

__all__ = ["read_effect_dates"]

_ACT_WIDE: Final = re.compile(
    r"\b(?:this (?:regulation|directive|decision)|it) shall (?:apply|take effect)\s+"
    r"(?:as\s+)?from\b",
    re.IGNORECASE,
)
"""The act speaking about itself. Its subject is what makes the date an act-wide default."""

_ACT_WIDE_FORCE: Final = re.compile(
    r"\b(?:this (?:regulation|directive|decision)|it) shall enter into force\b", re.IGNORECASE
)
"""The weaker act-wide answer, read only where the act names no date of application."""

_FINAL_PROVISIONS: Final = re.compile(
    f"{_ACT_WIDE.pattern}|{_ACT_WIDE_FORCE.pattern}", re.IGNORECASE
)
"""What makes an article the final-provisions one: it says when the act itself applies.

*"This Regulation shall apply to intermediary services"* is a scope article and says nothing
about a date, which is why the phrase has to reach as far as the `from`.
"""

_DEFERRAL: Final = re.compile(
    r"\bshall (?:apply|take effect)\s+(?:as\s+)?from\b|\bwith effect (?:as )?from\b",
    re.IGNORECASE,
)

_ENUMERATED: Final = re.compile(
    r"\b(?:points|paragraphs|sections|subparagraphs|indents)\b", re.IGNORECASE
)
"""A deferral written as an enumeration below the top level: read in part, never in whole."""

_UNIT_LIST: Final = re.compile(
    r"\b(Articles?|Annexes?)\s+"
    r"((?:[IVXLCDM]+|\d+[a-z]?)(?:\s*\([^)]*\))?"
    r"(?:\s*(?:,|and)\s*(?:[IVXLCDM]+|\d+[a-z]?)(?:\s*\([^)]*\))?)*)",
    re.IGNORECASE,
)
"""Every top-level unit a statement names, however the enumeration is written.

Read only to *guard* those units, never to date them: a fragment this splits wrongly costs a
date nobody reads, where a fragment resolved wrongly would cost a claim.
"""

_RANGE: Final = re.compile(r"\b(?:Articles?|Annexes?)\s+(?:[IVXLCDM]+|\d+[a-z]?)\s+to\s", re.I)
"""A range names units it does not write, so a statement carrying one is read as naming none."""

_TOP_LEVEL: Final = frozenset({LocationCode.AR, LocationCode.AN, LocationCode.APP})


def read_effect_dates(articles: Iterable[Element]) -> EffectDates:
    """What the act's final provisions say, for the act and for the coordinates they name."""
    reader = _Reader()
    for article in articles:
        if _FINAL_PROVISIONS.search(prose(article)):
            reader.read(article)
    return reader.result()


class _Reader:
    """The walk: the act's own dates, one dated statement at a time."""

    def __init__(self) -> None:
        self.application: date | None = None
        self.entry: date | None = None
        self.deferrals: list[Deferral] = []
        self.guarded: list[ProvisionLocation] = []
        self.unread = 0

    def read(self, article: Element) -> None:
        for statement in _dated_statements(article):
            self._read(prose(statement), _stated_dates(statement))

    def result(self) -> EffectDates:
        return EffectDates(
            default=None if self.unread else self.application or self.entry,
            deferrals=tuple(self.deferrals),
            guarded=tuple(dict.fromkeys(self.guarded)),
            unread=self.unread,
        )

    def _read(self, text: str, dates: set[date]) -> None:
        """One dated statement: the act's own date, a deferral, or a doubt about some units."""
        if _RANGE.search(text):
            # "Articles 95 to 98" names two units and means four. Nothing here can say which
            # they are, so the statement dates nothing and takes the act's default with it.
            self.unread += 1
            return
        stated = dates.pop() if len(dates) == 1 else None
        named = _named_units(text)
        if _ACT_WIDE.search(text) or _ACT_WIDE_FORCE.search(text):
            self._act_wide(text, stated, named)
            return
        if not _DEFERRAL.search(text):
            return
        where = parse_reference(text)
        deferred = where is not None and where.segments[0].code in _TOP_LEVEL
        container = where.top_level if where is not None and deferred else None
        self.guarded.extend(unit for unit in named if unit != container)
        if not deferred or stated is None:
            self.unread += 0 if named else 1
            return
        if _ENUMERATED.search(text) and container is not None:
            # "points (2) and (3) of Article 63": the grammar keeps the first coordinate at
            # each depth, so the rest of that article is doubted rather than defaulted.
            self.guarded.append(container)
            if where is not None and where.depth == 1:
                return
        if where is not None:
            self.deferrals.append(Deferral(location=where, effective=stated))

    def _act_wide(self, text: str, stated: date | None, named: list[ProvisionLocation]) -> None:
        """The act speaking about itself, and any exceptions it names in the same breath.

        *"It shall apply from 21 April 2021, except for Articles 270(1) and 274"* states the
        default and takes two of its own articles out of it in one sentence. The exceptions are
        guarded, so instructions drafted there carry no date at all, and the default stands for
        the rest of the act.
        """
        self.guarded.extend(named)
        if stated is None:
            return
        if _ACT_WIDE.search(text):
            self.application = self.application or stated
        else:
            self.entry = self.entry or stated


def _named_units(text: str) -> list[ProvisionLocation]:
    """The top-level units a statement names, read as a list rather than as a coordinate.

    Read only to guard those units, never to date them, so an enumeration this splits at the
    wrong comma costs a date nobody reads where a coordinate resolved wrongly would cost a claim.
    """
    found: list[ProvisionLocation] = []
    for matched in _UNIT_LIST.finditer(text):
        code = LocationCode.AN if matched[1].lower().startswith("annex") else LocationCode.AR
        for token in re.split(r"\s*(?:,|and)\s*", matched[2]):
            value = token.split("(")[0].strip()
            if not value:
                continue
            found.append(
                ProvisionLocation(
                    segments=(
                        LocationSegment(
                            code=code,
                            value=value.upper() if code is LocationCode.AN else value.lower(),
                        ),
                    )
                )
            )
    return found


def _dated_statements(article: Element) -> list[Element]:
    """The innermost elements carrying a `DATE`: one statement's worth of the article each."""
    found: list[Element] = []

    def walk(element: Element) -> bool:
        direct = False
        deeper = False
        for child in element:
            if child.tag in QUOTED:
                continue
            if child.tag == "DATE":
                direct = True
            elif walk(child):
                deeper = True
        if direct and not deeper:
            found.append(element)
        return direct or deeper

    walk(article)
    return found


def _stated_dates(statement: Element) -> set[date]:
    found = (compact_date(child.get("ISO")) for child in statement if child.tag == "DATE")
    return {stated for stated in found if stated is not None}
