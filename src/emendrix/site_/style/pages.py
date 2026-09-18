"""The front door, the roster and the page that argues: rules no other page needs.

Sixth in the cascade, so everything here may rely on `fonts`, `tokens`, `base` and `tags` and
nothing here is relied on by them. Three page families live in this module and none of their
selectors escapes its own page: the home page's hero, credibility strip and event cards; the
acts index's roster rows; the methodology page's table columns, caveat list, loop grid and
glossary. The feeds page and the about page carry no rule of their own, because they are prose
the shell already styles, and a class invented for them would be a class nothing else could
reuse.

Two hierarchy decisions are worth stating, because they are what the markup was reshaped for
on 2026-09-03:

- **A card leads with the act's name.** The heading holds the name alone, the counts and the
  date follow as one small line, and the version pair sits last, set as an identifier at
  reduced contrast. The name and the version pair are not one heading, which would put an
  identifier at the same rank as the thing it identifies.
- **A roster row is two lines, not one chain.** The name and the identifiers on the first, the
  official title and the dated words on the second, so a reader scanning forty rows reads a
  column of names rather than a column of separators.

The count of changes where sources differ is a tag in the neutral provenance look, from
`tags`, rather than a clause appended to the provision count, so it reads as the note it is.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["PAGES"]

PAGES: Final = """\
.hero { padding: var(--space-4) 0 var(--space-3); text-align: center; }
.hero h1 { max-width: none; margin-bottom: var(--space-3); }
.hero p { max-width: 42rem; margin: 0 auto var(--space-3); }
/* A measured figure, not a warning: a panel with a rule in the act colour, never the notice
   surface the disclaimer owns. */
.strip {
  margin: 0 auto var(--space-5);
  padding: var(--space-3) var(--space-4);
  max-width: 62ch;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-top: 3px solid var(--type-act);
  border-radius: var(--radius);
  font-size: var(--text-meta);
}
.strip strong { font-variant-numeric: tabular-nums; }
.cardrow { padding: var(--space-3) 0 var(--space-4); border-top: 1px solid var(--rule); }
.cardrow:last-of-type { border-bottom: 1px solid var(--rule); }
.cardrow h3 { font-size: var(--text-h3); margin: 0 0 var(--space-1); }
.cardrow .facts { margin: 0 0 var(--space-1); }
.cardrow .ident { display: block; margin: 0; }
.roster { list-style: none; margin: 0 0 var(--space-5); padding: 0; }
.roster li { padding: var(--space-3) 0; border-top: 1px solid var(--rule); }
.roster li:last-child { border-bottom: 1px solid var(--rule); }
.roster > li > a { font-weight: 600; font-size: var(--text-body); }
.roster .ident { margin-left: .35rem; }
.roster .sub { display: block; max-width: 82ch; margin-top: .15rem; font-family: var(--serif);
               font-size: var(--text-meta); color: var(--fg); }
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
