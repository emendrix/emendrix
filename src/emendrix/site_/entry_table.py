"""The rows of a profiled table that a change moved, as a table a reader can read.

When a change carries `table_entries`, the keyed diff of a table's rows read from the act's own
markup, its block shows them above the text: a count line, then each entry by its key and
identifiers under the table's own header rows. Every cell is the row as printed and every count
is read off the delta; no model wrote any of it, and nothing says what a row means. `None`
renders nothing; a delta with no changes says no keyed entry moved.

Nothing is hidden without its count: per kind, the first `OPEN` entries are open, the rest up
to `LISTED` sit behind one closed `<details>` naming how many, and past that only the keys are
listed, with the file holding their rows. A typography-only amendment is still an amendment,
in its own closed `<details>` under the amended table. The payload records no span direction:
a covered position joins the cell above it when everything under that cell's columns is
covered too, and the cell to its left otherwise, which is how header and grouped rows read; a
position past the end of a short row is an empty cell.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import groupby
from typing import Final, Literal

from emendrix.core import EntryChange, EntryDelta, EntryKind, EntryTable
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.worddiff import word_diff

__all__ = ["LISTED", "OPEN", "entry_table"]

OPEN: Final = 50
"""Entries of one kind shown open; the rest are folded or listed by key."""

LISTED: Final = 200
"""Entries of one kind rendered as rows at all. Past it, keys only: the rows are in the file."""

_KINDS: Final[tuple[EntryKind, ...]] = ("added", "amended", "removed")
_SCHEMES: Final = {"cas": "CAS", "ec": "EC", "index": "Index No"}
_TYPOGRAPHY: Final = "spacing, dash forms or accents"

Changes = Sequence[EntryChange]
Tables = Sequence[EntryTable]
Grid = Sequence[Sequence[str | None]]
Placed = tuple[int, str | None, int, int]
"""One cell a row prints: its column, its text (`None` for a gap nothing covers), its spans."""


def _n(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


def _count_line(delta: EntryDelta) -> str:
    added, amended, removed = (delta.count(kind) for kind in _KINDS)
    typography, spaced = delta.typography_only, delta.whitespace_only
    if not delta.changes:
        line = (
            "No keyed table entry changed between these two versions. "
            "The text below shows where the provision did change."
        )
        if spaced:
            line += f" {_n(spaced, 'entry changed', 'entries changed')} only in whitespace."
        return line
    line = f"{_n(added, 'entry', 'entries')} added, {amended} amended, {removed} removed"
    if typography:
        verb = "differs" if typography == 1 else "differ"
        line += f" ({typography} of the amended {verb} only in {_TYPOGRAPHY})"
    line += "."
    if spaced:
        verb = "is" if spaced == 1 else "are"
        line += f" {spaced} more changed only in whitespace and {verb} not listed."
    return line


_GAPS: Final = (
    ("unkeyed_rows", "row", "carries no key and is not compared"),
    ("unrecognised_tables", "table", "could not be recognised and is not read"),
)
"""Each gap the sentence names: the counter, its noun, and the rest of the clause for one."""


def _gap_line(delta: EntryDelta) -> str | None:
    """The gaps either side counted, both sides named where the two versions count differently."""
    parts: list[str] = []
    for field, noun, one in _GAPS:
        old, new = getattr(delta.gaps_before, field), getattr(delta.gaps_after, field)
        many = one.replace("carries", "carry").replace(" is ", " are ")
        if old != new:
            parts.append(
                f"{_n(old, noun, noun + 's')} in the previous version and {new} in this one {many}"
            )
        elif new:
            parts.append(f"{_n(new, noun, noun + 's')} {one if new == 1 else many}")
    sentences = [f"{'; '.join(parts)}."] if parts else []
    if delta.unpaired:
        verb = "is" if len(delta.unpaired) == 1 else "are"
        sentences.append(
            f"{_n(len(delta.unpaired), 'key', 'keys')} printed a different number of times "
            f"in the two versions {verb} not compared."
        )
    return " ".join(sentences) or None


def _layout(grid: Grid, width: int) -> tuple[list[list[Placed]], dict[tuple[int, int], str]]:
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


def _spans(across: int, down: int) -> str:
    return "".join(
        f' {name}="{n}"' for name, n in (("colspan", across), ("rowspan", down)) if n > 1
    )


Side = Literal["before", "after"]


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


def _rows(grid: Grid, width: int, lead: list[Html], other: Grid | None, side: Side) -> list[Html]:
    """One side's rows; against `other`, a cell that differs carries the word diff."""
    theirs = _layout(other, width)[1] if other is not None else {}
    rows: list[Html] = []
    for r, row in enumerate(_layout(grid, width)[0]):
        cells = list(lead) if r == 0 else []
        for c, text, across, down in row:
            spans = _spans(across, down)
            if text is None:
                cells.append(Html(f"<td{spans}></td>"))
            elif other is not None and theirs.get((r, c), "") != text:
                marked = _marked(text, theirs.get((r, c), ""), side)
                cells.append(Html(f'<td class="differs"{spans}>{marked}</td>'))
            else:
                cells.append(Html(f"<td{spans}>{escape(text)}</td>"))
        rows.append(Html(f"<tr>{join(cells)}</tr>"))
    return rows


