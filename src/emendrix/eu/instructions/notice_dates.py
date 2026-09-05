"""The act's own dates as the Publications Office publishes them, beside the act's text.

The third reader of the same question `effect.py` and `final_provisions.py` answer from the
act's prose and its markup. Most amending acts enter into force *"on the twentieth day
following that of its publication"* and never write that day, so the two text readers have
nothing to read and the instructions of such an act carry no date at all. The day itself is
published: the CELLAR notice of the act carries `RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE`, one
element per date, each annotated with a `TYPE_OF_DATE` (`EV` for entry into force, `MA` for
application) and a `COMMENT_ON_DATE` saying how the Publications Office arrived at it. On
`32024R1860` the `EV` entry is annotated `{DATPUB} {V} {ART} 3`: the publication date, per the
act's own Article 3. The twentieth-day arithmetic, already done, by the authority that
publishes the act, so reading it is not inference.

Two facts about that annotation, both measured on 2026-09-05 over the 295 tree notices this
installation's disk cache then held, and both load-bearing:

1. **`COMMENT_ON_DATE` names the provision that *states* the date, never the provisions the
   date covers.** Every comment in the cache ends `{V} {ART} n`, and on `32021R2117` all five
   entries name Article 6, which is that act's entry-into-force article, while the parts they
   stage sit in Articles 1, 2 and 3. So the comment cannot scope an entry onto an instruction
   coordinate, and this module never tries: what it reads out of the comment is the one
   distinction the comment does make, `MA/PART` for an entry that dates part of the act
   against a bare `MA` for the act as a whole.
2. **A staged act carries several `MA` entries and the notice does not say which part each
   covers.** `32019R0876` carries seven, one of them the sentinel `1001-01-01` that 17 of the
   cached notices write for a day a later decision will fix. Picking the earliest or the latest
   would be the guess the two-clocks rule forbids, so an act carrying any entry this cannot
   place carries **no** act-wide answer at all and is counted. An instruction left undated is
   claimed exactly as it was before this module existed, which is the safe direction:
   under-scoping leaves a true claim in place, over-scoping deletes one.

A value outside `PLAUSIBLE` is a counted gap and never a date. `1001-01-01` is not a day any
act applies from, and the test is the value's own implausibility rather than that literal.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.eu.dates import iso_date
from emendrix.eu.xml_ import fromstring

__all__ = ["PLAUSIBLE", "ActDates", "DateKind", "NoticeDate", "parse_act_dates"]

_ENTRY: Final = "RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE"

_TEMPLATE: Final = re.compile(r"\{([^|}]+)\|[^}]*\}")
"""`{MA/PART|http://…/fd_335/MA%2FPART}` → `MA/PART`. The code carries a `/`, so this is not
`mod_roles._TEMPLATE`, whose `\\w+` was written for a role vocabulary that has none."""

PLAUSIBLE: Final = (date(1952, 1, 1), date(2099, 12, 31))
"""The span a date on a legal act of this corpus can fall in, inclusive.

