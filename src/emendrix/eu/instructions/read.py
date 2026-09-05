"""Reading the instruction list out of an amending act's own markup.

The pattern table, the clause extraction and the walk, and nothing else: what the records
*are* is `model.py`, which is also where the signal built out of them lives, and what the
records are scored against is `emendrix.eu.instructions` (the package docstring). What a
clause *points at* is `eu/references.py`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final
from xml.etree.ElementTree import Element

from emendrix.core import ActId, ChangeType, ProvisionLocation
from emendrix.eu.formex.amending import named_act, quoted_location
from emendrix.eu.formex.documents import act_documents, documents_of, unit_elements
from emendrix.eu.formex.locations import annex_segment
from emendrix.eu.formex.model import CoverageCounter
from emendrix.eu.formex.text import flat_text
from emendrix.eu.instructions.effect import EffectDates, EffectDateSource, prose
from emendrix.eu.instructions.final_provisions import read_effect_dates
from emendrix.eu.instructions.model import InstructionParse, InstructionRecord, UnreadInstruction
from emendrix.eu.instructions.notice_dates import ActDates
from emendrix.eu.packages import FormexPackage
from emendrix.eu.references import parse_reference, resolve
from emendrix.eu.xml_ import NOT_WELL_FORMED, fromstring

__all__ = ["AMEND", "INSTRUCTION_VERBS", "parse_instructions"]


AMEND: Final = "amends"
"""Not a change of its own: *"X is amended as follows:"* introduces the changes to X."""

INSTRUCTION_VERBS: Final[tuple[tuple[re.Pattern[str], str | ChangeType], ...]] = (
    # "Article 2 is amended as follows:", "Annex I is amended as follows:" — a container.
    (re.compile(r"\bamended as follows\b", re.IGNORECASE), AMEND),
    # "point (g) is replaced by the following:", "the date 26 May 2020 is replaced by …"
    (re.compile(r"\b(?:is|are)\s+replaced\b", re.IGNORECASE), ChangeType.MODIFIED),
    # "paragraph 5 is deleted;", "points 7 and 9 are deleted;"
    (re.compile(r"\b(?:is|are)\s+deleted\b", re.IGNORECASE), ChangeType.DELETED),
    # "the following Article is inserted:", "the following paragraphs are added:"
    (re.compile(r"\b(?:is|are)\s+(?:inserted|added)\b", re.IGNORECASE), ChangeType.INSERTED),
)
"""The whole pattern table, anchored on the verb of a clause the quoted text is stripped from.

Order matters: *"is amended as follows"* is tested first because the clause that introduces
sub-instructions also contains one of them in its own words.
"""

_INSTRUCTION_HINT: Final = re.compile(
    r"\b(amend(?:ed|ment)|replaced|deleted|inserted|added|renumbered|substituted)\b",
    re.IGNORECASE,
)
"""What makes a clause *look like* an instruction. A clause that looks like one and yields no
record is an unread instruction and is counted; a clause that does not is simply not one."""

_CLAUSE_SKIPPED: Final = frozenset({"NO.P", "LIST", "QUOT.S", "TI.ART", "STI.ART"})
"""Excluded from a clause: its heading, its enumerator, its sub-instructions, and the text it
quotes. The heading carries the amending article's own number, and the reference grammar keeps
only the first coordinate at each depth, so a heading left in speaks before the instruction does."""

_QUOTED_TAGS: Final = frozenset({"ARTICLE", "PARAG", "INCL.ELEMENT"})


def parse_instructions(
    package: FormexPackage, *, dates: ActDates | None = None
) -> InstructionParse:
    """Read the instructions of an amending act out of its own Formex package.

    `dates` is what the act's own notice publishes about its dates, a value from the
    composition root because the notice is a second document and nothing here fetches. Without
    it the act is dated from its own text alone, which a caller holding no notice can say.
    """
    documents = act_documents(package, CoverageCounter())
    articles = [
        (unit, named_act(unit))
        for document in documents_of(documents)
        for unit, is_annex in unit_elements(document)
        if not is_annex
    ]
    scoped = any(target is not None for _, target in articles)
    effect = read_effect_dates((unit for unit, _ in articles), dates=dates)
    reader = _Reader(package, scoped=scoped, effect=effect)
    for unit, target in articles:
        reader.read_article(unit, target)
    return InstructionParse(
        act=package.act,
        records=tuple(reader.records),
        unread=tuple(reader.unread),
        targets=tuple(dict.fromkeys(target for _, target in articles if target is not None)),
        scoped=scoped,
    )


def _clause(node: Element) -> str:
    """The instruction's own words: everything but its enumerator, sub-list and quoted text."""
    return prose(node, skipped=_CLAUSE_SKIPPED)


def _verb(clause: str) -> str | ChangeType | None:
    for pattern, kind in INSTRUCTION_VERBS:
        if pattern.search(clause):
            return kind
    return None


def _lead_in(host: Element) -> ProvisionLocation | None:
    """The container an article's own lead-in names, scoping the list drafted under it.

    `32025R2457` Article 3 opens *"Annex I to Regulation (EU) 2017/745 is amended as
    follows:"* in the alinea that holds the list, and the items are drafted relative to it
    (*"in Section 10.4.1, point (b) is replaced"*), exactly as an item that introduces a
    sub-list scopes its sub-items. The commonest lead-in (*"Regulation (EU) 2017/745 is
    amended as follows:"*) names no provision and scopes nothing, which leaves every
    absolute-referenced act unaffected. Verified 2026-08-11 against the pinned package; without
    the scoping, those four sections lose their annex.
    """
    clause = _clause(host)
    if _verb(clause) != AMEND:
        return None
    return parse_reference(clause)


