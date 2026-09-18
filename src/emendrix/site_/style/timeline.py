"""The act, event and amendment pages as documents: header lines, columns, rail and pager.

Fifth in the cascade and split off `evidence` on 2026-09-05, when gathering an event's
changes with no text to show needed rules that module had no room for. The seam is the one
those two halves always had: this is the page a reader is standing on, its identifying lines,
its two columns and the sticky index in the left one, the rail an act's history is drawn as,
the card each event opens with, the list of dates an act's text names, and the pager at the
foot of an event. What follows in `evidence` is one change and the text it quotes. A rule
here may be relied on by one there and never the reverse, which is what makes the order a
contract: the event page's `.event-layout` variant, the sticky column it puts the in-page
index in, and the print block that undoes several of these all sit downstream.

Two decisions carry the look of these pages and are worth stating:

- **The timeline is drawn as one.** A rail with a node per event, because an act's history is
  genuinely a sequence and the heading of each entry is its date. The events carry no panel,
  border or radius: identical rounded cards say the entries are alike, and what a reader needs
  to see is where each one sits on the line. Each node is a ring in the version colour and the
  newest is filled, drawn with a border as well as a fill so it survives forced colours.
- **An index is bounded by what it is at that width.** The act page's index is a `<details>`
  of hundreds of links and is capped everywhere; an event page's is a row of a few dozen that
  costs a few lines, so it is capped only at the width where it becomes a sticky column beside
  the changes, which is a rule `evidence` writes. Two indexes, two caps, and neither rule is
  written for the other's shape.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["TIMELINE"]

TIMELINE: Final = """\
/* An official title or heading, in the law's own words: the serif, one step down. */
.official {
  margin: 0 0 var(--space-3);
  max-width: 82ch;
  font-family: var(--serif);
  font-size: var(--text-meta);
  line-height: 1.55;
  color: var(--muted);
}
.links { margin: var(--space-1) 0 var(--space-4); font-size: var(--text-meta); line-height: 1.55; }
/* The neighbours line closes the header, so its gap above is the links line's own. */
.related { margin: 0 0 var(--space-4); font-size: var(--text-meta); color: var(--muted); }
.layout { display: block; }
/* The index is bounded at every width. An act with hundreds of provisions renders hundreds
   of links, and `<details open>` opens them all: unbounded, the CRR index stands 20510px tall
   on a 390px screen and the timeline it sits above starts below all of it. */
.sidebar {
  margin: var(--space-4) 0;
  padding: var(--space-2) var(--space-3) var(--space-3);
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  font-size: var(--text-meta);
  line-height: 1.45;
  max-height: 60vh;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.sidebar summary { padding: var(--space-2) 0; font-weight: 600; color: var(--fg); }
.sidebar h2 {
  margin: var(--space-3) 0 var(--space-2);
  padding: 0;
  border: 0;
  font-size: var(--text-label);
  letter-spacing: .01em;
  color: var(--muted);
}
.sidebar ul { list-style: none; margin: 0; padding: 0; }
.sidebar li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 .4rem;
              padding: .3rem 0; border-top: 1px solid var(--rule); }
.sidebar li:first-child { border-top: 0; }
@media (min-width: 60rem) {
  .layout {
    display: grid;
    grid-template-columns: var(--index-width) minmax(0, 1fr);
    gap: var(--space-5);
    align-items: start;
  }
  .sidebar { position: sticky; top: var(--space-3); max-height: calc(100vh - 2rem);
             margin: 0; overflow-y: auto; }
  /* The dates list follows the timeline down the page, so it belongs in the timeline's column
     rather than under the index: auto-placement would otherwise start it a row lower in the
     narrow one, where a row of two links and a date does not fit. */
  .layout > .dates-named { grid-column: 2; }
}
/* The rail and its nodes: an act's history is a sequence, and the heading of each entry on
   it is a date. Drawn in the sheet so the markup stays one article per event. */
.timeline { min-width: 0; }
.layout > .timeline, .amended > .timeline { padding-left: var(--space-5);
                                            border-left: 2px solid var(--rule);
                                            margin-left: .45rem; }
.timeline .event { position: relative; padding-bottom: var(--space-5); }
.timeline .event::before {
  content: "";
  position: absolute;
  top: .45rem;
  left: calc(-1 * var(--space-5) - .45rem - 1px);
  width: .9rem;
  height: .9rem;
  border-radius: 50%;
  border: 2px solid var(--type-version);
  background: var(--bg);
}
.timeline .event:first-of-type::before { background: var(--type-version); }
.timeline .event:last-child { padding-bottom: 0; }
/* A phone gives the rail less of its narrow column. */
@media (max-width: 40rem) {
  .layout > .timeline, .amended > .timeline { padding-left: var(--space-4); }
  .timeline .event::before { left: calc(-1 * var(--space-4) - .45rem - 1px); }
}
.event { min-width: 0; }
.event > h2 {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  margin: 0 0 var(--space-2);
  padding: 0;
  border: 0;
  font-size: var(--text-h3);
  line-height: 1.3;
}
.event > .ident { margin: 0 0 var(--space-1); }
/* Every date one act's text names, under its timeline. A list rather than a table: a row is a
   date and the two places it can be checked, and columns would promise a structure the corpus
   never wrote. The date leads each row in tabular figures, so the dates scan as a column
   while the words around them stay prose. */
.dates-named { margin: var(--space-5) 0 0; }
.dates-named ul { list-style: none; margin: 0; padding: 0; font-size: var(--text-meta); }
.dates-named li { padding: .2rem 0; }
.dates-named .on { font-weight: 600; font-variant-numeric: tabular-nums lining-nums; }
/* One watched act on an amending instrument's page: its own heading, then the rail of events
   that instrument produced there. The heading carries the act, so it is set as a page heading
   rather than as a card's. */
.amended { margin: var(--space-5) 0 0; }
.amended > h2 a { text-decoration: none; }
.amended > h2 a:hover { text-decoration: underline; }
/* The events either side of this one, at the foot of an event page. Each link carries the date
   it goes to, so the row is read rather than decoded; they sit at the two ends of the line so
   the direction is visible before the words are. */
.pager { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--space-3);
         margin: var(--space-5) 0 0; padding-top: var(--space-3);
         border-top: 1px solid var(--rule); font-size: var(--text-meta); line-height: 1.4; }
/* The instrument that made the event, under the version pair it produced. Set small, like the
   other fact lines, the instrument's link in the semibold, and the declared short name in the
   text colour beside the muted number, so the label and the identifier read as two kinds of
   name without a slant the site does not load. */
.amending { font-size: var(--text-meta); color: var(--muted); margin-bottom: var(--space-1); }
.amending a:first-of-type { font-weight: 600; }
.amending .ttl { color: var(--fg); }
"""
