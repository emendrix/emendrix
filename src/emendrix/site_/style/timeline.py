"""The act, version and amending-act pages as documents: header lines, columns, rail and pager.

Seventh in the cascade and split off `evidence` on 2026-09-05, when gathering an event's changes
with no text to show needed rules that module had no room for. The seam is the one those two
halves always had: this is the page a reader is standing on, its identifying lines, its two
columns and the sticky index in the left one, the rail an act's history is drawn as, the card
each version is listed as, the masthead a version's own page opens with, the list of dates an
act's text names (and the cross-act list on Dates ahead, which shares its rows and adds sector
and year headings), and the pager between versions. What follows in `evidence` is one change and
the text it quotes. A rule here may be relied on by one there and never the reverse, which is
what makes the order a contract: the event page's `.event-layout` variant, the sticky column it
puts the in-page index in, and the print block that undoes several of these all sit downstream.

Two decisions carry the look of these pages and are worth stating:

- **The timeline is drawn as one.** A rail with a node per version, because an act's history is
  genuinely a sequence and the heading of each entry is its date. The cards carry no panel,
  border or radius: identical rounded cards say the entries are alike, and what a reader needs
  to see is where each one sits on the line. Each node is a ring in the version colour and the
  newest is filled, drawn with a border as well as a fill so it survives forced colours.
- **A version's own page is not a card.** Its masthead continues the version band under the
  heading, so the page's subject reads as a masthead and never as one item of a list.
- **An index is bounded by what it is at that width.** The act page's index is a `<details>`
  of hundreds of links and is capped everywhere; an event page's is a grid of a few dozen
  coordinates that costs a few lines, so it is capped only at the width where it becomes a
  sticky column beside the changes, which is a rule `evidence` writes. Two indexes, two caps,
  and neither rule is written for the other's shape.

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
   on a 390px screen, and the dates list that follows it on a phone starts below all of it. */
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
/* A provision's title under its coordinate, one line, cut by the sheet and never the markup. */
.sidebar li .ttl { flex: 1 1 100%; min-width: 0; overflow: hidden; white-space: nowrap;
                   text-overflow: ellipsis; color: var(--muted); }
.sidebar li > a + .tag { margin-left: auto; }
.sidebar .versions a { font-weight: 600; }
.sidebar .versions .small { flex: 1 1 100%; color: var(--muted); }
/* The markup runs timeline, index, dates, which is the order a phone reads in; a wide screen
   places the index in the left column by area, beside both, and caps it at the viewport so a
   short timeline never stands beside a taller box of links. */
@media (min-width: 60rem) {
  .layout {
    display: grid;
    grid-template-columns: var(--index-width) minmax(0, 1fr);
    grid-template-areas: "index main" "index dates";
    gap: var(--space-5);
    align-items: start;
  }
  .layout > .sidebar { grid-area: index; }
  .layout > .timeline { grid-area: main; }
  .layout > .dates-named { grid-area: dates; }
  .sidebar { position: sticky; top: var(--space-3); max-height: calc(100vh - 2rem);
             margin: 0; overflow-y: auto; }
}
/* The rail and its nodes: an act's history is a sequence, and each version on it is a point.
   Each card draws its own stretch of the line, so a heading above the cards stands clear of
   it, and the last card's stretch is transparent so the line ends at the last node. */
.timeline { min-width: 0; }
.event {
  position: relative;
  min-width: 0;
  padding: 0 0 var(--space-5) var(--space-5);
  border-left: 2px solid var(--rule);
  margin-left: .45rem;
}
.event:last-of-type { border-left-color: transparent; padding-bottom: var(--space-3); }
.event::before {
  content: "";
  position: absolute;
  left: calc(-.45rem - 1px);
  top: .45rem;
  width: .9rem;
  height: .9rem;
  border-radius: 50%;
  border: 2px solid var(--type-version);
  background: var(--bg);
}
.event:first-of-type::before { background: var(--type-version); }
/* A card: the version's name as its one link, what made it, its tally, its identifiers. */
.event > h2, .event > h3 { font-size: var(--text-h3); line-height: 1.3;
                           margin: 0 0 var(--space-2); }
.event .amending { font-size: var(--text-meta); color: var(--muted);
                   margin-bottom: var(--space-1); }
.event .amending a:first-of-type { font-weight: 600; }
.event .subject {
  font-family: var(--serif);
  font-size: var(--text-body);
  line-height: 1.5;
  color: var(--fg);
  max-width: 66ch;
  margin-bottom: var(--space-2);
}
.event .tally, .version-masthead .tally { display: inline; font-weight: 600;
                                          margin-right: var(--space-2); }
.event .tally { font-size: var(--text-meta); }
.event .tally + .tags, .version-masthead .tally + .tags { display: inline-flex;
                                                          vertical-align: middle;
                                                          margin-bottom: var(--space-2); }
.event .ident, .event .note { font-size: var(--text-meta); color: var(--muted); margin-bottom: 0; }
.event .note { margin-top: var(--space-1); }
.timeline > .section { margin: 0 0 var(--space-2); }
.timeline > .tags-help { margin-bottom: var(--space-4); }
/* A phone gives the rail less of its narrow column. */
@media (max-width: 40rem) {
  .event { padding-left: var(--space-4); }
}
/* The version masthead continues the version band below the header: a page's subject, not a
   card. Its facts sit in two groups, side by side where there is room. */
.version-masthead {
  margin-top: calc(-1 * var(--space-4));
  padding: 0 0 var(--space-4);
  margin-bottom: var(--space-5);
  background: var(--type-version-tint);
  border-bottom: 1px solid var(--rule);
  border-image: conic-gradient(var(--rule) 0 0) 0 0 1 0 / 0 0 1px 0 / 0 100vmax;
  box-shadow: 0 0 0 100vmax var(--type-version-tint);
  clip-path: inset(0 -100vmax -1px);
}
.version-masthead .amending { font-size: var(--text-body); margin-bottom: var(--space-2); }
.version-masthead .amending a:first-of-type { font-weight: 600; }
/* The amending act's official title: the law's words, so the serif, at a readable size. */
.version-masthead .lede { font-family: var(--serif); font-size: var(--text-lede); line-height: 1.45;
                          color: var(--fg); max-width: 66ch; }
.version-masthead .dates { font-size: var(--text-meta); color: var(--muted); }
.version-masthead .ident, .version-masthead .instruments { font-size: var(--text-meta);
                                                           color: var(--muted); max-width: 80ch; }
.version-masthead .ident code { color: var(--fg); }
/* Why a version's code can carry a date it is not in force from, under the codes it explains. */
.version-masthead .ident .note { display: block; margin-top: var(--space-1); }
.summary {
  display: grid;
  gap: 0 var(--space-5);
  border-top: 1px solid var(--rule);
  padding-top: var(--space-3);
  margin-top: var(--space-3);
}
@media (min-width: 60rem) {
  .summary { grid-template-columns: minmax(0, 1fr) minmax(0, 22rem); }
}
.status { font-weight: 600; margin-bottom: var(--space-2); }
.section { font-size: var(--text-h2); margin: 0 0 var(--space-4); }
/* Every date one act's text names, under its timeline. A list rather than a table: a row is a
   date and the two places it can be checked, and columns would promise a structure the corpus
   never wrote. The date leads each row in tabular figures, so the dates scan as a column
   while the words around them stay prose. */
.dates-named { margin: var(--space-5) 0 0; }
.dates-named ul { list-style: none; margin: 0; padding: 0; font-size: var(--text-meta); }
.dates-named li { padding: .2rem 0; }
.dates-named .on { font-weight: 600; font-variant-numeric: tabular-nums lining-nums; }
/* Dates ahead gathers its list by sector, then by year. A sector is a heading a reader jumps
   to from the list above it, so it opens under a rule; the year beneath it is a marker in the
   body size, and a far year's qualifier is set quieter than the year it qualifies. */
.dates-named .sectors ul { margin: 0 0 var(--space-4); }
.dates-named .sectors li { padding: 0; }
.dates-named h3 { margin: var(--space-4) 0 var(--space-2); padding-top: var(--space-3);
                  border-top: 1px solid var(--rule); scroll-margin-top: var(--space-3); }
.dates-named h4 { font-family: var(--sans); font-size: var(--text-body); font-weight: 600;
                  line-height: 1.3; color: var(--fg); margin: var(--space-3) 0 var(--space-1);
                  font-variant-numeric: tabular-nums lining-nums; }
.dates-named h3 + h4 { margin-top: 0; }
.dates-named h4 .small { font-weight: 400; margin-left: var(--space-2); }
/* One watched act on an amending instrument's page: its own heading, then the rail of events
   that instrument produced there. The heading carries the act, so it is set as a page heading
   rather than as a card's. */
.amended { margin: var(--space-5) 0 0; }
.amended > h2 a { text-decoration: none; }
.amended > h2 a:hover { text-decoration: underline; }
/* The versions either side of this one: quiet local navigation, each direction's date under
   it, at the two ends of the line so the direction is visible before the words are. */
.pager { display: flex; justify-content: space-between; gap: var(--space-3);
         font-size: var(--text-meta); line-height: 1.4; margin: 0; }
.pager a { text-decoration: none; display: inline-flex; flex-direction: column; }
.pager a > span:first-child { text-decoration: underline; text-underline-offset: .18em;
                              text-decoration-thickness: 1px; }
.pager a:hover > span:first-child { text-decoration-thickness: 2px; }
.pager .small { color: var(--muted); }
.pager [rel="next"] { margin-left: auto; text-align: right; }
.pager--foot { border-top: 1px solid var(--rule); padding-top: var(--space-3);
               margin-top: var(--space-5); }
/* The amending act that made a version or moved a provision: its name in the semibold, its
   identifier small beside it, EUR-Lex last. */
.amending { font-size: var(--text-meta); color: var(--muted); margin-bottom: var(--space-1); }
.amending a:first-of-type { font-weight: 600; }
"""
