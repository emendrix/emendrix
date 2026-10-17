"""The rows of a profiled table that a change moved, as a table a reader can read.

When a change carries `table_entries`, the keyed diff of a table's rows read from the act's own
markup, its block shows them above the text: a count line, then each entry by its key and
identifiers under the table's own header rows. Every cell is the row as printed and every count
is read off the delta; no model wrote any of it, and nothing says what a row means. `None`
renders nothing; a delta with no changes says no keyed entry moved.

Nothing is hidden without its count: per kind, the first `OPEN` entries are open, the rest up
to `LISTED` sit behind one closed `<details>` naming how many, and past that only the keys are
listed, with the file holding their rows. A typography-only amendment is still an amendment,
in its own closed `<details>` under the amended table. How rows become cells, spans and word
diffs is `entry_grid`'s. Each CAS and EC number an entry carries links to its own page where the
build wrote one; every other identifier is printed as text.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import groupby
from typing import Final

from emendrix.core import EntryChange, EntryDelta, EntryKind, EntryTable
from emendrix.site_.entry_grid import grid_rows, head_rows, spans
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.substance_inputs import NO_LINKS, SubstanceLinks

__all__ = ["LISTED", "OPEN", "SCHEMES", "change_table", "entry_table"]

OPEN: Final = 50
"""Entries of one kind shown open; the rest are folded or listed by key."""

LISTED: Final = 200
"""Entries of one kind rendered as rows at all. Past it, keys only: the rows are in the file."""

_KINDS: Final[tuple[EntryKind, ...]] = ("added", "amended", "removed")
SCHEMES: Final = {"cas": "CAS", "ec": "EC", "index": "Index No"}
"""How each identifier scheme is named before its value, on every page that prints one."""
_TYPOGRAPHY: Final = "spacing, dash forms or accents"

Changes = Sequence[EntryChange]
Tables = Sequence[EntryTable]
Line = tuple[str, str | None]
"""One line naming an entry: its words, and the page they link to where there is one."""


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


def _named(change: EntryChange, table: EntryTable | None, links: SubstanceLinks) -> list[Line]:
    """The entry's key (its name where the name is the key), identifiers and block heading."""
    entry = change.after or change.before
    assert entry is not None
    label = table.key_label if table is not None else None
    lines: list[Line] = [(f"{label} {change.key}" if label else (entry.name or change.key), None)]
    if change.occurrence > 1:
        lines.append((f"occurrence {change.occurrence}", None))
    sides = [side for side in (change.before, change.after) if side is not None]
    found = sorted({(ident.scheme, ident.value) for side in sides for ident in side.identifiers})
    for scheme, value in found:
        line = f"{SCHEMES.get(scheme, scheme.upper())} {value}"
        if line != lines[0][0]:
            lines.append((line, links.href(scheme, value)))
    groups = sorted({side.group for side in sides if side.group})
    return lines + [(f"In: {group}", None) for group in groups]


def _inline(words: str, href: str | None) -> Html:
    return escape(words) if href is None else Html(f'<a href="{escape(href)}">{escape(words)}</a>')


def _who(change: EntryChange, table: EntryTable | None, rows: int, links: SubstanceLinks) -> Html:
    named = _named(change, table, links)
    lines = join(Html(f"<span>{_inline(words, href)}</span>") for words, href in named)
    return Html(f'<th scope="rowgroup"{spans(1, rows)}>{lines}</th>')


def _body(change: EntryChange, table: EntryTable | None, width: int, links: SubstanceLinks) -> Html:
    before, after = change.before, change.after
    if change.kind != "amended":
        entry = after or before
        assert entry is not None
        who = _who(change, table, len(entry.rows), links)
        return Html(f"<tbody>{join(grid_rows(entry.rows, width, [who], None, 'after'))}</tbody>")
    assert before is not None and after is not None
    who = _who(change, table, len(before.rows) + len(after.rows), links)
    old = Html(f'<td class="side"{spans(1, len(before.rows))}>Before</td>')
    new = Html(f'<td class="side"{spans(1, len(after.rows))}>After</td>')
    rows = grid_rows(before.rows, width, [who, old], after.rows, "before")
    rows += grid_rows(after.rows, width, [new], before.rows, "after")
    return Html(f"<tbody>{join(rows)}</tbody>")


