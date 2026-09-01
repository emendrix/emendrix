"""Text out of Formex elements: the verbatim form, the comparison form, and the dates.

Two text forms, built here and never derived from one another. `comparison_text` inserts a
separator at *every* element boundary and then collapses whitespace; `verbatim_text` keeps
the document's own characters and its own spacing, and breaks the line only where the markup
opens a new block. That difference is the whole difficulty of comparing across Formex
generations: on the REACH 2008→2009 pair, extraction that loses element boundaries reports
all 143 comparable units as modified against 40 real ones (measured 2026-08-05). Collapsing
whitespace afterwards cannot put back a boundary that extraction never emitted.

## Why the verbatim form carries a line break at all

Formex is a tree, not a character stream, and it puts no whitespace between a block and the
next one: `</TI.ART><STI.ART>`, `</NO.PARAG><ALINEA>` and `</ALINEA></PARAG><PARAG>` are
directly adjacent in the source (read off the 2017R0745 2017-05-05 consolidation on
2026-08-12). Joining the text nodes with nothing manufactures character sequences that appear
neither in the document nor in any published rendering of the law: `59Derogation`,
`procedures1.By`, `health.2.The`. There is no stream to transcribe, so the line break is a
serialization choice rather than a normalisation of stored text, and it is a smaller edit than
the ones this module already makes (a whole subtree dropped, every processing instruction
dropped, all markup dropped).

Nothing is collapsed, nothing is trimmed and no character of the document is lost: the only
edit is an inserted separator, and only at a boundary the source marked with markup and left
without text.

## Which boundaries get one

`BLOCK_ELEMENTS` and `DETACHED_ELEMENTS`, and only when the line has text on it already.
Both sets are measured, not guessed. An element is in the first because across all 44
committed Formex packages it never once appears inside a run of text. The eight tags that do
(`HT`, `DATE`, `FT`, `LINK`, `REF.DOC`, `REF.DOC.OJ`, `QUOT.START`, `QUOT.END`) are left
joined with nothing, because a separator around them damages a sentence: `<DATE>` sits
mid-clause, and a blanket one turns `from 24 April 2020 to 25 May 2021,` into `from  24 April
2020  to  25 May 2021 ,`.

`DETACHED_ELEMENTS` is the third case, and the reason there are two sets rather than one. A
footnote (`NOTE`) and the quoted text of another act (`QUOT.S`) sit *inside* a run of text, so
neither can join the first set without making its safety argument false, and their content is
still a block the source leaves without a separator. Joined with nothing they run the sentence
into the footnote: `CouncilRegulation (EU) 2017/745` and `the following point is added:(i)`,
both in MDR Article 118 (read 2026-09-01), the same class as `59Derogation`. The break goes
before their content and not after it, because the interrupted sentence resumes in the tail
and a second break there strands its closing full stop on a line of its own.

One subtree is excluded from **both** forms: `BIB.INSTANCE`, the publication metadata block
(OJ page numbers, volume, document date) that a standalone `ANNEX` document carries and its
consolidated counterpart does not. Provision text it is not, and including it fabricates annex
changes. Nothing else is dropped.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final
from xml.etree.ElementTree import Element

from emendrix.core import ComparisonText, DateMention, ProvisionText, normalize_for_comparison
from emendrix.eu.dates import compact_date

__all__ = [
    "BLOCK_ELEMENTS",
    "CONTEXT_LIMIT",
    "DETACHED_ELEMENTS",
    "SKIPPED_SUBTREES",
    "comparison_text",
    "date_mentions",
    "flat_text",
    "head_text",
    "verbatim_text",
]

SKIPPED_SUBTREES: Final = frozenset({"BIB.INSTANCE"})
"""Subtrees that are not provision text (see the module docstring)."""

CONTEXT_LIMIT: Final = 240
"""How much of the enclosing text a `DateMention` carries. Truncation is marked with `…`."""

_ELLIPSIS: Final = "…"

BLOCK_ELEMENTS: Final = frozenset(
    {
        # Provision structure.
        "ARTICLE",
        "PARAG",
        "ALINEA",
        "NP",
        "TXT",
        "LIST",
        "ITEM",
        "P",
        "DLIST",
        "DLIST.ITEM",
        "TERM",
        "DEFINITION",
        # Annex structure.
        "ANNEX",
        "CONS.ANNEX",
        "CONTENTS",
        "GR.SEQ",
        # Headings and enumerators, each of which is a line of its own.
        "TITLE",
        "TI",
        "STI",
        "TI.ART",
        "STI.ART",
        "TI.BLK",
        "NO.PARAG",
        "NO.P",
        "NO.GR.SEQ",
        "NO.ITEM",
        # Tables, read as prose: a cell per column, a line per row.
        "TBL",
        "CORPUS",
        "BLK",
        "ROW",
        "CELL",
        "GR.NOTES",
        "LOC.NOTES",
        # Tables of contents, annotations, addresses, embedded graphics.
        "TOC",
        "TOC.BLK",
        "TOC.ITEM",
        "ITEM.CONT",
        "ANNOTATION",
        "GR.ANNOTATION",
        "ADDR",
        "INCL.ELEMENT",
        "IMG.CNT",
    }
)
"""Elements that open a block, so the verbatim form breaks the line before them.

