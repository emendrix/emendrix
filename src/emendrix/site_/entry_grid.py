"""A table's rows as a grid of cells: where each cell stands, what it spans, and how it differs.

Split out of `entry_table` on 2026-10-17, when that module reached the size cap while gaining
links from identifiers to their pages. The seam is geometry against meaning: this module turns
rows of cells into `<tr>` elements, header rows included, and knows nothing of kinds, counts,
keys or identifiers; `entry_table` decides which entries show and says what they are. The
substance pages print one entry's rows under its table's header through `printed`, the same
grid an event page's entry table is drawn with.

The payload records no span direction: a covered position joins the cell above it when
everything under that cell's columns is covered too, and the cell to its left otherwise, which
is how header and grouped rows read; a position past the end of a short row is an empty cell.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from emendrix.core import EntryTable, TableEntry
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.worddiff import word_diff

__all__ = ["Grid", "Side", "grid_rows", "head_rows", "layout", "printed", "spans"]

Grid = Sequence[Sequence[str | None]]
Placed = tuple[int, str | None, int, int]
"""One cell a row prints: its column, its text (`None` for a gap nothing covers), its spans."""

Side = Literal["before", "after"]


def layout(grid: Grid, width: int) -> tuple[list[list[Placed]], dict[tuple[int, int], str]]:
    """Each row's own cells with their spans, and the text standing at every position."""
    padded = [[*row, *([None] * (width - len(row)))] for row in grid]
    owner: list[list[tuple[int, int] | None]] = []
    span: dict[tuple[int, int], list[int]] = {}
    for r, cells in enumerate(padded):
        here: list[tuple[int, int] | None] = []
        for c, text in enumerate(cells):
            origin: tuple[int, int] | None = None
            if c >= len(grid[r]):
                pass  # a short row's missing cells are gaps, never part of a span
            elif text is not None:
                origin = (r, c)
                span[origin] = [1, 1]
            else:
                above = owner[r - 1][c] if r else None
                if above is not None and all(
                    cells[col] is None for col in range(above[1], above[1] + span[above][0])
                ):
                    origin = above
                    span[above][1] = r - above[0] + 1
                left = here[c - 1] if c else None
                if origin is None and left is not None and left[0] == r:
                    origin = left
                    span[left][0] += 1
            here.append(origin)
        owner.append(here)
    placed = [
        [
            (c, padded[r][c], span[o][0], span[o][1]) if o == (r, c) else (c, None, 1, 1)
            for c, o in enumerate(here)
            if o is None or o == (r, c)
        ]
        for r, here in enumerate(owner)
    ]
    standing = {
        (r, c): padded[o[0]][o[1]] or ""
        for r, here in enumerate(owner)
        for c, o in enumerate(here)
        if o is not None
    }
    return placed, standing


def spans(across: int, down: int) -> str:
    """The `colspan` and `rowspan` attributes a cell needs, each only where it spans."""
    return "".join(
        f' {name}="{n}"' for name, n in (("colspan", across), ("rowspan", down)) if n > 1
    )


def _marked(mine: str, theirs: str, side: Side) -> Html:
    """One side of a cell that differs: what it shares with the other, and what is its own."""
    own, tag = ("deleted", "del") if side == "before" else ("inserted", "ins")
    pair = (mine, theirs) if side == "before" else (theirs, mine)
    parts: list[Html] = []
    for span in word_diff(*pair):
        if span.kind == "equal":
            parts.append(escape(span.text + span.sep))
        elif span.kind == own:
            parts.append(Html(f"<{tag}>{escape(span.text)}</{tag}>{escape(span.sep)}"))
    return Html(join(parts).rstrip())


def grid_rows(
    grid: Grid, width: int, lead: list[Html], other: Grid | None, side: Side
) -> list[Html]:
    """One side's rows; against `other`, a cell that differs carries the word diff."""
    theirs = layout(other, width)[1] if other is not None else {}
    rows: list[Html] = []
    for r, row in enumerate(layout(grid, width)[0]):
        cells = list(lead) if r == 0 else []
        for c, text, across, down in row:
            spanned = spans(across, down)
            if text is None:
                cells.append(Html(f"<td{spanned}></td>"))
            elif other is not None and theirs.get((r, c), "") != text:
                marked = _marked(text, theirs.get((r, c), ""), side)
                cells.append(Html(f'<td class="differs"{spanned}>{marked}</td>'))
            else:
                cells.append(Html(f"<td{spanned}>{escape(text)}</td>"))
        rows.append(Html(f"<tr>{join(cells)}</tr>"))
    return rows


def head_rows(header: Grid, width: int, lead: list[Html]) -> list[Html]:
    """The table's own header rows, `lead` first; a table with none gets one plain label."""
    shown = header or (("Row as printed", *([None] * (width - 1))),)
    head: list[Html] = []
    for r, row in enumerate(layout(shown, width)[0]):
        cells = [*lead] if r == 0 else []
        cells += [
            Html(f'<th scope="col"{spans(a, d)}>{escape(t or "")}</th>') for _, t, a, d in row
        ]
        head.append(Html(f"<tr>{join(cells)}</tr>"))
    return head


def printed(entry: TableEntry, table: EntryTable | None) -> Html:
    """One entry's rows as the act prints them, under its table's header rows."""
    header = table.header if table is not None else ()
    width = max((len(row) for grid in (header, entry.rows) for row in grid), default=0)
    caption = f"{entry.container.human}, table {entry.table}"
    return Html(
        f'<div class="entries"><div class="entries-scroll"><table>'
        f"<caption>{escape(caption)}</caption>"
        f"<thead>{join(head_rows(header, width, []))}</thead>"
        f"<tbody>{join(grid_rows(entry.rows, width, [], None, 'after'))}</tbody>"
        "</table></div></div>"
    )