def _named(change: EntryChange, table: EntryTable | None) -> list[str]:
    """The entry's key (its name where the name is the key), identifiers and block heading."""
    entry = change.after or change.before
    assert entry is not None
    label = table.key_label if table is not None else None
    lines = [f"{label} {change.key}" if label else (entry.name or change.key)]
    if change.occurrence > 1:
        lines.append(f"occurrence {change.occurrence}")
    sides = [side for side in (change.before, change.after) if side is not None]
    found = sorted({(ident.scheme, ident.value) for side in sides for ident in side.identifiers})
    named = (f"{_SCHEMES.get(scheme, scheme.upper())} {value}" for scheme, value in found)
    lines += [line for line in named if line != lines[0]]
    return lines + [
        f"In: {group}" for group in sorted({side.group for side in sides if side.group})
    ]


def _who(change: EntryChange, table: EntryTable | None, rows: int) -> Html:
    lines = join(Html(f"<span>{escape(line)}</span>") for line in _named(change, table))
    return Html(f'<th scope="rowgroup"{_spans(1, rows)}>{lines}</th>')


def _body(change: EntryChange, table: EntryTable | None, width: int) -> Html:
    before, after = change.before, change.after
    if change.kind != "amended":
        entry = after or before
        assert entry is not None
        who = _who(change, table, len(entry.rows))
        return Html(f"<tbody>{join(_rows(entry.rows, width, [who], None, 'after'))}</tbody>")
    assert before is not None and after is not None
    who = _who(change, table, len(before.rows) + len(after.rows))
    old = Html(f'<td class="side"{_spans(1, len(before.rows))}>Before</td>')
    new = Html(f'<td class="side"{_spans(1, len(after.rows))}>After</td>')
    rows = _rows(before.rows, width, [who, old], after.rows, "before")
    rows += _rows(after.rows, width, [new], before.rows, "after")
    return Html(f"<tbody>{join(rows)}</tbody>")


def _table_of(change: EntryChange, tables: Tables) -> EntryTable | None:
    place = (change.container, change.table)
    return next((table for table in tables if (table.container, table.table) == place), None)