Measured over all 44 committed Formex packages on 2026-08-12: every tag here occurs inside a
unit's subtree and not once, in any of them, does the source put text immediately before or
after it. An element left out of the set is joined with nothing, which is what an inline one
needs and what an unrecognised one gets, so a tag this project has never seen keeps the
conservative behaviour rather than acquiring a break in the middle of a sentence.
"""

DETACHED_ELEMENTS: Final = frozenset({"NOTE", "QUOT.S"})
"""Elements sitting inside a run of text whose content is a block of its own.

A footnote and the quoted text of another act interrupt a sentence rather than continuing it,
so the line breaks before their content even though the element itself has text right beside
it. That is what keeps them out of `BLOCK_ELEMENTS`, whose members are exactly the tags that
never carry adjacent text: these two carry it 2380 times, so admitting them there would falsify
the one claim that set is safe because of.

Both figures are measured over all 44 committed Formex packages on 2026-09-01, walking only the
subtrees `verbatim_text` is ever called on. In those, `NOTE` and `QUOT.S` are the only tags
outside `BLOCK_ELEMENTS` that hold a block child, 1904 times and 346 times, so this set is the
whole class rather than the two instances that exposed it.
"""

_CONTINUED_BY: Final = frozenset({"NO.PARAG", "NO.P", "NO.GR.SEQ", "NO.ITEM"})
"""Enumerators. What follows one shares its line: `1.` and its paragraph are one line."""

_CONTINUING: Final = frozenset({"CELL"})
"""A table's cells read across the row, so a cell continues the line rather than opening one."""

_BREAK: Final = "\n"
_SAME_LINE: Final = " "


def _fragments(element: Element) -> Iterator[str]:
    """Every text fragment under `element`, in document order, `BIB.INSTANCE` aside."""
    if element.text:
        yield element.text
    for child in element:
        if child.tag not in SKIPPED_SUBTREES:
            yield from _fragments(child)
        if child.tail:
            yield child.tail


def _open_line(parts: list[str]) -> bool:
    """Whether this element has already put a character on the line it is writing.

    Nothing empty is ever appended to `parts`, so the last fragment's last character is the
    last character emitted. A block that opens an element, or that follows whitespace the
    document already supplied, needs no separator of ours.
    """
    return bool(parts) and not parts[-1][-1].isspace()


def _separator(previous: str | None, tag: str) -> str:
    return _SAME_LINE if previous in _CONTINUED_BY or tag in _CONTINUING else _BREAK


