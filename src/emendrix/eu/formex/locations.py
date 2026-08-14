"""Formex elements → canonical location segments, and the tag vocabulary that decides.

The whole reason Formex 4 is workable is that its nesting maps 1:1 onto the CELLAR
modification-location vocabulary. Everything this
module knows was read off the pinned fixtures on 2026-08-06, against the forms the AI Act's
branch notice actually publishes (`AR 5 PA 1 ALN 1 PTA (bb)`, `AN I SCT A PO 1`).

The two vocabularies agree on the codes and not always on the *path*: the metadata elides
segments the markup keeps, writing `AR 3 PO 14` where the structure is `AR 3 ALN 1 PO 14` and
`AR 113 PA 3` where Article 113 has no `PARAG` at all. This module reproduces the markup,
faithfully; reconciling the two paths is corroboration's job, and the unit of change, the
top-level segment, is identical either way.

| Element | Segment | Value read from | Fixture that proves it |
|---|---|---|---|
| `ARTICLE` | `AR 4a` | `@IDENTIFIER="004A"` | AI Act v2, Digital Omnibus |
| `PARAG` | `PA 1a` | `@IDENTIFIER="005.001A"`, last part | AI Act v2 |
| `ALINEA` | `ALN 1` | position among its siblings | AI Act v2 `AR 5 PA 1 ALN 1` |
| `NP` (alpha) | `PTA (bb)` | `NO.P`, parentheses kept | AI Act v2 Art. 5(1) |
| `NP` (roman) | `PTI (ii)` | `NO.P` under `LIST TYPE="roman"` | AI Act v2 Art. 113 |
| `NP` (arabic) | `PO 14` | `NO.P`, parentheses dropped | AI Act v2 Art. 3 |
| `NP` (dash) | `TIRE 2` | position under `LIST TYPE="DASH"` | REACH annexes |
| `CONS.ANNEX`/`ANNEX` | `AN III` | `TITLE/TI` | all seven packages |
| `CONS.ANNEX` (nested) | `APP 1` | `TITLE/TI` | REACH Annex XVII |
| `GR.SEQ` (in an annex) | `SCT A` | `NO.GR.SEQ` or `TITLE/TI` | AI Act v2 Annex I |

Two rules carry the design and are easy to get wrong. **Chapters and titles are
transparent**: `DIVISION` and the act-level `GR.SEQ` groupings are descended through without
producing a segment, because the unit of change is the article and `TIT 1 AR 5` would
key onto nothing. **Quoted structure is not structure**: `QUOT.S` is never descended into
here — what an amending act quotes is another act's text, and it is collected separately by
`amending.py`.
"""

from __future__ import annotations

import re
from typing import Final
from xml.etree.ElementTree import Element

from emendrix.core import LocationCode
from emendrix.eu.formex.text import flat_text

__all__ = [
    "INLINE",
    "LOCATABLE",
    "TRANSPARENT",
    "annex_segment",
    "article_value",
    "decode_identifier",
    "point_segment",
    "section_value",
    "title_of",
]

Segment = tuple[LocationCode, str | None]

LOCATABLE: Final = frozenset({"PARAG", "ALINEA", "NP", "GR.SEQ", "CONS.ANNEX", "ANNEX"})
"""Elements the walk tries to turn into a node. A failure to read a number is counted."""

TRANSPARENT: Final = frozenset(
    {
        # Act and annex scaffolding: descended through, never a segment of their own.
        "CONS.DOC",
        "ENACTING.TERMS",
        "FINAL",
        "CONTENTS",
        "DIVISION",
        "GR.SEQ",
        # Enumerations and prose containers.
        "LIST",
        "ITEM",
        "P",
        "TXT",
        "BLK",
        "DLIST",
        "DLIST.ITEM",
        "DEFINITION",
    }
)
"""Containers with no location of their own. Their located descendants attach to the parent."""

INLINE: Final = frozenset(
    {
        # Headings and enumerators — read as text, never walked for structure.
        "TITLE",
        "TI",
        "STI",
        "TI.BLK",
        "TI.ART",
        "STI.ART",
        "NO.PARAG",
        "NO.P",
        "NO.GR.SEQ",
        "NO.ITEM",
        "NO.SEQ",
        "TERM",
        # Inline typography, references and marks.
        "HT",
        "FT",
        "IE",
        "DATE",
        "LINK",
        "ADDR",
        "IMG.CNT",
        "INCL.ELEMENT",
        "INCLUSIONS",
        "REF.DOC",
        "REF.DOC.OJ",
        "QUOT.START",
        "QUOT.END",
        # A table is read as prose and never as coordinates: REACH Annex XVII is one table of
        # 24 restriction entries, each of which re-uses the enumerators `1.`, `(a)`, `(b)`, so
        # placing its interior would mint the same location two dozen times. Deep table
        # structure is the declared v0.1 gap; the cells' text still reaches every ancestor.
        "TBL",
        # Not provision structure: footnotes, consolidation notes, tables of contents, and
        # the quoted text of *another* act (`amending.py` owns that one).
        "NOTE",
        "ANNOTATION",
        "GR.ANNOTATION",
        "TOC",
        "TOC.BLK",
        "TOC.ITEM",
        "ITEM.CONT",
        "QUOT.S",
        # An `ARTICLE` reached from inside another provision is quoted text, not a provision.
        "ARTICLE",
    }
)
"""Elements whose content is text. Not walked — but their text still reaches every ancestor."""

