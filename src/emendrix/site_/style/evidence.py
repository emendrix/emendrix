"""The text a change quotes, and the map over the changes: the index, the diff, the table.

Ninth in the cascade, after `change`, so a rule here may rely on everything before it and on
`timeline` and `change` in particular, which draw the pages and the blocks this text sits in.
This module dresses the evidence rather than the statement about it: the in-page map of the
changes and the sticky column it becomes, the gathered rows with no text to show, the
`<details>` a change's text sits in, the strip naming the two sides compared, the unified diff,
the verbatim blocks and the metrics table.

`timeline` was split off on 2026-09-05, when the gathered rows needed rules this module had no
room for under the size cap, and `change` on 2026-09-18, for the same reason. Two decisions
carry the look of the text and are worth stating:

- **The law's register.** The diff and the verbatim text are EUR-Lex's words, set in the serif
  with ligatures off and tabular figures, on a panel under a strip naming both sides, by role
  and with their consolidation codes as identifiers. The explanation above it is the model's,
  in the sans, and `change` sets it; a reader can tell who is speaking before reading a word.
- **Prose and evidence each have a measure.** Prose is held to `--measure` by `base`; the diff
  and the verbatim blocks to `--legal-measure`, about eighty characters of the serif, chosen
  on 2026-09-18. Stored text carries its own line breaks, and a line that ran the full width
  of the shell would be a line nobody can track back to its start.

Two rules carry a constraint rather than a preference and are commented where they sit: the
diff preserves the line breaks the stored text already has, and every mark inside a diff says
what it is by an underline or a strike-through as well as by its tint.

The table rules are generic on purpose. The methodology page is the only page with a table
today, and its column behaviour lives with that page in `pages`; the shape of a table is
evidence typography and belongs here, where an act page that grows one would find it.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["EVIDENCE"]

EVIDENCE: Final = """\
/* A map of the page, not a second copy of it: one wrapping row, so forty-five provisions
   cost a few lines of height and a reader can see the whole event at once. */
.touched { margin: var(--space-3) 0 var(--space-4); padding: var(--space-3);
           background: var(--panel); border: 1px solid var(--rule);
           border-radius: var(--radius); font-size: var(--text-meta); line-height: 1.35; }
.touched p { margin: 0 0 var(--space-2); }
.touched ol { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-3);
              list-style: none; margin: 0; padding: 0; }
.touched li { display: flex; align-items: baseline; gap: var(--space-1); }
.touched li > a .loc { font-weight: inherit; }
/* A row is a coordinate while the index is a wrapping row, and a coordinate over its title
   once it is a column; the title is whole in the markup and cut to one line here. */
.touched li > a .ttl { display: none; }
/* The decade of characters a change moved, as weight on its link, so the index reads as a map
   of where the text is rather than only of where a change is. Two weights are loaded, so the
   four decades fall into two; the count beside each one is the fact, and the classes claim
   nothing about importance. */
.touched .mag-1 a { font-weight: 400; }
.touched .mag-2 a { font-weight: 400; }
.touched .mag-3 a { font-weight: 600; }
.touched .mag-4 a { font-weight: 600; }
/* The same grid the act page draws, with the event's index as the left column, at the one
   width the act page becomes two columns. The `.sidebar` cap above is deliberately not reused:
   that one bounds a `<details>` of hundreds of links at every width, where this is a row of
   forty coordinates that costs a few lines while it is a row and needs the cap only once it
   stands as a column. Below the query nothing here applies and the row is untouched. */
