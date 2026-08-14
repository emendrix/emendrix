"""Coordinates a model sentence names, read off the prose and nothing else.

The one regular expression of the unsupported-coordinate check lives here, and it is applied
only to model prose, which genuinely is prose. Provision text is never pattern-matched: a
source format may flatten a paragraph number straight into the surrounding words (the
committed prompts carry `...conformity with certain requirements1.High-risk AI systems...`,
verified 2026-08-08), so a pattern over provision text either finds no numbering at all or
matches every parenthesised cross-reference. Whether a named coordinate is *supported* is therefore
resolved structurally, in `gate/check.py`, against sets the context builder computed from the
provision trees; this module only says which coordinates a sentence wrote down.

The recogniser is deliberately conservative, because its precision is the entire value of the
count it feeds. A mention it misses is a silent undercount and acceptable; a mention it
invents becomes a wrong published number and is not. When the grammar is ambiguous it does
not recognise. Concretely it reads, relative to the provision under discussion:

- `paragraph 3`, `paragraphs 1 and 2`, `paragraphs 2, 3 and 4`;
- `paragraphs 1 to 4` as its two endpoints, never expanded: an expanded range would assert
  coordinates the sentence did not write;
- a lettered point written directly against its paragraph, `paragraphs 9(e) and 10`;
- `Article N(2)` and `Article N(1)(a)`, only when `N` is the provision's own article number.

And it refuses, each refusal tested:

- any reference followed by `of ...`: `Article 11(13) of Directive 93/42/EEC`,
  `Article 12(1) of that Regulation`, `paragraph 1 of Article 10`. Cross-instrument
  references are the dominant false positive in the prose this design was measured against
  (2026-08-08), and the cost is only an undercount on `of this Regulation` self-references;
- any `Article M(...)` where `M` is not the provision's own number;
- everything, when the unit is not an article: annex prose numbers its parts in vocabularies
  (`point 3`, `Section A`) that cannot be mapped to canonical codes without guessing;
- a numeric group where a lettered point is expected (`paragraph 9(1)`): the numbering style
  is ambiguous between a point and a subparagraph, so recognition stops at the paragraph.
"""

from __future__ import annotations

import re
from typing import Final

from emendrix.core import ProvisionLocation
from emendrix.core.location_codes import LocationCode

__all__ = ["mentioned_locations"]

_POINT: Final = r"\([a-z0-9]{1,4}\)"
_ITEM: Final = rf"\d{{1,3}}[a-z]?(?:{_POINT})*"
_JOIN: Final = r"(?:\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or|to)\s+)"

_PARAGRAPHS: Final = re.compile(rf"\bparagraphs?\s+({_ITEM}(?:{_JOIN}{_ITEM})*)", re.IGNORECASE)
_ARTICLE: Final = re.compile(rf"\bArticle\s+(\d{{1,3}}[a-z]?)\s?((?:{_POINT})+)", re.IGNORECASE)
_ONE_ITEM: Final = re.compile(rf"(\d{{1,3}}[a-z]?)((?:{_POINT})*)")
_GROUPS: Final = re.compile(r"\(([a-z0-9]{1,4})\)")
_OF_SUFFIX: Final = re.compile(r"\s+of\b", re.IGNORECASE)


def _own_article_number(unit: ProvisionLocation) -> str | None:
    """The unit's own article number, or `None` when the unit is not an article."""
    head = unit.segments[0]
    if head.code is LocationCode.AR and head.value is not None:
        return head.value.lower()
    return None


def _resolve(unit: ProvisionLocation, number: str, groups: list[str]) -> ProvisionLocation:
    """The most precise location one textual mention safely supports.

    The paragraph, then the first parenthesised group as a lettered point when it is one.
    Deeper nesting is ignored rather than guessed at: the canonical path may thread an
    unnumbered alinea between paragraph and point, and inventing that segment here would
    put coordinates in the count that no sentence wrote.
    """
    location = unit.top_level.child(LocationCode.PA, number.lower())
    if groups and not groups[0].isdigit():
        location = location.child(LocationCode.PTA, f"({groups[0].lower()})")
    return location


def mentioned_locations(sentence: str, unit: ProvisionLocation) -> frozenset[ProvisionLocation]:
    """Every coordinate of `unit` that `sentence` names. Pure; model prose only."""
    own = _own_article_number(unit)
    if own is None:
        return frozenset()
    found: set[ProvisionLocation] = set()
    for match in _PARAGRAPHS.finditer(sentence):
        if _OF_SUFFIX.match(sentence, match.end()):
            continue
        for item in _ONE_ITEM.finditer(match.group(1)):
            found.add(_resolve(unit, item.group(1), _GROUPS.findall(item.group(2))))
    for match in _ARTICLE.finditer(sentence):
        if _OF_SUFFIX.match(sentence, match.end()):
            continue
        if match.group(1).lower() != own:
            continue
        groups = _GROUPS.findall(match.group(2))
        if not groups[0].isdigit():
            continue
        found.add(_resolve(unit, groups[0], groups[1:]))
    return frozenset(found)
