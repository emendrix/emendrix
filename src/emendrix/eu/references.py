"""Amending prose → a canonical location: the reference grammar of EU instruction clauses.

`eu/formex/locations.py` reads locations out of *markup*. This module reads them out of the
*sentence* an amending act writes about another act — "in Article 1(2), point (g)",
"in point (h) of Section 5.1 of Annex IX", "in paragraph 1, the first subparagraph". Nothing
here parses instructions or decides what happened; it answers one question, *which provision
is this clause pointing at*, and answers `None` rather than guessing.

Two properties of the real drafting shape everything below. Both were read off the pinned
amending acts `32026R1744` and `32020R0561` on 2026-08-06.

**References are written in either nesting order.** Outermost-first with commas — *"in
Article 1(2), point (g) is replaced"* — and innermost-first with *of* — *"in point (h) of
Section 5.1 of Annex IX"*. Position in the sentence therefore cannot order the path, so the
segments found are ordered by **nesting depth** (`_DEPTH` below), stably, which reproduces
both forms and needs no separate rule for either.

**Most clauses are relative.** Inside *"Article 5 is amended as follows:"* the sub-clause
*"paragraph 1 is replaced"* names `PA 1` and means `AR 5 PA 1`. A reference is absolute when
it starts at a top-level unit (`AR`/`AN`) and relative otherwise; `resolve` is where the two
meet.

What is deliberately *not* read: ranges ("Annexes VI to X"), enumerations beyond their first
member ("points 7 and 9" → `PO 7`), and sentence coordinates ("in the first sentence"). Each
lands one level shallower than the prose allows, which is a coarser coordinate and never a
wrong unit, and the unit is what the metrics score.
"""

from __future__ import annotations

import re
from typing import Final

from emendrix.core import LocationCode, LocationSegment, ProvisionLocation

__all__ = ["ORDINALS", "parse_reference", "reference_segments", "resolve"]

ORDINALS: Final[dict[str, int]] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
"""Written ordinals, as the drafting uses them ("the second subparagraph"). Ten is plenty."""

_ORDINAL_ALTERNATION: Final = "|".join(ORDINALS)

# One alternation, one named group per form, with the example each form was read from.
_REFERENCE: Final = re.compile(
    rf"""
      (?P<article>\bArticles?\s+(?P<art>\d+[a-z]?)          # "Article 4a", "Articles 5"
        (?:\s*\((?P<art_para>\d+[a-z]?)\))?)                # "Article 1(2)"
    | (?P<annex>\bAnnex(?:es)?\s+(?P<an>[IVXLCDM]+|\d+[a-z]?)\b)   # "Annex IX"
    | (?P<appendix>\bAppendix\s+(?P<app>[IVXLCDM]+|\d+[a-z]?)\b)   # "Appendix 1"
    | (?P<section>\bSections?\s+(?P<sct>[0-9A-Za-z][0-9A-Za-z.]*?)\.?(?=[\s,]|$))  # "Section 5.1"
    # "Part C" — the enumerator must be written as one, or "the introductory part" is a part.
    | (?P<part>\bParts?\s+(?-i:(?P<prt>[IVXLCDM]{{1,6}}|[A-Z]|\d+))\b)
    | (?P<paragraph>\bparagraphs?\s+(?P<pa>\d+[a-z]?))             # "paragraph 1a"
    | (?P<ordinal_paragraph>\bthe\s+(?P<ord_pa>{_ORDINAL_ALTERNATION})\s+paragraph\b)
    | (?P<subparagraph>\bthe\s+(?P<ord_aln>{_ORDINAL_ALTERNATION})\s+subparagraph\b)
    | (?P<indent>\bthe\s+(?P<ord_tire>{_ORDINAL_ALTERNATION})\s+indent\b)
    | (?P<point>\bpoints?\s+(?:\((?P<point_letter>[0-9a-z]{{1,3}})\)|(?P<point_number>\d+)))
    | (?P<heading>\bthe\s+heading\b)                               # "the heading is replaced"
    """,
    re.VERBOSE | re.IGNORECASE,
)

