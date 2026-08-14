"""An amending act: its own provisions, and the text it quotes of the act it amends.

An amending act is an act, so its own articles parse exactly like any other's. What it
additionally carries is the reason this module exists.

**EU drafting omits the identifier of what it inserts.** The instruction reads *"(25) the
following Article is inserted:"*, with no number, so a regex over the flattened prose misses
every insertion: exactly the 6-of-42 recall gap measured on the Digital Omnibus. The number is
not lost, only relocated. The inserted article appears as a real `ARTICLE` element, with its
`@IDENTIFIER` and its `TI.ART`, inside the quoted text, and recovering it is what closes the
gap for corroboration.

Quoted structure is marked twice over and both marks are used: the quoted element sits inside
a `QUOT.S` (quoted structure) wrapper, and an `ARTICLE` inside another `ARTICLE` is quoted by
construction. On `32026R1744` the two rules agree exactly — 7 quoted articles (`4`, `4a`,
`60a`, `75a` to `75d`) and 66 quoted paragraphs (measured 2026-08-06).

**Quoted paragraphs carry a full location.** A `PARAG` identifier is `article.paragraph`, so
a quoted `<PARAG IDENTIFIER="005.001A">` names `AR 5 PA 1a` on its own. Of the 62 quotations
this act aims at the AI Act, **58 reproduce a CELLAR modification-location string exactly**
and the remaining four (`AR 25 PA 4`, `AR 57 PA 1`, `AR 58 PA 1`, `AR 60 PA 1`) are a prefix
of one: the quote replaces a whole paragraph where the annotation names the alinea inside it
(measured 2026-08-06 against `tests/fixtures/eu/celex_32024R1689.branch.xml`). Reconciling the
two forms is corroboration's work; producing a location worth reconciling is this module's.

**Which act each quote belongs to.** An amending act amends several regulations in parallel
articles (`Article 1 — Amendments to Regulation (EU) 2024/1689`, `Article 2 — … 2018/1139`,
`Article 3 — … 2023/1230`), so an unscoped list of quotations would attribute one
regulation's insertions to another. Each quote is therefore tagged with the act its
instruction article names. Only `Regulation` references resolve to a CELEX: directives and
decisions carry other type letters and no fixture pins one, so they stay `None` rather than
being guessed, as does any citation the reference grammar below does not read cleanly.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Final
from xml.etree.ElementTree import Element

from emendrix.core import (
    ActId,
    AmendingActDoc,
    LocationCode,
    LocationSegment,
    ProvisionLocation,
    QuotedProvision,
)
from emendrix.eu.formex.documents import act_documents, documents_of, unit_elements
from emendrix.eu.formex.locations import article_value, decode_identifier
from emendrix.eu.formex.model import CoverageCounter, ParsedAmendingAct
from emendrix.eu.formex.parse import build_tree
from emendrix.eu.formex.text import comparison_text, head_text, verbatim_text
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.packages import FormexPackage

__all__ = [
    "QUOTED_TAGS",
    "Instruction",
    "instructions",
    "named_act",
    "parse_amending_act",
    "quoted_location",
    "quoted_provisions",
]

QUOTED_TAGS: Final = frozenset({"ARTICLE", "PARAG"})
"""What a quotation may be of. Deeper quoted fragments have no identifier to recover."""

_QUOTE_WRAPPER: Final = "QUOT.S"

# `Regulation (EU) 2024/1689` (year first) and `Regulation (EC) No 1907/2006` (number first).
# The order flipped with the 2015 numbering reform and **the `No` is the marker**: the older
# form always carries it, the newer form never does. Digit length cannot decide it — REACH is
# `No 1907/2006`, four digits either side, and reading it positionally yields `31907R2006`.
_REGULATION: Final = re.compile(
    r"\bRegulations?\s*\((?:EU|EC|EEC|Euratom)(?:,\s*Euratom)?\)\s*(?P<old>No\.?\s*)?"
    r"(?P<first>\d{1,4})/(?P<second>\d{2,4})",
    re.IGNORECASE,
)
_YEARS: Final = range(1952, 2100)
"""Plausible act years: from the first Community act to a century out. Outside it, no answer."""

_LEAD_IN: Final = 400
"""How much of an instruction article is read for the act it names — title and lead-in clause."""

Instruction = tuple[Element, ActId | None]
"""One top-level unit of an amending act, and the act its instructions target."""


def parse_amending_act(package: FormexPackage) -> ParsedAmendingAct:
    """The amending document: its own tree, what it amends, and what it quotes."""
    counter = CoverageCounter()
    documents = act_documents(package, counter)
    tree = build_tree(documents, package, counter)
    found = tuple(instructions(documents_of(documents)))
    document = AmendingActDoc(
        act=package.act,
        tree=tree,
        amends=tuple(dict.fromkeys(target for _, target in found if target is not None)),
        quoted=tuple(quoted_provisions(found)),
    )
    return ParsedAmendingAct(document=document, coverage=counter.freeze())


def instructions(documents: tuple[Element, ...]) -> Iterator[Instruction]:
    """Each top-level unit of the amending act, with the act it names, in document order.

    An annex of an amending act carries amendments too, but it names no act of its own — the
    instruction that delegates to it does ("*Annexes VI to X … are amended in accordance with
    the Annex to this Regulation*", as `32022R0477` does). That shape is out of scope for v0.1,
    so an annex's quotations are reported with no act rather than with a guessed one.
    """
    for document in documents:
        for unit, is_annex in unit_elements(document):
            yield unit, (None if is_annex else named_act(unit))


def named_act(article: Element) -> ActId | None:
    """The act an instruction article targets, read from its title and its lead-in clause.

    Returns `None` rather than a guess whenever the citation does not read cleanly — a
    two-digit year (`(EEC) No 2913/92`), a year outside `_YEARS`, a form the regex does not
    know. A quotation with no act is honest; one attributed to the wrong act is not.
    """
    matched = _REGULATION.search(head_text(article, _LEAD_IN))
    if matched is None:
        return None
    first, second = matched["first"], matched["second"]
    year, number = (second, first) if matched["old"] else (first, second)
    if len(year) != 4 or int(year) not in _YEARS or not 0 < int(number) < 10000:
        return None
    return act_id(Celex.parse(f"3{year}R{int(number):04d}"))


def quoted_provisions(found: tuple[Instruction, ...]) -> Iterator[QuotedProvision]:
    """Every outermost quoted `ARTICLE`/`PARAG`, in document order.

    Outermost only: the paragraphs of a quoted article are part of that article, not seven
    more quotations of their own.
    """
    for unit, target in found:
        for element in _quoted_elements(unit):
            yield QuotedProvision(
                location=quoted_location(element),
                amended_act=target,
                text=verbatim_text(element),
                comparison_text=comparison_text(element),
            )


def _quoted_elements(unit: Element) -> Iterator[Element]:
    def walk(element: Element, quoted: bool) -> Iterator[Element]:
        for child in element:
            inside = quoted or child.tag == _QUOTE_WRAPPER
            if inside and child.tag in QUOTED_TAGS:
                yield child
            else:
                yield from walk(child, inside)

    yield from walk(unit, False)


def quoted_location(element: Element) -> ProvisionLocation | None:
    """`AR 4a` from a quoted article, `AR 5 PA 1a` from a quoted paragraph, else `None`."""
    if element.tag == "ARTICLE":
        number = article_value(element)
        return None if number is None else _location((LocationCode.AR, number))
    article, _, paragraph = (element.get("IDENTIFIER") or "").strip().partition(".")
    number, within = decode_identifier(article), decode_identifier(paragraph)
    if number is None or within is None:
        return None
    return _location((LocationCode.AR, number), (LocationCode.PA, within))


def _location(*segments: tuple[LocationCode, str]) -> ProvisionLocation:
    return ProvisionLocation(
        segments=tuple(LocationSegment(code=code, value=value) for code, value in segments)
    )
