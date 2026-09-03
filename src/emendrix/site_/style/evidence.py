"""The act page, the event page and the text they quote: layout, blocks, diffs, tables.

Last in the cascade, so a rule here may rely on everything before it. This is the half of the
sheet that dresses evidence rather than navigation: the act page's header lines, its two-column
layout and sticky index, the timeline, the change blocks and their headings, the in-page map of
touched provisions, the dispute and applies lines, the unified diff, the verbatim blocks and the
metrics table.

Three decisions carry the look of these two pages and are worth stating:

- **The timeline is drawn as one.** A rail with a node per event, because an act's history is
  genuinely a sequence and the heading of each entry is now its date. The events lost the
  panel, border and radius they used to be boxed in: identical rounded cards say the entries
  are alike, and what a reader needs to see is where each one sits on the line.
- **A change block is a row on a document, not a card.** A hairline above it, the heading on
  one baseline (pill, coordinate, title), and horizontal padding it always has, so the tint a
  fragment link puts on `.chg:target` has room to sit in and lands without moving anything.
- **Prose inside a block is held to the measure; the evidence is not.** `main > p` in `base`
  caps only direct children, and every sentence on an event page is nested two levels down.
  The diff is the one thing deliberately let out to the full column: it is prose to read but
  it is also the artifact, and stored text carries its own line structure.

Two rules carry a constraint rather than a preference and are commented where they sit: the
diff preserves the line breaks the stored text already has, and the print block must name any
two-class selector it wants to strip.

The table rules are generic on purpose. The methodology page is the only page with a table
today, and its column behaviour lives with that page in `pages`; the shape of a table is
evidence typography and belongs here, where an act page that grows one would find it.

The `@media print` block closes the sheet, and it is here rather than with the chrome it
mostly undoes for one reason: a print rule beats a screen rule of the same specificity only
by coming after it, and the screen rules it overrides are spread across all four modules.
Coming last is not enough on its own: a two-class or pseudo-class selector outranks a
one-class one whatever the order, so `.chg:target` and the two tinted verbatim blocks are
named again there rather than left to the blanket line. It takes the header's navigation and
the search mount off the page, drops the background tints that cost ink and say nothing on
paper, and keeps the disclaimer, which every user-facing output of this project carries.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["EVIDENCE"]

EVIDENCE: Final = """\
.official {
  margin: var(--space-2) 0;
  font-family: var(--display);
  font-size: var(--step-1);
  line-height: 1.45;
  color: var(--muted);
}
.links { margin: var(--space-1) 0 var(--space-4); font-size: var(--step-sm); }
.layout { display: block; }
/* The index is bounded at every width. An act with hundreds of provisions renders hundreds
   of links, and `<details open>` opens them all: unbounded, the CRR index stands 20510px tall
   on a 390px screen and the timeline it sits above starts below all of it. */
.sidebar {
  margin: var(--space-4) 0;
  padding: .2rem 1rem .8rem;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 6px;
  font-size: var(--step-sm);
  max-height: 60vh;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.sidebar summary { padding: var(--space-2) 0; font-family: var(--display);
                   font-size: var(--step-0); }
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
.sidebar li { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-1);
              padding: .15rem 0; }
@media (min-width: 60rem) {
  .layout {
    display: grid;
    grid-template-columns: 16rem minmax(0, 1fr);
    gap: 2rem;
    align-items: start;
  }
  .sidebar { position: sticky; top: 1rem; max-height: calc(100vh - 2rem); overflow-y: auto; }
}
/* The rail and its nodes: an act's history is a sequence, and the heading of each entry on
   it is a date. Drawn in the sheet so the markup stays one article per event. */
.timeline { min-width: 0; }
.layout > .timeline { padding-left: var(--space-4); border-left: 1px solid var(--rule); }
.timeline .event { position: relative; padding-bottom: var(--space-5); }
.timeline .event::before {
  content: "";
  position: absolute;
  top: .8em;
  left: calc(-1 * var(--space-4) - 3px);
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
}
.timeline .event:last-child { padding-bottom: 0; }
.event { min-width: 0; }
.event > h2 {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  border: 0;
  font-size: var(--step-2);
}
.event > p { max-width: var(--measure); }
.event > .ident { margin: var(--space-1) 0 0; }
.chg {
  margin: 0 calc(-1 * var(--space-3));
  padding: var(--space-4) var(--space-3) var(--space-3);
  border-top: 1px solid var(--rule);
  scroll-margin-top: var(--space-3);
}
.chg:target { background: var(--mark); }
.chg h3 { margin: 0; display: flex; flex-wrap: wrap; align-items: baseline;
          gap: var(--space-1) var(--space-2); }
.chg .loc { font-weight: 600; }
.chg .ttl { font-family: var(--sans); font-weight: 400; font-size: var(--step-sm); }
.chg > p { max-width: var(--measure); }
.chg .applies { margin: var(--space-1) 0 var(--space-2); }
/* A map of the page, not a second copy of it: one wrapping row, so forty-five provisions
   cost a few lines of height and a reader can see the whole event at once. */
.touched { margin: var(--space-3) 0 var(--space-4); padding: var(--space-2) 0;
           border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.touched ol { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-3);
              list-style: none; margin: 0; padding: 0; font-size: var(--step-sm); }
.touched li { display: flex; align-items: baseline; gap: var(--space-1); }
.applies { font-size: var(--step-sm); color: var(--muted); }
.disputed { font-size: var(--step-sm); color: var(--warn); }
details { margin: var(--space-3) 0 0; }
summary { cursor: pointer; font-size: var(--step-sm); color: var(--accent); }
summary:hover { text-decoration: underline; }
.diff {
  margin: 0;
  padding: var(--space-3);
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 4px;
  font-family: var(--display);
  line-height: 1.7;
  /* The stored text breaks at every block boundary the source document opened, and the
     unified view emits those breaks. Without this they would collapse and a provision would
     read as one wall of prose. */
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
/* Both tints carry foreground text, so what is readable never depends on a coloured
   foreground surviving a theme swap. */
.diff ins, .diff del { padding: .05rem .2rem; border-radius: 2px; color: var(--fg); }
.diff ins { background: var(--ins); text-decoration: none; }
.diff del { background: var(--del); text-decoration: line-through; }
.elided {
  display: inline-block;
  padding: 0 .4rem;
  border: 1px dashed var(--rule);
  border-radius: 3px;
  font-family: var(--sans);
  font-size: var(--step-sm);
  font-style: italic;
  color: var(--muted);
}
.verbatim {
  margin: 0;
  padding: var(--space-3);
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 4px;
  font-family: var(--display);
  font-size: .95rem;
  line-height: 1.7;
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
  #search, header.bar nav, .skip { display: none; }
  body { padding: 0; }
  main, header.bar, footer { max-width: none; }
  /* A scroll box cannot be scrolled on paper, so the index prints whole. */
  .sidebar { max-height: none; overflow: visible; }
  .strip, .disclaimer, .sidebar, .diff, .verbatim, .loop li, .pill, .tag
    { background: transparent; }
  /* Named again because a two-class or pseudo-class selector outranks a one-class one
     whatever the order: what these three tints say is already written beside them, in the
     label above a whole inserted or deleted provision, in the word inside the pill, and in
     the fragment that brought a reader to one block. */
  .verbatim.ins, .verbatim.del, .pill.ins, .chg:target { background: transparent; }
  /* The tints inside a diff are the only ones that say something no word beside them does,
     so they stay, and inserted text is underlined as well for a printer with no colour. */
  .diff ins { text-decoration: underline; }
  a { color: inherit; }
}
"""
