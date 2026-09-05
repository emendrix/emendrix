"""The front door, the roster and the page that argues: rules no other page needs.

Third in the cascade, so everything here may rely on `tokens` and `base` and nothing here is
relied on by them. Three page families live in this module and none of their selectors escapes
its own page: the home page's hero, credibility strip and event cards; the acts index's roster
rows; the methodology page's table columns, caveat list and loop grid. The feeds page and the
about page carry no rule of their own, because they are prose the shell already styles, and a
class invented for them would be a class nothing else could reuse.

Two hierarchy decisions are worth stating, because they are what the markup was reshaped for
on 2026-09-03:

- **A card leads with the act's name.** The heading holds the name alone, the counts and the
  date follow as one small line, and the version pair sits last in the mono face at reduced
  contrast. The name and the version pair are not one heading, which would put an identifier at
  the same rank as the thing it identifies.
- **A roster row is two lines, not one chain.** The name and the identifiers on the first, the
  official title and the dated words on the second, so a reader scanning forty rows reads a
  column of names rather than a column of separators.

The disputed count is a bordered chip in the warn colour rather than a clause appended to the
provision count, and deliberately not the change-type pill: that pill carries a single
uppercase word, and `1 disputed change` set the same way would shout the one number on the
page that most needs to read as a note.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["PAGES"]

PAGES: Final = """\
.hero { padding: var(--space-5) 0 var(--space-3); text-align: center; }
.hero h1 { margin-bottom: var(--space-3); }
.hero p { max-width: 42rem; margin: .7rem auto; }
.strip {
  margin: 0 auto var(--space-5);
  padding: .7rem 1rem;
  max-width: var(--measure);
  border-left: 3px solid var(--accent);
  background: var(--mark);
  font-size: .92rem;
}
.cardrow { padding: var(--space-3) 0; border-top: 1px solid var(--rule); }
.cardrow:last-of-type { border-bottom: 1px solid var(--rule); }
.cardrow h3 { margin: 0; }
.cardrow h3 a { text-decoration: none; }
.cardrow h3 a:hover { text-decoration: underline; }
.cardrow .facts { margin: var(--space-1) 0 0; }
.cardrow .ident { display: block; margin: var(--space-1) 0 0; }
.cardrow .disp { padding: 0 .35rem; border: 1px solid var(--warn); border-radius: 3px;
                 color: var(--warn); }
.roster { list-style: none; margin: 0; padding: 0; }
.roster li { padding: var(--space-2) 0; border-top: 1px solid var(--rule); }
.roster li:last-child { border-bottom: 1px solid var(--rule); }
.roster > li > a { font-family: var(--display); font-size: var(--step-1);
                   text-decoration: none; }
.roster > li > a:hover { text-decoration: underline; }
.roster .ident { margin-left: var(--space-1); }
.roster .sub { display: block; max-width: var(--measure); margin-top: var(--space-1);
               font-size: var(--step-sm); color: var(--muted); }
td.result { white-space: nowrap; }
td.meaning { color: var(--muted); }
.caveats { margin: .75rem 0 0; padding-left: 1.1rem; font-size: .92rem; color: var(--muted); }
.caveats li { margin: .3rem 0; }
.loop { list-style: none; display: grid; gap: .75rem; padding: 0; margin: var(--space-3) 0;
        grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); }
.loop li { background: var(--panel); border: 1px solid var(--rule); border-radius: 6px;
           padding: .7rem .8rem; font-size: var(--step-sm); }
.loop b { display: block; font-size: .78rem; letter-spacing: .06em; color: var(--accent); }
"""
