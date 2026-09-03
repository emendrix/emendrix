"""The act page, the event page and the text they quote: layout, blocks, diffs, tables.

Last in the cascade, so a rule here may rely on everything before it. This is the half of the
sheet that dresses evidence rather than navigation: the act page's two-column layout and its
sticky index, the timeline cards, the change blocks and their headings, the in-page list of
touched provisions, the dispute and applies lines, the unified diff, the verbatim blocks and
the metrics table.

Two rules carry a constraint rather than a preference and are commented where they sit: the
diff preserves the line breaks the stored text already has, and a two-column list of touched
provisions must not split an item across the fold.

The table rules are generic on purpose. The methodology page is the only page with a table
today, and its column behaviour lives with that page in `pages`; the shape of a table is
evidence typography and belongs here, where an act page that grows one would find it.

The `@media print` block closes the sheet, and it is here rather than with the chrome it
mostly undoes for one reason: a print rule beats a screen rule of the same specificity only
by coming after it, and the screen rules it overrides are spread across all four modules. It
takes the header's navigation and the search mount off the page, drops the background tints
that cost ink and say nothing on paper, and keeps the disclaimer, which every user-facing
output of this project carries.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["EVIDENCE"]

EVIDENCE: Final = """\
.layout { display: block; }
.sidebar {
  margin: var(--space-4) 0;
  padding: .2rem 1rem .8rem;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 6px;
  font-size: .88rem;
}
.sidebar h2 {
  margin: var(--space-3) 0 .3rem;
  padding: 0;
  border: 0;
  font-family: var(--sans);
  font-size: .75rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.sidebar ul { list-style: none; margin: 0; padding: 0; }
.sidebar li { padding: .12rem 0; }
.sidebar summary { padding: .6rem 0; }
@media (min-width: 60rem) {
  .layout {
    display: grid;
    grid-template-columns: 16rem minmax(0, 1fr);
    gap: 2rem;
    align-items: start;
  }
  .sidebar { position: sticky; top: 1rem; max-height: calc(100vh - 2rem); overflow-y: auto; }
}
.timeline { min-width: 0; }
.event {
  margin: 1.25rem 0;
  padding: 1rem 1.1rem;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 6px;
}
.event h3 { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: baseline; }
.changes { list-style: none; margin: 0; padding: 0; }
.changes > li { padding: .7rem 0; border-top: 1px solid var(--rule); }
.chg { padding: .8rem 0; border-top: 1px solid var(--rule); scroll-margin-top: 1rem; }
.chg:target { background: var(--mark); }
.chg h3 { margin: 0; display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: baseline; }
.chg .loc { font-weight: 600; }
.chg .applies { margin: .1rem 0 .4rem; }
.touched ol { columns: 2; list-style: none; padding: 0; margin: var(--space-2) 0 var(--space-3);
              font-size: .88rem; }
/* A list item split across two columns reads as two provisions. */
.touched li { break-inside: avoid; padding: .1rem 0; }
.applies { font-size: .8rem; color: var(--muted); }
.disputed { font-size: .82rem; color: var(--warn); }
details { margin: var(--space-2) 0 0; }
summary { cursor: pointer; font-size: var(--step-sm); color: var(--accent); }
.diff {
  margin: .2rem 0 0;
  padding: .7rem .8rem;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 4px;
  font-family: var(--display);
  /* The stored text breaks at every block boundary the source document opened, and the
     unified view emits those breaks. Without this they would collapse and a provision would
     read as one wall of prose. */
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.diff ins { background: var(--ins); padding: 0 .1rem; border-radius: 2px;
            text-decoration: none; }
.diff del { background: var(--del); padding: 0 .1rem; border-radius: 2px;
            text-decoration: line-through; }
.elided { color: var(--muted); font-style: italic; }
.before-after pre, .verbatim {
  margin: 0;
  padding: .7rem .8rem;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 4px;
  font-family: var(--display);
  font-size: .95rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.verbatim.ins { background: var(--ins); }
.verbatim.del { background: var(--del); }
table { border-collapse: collapse; width: 100%; font-size: .88rem; min-width: 40rem; }
th, td { text-align: left; vertical-align: top; padding: .5rem .6rem;
         border-bottom: 1px solid var(--rule); }
th { font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
@media print {
  #search, header.bar nav { display: none; }
  body { padding: 0; }
  main, header.bar, footer { max-width: none; }
  .strip, .disclaimer, .sidebar, .event, .diff, .verbatim, .before-after pre, .loop li,
  .pill, .tag { background: transparent; }
  /* Named again because a two-class selector outranks a one-class one whatever the order:
     what these two tints say is already written beside them, in the label above a whole
     inserted or deleted provision and in the word inside the pill. */
  .verbatim.ins, .verbatim.del, .pill.ins { background: transparent; }
  /* The tints inside a diff are the only ones that say something no word beside them does,
     so they stay, and inserted text is underlined as well for a printer with no colour. */
  .diff ins { text-decoration: underline; }
  a { color: inherit; }
}
"""