def _table_of(change: EntryChange, tables: Tables) -> EntryTable | None:
    place = (change.container, change.table)
    return next((table for table in tables if (table.container, table.table) == place), None)


def _table(kind: EntryKind, changes: Changes, tables: Tables, links: SubstanceLinks) -> Html:
    """One `<table>` for one kind's entries of one table, under that table's header rows."""
    first = changes[0]
    table = _table_of(first, tables)
    header = table.header if table is not None else ()
    sides = [side for change in changes for side in (change.before, change.after) if side]
    grids = (header, *(side.rows for side in sides))
    width = max((len(row) for grid in grids for row in grid), default=0)
    depth = max(len(header), 1)
    lead = [Html(f'<th scope="col"{spans(1, depth)}>Identifiers</th>')]
    if kind == "amended":
        lead.append(Html(f'<th scope="col"{spans(1, depth)}>Version</th>'))
    head = head_rows(header, width, lead)
    caption = f"{kind.capitalize()} entries, {first.container.human}, table {first.table}"
    body = join(_body(change, table, width, links) for change in changes)
    return Html(
        f'<div class="entries-scroll"><table><caption>{escape(caption)}</caption>'
        f"<thead>{join(head)}</thead>{body}</table></div>"
    )


def _tables(kind: EntryKind, changes: Changes, tables: Tables, links: SubstanceLinks) -> list[Html]:
    grouped = groupby(changes, key=lambda change: (change.container.canonical, change.table))
    return [_table(kind, list(group), tables, links) for _, group in grouped]


def _tiers(
    kind: EntryKind, changes: Changes, tables: Tables, href: str, open_: int, links: SubstanceLinks
) -> list[Html]:
    """The first `open_` as tables, the rest to `LISTED` behind one count, then keys alone."""
    lines = _tables(kind, changes[:open_], tables, links)
    middle = changes[open_:LISTED]
    if middle:
        summary = f"{len(middle)} more {kind} {'entry' if len(middle) == 1 else 'entries'}"
        lines.append(Html(f"<details><summary>{escape(summary)}</summary>"))
        lines += _tables(kind, middle, tables, links)
        lines.append(Html("</details>"))
    rest = changes[LISTED:]
    if rest:
        noun = "entry" if len(rest) == 1 else "entries"
        listed = (_named(c, _table_of(c, tables), links) for c in rest)
        keys = join(
            Html(f"<li>{join((_inline(*line) for line in named), ', ')}</li>") for named in listed
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


def change_table(change: EntryChange, tables: Tables, links: SubstanceLinks) -> Html:
    """One entry change alone, before and after under its table's header, as a substance page
    lists it in a history."""
    return Html(f'<div class="entries">{_table(change.kind, [change], tables, links)}</div>')


def entry_table(
    delta: EntryDelta | None, rows_href: str, links: SubstanceLinks = NO_LINKS
) -> list[Html]:
    """The entry table of one change, or nothing where the change carries no delta.

    `rows_href` is the address of the change's own file in the API, where the rows of an entry
    listed by key alone are; the caller builds it from the layout the record is served under.
    `links` names the substance pages the build wrote, under the page's own climb to the root.
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
        lines += _tiers(kind, plain, delta.tables, rows_href, OPEN, links)
        typography = [change for change in changes if change.typography_only]
        if typography:
            summary = (
                f"{_n(len(typography), 'entry differs', 'entries differ')} only in {_TYPOGRAPHY}"
            )
            lines.append(Html(f'<details class="typography"><summary>{escape(summary)}</summary>'))
            lines += _tiers(kind, typography, delta.tables, rows_href, LISTED, links)
            lines.append(Html("</details>"))
    lines.append(Html("</section>"))
    return lines
