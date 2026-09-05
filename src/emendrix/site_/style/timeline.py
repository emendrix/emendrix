"""The act, event and amendment pages as documents: header lines, columns, rail and pager.

Fourth in the cascade and split off `evidence` on 2026-09-05, when gathering an event's
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
  to see is where each one sits on the line.
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
"""