def _table(kind: EntryKind, changes: Changes, tables: Tables) -> Html:
    """One `<table>` for one kind's entries of one table, under that table's header rows."""
    first = changes[0]
    table = _table_of(first, tables)
    header = table.header if table is not None else ()
    sides = [side for change in changes for side in (change.before, change.after) if side]
    grids = (header, *(side.rows for side in sides))
    width = max((len(row) for grid in grids for row in grid), default=0)
    depth = max(len(header), 1)
    lead = [Html(f'<th scope="col"{_spans(1, depth)}>Identifiers</th>')]
    if kind == "amended":
        lead.append(Html(f'<th scope="col"{_spans(1, depth)}>Version</th>'))
    shown = header or (("Row as printed", *([None] * (width - 1))),)
    head: list[Html] = []
    for r, row in enumerate(_layout(shown, width)[0]):
        cells = [*lead] if r == 0 else []
        cells += [
            Html(f'<th scope="col"{_spans(a, d)}>{escape(t or "")}</th>') for _, t, a, d in row
        ]
        head.append(Html(f"<tr>{join(cells)}</tr>"))
    caption = f"{kind.capitalize()} entries, {first.container.human}, table {first.table}"
    return Html(
        f'<div class="entries-scroll"><table><caption>{escape(caption)}</caption>'
        f"<thead>{join(head)}</thead>{join(_body(c, table, width) for c in changes)}"
        "</table></div>"
    )


def _tables(kind: EntryKind, changes: Changes, tables: Tables) -> list[Html]:
    grouped = groupby(changes, key=lambda change: (change.container.canonical, change.table))
    return [_table(kind, list(group), tables) for _, group in grouped]


def _tiers(kind: EntryKind, changes: Changes, tables: Tables, href: str, open_: int) -> list[Html]:
    """The first `open_` as tables, the rest to `LISTED` behind one count, then keys alone."""
    lines = _tables(kind, changes[:open_], tables)
    middle = changes[open_:LISTED]
    if middle:
        summary = f"{len(middle)} more {kind} {'entry' if len(middle) == 1 else 'entries'}"
        lines.append(Html(f"<details><summary>{escape(summary)}</summary>"))
        lines += _tables(kind, middle, tables)
        lines.append(Html("</details>"))
    rest = changes[LISTED:]
    if rest:
        noun = "entry" if len(rest) == 1 else "entries"
        keys = join(
            Html(f"<li>{escape(', '.join(_named(c, _table_of(c, tables))))}</li>") for c in rest
        )
        shown = href.lstrip("./")
        lines += [
            Html(f'<p class="small">{len(rest)} more {kind} {noun}, by key only:</p>'),
            Html(f'<ul class="entry-keys">{keys}</ul>'),
            Html(
                '<p class="small">Their rows are in this change\'s file: '
                f'<a href="{escape(href)}">{escape(shown)}</a>.</p>'
            ),
        ]
    return lines


def entry_table(delta: EntryDelta | None, rows_href: str) -> list[Html]:
    """The entry table of one change, or nothing where the change carries no delta.

    `rows_href` is the address of the change's own file in the API, where the rows of an entry
    listed by key alone are; the caller builds it from the layout the record is served under.
    """
    if delta is None:
        return []
    lines = [
        Html('<section class="entries" aria-label="Table entries">'),
        Html(f'<p class="entries-count">{escape(_count_line(delta))}</p>'),
    ]
    gaps = _gap_line(delta)
    if gaps is not None:
        lines.append(Html(f'<p class="small muted">{escape(gaps)}</p>'))
    for kind in _KINDS:
        changes = [change for change in delta.changes if change.kind == kind]
        if not changes:
            continue
        lines.append(Html(f"<h4>{escape(_n(len(changes), 'entry', 'entries'))} {kind}</h4>"))
        plain = [change for change in changes if not change.typography_only]
        lines += _tiers(kind, plain, delta.tables, rows_href, OPEN)
        typography = [change for change in changes if change.typography_only]
        if typography:
            summary = (
                f"{_n(len(typography), 'entry differs', 'entries differ')} only in {_TYPOGRAPHY}"
            )
            lines.append(Html(f'<details class="typography"><summary>{escape(summary)}</summary>'))
            lines += _tiers(kind, typography, delta.tables, rows_href, LISTED)
            lines.append(Html("</details>"))
    lines.append(Html("</section>"))
    return lines
