"""The markup reader: what an act's final-provisions article says about its own dates.

The companion of the prose reader in `effect.py`, and a separate module because it reads a
separate representation. *"Article 1, point (1), and Article 2, point (1), shall apply from
`<DATE ISO="20250110">`10 January 2025`</DATE>`"* (`32024R1860` Article 3) is markup: the date
is a tagged attribute and the deferred instructions are named by coordinate, which the
reference grammar resolves to `AR 1 PO 1`, the same coordinate the instruction walk writes as
`AR 001 (1)`. Reading that as a sentence would lose the tag and gain a date format problem.

Four rules carry the safety of the whole read, and each answers *"nothing"* rather than
guessing:

- **The article has to be speaking about the act itself.** A final-provisions article says
  *"This Regulation shall apply from …"*; a scope article says *"This Regulation shall apply to
  intermediary services"* and an instruction article says what another act shall do, in that
  act's own words. Only the first is read, and quoted text is excluded everywhere.
- **A statement that writes out every point it defers is read to all of them.** The sentence
  above names two coordinates and both are deferred; `32021R2117` Article 6 names twenty over
  four sentences and all twenty are. That grammar is `enumerated.py`, and it refuses anything
  it does not cover in full, which leaves the two rules below in charge of the rest.
- **Otherwise a deferral scopes only the coordinate the reference grammar resolved**, which
  keeps the first coordinate at each depth.
- **Every other unit such a deferral names is guarded rather than dated.** The whole of
  Article 1 carries no date where the deferral is written as an enumeration this cannot
  separate (*"The following points of Article 1 … shall apply from 27 June 2019:"*, whose
  points are listed in a sub-list, half of them with ranges and other acts in them). The act's
  default would be the wrong answer for part of what that article drafted and this cannot say
  which part, so it answers nothing and those instructions are claimed exactly as they were
  before.

The act's default itself is withdrawn only where a dated statement names no unit this can read
at all, which is doubt with nowhere narrower to put it.

The act's *notice* has its own act-wide answer (`notice_dates.py`), withheld wherever the
notice dates part of the act separately, because the notice never says which part. This reader
is the one document that can say: where every dated statement of the act was read in full and
the days they attribute cover every day the notice staged, the staging is placed and the
notice's answer stands for the rest. Anything read in part leaves that answer where it was.
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
from emendrix.eu.instructions.enumerated import read_enumerated
from emendrix.eu.instructions.notice_dates import ActDates
from emendrix.eu.references import parse_reference

__all__ = ["FINAL_PROVISIONS", "read_effect_dates"]

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

FINAL_PROVISIONS: Final = re.compile(
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


def read_effect_dates(articles: Iterable[Element], *, dates: ActDates | None = None) -> EffectDates:
    """What the act's final provisions say, for the act and for the coordinates they name.

    `dates` is the act's own CELLAR notice (`notice_dates.py`), a value passed down from the
    composition root because the notice is a different document. Only its act-wide answer is
    taken, and the tier order that decides when that answer is read at all is `effect.py`.
    """
    reader = _Reader(dates=dates)
    for article in articles:
        if FINAL_PROVISIONS.search(prose(article)):
            reader.read(article)
    return reader.result()


class _Reader:
    """The walk: the act's own dates, one dated statement at a time."""

    def __init__(self, *, dates: ActDates | None = None) -> None:
        self.dates = dates
        self.application: date | None = None
        self.entry: date | None = None
        self.deferrals: list[Deferral] = []
        self.guarded: list[ProvisionLocation] = []
        self.placed: set[date] = set()
        self.partial = 0
        self.unread = 0

    def read(self, article: Element) -> None:
        for statement in _dated_statements(article):
            self._read(prose(statement), _stated_dates(statement))

    def result(self) -> EffectDates:
        return EffectDates(
            default=None if self.unread else self.application or self.entry,
            published=self._published(),
            deferrals=tuple(self.deferrals),
            guarded=tuple(dict.fromkeys(self.guarded)),
            unread=self.unread,
        )

    def _published(self) -> date | None:
        """The act-wide day its notice publishes, where the notice can place what it staged.

        A notice that dates part of an act separately publishes no act-wide answer on its own,
        because it never says which part. Where this reader read every dated statement of the
        act in full, it does say: each staged day is the day of a deferral written out here,
        so what is left is the rest of the act and the notice's own answer covers it.

        Only a statement read in full may place a day. A statement read to its first
        coordinate has left the reader not knowing what else that day covers, which is the
        same not-knowing the notice has, and two of those do not make an answer.
        """
        if self.dates is None:
            return None
        if self.unread or self.guarded or self.partial:
            return self.dates.default
        return self.dates.default_beside(self.placed)

    def _read(self, text: str, tagged: set[date]) -> None:
        """One dated statement: the act's own date, a deferral, or a doubt about some units.

        `tagged` is what the statement's own `DATE` elements say, not the act's notice.
        """
        if _RANGE.search(text):
            # "Articles 95 to 98" names two units and means four. Nothing here can say which
            # they are, so the statement dates nothing and takes the act's default with it.
            self.unread += 1
            return
        stated = tagged.pop() if len(tagged) == 1 else None
        named = _named_units(text)
        if _ACT_WIDE.search(text) or _ACT_WIDE_FORCE.search(text):
            self._act_wide(text, stated, named)
            return
        deferral = _DEFERRAL.search(text)
        if deferral is None:
            return
        if stated is not None:
            listed = read_enumerated(text[: deferral.start()])
            if listed is not None:
                # Every point the statement defers is written out in it, so there is nothing
                # left to doubt: the rest of the units it names keep the act's own default.
                self.deferrals.extend(
                    Deferral(location=where, effective=stated) for where in listed
                )
                self.placed.add(stated)
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
            self.partial += 1

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