The lower bound is the year the earliest acts CELLAR carries entered into force; the upper is
far beyond any deferral the drafting states. Fixed values rather than a window around today,
because nothing below the CLI boundary reads a clock.
"""


class DateKind(StrEnum):
    """The `TYPE_OF_DATE` codes observed on the cached notices. Anything else is carried raw."""

    ENTRY_INTO_FORCE = "EV"
    APPLICATION = "MA"
    PARTIAL_APPLICATION = "MA/PART"


_KINDS: Final = frozenset(str(kind) for kind in DateKind)


class NoticeDate(BaseModel):
    """One dated entry of the notice: the day, what kind of day it is, and what was said of it."""

    model_config = ConfigDict(frozen=True)

    value: date
    kind: str = Field(
        description="The `TYPE_OF_DATE` code, template stripped; outside `DateKind` it is raw."
    )
    comment: str = Field(
        default="", description="The `COMMENT_ON_DATE` codes, templates stripped, in order."
    )

    @property
    def staged(self) -> bool:
        """True where this entry dates part of the act rather than the act.

        Read from either field, because the corpus writes the distinction in one or the other
        and never in both: of the 742 dated entries in the cache on 2026-09-05, 29 are marked
        in `TYPE_OF_DATE` and a disjoint 262 in `COMMENT_ON_DATE`.
        """
        partial = str(DateKind.PARTIAL_APPLICATION)
        return self.kind == partial or self.comment.startswith(partial)

    @property
    def placed(self) -> bool:
        """True where the notice says what this date is about, in a code this module knows."""
        return self.kind in _KINDS and not self.staged


class ActDates(BaseModel):
    """What one act's notice says about when the act itself took effect, and what it could not.

    Every count here is a coverage gap, never an error: a notice this cannot read leaves the
    act's instructions dated exactly as the act's own text dated them.
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[NoticeDate, ...] = ()
    implausible: tuple[str, ...] = Field(
        default=(), description="`VALUE`s no date rule accepted, or outside `PLAUSIBLE`."
    )
    unknown_kinds: tuple[tuple[str, int], ...] = Field(
        default=(), description="`TYPE_OF_DATE` code → count, for codes outside `DateKind`."
    )

    @property
    def unplaced(self) -> tuple[NoticeDate, ...]:
        """Entries the notice dates and this cannot attribute: staged, or of an unknown kind."""
        return tuple(entry for entry in self.entries if not entry.placed)

    @property
    def default(self) -> date | None:
        """The one day this notice says the whole act took effect, or nothing at all.

        The act's date of application answers where it states one, its entry into force
        otherwise, which is the order `final_provisions.py` reads the same two out of the act's
        own prose. Anything the reader could not place, an implausible value included, takes
        the answer away rather than being reasoned around.
        """
        if self.implausible or self.unplaced:
            return None
        return self._sole(DateKind.APPLICATION) or self._sole(DateKind.ENTRY_INTO_FORCE)

    def _sole(self, kind: DateKind) -> date | None:
        """The one placed date of this kind, or `None` where the notice states none or several."""
        found = {entry.value for entry in self.entries if entry.placed and entry.kind == kind}
        return found.pop() if len(found) == 1 else None


def parse_act_dates(notice_xml: bytes) -> ActDates:
    """Read every `RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE` out of an act's notice.

    A notice with no `WORK` element states nothing about the act, which is an answer and is
    reported as an empty read rather than raised over.
    """
    work = fromstring(notice_xml).find("WORK")
    if work is None:
        return ActDates()

    entries: list[NoticeDate] = []
    implausible: list[str] = []
    unknown: dict[str, int] = {}
    for element in work.findall(_ENTRY):
        raw = (element.findtext("VALUE") or "").strip()
        value = iso_date(raw)
        if value is None or not PLAUSIBLE[0] <= value <= PLAUSIBLE[1]:
            implausible.append(raw)
            continue
        # One annotation per entry: 742 annotations over the 742 entries of the 295 notices
        # cached on 2026-09-05, so reading the first is reading the only one.
        kind = _codes(element.findtext("ANNOTATION/TYPE_OF_DATE"))
        if kind not in _KINDS:
            unknown[kind] = unknown.get(kind, 0) + 1
        entries.append(
            NoticeDate(
                value=value,
                kind=kind,
                comment=_codes(element.findtext("ANNOTATION/COMMENT_ON_DATE")),
            )
        )
    return ActDates(
        entries=tuple(entries),
        implausible=tuple(implausible),
        unknown_kinds=tuple(sorted(unknown.items())),
    )


def _codes(raw: str | None) -> str:
    """`'{DATPUB|…} {V|…} {ART|…} 3'` → `'DATPUB V ART 3'`, the codes without their authority."""
    return " ".join(_TEMPLATE.sub(lambda found: found[1], raw or "").split())
