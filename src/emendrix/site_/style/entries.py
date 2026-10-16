"""A change's table entries: the rows the act prints, keyed, before the text that holds them.

After `evidence`, whose generic table rules these narrow: an entry table keeps its grid on a
phone rather than stacking into blocks, because a row read cell by cell under its header is
the whole point of it, and a table wider than the screen scrolls inside its own box instead of
the page. Cells are the law's words, so they take the serif and keep their own line breaks;
the identifiers column is the site naming the entry, in the sans.

Every colour is a token, so the dark scheme needs no line of its own here: the palette swap
in `tokens` carries it. Print and forced colours are in `media`, last in the cascade.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["ENTRIES"]

ENTRIES: Final = """\
.entries { margin: var(--space-3) 0; }
.entries-count { margin: 0 0 var(--space-2); font-size: var(--text-meta); font-weight: 600; }
.entries h4 { margin: var(--space-3) 0 var(--space-2); font-size: var(--text-body); }
.entries details { margin: var(--space-2) 0; }
.entries summary { font-size: var(--text-meta); cursor: pointer; }
/* A wide table scrolls inside its own box, never the page. */
.entries-scroll { max-width: 100%; overflow-x: auto; margin: 0 0 var(--space-3); }
/* Named with the class so these outrank the phone rule that stacks a generic table. */
.entries table { display: table; width: auto; min-width: 100%; font-size: var(--text-meta); }
.entries caption { padding: 0 0 var(--space-1); text-align: left; font-size: var(--text-label);
                   color: var(--muted); caption-side: top; }
.entries thead { position: static; width: auto; height: auto; overflow: visible;
                 clip-path: none; display: table-header-group; }
.entries tbody { display: table-row-group; }
.entries tr { display: table-row; padding: 0; border: 0; }
.entries th, .entries td { display: table-cell; padding: .35rem .5rem; vertical-align: top;
                           border: 1px solid var(--rule); font-weight: 400; }
.entries thead th { color: var(--muted); font-weight: 600; white-space: pre-wrap; }
/* The row as printed: the serif, its own line breaks kept. */
.entries td { font-family: var(--serif); white-space: pre-wrap; overflow-wrap: anywhere;
              min-width: 6rem; color: var(--fg); }
.entries tbody th { font-family: var(--sans); text-align: left; white-space: nowrap;
                    color: var(--fg); }
.entries tbody th span { display: block; }
.entries tbody th span:first-child { font-weight: 600; }
.entries td.side { font-family: var(--sans); color: var(--muted); min-width: 0;
                   white-space: nowrap; }
/* A cell that differs keeps its marks as a diff does: a tint, and an underline or a strike. */
.entries td.differs { border-left: 3px solid var(--edge); }
.entries ins, .entries del { padding: 0 .1em; border-radius: 2px; color: var(--fg); }
.entries ins { background: var(--ins); text-decoration: underline; text-underline-offset: .2em; }
.entries del { background: var(--del); text-decoration: line-through; }
.entry-keys { columns: 16rem; margin: 0 0 var(--space-2); font-size: var(--text-meta); }
"""
