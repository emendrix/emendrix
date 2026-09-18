"""The front door, the roster and the page that argues: rules no other page needs.

Sixth in the cascade, so everything here may rely on `fonts`, `tokens`, `base` and `tags` and
nothing here is relied on by them. Three page families live in this module and none of their
selectors escapes its own page: the home page's hero, stat strip and version cards; the
rosters' sector jump list and rows; the methodology page's table columns, caveat list, loop
grid and glossary. The feeds page and the about page carry no rule of their own, because
they are prose the shell already styles, and a class invented for them would be a class
nothing else could reuse.

Two hierarchy decisions are worth stating, because they are what the markup is shaped for:

- **A card is led by its act.** A caption in the act's colour and shape names the act and goes
  to its page, the heading names the version and goes to its page, the tally follows as one
  small line, and the version pair sits last, set as identifiers at reduced contrast.
- **A roster row is lines, not one chain.** The name and the identifiers on the first, then
  the official title in the law's face, then the dated words, so a reader scanning forty rows
  reads a column of names rather than a column of separators.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["PAGES"]

PAGES: Final = """\
.hero { padding: var(--space-4) 0 var(--space-3); text-align: center; }
.hero h1 { max-width: none; margin-bottom: var(--space-3); }
.hero p { max-width: 42rem; margin: 0 auto var(--space-3); }
/* Home: a version card led by its act, then the stat strip after the list. */
.cardrow { padding: var(--space-3) 0 var(--space-4); border-top: 1px solid var(--rule); }
.cardrow:last-of-type { border-bottom: 1px solid var(--rule); }
.cardrow .caption { margin-bottom: .1rem; --type: var(--type-act); }
.cardrow .caption::before { border-radius: 1px; }
.cardrow h3 { font-size: var(--text-h3); margin: 0 0 var(--space-1); }
.cardrow .made { font-size: var(--text-meta); color: var(--muted); margin-bottom: var(--space-2); }
.cardrow .tally { display: inline; font-size: var(--text-meta); font-weight: 600;
                  margin-right: var(--space-2); }
.cardrow .tally + .tags { display: inline-flex; vertical-align: middle;
                          margin-bottom: var(--space-2); }
.cardrow .ident { display: block; font-size: var(--text-meta); color: var(--muted); margin: 0; }
/* A measured figure, not a warning: a panel with a rule in the act colour, never the notice
   surface the disclaimer owns. */
.stat {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-1) var(--space-4);
  align-items: baseline;
  max-width: 62ch;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-top: 3px solid var(--type-act);
  border-radius: var(--radius);
  padding: var(--space-3) var(--space-4);
  margin: var(--space-5) 0;
  font-size: var(--text-meta);
}
.stat strong { font-size: var(--text-h2); line-height: 1; font-variant-numeric: tabular-nums; }
/* Rosters (acts, amending acts): one row per object, name first, identifier demoted. */
.sectors ul { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); list-style: none;
              padding: 0; margin: 0 0 var(--space-5); font-size: var(--text-meta); }
.sectors a { font-weight: 600; }
.sectors .small { color: var(--muted); margin-left: .25rem; }
.roster { list-style: none; margin: 0 0 var(--space-5); padding: 0; }
.roster li { padding: var(--space-3) 0; border-top: 1px solid var(--rule); }
.roster li:last-child { border-bottom: 1px solid var(--rule); }
.roster > li > a:first-child { font-weight: 600; font-size: var(--text-body); }
.roster .ident { margin-left: .35rem; }
.roster .sub { display: block; max-width: 82ch; margin-top: .15rem; font-family: var(--serif);
               font-size: var(--text-meta); color: var(--fg); }
.roster .facts { display: block; margin: .15rem 0 0; }
td.result { white-space: nowrap; font-variant-numeric: tabular-nums; }
td.meaning { color: var(--muted); }
.caveats { margin: var(--space-3) 0 0; padding-left: 1.1rem; font-size: var(--text-meta);
           color: var(--muted); }
.caveats li { margin: .3rem 0; max-width: var(--measure); }
.loop { list-style: none; display: grid; gap: .75rem; padding: 0; margin: var(--space-3) 0;
        grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); }
.loop li { background: var(--panel); border: 1px solid var(--rule); border-radius: var(--radius);
           padding: .7rem .8rem; font-size: var(--text-meta); }
.loop b { display: block; font-size: var(--text-label); font-weight: 600; color: var(--fg); }
/* The glossary: one definition per term, each term addressable and lit when a link lands on it. */
.glossary dt { font-weight: 600; margin-top: var(--space-3); scroll-margin-top: var(--space-3); }
.glossary dt:target { background: var(--mark); box-shadow: 0 0 0 .3rem var(--mark); }
.glossary dd { margin: .2rem 0 0; max-width: var(--measure); }
"""
