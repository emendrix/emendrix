"""One change on a page, and the text it quotes: the block, the marks, the diff, the table.

Sixth in the cascade, so a rule here may rely on everything before it and on `timeline` in
particular, which draws the pages these blocks sit on. This module dresses the evidence rather
than the page: the change block and its heading, the in-page map of touched provisions and the
sticky column it becomes, the permalink and the citation row, the applies and dates lines, the
disagreement note and the badge that grades it, the gathered rows with no text to show, the
unified diff, the verbatim blocks and the metrics table. A provision page's steps reuse the
change block: a step is one change, stated the way every other change on the site is stated,
drawn on the rail an act's timeline uses. The permalink and the citation row are shared the
same way, by both pages that show a change.

`timeline` was split off on 2026-09-05, when the gathered rows needed rules this module had no
room for under the size cap. Three decisions carry the look of a change and are worth stating:

- **Two registers, two faces.** The explanation is the model's words and is set in the sans,
  the largest text on the block. The diff and the verbatim text are the law's words, set in
  the serif with ligatures off and tabular figures, on a panel under a strip naming the two
  versions compared. A reader can tell who is speaking before reading a word.
- **Prose and evidence each have a measure.** Prose is held to `--measure` by `base`; the diff
  and the verbatim blocks to `--legal-measure`, about eighty characters of the serif, chosen
  on 2026-09-18. Stored text carries its own line breaks, and a line that ran the full width
  of the shell would be a line nobody can track back to its start.
- **A disagreement is graded by border and fill, never by hue alone.** The three shapes a
  disagreement takes all keep the one alert colour; a dashed border, a plain one and a filled
  double-weight one tell them apart, and the shape rides in on a class the change block
  carries.

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
.chg {
  padding: var(--space-4) 0 var(--space-3);
  border-top: 1px solid var(--rule);
  scroll-margin-top: var(--space-3);
}
.chg:target { background: var(--mark); box-shadow: 0 0 0 var(--space-3) var(--mark); }
.chg h3 { margin: 0 0 var(--space-2); display: flex; flex-wrap: wrap; align-items: baseline;
          gap: .15rem .6rem; font-size: var(--text-h3); line-height: 1.3; }
.chg h3 .pill { align-self: center; }
.chg .loc { font-weight: 600; }
/* The coordinate in a change heading leads to that provision's own history. It keeps the
   weight and the colour it had as a span: it is still the heading of the block, not an
   invitation to leave it. */
a.loc { color: inherit; font-weight: 600; }
.chg .ttl { font-weight: 600; color: var(--fg); }
/* The explanation, the largest text on the block and the model's words, in the sans. */
.chg > p:not([class]) { font-size: var(--text-explain); line-height: 1.55; max-width: 64ch; }
.chg .applies { margin: 0 0 var(--space-1); }
/* One step of a provision's history: a change block on the same rail an act's timeline is
   drawn as, one node per version, the newest filled. */
.chg.step {
  position: relative;
  margin-left: .45rem;
  padding: 0 0 var(--space-5) var(--space-5);
  border-top: 0;
  border-left: 2px solid var(--rule);
}
.chg.step:last-of-type { border-left-color: transparent; }
.chg.step::before {
  content: "";
  position: absolute;
  left: calc(-.45rem - 1px);
  top: .5rem;
  width: .9rem;
  height: .9rem;
  border-radius: 50%;
  border: 2px solid var(--type-version);
  background: var(--bg);
}
.chg.step:first-of-type::before { background: var(--type-version); }
.chg.step:target { background: transparent; box-shadow: none; }
.chg.step:target > h2 { background: var(--mark); box-shadow: 0 0 0 .4rem var(--mark); }
.step h2 { display: flex; flex-wrap: wrap; gap: .15rem .6rem; align-items: baseline;
           margin: 0 0 var(--space-2); padding: 0; border: 0; font-size: var(--text-h3);
           line-height: 1.3; }
.step h2 .pill { align-self: center; }
/* How much of the provision moved, in characters, beside the kind of change it was. Tabular
   figures because it is a figure standing next to a label, and never wrapped: `+1,204` alone
   at the end of a row would read as the whole count. */
.mag { font-size: var(--text-label); font-weight: 400; color: var(--muted);
       white-space: nowrap; }
/* A map of the page, not a second copy of it: one wrapping row, so forty-five provisions
   cost a few lines of height and a reader can see the whole event at once. */
.touched { margin: var(--space-3) 0 var(--space-4); padding: var(--space-3);
           background: var(--panel); border: 1px solid var(--rule);
           border-radius: var(--radius); font-size: var(--text-meta); line-height: 1.35; }
.touched p { margin: 0 0 var(--space-2); }
.touched ol { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-3);
              list-style: none; margin: 0; padding: 0; }
.touched li { display: flex; align-items: baseline; gap: var(--space-1); }
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
  .event-layout .touched .mag { margin-left: auto; }
  .changes { min-width: 0; }
  .changes > .chg:first-child { border-top: 0; padding-top: 0; }
}
/* One change's own address, at the end of the heading that names it. Set in the muted colour
   because it is furniture beside a coordinate that is not, and pushed to the end of the row by
   the heading's own flex. */
.permalink { margin-left: auto; padding: 0 .25rem; color: var(--muted); font-weight: 400;
             font-size: var(--text-meta); text-decoration: none; }
.permalink:hover, .permalink:focus { color: var(--link); }
/* The citations of one change, once, under its sentences. The lead word is muted and the
   anchors keep the sheet's link colour, so the row reads as links with a label rather than as
   a sentence. */
.cites { margin: var(--space-3) 0 0; font-size: var(--text-meta); color: var(--muted); }
/* Clock 2's answer for one change, on every block. A date is lifted out of the muted colour
   and set in tabular figures, so it scans as the figure it is; the two stated non-answers keep
   the muted colour, and recede without the line ever going silent about them. */
.applies { font-size: var(--text-meta); color: var(--muted); }
.applies .date { color: var(--fg); }
/* The dates a change moved, directly under the line that says whether one of them governs the
   provision. Set like the applies line, because the two are facts of the same rank about one
   change, and in tabular figures so a column of ISO dates reads as a column. */
.dates { margin: var(--space-1) 0 var(--space-2); font-size: var(--text-meta);
         color: var(--muted); font-variant-numeric: tabular-nums lining-nums; }
.disputed { font-size: var(--text-meta); color: var(--alert); }
/* A disagreement is graded by which of the three shapes it is, and the badge carries the
   grade. All three keep the one alert colour; the border style and the fill are what tell
   them apart, so the colour is never the grade on its own. The evidenced shape, a change the
   comparison read and another source did not list, is the plain disputed pill. */
.disp-none .pill.disp { border-style: dashed; }
.disp-kind .pill.disp { background: var(--alert-tint); border-width: 2px; }
/* The source that named a row with no text, on the heading that is the whole of that row
   until it is opened. Set like the title beside it, smaller and muted, so the heading stays
   one coordinate and everything after it reads as a note about it. */
.chg .by { font-weight: 400; font-size: var(--text-meta); color: var(--muted); }
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