@media (min-width: 60rem) {
  .event-layout .touched {
    position: sticky;
    top: var(--space-3);
    max-height: calc(100vh - 2rem);
    margin: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  .event-layout .touched ol { display: block; }
  .event-layout .touched li { padding: .45rem 0; border-top: 1px solid var(--rule); }
  .event-layout .touched li:first-child { border-top: 0; }
  .event-layout .touched li { display: grid; grid-template-columns: minmax(0, 1fr) auto;
                              gap: .1rem .5rem; }
  .event-layout .touched li > a { grid-row: span 2; min-width: 0; text-decoration: none; }
  .event-layout .touched li > a .loc { text-decoration: underline; text-underline-offset: .18em;
                                       text-decoration-thickness: 1px; }
  .event-layout .touched li > a:hover .loc { text-decoration-thickness: 2px; }
  .event-layout .touched li > a .ttl { display: block; overflow: hidden; margin-top: .1rem;
                                       color: var(--muted); font-size: var(--text-label);
                                       font-weight: 400; line-height: 1.35;
                                       text-overflow: ellipsis; white-space: nowrap; }
  .event-layout .touched li .tag, .event-layout .touched li .mag { justify-self: end;
                                                                   align-self: start; }
  .event-layout .touched li .mag { grid-column: 2; }
  .changes { min-width: 0; }
  .changes > .chg:first-child { border-top: 0; padding-top: 0; }
}
/* The changes with no text to show, gathered at the foot of an event: one line each, with the
   rest of the block hidden until the row is the fragment target. `:target` is what a permalink
   into this list sets, so the link that names a row is the link that opens it, with no script
   and nothing dropped from the markup. */
.quiet { margin: var(--space-5) 0 0; }
.quiet .chg { padding: .2rem 0; border-top: 0; }
.quiet .chg > *:not(h3) { display: none; }
.quiet .chg:target { padding: var(--space-3) 0; }
.quiet .chg:target > *:not(h3) { display: block; }
details { margin: var(--space-3) 0 var(--space-2); }
summary { cursor: pointer; width: fit-content; padding: .35rem 0; font-weight: 600;
          font-size: var(--text-meta); color: var(--link); }
summary::marker { color: var(--link); }
summary:hover { text-decoration: underline; }
details[open] > summary { margin-bottom: var(--space-2); }
/* The strip above a diff or a whole provision: which versions it compares, joined to the box
   under it and exactly as wide, which is why the legal measure is set in `rem`. */
.lbl {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: .25rem .5rem;
  max-width: var(--legal-measure);
  margin: 0;
  padding: .5rem .9rem;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-bottom: 0;
  border-radius: var(--radius) var(--radius) 0 0;
  font-size: var(--text-label);
  color: var(--muted);
}
/* The two sides compared, named, and each marked with the glyph and tint its text carries
   below, so the label is also the legend. */
.lbl .side-before, .lbl .side-after { padding: 0 .2rem; border-radius: 2px; color: var(--fg);
                                      font-weight: 600; }
.lbl .side-before { background: var(--del); }
.lbl .side-after { background: var(--ins); }
.lbl .side-before::before { content: "\\2212\\00a0"; }
.lbl .side-after::before { content: "+\\00a0"; }
/* The law's own words: the serif, held to the legal measure, with no ligature and tabular
   figures, so the text reads as EUR-Lex wrote it and no two characters can merge. */
.diff, .verbatim {
  max-width: var(--legal-measure);
  margin: 0 0 var(--space-3);
  padding: .9rem 1.1rem 1rem;
  background: var(--panel);
  color: var(--fg);
  border: 1px solid var(--rule);
  border-left: 3px solid var(--edge);
  border-radius: 0 0 var(--radius) var(--radius);
  font-family: var(--serif);
  font-size: var(--text-legal);
  line-height: 1.7;
  font-variant-ligatures: none;
  font-variant-numeric: tabular-nums lining-nums;
  font-kerning: normal;
  /* The stored text breaks at every block boundary the source document opened, and the
     unified view emits those breaks. Without this they would collapse and a provision would
     read as one wall of prose. */
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
/* Both tints carry foreground text, so what is readable never depends on a coloured
   foreground surviving a theme swap, and both marks also say which they are without their
   tint: an insertion is underlined and a deletion struck through, on screen as on paper. A
   diff block holds no links, so an underline inside one can mean only the one thing. */
.diff ins, .diff del { padding: 0 .1em; border-radius: 2px; color: var(--fg); }
.diff ins { background: var(--ins); text-decoration: underline; text-underline-offset: .2em;
            text-decoration-thickness: 1px; }
.diff del { background: var(--del); text-decoration: line-through;
            text-decoration-thickness: 1px; }
/* The site's interruption of the text rather than part of it: the sans, in a chip whose
   `--edge` border is visible at 3:1. */
.elided {
  display: inline-block;
  margin: 0 .15rem;
  padding: 0 .45rem;
  border: 1px dashed var(--edge);
  border-radius: var(--radius);
  font: 400 var(--text-label)/1.4 var(--sans);
  color: var(--muted);
  white-space: nowrap;
}
.verbatim.ins { background: var(--ins); border-left-color: var(--kind-inserted); }
.verbatim.del { background: var(--del); border-left-color: var(--kind-deleted); }
/* A phone gives the step rail and the legal text less padding and more of the line. */
@media (max-width: 40rem) {
  .chg.step { padding-left: var(--space-4); }
  .diff, .verbatim { padding: .75rem .8rem; }
}
table { border-collapse: collapse; width: 100%; font-size: var(--text-meta); min-width: 40rem; }
th, td { text-align: left; vertical-align: top; padding: .5rem .6rem;
         border-bottom: 1px solid var(--rule); }
th { font-size: var(--text-label); font-weight: 600; color: var(--muted); }
"""