def _verbatim_fragments(element: Element) -> list[str]:
    """`_fragments`, with a separator inserted where the markup opens a new block.

    A `DETACHED_ELEMENTS` child opens one too: its content is a block even though the element
    interrupts a sentence rather than following one (see the module docstring).

    Every separator is decided by the element doing the walking and inserted into *its* own
    stream, never into a child's. A child's fragments therefore land contiguously and
    unaltered, which is what makes a descendant's verbatim text a literal substring of its
    ancestor's: the property `explain/context.py` checks containment against.
    """
    parts: list[str] = []
    previous: str | None = None
    if element.text:
        parts.append(element.text)
    for child in element:
        if child.tag not in SKIPPED_SUBTREES:
            if (child.tag in BLOCK_ELEMENTS or child.tag in DETACHED_ELEMENTS) and _open_line(
                parts
            ):
                parts.append(_separator(previous, child.tag))
            emitted = len(parts)
            parts.extend(_verbatim_fragments(child))
            previous = child.tag if len(parts) > emitted else previous
        if child.tail:
            parts.append(child.tail)
            previous = None
    return parts


def verbatim_text(element: Element) -> ProvisionText:
    """The characters the document produced, and a line break where it opened a block.

    Never normalised, never collapsed, never trimmed: this is what gets quoted. The only
    edit is the separator, and it lands only at a boundary the source marked with markup and
    left without text of its own (see the module docstring for why, and for the measurement
    that decided which boundaries those are).
    """
    return ProvisionText("".join(_verbatim_fragments(element)))


def flat_text(element: Element) -> str:
    """Whitespace-collapsed text with a separator at every element boundary.

    Every boundary, including the inline ones `verbatim_text` leaves alone: this form is
    only ever compared and never shown, so an extra space costs nothing and a missing one
    costs a match. That is also why it is not `verbatim_text` with the spaces squeezed out.
    The 2008 Formex generation runs an annex title into its subtitle with no whitespace
    between the elements (`ANNEX I` + `GENERAL PROVISIONS…`), and a number regex over a form
    that lost that boundary finds no annex at all.
    """
    return normalize_for_comparison(" ".join(_fragments(element)))


def comparison_text(element: Element) -> ComparisonText:
    """`flat_text`, typed as what the diff is allowed to compare and never to quote."""
    return ComparisonText(flat_text(element))


def head_text(element: Element, limit: int) -> str:
    """`flat_text` of roughly the first `limit` characters, without flattening the rest.

    An amending act's Article 1 can be the whole act: on `32026R1744` it is 180 kB inside one
    `ALINEA`. Reading a lead-in clause must not cost that.
    """
    parts: list[str] = []
    length = 0
    for fragment in _fragments(element):
        parts.append(fragment)
        length += len(fragment)
        if length >= limit:
            break
    return normalize_for_comparison(" ".join(parts))


def _context(element: Element) -> str:
    text = flat_text(element)
    if len(text) <= CONTEXT_LIMIT:
        return text
    return text[:CONTEXT_LIMIT].rstrip() + _ELLIPSIS


def date_mentions(element: Element) -> tuple[tuple[DateMention, ...], int]:
    """Every `<DATE ISO=…>` under `element`, with its surrounding text, and how many failed.

    Dates are extracted, never interpreted: what an act's application article *means* by a
    date is prose, so the second clock quotes and does not infer.

    The attribute is named `ISO` and holds `20271202`, which is not the ISO spelling CELLAR's
    notices use — hence `eu.dates.compact_date` here and `iso_date` there.
    """
    found: list[DateMention] = []
    unreadable = 0

    def walk(node: Element) -> None:
        nonlocal unreadable
        for child in node:
            if child.tag in SKIPPED_SUBTREES:
                continue
            if child.tag == "DATE":
                value = compact_date(child.get("ISO"))
                if value is None:
                    unreadable += 1
                else:
                    found.append(DateMention(value=value, context=_context(node)))
            walk(child)

    walk(element)
    return tuple(found), unreadable
