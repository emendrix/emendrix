"""The act, event and amendment pages and the text they quote: layout, blocks, diffs, tables.

Last in the cascade, so a rule here may rely on everything before it. This is the half of the
sheet that dresses evidence rather than navigation: the act page's header lines, its two-column
layout and sticky index, the timeline, the change blocks and their headings, the in-page map of
touched provisions, the dispute, applies and dates lines, the act's list of the dates its text
names, the unified diff, the verbatim blocks, the metrics table, and the two rules an amending
instrument's page and the event pager need. Both
of those reuse the timeline rather than inventing a second one, an instrument's page being a
timeline per watched act it moved. A provision page's steps reuse the change block for the same
reason: a step is one change, stated the way every other change on the site is stated, and the
three rules it adds only undo the block's horizontal bleed and set its heading level. The
permalink and the citation row are shared the same way, by both pages that show a change.

Four decisions carry the look of these two pages and are worth stating:

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
- **An index is bounded by what it is at that width.** The act page's index is a `<details>`
  of hundreds of links and is capped everywhere; an event page's is a row of a few dozen that
  costs a few lines, so it is capped only at the width where it becomes a sticky column beside
  the changes. Two indexes, two caps, and neither rule is written for the other's shape.

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
/* The neighbours line closes the header, so its gap above is the links line's own. */
.related { margin: 0 0 var(--space-4); font-size: var(--step-sm); color: var(--muted); }
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
  /* The dates list follows the timeline down the page, so it belongs in the timeline's column
     rather than under the index: auto-placement would otherwise start it a row lower in the
     16rem one, where a row of two links and a date does not fit. */
  .layout > .dates-named { grid-column: 2; }
}
/* The rail and its nodes: an act's history is a sequence, and the heading of each entry on
   it is a date. Drawn in the sheet so the markup stays one article per event. */
.timeline { min-width: 0; }
.layout > .timeline, .amended > .timeline { padding-left: var(--space-4);
                                            border-left: 1px solid var(--rule); }
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
.applies { font-size: var(--step-sm); color: var(--muted); }
/* The dates a change moved, directly under the line that says whether one of them governs the
   provision. Set like the applies line, because the two are facts of the same rank about one
   change, and in tabular figures so a column of ISO dates reads as a column. */
.dates { margin: var(--space-1) 0 var(--space-2); font-size: var(--step-sm);
         color: var(--muted); font-variant-numeric: tabular-nums; }
/* Every date one act's text names, under its timeline. A list rather than a table: a row is a
   date and the two places it can be checked, and columns would promise a structure the corpus
   never wrote. The date leads each row in the mono face, so the dates scan as a column while
   the words around them stay prose. */
.dates-named { margin: var(--space-5) 0 0; }
.dates-named ul { list-style: none; margin: 0; padding: 0; font-size: var(--step-sm); }
.dates-named li { padding: .15rem 0; }
.dates-named .on { font-family: var(--mono); font-variant-numeric: tabular-nums; }
/* One watched act on an amending instrument's page: its own heading, then the rail of events
   that instrument produced there. The heading carries the act, so it is set as a page heading
   rather than as a card's. */
.amended { margin: var(--space-5) 0 0; }
.amended > h2 a { text-decoration: none; }
.amended > h2 a:hover { text-decoration: underline; }
/* The events either side of this one, at the foot of an event page. Each link carries the date
   it goes to, so the row is read rather than decoded; they sit at the two ends of the line so
   the direction is visible before the words are. */
.pager { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--space-2);
         margin: var(--space-5) 0 0; padding-top: var(--space-3);
         border-top: 1px solid var(--rule); font-size: var(--step-sm); }
/* The instrument that made the event, under the version pair it produced. Set small, like the
   other fact lines, and the declared short name italic beside the number so the label and the
   identifier read as two different kinds of name. */
.amending { font-size: var(--step-sm); }
.amending .ttl { font-style: italic; }
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
  .strip, .disclaimer, .sidebar, .diff, .verbatim, .loop li, .pill, .tag
    { background: transparent; }
  /* Named again because a two-class or pseudo-class selector outranks a one-class one
     whatever the order: what these three tints say is already written beside them, in the
     label above a whole inserted or deleted provision, in the word inside the pill, and in
     the fragment that brought a reader to one block. */
  .verbatim.ins, .verbatim.del, .pill.ins, .chg:target { background: transparent; }
  /* The tints inside a diff are the only ones that say something no word beside them does,
     so they stay, and nothing is redeclared for them: the screen rules already underline an
     insertion and strike a deletion, which is what a printer with no colour reads. */
  a { color: inherit; }
}
"""
