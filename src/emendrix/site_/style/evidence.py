"""One change on a page, and the text it quotes: the block, the marks, the diff, the print rules.

Last in the cascade, so a rule here may rely on everything before it and on `timeline` in
particular, which draws the pages these blocks sit on. This module dresses the evidence rather
than the page: the change block and its heading, the in-page map of touched provisions and the
sticky column it becomes, the permalink and the citation row, the applies and dates lines, the
disagreement note and the badge that grades it, the gathered rows with no text to show, the
unified diff, the verbatim blocks and the metrics table. A provision page's steps reuse the
change block: a step is one change, stated the way every other change on the site is stated,
and the three rules it adds only undo the block's horizontal bleed and set its heading level.
The permalink and the citation row are shared the same way, by both pages that show a change.

`timeline` was split off on 2026-09-05, when the gathered rows needed rules this module had no
room for under the size cap. Three decisions carry the look of a change and are worth stating:

- **A change block is a row on a document, not a card.** A hairline above it, the heading on
  one baseline (pill, coordinate, title), and horizontal padding it always has, so the tint a
  fragment link puts on `.chg:target` has room to sit in and lands without moving anything.
- **Prose inside a block is held to the measure; the evidence is not.** `main > p` in `base`
  caps only direct children, and every sentence on an event page is nested two levels down.
  The diff is the one thing deliberately let out to the full column: it is prose to read but
  it is also the artifact, and stored text carries its own line structure.
- **A disagreement is graded by weight, never by hue.** The three shapes a disagreement takes
  all keep the one disputed colour; the border and the weight of the badge are what tell them
  apart, and the shape rides in on a class the change block carries.

Two rules carry a constraint rather than a preference and are commented where they sit: the
diff preserves the line breaks the stored text already has, and the print block must name any
two-class selector it wants to strip.

The table rules are generic on purpose. The methodology page is the only page with a table
today, and its column behaviour lives with that page in `pages`; the shape of a table is
evidence typography and belongs here, where an act page that grows one would find it.

The `@media print` block closes the sheet, and it is here rather than with the chrome it
mostly undoes for one reason: a print rule beats a screen rule of the same specificity only
by coming after it, and the screen rules it overrides are spread across all five modules.
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
/* The coordinate in a change heading leads to that provision's own history. It keeps the
   weight and the colour it had as a span: it is still the heading of the block, not an
   invitation to leave it. */
a.loc { color: inherit; font-weight: 600; }
.chg .ttl { font-family: var(--sans); font-weight: 400; font-size: var(--step-sm); }
.chg > p { max-width: var(--measure); }
.chg .applies { margin: var(--space-1) 0 var(--space-2); }
/* One step of a provision's history. It is a change block, so it inherits the hairline, the
   heading baseline and the target tint; what it does not want is the block's bleed into the
   gutters, the steps here being a list down the page rather than rows under one event. */
.step { margin: var(--space-4) 0; }
.step h2 { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: baseline;
           margin: 0; padding: 0; border: 0; font-size: var(--step-1); }
/* How much of the provision moved, in characters, beside the kind of change it was. The mono
   face because it is a figure standing next to a label, and never wrapped: `+1,204` alone at
   the end of a row would read as the whole count. */
.mag { font-family: var(--mono); font-size: var(--step-xs); color: var(--muted);
       white-space: nowrap; }
/* A map of the page, not a second copy of it: one wrapping row, so forty-five provisions
   cost a few lines of height and a reader can see the whole event at once. */
.touched { margin: var(--space-3) 0 var(--space-4); padding: var(--space-2) 0;
           border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.touched p { margin: 0 0 var(--space-1); }
.touched ol { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-3);
              list-style: none; margin: 0; padding: 0; font-size: var(--step-sm); }
.touched li { display: flex; align-items: baseline; gap: var(--space-1); }
/* The decade of characters a change moved, as weight on its link, so the index reads as a map
   of where the text is rather than only of where a change is. Weight and nothing else: colour
   is spent on diffs, disputes and links, and a heavier link is still a link. The classes are
   decades and claim nothing about importance; the count beside each one is the fact. */
.touched .mag-1 a { font-weight: 400; }
.touched .mag-2 a { font-weight: 500; }
.touched .mag-3 a { font-weight: 600; }
.touched .mag-4 a { font-weight: 700; }
/* The same grid the act page draws, with the event's index as the left column, at the one
   width the act page becomes two columns. The `.sidebar` cap above is deliberately not reused:
   that one bounds a `<details>` of hundreds of links at every width, where this is a row of
   forty coordinates that costs a few lines while it is a row and needs the cap only once it
   stands as a column. Below the query nothing here applies and the row is untouched. */
@media (min-width: 60rem) {
  .event-layout .touched {
    position: sticky;
    top: 1rem;
    max-height: calc(100vh - 2rem);
    margin: 0;
    padding: 0;
    border: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  .event-layout .touched ol { display: block; }
  .event-layout .touched li { padding: .15rem 0; }
  .changes { min-width: 0; }
}
/* One change's own address, at the end of the heading that names it. Set in the muted colour
   because it is furniture beside a coordinate that is not, and pushed to the end of the row by
   the heading's own flex. */
.permalink { margin-left: auto; color: var(--muted); text-decoration: none; }
.permalink:hover, .permalink:focus { color: var(--accent); }
/* The citations of one change, once, under its sentences. The lead word is muted and the
   anchors keep the sheet's link colour, so the row reads as links with a label rather than as
   a sentence. */
.cites { font-size: var(--step-sm); color: var(--muted); }
/* Clock 2's answer for one change, on every block. A date is lifted out of the muted colour
   and set in tabular figures, so it scans as the figure it is; the two stated non-answers keep
   the muted colour, and recede without the line ever going silent about them. No hue is spent
   on the distinction: colour here goes to diffs, disputes and links. */
.applies { font-size: var(--step-sm); color: var(--muted); }
.applies .date { color: var(--fg); font-variant-numeric: tabular-nums; }
/* The dates a change moved, directly under the line that says whether one of them governs the
   provision. Set like the applies line, because the two are facts of the same rank about one
   change, and in tabular figures so a column of ISO dates reads as a column. */
.dates { margin: var(--space-1) 0 var(--space-2); font-size: var(--step-sm);
         color: var(--muted); font-variant-numeric: tabular-nums; }
.disputed { font-size: var(--step-sm); color: var(--warn); }
/* A disagreement is graded by which of the three shapes it is, and the badge carries the
   grade. No hue is spent on it: all three keep the one disputed colour, and the border and
   the weight are what tell them apart. The evidenced shape, a change the comparison read and
   another source did not list, is the plain disputed pill and adds no rule at all. */
.disp-none .pill.disp { border-style: dashed; }
.disp-kind .pill.disp { background: var(--mark); font-weight: 700; }
/* The source that named a row with no text, on the heading that is the whole of that row
   until it is opened. Set like the title beside it: the sans face at the small step, so the
   heading stays one coordinate and everything after it reads as a note about it. */
.chg .by { font-family: var(--sans); font-weight: 400; font-size: var(--step-sm);
           color: var(--muted); }
/* The changes with no text to show, gathered at the foot of an event: one line each, with the
   rest of the block hidden until the row is the fragment target. `:target` is what a permalink
   into this list sets, so the link that names a row is the link that opens it, with no script
   and nothing dropped from the markup. */
.quiet { margin: var(--space-5) 0 0; }
.quiet .chg { margin: 0; padding: .2rem var(--space-3); border-top: 0; }
.quiet .chg > *:not(h3) { display: none; }
.quiet .chg:target { padding: var(--space-3); }
.quiet .chg:target > *:not(h3) { display: block; }
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
   foreground surviving a theme swap, and both marks also say which they are without their
   tint: an insertion is underlined and a deletion struck through, on screen as on paper. A
   diff block holds no links, so an underline inside one can mean only the one thing. */
.diff ins, .diff del { padding: .05rem .2rem; border-radius: 2px; color: var(--fg); }
.diff ins { background: var(--ins); text-decoration: underline;
            text-decoration-thickness: from-font; }
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
  /* A scroll box cannot be scrolled on paper, so both indexes print whole. */
  .sidebar { max-height: none; overflow: visible; }
  .event-layout .touched { position: static; max-height: none; overflow: visible; }
  /* Navigation, like the header's: a permalink and a way back to the top of a sheet of paper
     are both instructions a printed page cannot carry out. */
  .permalink, .backtop { display: none; }
  /* A row cannot be opened on paper either, so the gathered ones print whole, for the reason
     both indexes do. Named with the same two classes the screen rule uses, since a shorter
     selector would not outrank it. */
  .quiet .chg > *:not(h3) { display: block; }
  .strip, .disclaimer, .sidebar, .diff, .verbatim, .loop li, .pill, .tag
    { background: transparent; }
  /* Named again because a two-class or pseudo-class selector outranks a one-class one
     whatever the order: what these three tints say is already written beside them, in the
     label above a whole inserted or deleted provision, in the word inside the pill, and in
     the fragment that brought a reader to one block. */
  .verbatim.ins, .verbatim.del, .pill.ins, .chg:target { background: transparent; }
  /* And the filled badge of the one shape that is an alert, for the same reason and by the
     same rule: what its tint says is written beside it, in the lead of the note under it. */
  .disp-kind .pill.disp { background: transparent; }
  /* The tints inside a diff are the only ones that say something no word beside them does,
     so they stay, and nothing is redeclared for them: the screen rules already underline an
     insertion and strike a deletion, which is what a printer with no colour reads. */
  a { color: inherit; }
}

"""