class _Reader:
    """The walk. Holds the package (for `INCL.ELEMENT`), the act's own dates and its tallies."""

    def __init__(self, package: FormexPackage, *, scoped: bool, effect: EffectDates) -> None:
        self.package = package
        self.scoped = scoped
        self.effect = effect
        self.records: list[InstructionRecord] = []
        self.unread: list[UnreadInstruction] = []

    def read_article(self, article: Element, target: ActId | None) -> None:
        if self.scoped and target is None:
            return
        source = f"AR {article.get('IDENTIFIER') or '?'}"
        hosts = [alinea for alinea in article.findall("ALINEA") if alinea.findall("LIST")]
        if hosts:
            for host in hosts:
                context = _lead_in(host)
                for element in host.findall("LIST"):
                    self._read_list(element, context, source, target)
            return
        lists = article.findall("LIST")
        if lists:
            for element in lists:
                self._read_list(element, None, source, target)
            return
        self._read_clause(article, None, source, target)

    def _read_list(
        self, element: Element, context: ProvisionLocation | None, source: str, act: ActId | None
    ) -> None:
        for item in element.findall("ITEM"):
            node = item.find("NP")
            if node is not None:
                self._read_item(node, context, source, act)

    def _read_item(
        self, node: Element, context: ProvisionLocation | None, source: str, act: ActId | None
    ) -> None:
        enumerator = node.find("NO.P")
        marker = "" if enumerator is None else flat_text(enumerator)
        where = f"{source} {marker}".strip()
        clause = _clause(node)
        location = resolve(clause, context)
        sublists = node.findall("P/LIST")
        if sublists:
            for element in sublists:
                self._read_list(element, location, where, act)
            return
        self._emit(node, clause, location, where, act)

    def _read_clause(
        self, node: Element, context: ProvisionLocation | None, source: str, act: ActId | None
    ) -> None:
        clause = _clause(node)
        self._emit(node, clause, resolve(clause, context), source, act)

    def _emit(
        self,
        node: Element,
        clause: str,
        location: ProvisionLocation | None,
        where: str,
        act: ActId | None,
    ) -> None:
        kind = _verb(clause)
        if kind == AMEND:
            # "X is amended as follows:" with no sub-list is a replacement of X, quoted below
            # it — the only shape where the container verb stands for the change itself.
            kind = ChangeType.MODIFIED
        if not isinstance(kind, ChangeType):
            self._miss(clause, where, "no instruction verb")
            return
        dated = self.effect.for_clause(clause, where)
        quoted = self._quoted_locations(node)
        if kind is ChangeType.INSERTED and quoted:
            for target in quoted:
                self._record(target, kind, where, act, dated, from_quotation=True)
            return
        if location is None:
            self._miss(clause, where, "no provision reference")
            return
        if kind is ChangeType.INSERTED and location.depth == 1:
            # The prose never names what it inserts, so a lone top-level reference is the
            # host of the insertion, not the thing inserted.
            kind = ChangeType.MODIFIED
        self._record(location, kind, where, act, dated, from_quotation=False)

    def _record(
        self,
        location: ProvisionLocation,
        kind: ChangeType,
        where: str,
        act: ActId | None,
        dated: tuple[date | None, EffectDateSource],
        *,
        from_quotation: bool,
    ) -> None:
        effective, source = dated
        self.records.append(
            InstructionRecord(
                location=location,
                change_type=kind,
                source_ref=where,
                amended_act=act,
                from_quotation=from_quotation,
                effect_date=effective,
                effect_source=source,
            )
        )

    def _miss(self, clause: str, where: str, reason: str) -> None:
        if _INSTRUCTION_HINT.search(clause):
            self.unread.append(UnreadInstruction(source_ref=where, clause=clause, reason=reason))

    def _quoted_locations(self, node: Element) -> tuple[ProvisionLocation, ...]:
        """The identifiers of what this instruction quotes, outermost quotation first."""
        found: list[ProvisionLocation] = []
        for element in _quoted_elements(node):
            location = (
                self._included_annex(element)
                if element.tag == "INCL.ELEMENT"
                else quoted_location(element)
            )
            if location is not None:
                found.append(location)
        return tuple(found)

    def _included_annex(self, element: Element) -> ProvisionLocation | None:
        """`<INCL.ELEMENT FILEREF="…003601.fmx.xml">` — the annex the act ships as its own member.

        *"the following Annex is added:"* quotes by reference rather than inline, so the
        identifier `AN XIV` is in the referenced document's title (verified 2026-08-06 on
        `32026R1744`). A reference that resolves to nothing readable yields `None` — including
        a member the hardened parser declines to expand, which is unreadable in the same sense.
        """
        member = self.package.member(element.get("FILEREF") or "")
        if member is None:
            return None
        try:
            document = fromstring(member.data)
        except NOT_WELL_FORMED:
            return None
        segment = annex_segment(document)
        if segment is None:
            return None
        code, value = segment
        return ProvisionLocation.parse(f"{code} {value}")


def _quoted_elements(node: Element) -> list[Element]:
    """Outermost quoted provisions inside this instruction's own `P`, sub-lists excluded."""
    found: list[Element] = []

    def walk(element: Element, quoted: bool) -> None:
        for child in element:
            if child.tag == "LIST":
                continue
            inside = quoted or child.tag == "QUOT.S"
            if inside and child.tag in _QUOTED_TAGS:
                found.append(child)
            else:
                walk(child, inside)

    for paragraph in node.findall("P"):
        walk(paragraph, False)
    return found