_IDENTIFIER: Final = re.compile(r"^0*(\d+)([A-Za-z]*)$")
_ARTICLE_TITLE: Final = re.compile(r"\bArticle\s+(\d+\s*[A-Za-z]?)\b", re.IGNORECASE)
_ANNEX: Final = re.compile(r"\bANNEX\s+([IVXLCDM]+|\d+[A-Za-z]?)\b")
_APPENDIX: Final = re.compile(r"\bAPPENDIX\s+([IVXLCDM]+|\d+[A-Za-z]?)\b")
_SECTION: Final = re.compile(r"^(?:Section|SECTION)\s+([0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)")
_NUMBERED_TITLE: Final = re.compile(r"^(\d+(?:\.\d+)*)\.\s")
_MARKER: Final = re.compile(r"^\(?([0-9A-Za-z]+)\)?\.?$")
_ARABIC: Final = re.compile(r"^\d+[a-z]*$", re.IGNORECASE)
# Real characters from the documents, not typographic decoration.
_DASHES: Final = frozenset({"-", "–", "—", "―", "•", "*", ""})  # noqa: RUF001


def decode_identifier(raw: str | None) -> str | None:
    """`'004A'` → `'4a'`, `'0014'` → `'14'`. `None` when no rule applies.

    Zero-padded, letter-suffixed, and for a `PARAG` prefixed with its article
    (`'005.001A'` → `'1a'`), so only the last dotted part is read.
    """
    if raw is None:
        return None
    matched = _IDENTIFIER.fullmatch(raw.strip().rsplit(".", 1)[-1])
    if matched is None:
        return None
    return f"{int(matched[1])}{matched[2].lower()}"


def title_of(element: Element, *tags: str) -> str:
    """The flattened text of the first of `tags` this element carries, or `''`."""
    for tag in tags:
        found = element.find(tag)
        if found is not None:
            return flat_text(found)
    return ""


def article_value(element: Element) -> str | None:
    """The article number, from `@IDENTIFIER` and — when that fails — from `TI.ART`."""
    decoded = decode_identifier(element.get("IDENTIFIER"))
    if decoded is not None:
        return decoded
    matched = _ARTICLE_TITLE.search(title_of(element, "TI.ART"))
    return None if matched is None else matched[1].replace(" ", "").lower()


def annex_segment(element: Element) -> Segment | None:
    """`AN III` or `APP 1`, read from the annex's own title. `None` when it is unnumbered.

    An unnumbered one is real and must not become a unit: REACH opens its annexes with a
    `LIST OF ANNEXES` table of contents and the MDR with `ANNEXES`, and counting either as a
    provision would fabricate a change.
    """
    title = title_of(element, "TITLE/TI", "TITLE").upper()
    annex = _ANNEX.search(title)
    if annex is not None:
        return (LocationCode.AN, annex[1])
    appendix = _APPENDIX.search(title)
    if appendix is not None:
        return (LocationCode.APP, appendix[1])
    return None


def section_value(element: Element) -> str | None:
    """An annex section number: `NO.GR.SEQ` first, then a `Section A.` or `6.6.2.` title.

    A grouping with a title but no number (the MDR's `GENERAL SAFETY AND PERFORMANCE
    REQUIREMENTS`) yields `None` and is descended through transparently — its numbered
    descendants still surface.
    """
    numbered = title_of(element, "NO.GR.SEQ").strip().rstrip(".")
    if numbered:
        return numbered
    title = title_of(element, "TITLE/TI", "TITLE")
    section = _SECTION.match(title)
    if section is not None:
        return section[1].rstrip(".")
    plain = _NUMBERED_TITLE.match(title)
    return None if plain is None else plain[1]


def point_segment(element: Element, list_type: str | None) -> Segment | None:
    """The point code and value of an `NP`, from its `NO.P` marker and its list's type.

    The parentheses are not decoration: the metadata writes lettered points as `PTA (bb)`
    and numbered ones as `PO 14`, and matching that is what lets corroboration compare the two
    signals without a translation table.
    """
    marker = title_of(element, "NO.P").strip()
    if marker in _DASHES:
        return None if marker == "" else (LocationCode.TIRE, None)
    matched = _MARKER.fullmatch(marker)
    if matched is None:
        return None
    token = matched[1]
    if _ARABIC.fullmatch(token):
        return (LocationCode.PO, token)
    code = LocationCode.PTI if (list_type or "").lower() == "roman" else LocationCode.PTA
    return (code, f"({token.lower()})")