_DEPTH: Final[dict[LocationCode, int]] = {
    LocationCode.AR: 0,
    LocationCode.AN: 0,
    LocationCode.APP: 0,
    LocationCode.TIT: 1,
    LocationCode.PRT: 2,
    LocationCode.SCT: 3,
    LocationCode.SBS: 4,
    LocationCode.PA: 5,
    LocationCode.ALN: 6,
    LocationCode.PTA: 7,
    LocationCode.PO: 7,
    LocationCode.PTI: 7,
    LocationCode.TIRE: 7,
}
"""How deeply each code nests. Used only to order what a clause names — see the docstring.

At most one coordinate per rank survives, so the ranks are what decides that "points 7 and 9"
is one point and "Part C, section 6.6.2" is two coordinates rather than one.
"""

_TOP_LEVEL: Final = frozenset({LocationCode.AR, LocationCode.AN, LocationCode.APP})


def _segments_of(matched: re.Match[str]) -> list[tuple[LocationCode, str | None]]:
    if matched["article"]:
        found = [(LocationCode.AR, matched["art"].lower())]
        if matched["art_para"]:
            found.append((LocationCode.PA, matched["art_para"].lower()))
        return found
    if matched["annex"]:
        return [(LocationCode.AN, matched["an"].upper())]
    if matched["appendix"]:
        return [(LocationCode.APP, matched["app"].upper())]
    if matched["section"]:
        return [(LocationCode.SCT, matched["sct"])]
    if matched["part"]:
        return [(LocationCode.PRT, matched["prt"].upper())]
    if matched["paragraph"]:
        return [(LocationCode.PA, matched["pa"].lower())]
    if matched["ordinal_paragraph"]:
        return [(LocationCode.PA, str(ORDINALS[matched["ord_pa"].lower()]))]
    if matched["subparagraph"]:
        return [(LocationCode.ALN, str(ORDINALS[matched["ord_aln"].lower()]))]
    if matched["indent"]:
        return [(LocationCode.TIRE, str(ORDINALS[matched["ord_tire"].lower()]))]
    if matched["point"]:
        # The metadata's own spelling: a numbered point is `PO 14` with the parentheses
        # dropped, a lettered one `PTA (g)` with them kept (`eu/formex/locations.py`).
        token = matched["point_number"] or matched["point_letter"]
        if token.isdigit():
            return [(LocationCode.PO, token)]
        return [(LocationCode.PTA, f"({token.lower()})")]
    return [(LocationCode.TIT, None)]


def reference_segments(clause: str) -> tuple[LocationSegment, ...]:
    """Every provision coordinate `clause` names, ordered outermost-first.

    Only the *first* coordinate at each nesting depth survives, so "points 7 and 9" yields
    `PO 7` and "the date 26 May 2020 is replaced by 26 May 2021" yields nothing at all.
    """
    found: list[tuple[LocationCode, str | None]] = []
    for matched in _REFERENCE.finditer(clause):
        found.extend(_segments_of(matched))
    ordered = sorted(enumerate(found), key=lambda item: (_DEPTH.get(item[1][0], 9), item[0]))
    kept: list[LocationSegment] = []
    depths: set[int] = set()
    for _, (code, value) in ordered:
        depth = _DEPTH.get(code, 9)
        if depth in depths:
            continue
        depths.add(depth)
        kept.append(LocationSegment(code=code, value=value))
    return tuple(kept)


def parse_reference(clause: str) -> ProvisionLocation | None:
    """The location `clause` names on its own, or `None` when it names none."""
    segments = reference_segments(clause)
    return ProvisionLocation(segments=segments) if segments else None


def resolve(clause: str, context: ProvisionLocation | None) -> ProvisionLocation | None:
    """The location `clause` names, read inside `context`.

    Absolute when the clause starts at a top-level unit, relative otherwise — so
    *"paragraph 1 is replaced"* inside *"Article 5 is amended as follows:"* is `AR 5 PA 1`,
    and a clause that names nothing at all is the context itself.
    """
    segments = reference_segments(clause)
    if segments and segments[0].code in _TOP_LEVEL:
        return ProvisionLocation(segments=segments)
    if context is None:
        return ProvisionLocation(segments=segments) if segments else None
    return ProvisionLocation(segments=(*context.segments, *segments))
