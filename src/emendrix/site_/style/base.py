"""The shell and everything more than one page family needs: type, links, chrome.

Second in the cascade. What lives here is what a rule further down is allowed to assume: the
box model, the body face, the heading scale, the shared small-print classes (`.muted`,
`.small`, `.facts`, `.ident`, `.none`, `.quoted`, `.lbl`) and the pills, each of which is
minted by two or more of the page renderers. A class one page owns lives with that page
instead, in `pages` or `evidence`; `.official` left for `evidence` on 2026-09-03, the act
page's header being the only place that mints it.

Three rules are about being usable rather than about looking a way, and one of the three is
not here:

- **The measure.** `main` stays 62rem wide because tables and the act page's two columns need
  it, but a paragraph directly inside it is capped at `--measure`, so prose never runs the
  full width of a desktop window.
- **The focus ring.** Every interactive element shows one, through `:focus-visible`, so a
  reader navigating by keyboard can see where they are. The site has no script that could
  restore one that the sheet removed.
- **Print.** The rules are at the foot of `evidence`, the last module, because a print
  override has to win the cascade against the screen rule it overrides and most of those are
  written after this module. What they do belongs to the shell all the same, so the reason
  they are not here is stated here.

The `#search` selectors are the script's contract with this sheet (`static/search.js` builds
`input`, `ul.results` and `span.kind` inside `#search`); they are restyled here and never
renamed.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["BASE"]

BASE: Final = """\
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0 0 var(--space-5);
  background: var(--bg);
  color: var(--fg);
  font: var(--step-0)/1.6 var(--sans);
}
main { max-width: 62rem; margin: 0 auto; padding: var(--space-4) 1.25rem 0; }
main > p { max-width: var(--measure); }
h1, h2, h3, .display { font-family: var(--display); font-weight: 600; }
h1 { font-size: var(--step-3); line-height: 1.15; margin: 0 0 var(--space-1);
     letter-spacing: -.01em; }
h2 { font-size: var(--step-2); margin: var(--space-5) 0 var(--space-2); padding-bottom: .3rem;
     border-bottom: 1px solid var(--rule); }
h3 { font-size: var(--step-1); margin: 0 0 var(--space-1); }
p { margin: .6rem 0; }
a { color: var(--accent); text-underline-offset: .16em; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
code { font-family: var(--mono); font-size: .88em; }
/* An identifier a reader checks rather than reads: present on every page, one step down. */
code.id { color: var(--muted); }
.lede { max-width: var(--measure); font-size: 1.05rem; }
.muted { color: var(--muted); }
.small { font-size: var(--step-sm); }
/* A proper noun carrying a hyphen, kept off the line break that would read as two words. */
.nowrap { white-space: nowrap; }
.scroll { overflow-x: auto; }
.facts { margin: var(--space-1) 0 var(--space-3); font-size: var(--step-sm); color: var(--muted); }
.ident { font-size: var(--step-sm); color: var(--muted); }
.lbl { margin: var(--space-3) 0 var(--space-1); font-size: .75rem; letter-spacing: .06em;
       text-transform: uppercase; color: var(--muted); }
.quoted { font-style: italic; color: var(--muted); }
.none { font-style: italic; color: var(--muted); }
/* The pill and the tag are the two components whose whole content is a boundary and a word,
   so their border is `--edge` and not the hairline the rest of the sheet draws with. */
.pill {
  display: inline-block;
  padding: .05rem .45rem;
  border: 1px solid var(--edge);
  border-radius: 3px;
  background: var(--mark);
  font-size: var(--step-xs);
  letter-spacing: .06em;
  text-transform: uppercase;
}
.pill.ins { background: var(--ins); }
.pill.disp { background: transparent; border-color: var(--warn); color: var(--warn); }
.tag { display: inline-block; padding: .05rem .45rem; border: 1px solid var(--edge);
       border-radius: 3px; background: var(--mark); font-size: var(--step-xs);
       letter-spacing: .06em; }
/* Off-screen until it takes focus, then placed over the header rather than moving it, so
   arriving at the page shifts nothing. It is the first focusable element on every page. */
.skip {
  position: absolute;
  left: var(--space-3);
  top: var(--space-3);
  z-index: 2;
  padding: var(--space-2) var(--space-3);
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 6px;
  font-size: var(--step-sm);
  transform: translateY(-200%);
}
.skip:focus { transform: none; }
header.bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  max-width: 62rem;
  margin: 0 auto;
  padding: .85rem 1.25rem;
  border-bottom: 1px solid var(--rule);
}
.wordmark { font-family: var(--display); font-size: 1.2rem; letter-spacing: -.01em;
            color: var(--fg); text-decoration: none; }
.wordmark:hover { color: var(--accent); }
header.bar nav { display: flex; flex-wrap: wrap; gap: var(--space-3); font-size: .9rem; }
header.bar nav a { text-decoration: none; }
header.bar nav a:hover { text-decoration: underline; }
#search { position: relative; flex: 1 1 14rem; margin-left: auto; }
#search input {
  width: 100%;
  padding: .35rem .6rem;
  border: 1px solid var(--rule);
  border-radius: 4px;
  background: var(--panel);
  color: var(--fg);
  font: inherit;
  font-size: .9rem;
}
#search .results {
  position: absolute;
  z-index: 10;
  top: calc(100% + .25rem);
  left: 0;
  right: 0;
  max-height: 60vh;
  overflow-y: auto;
  margin: 0;
  padding: 0;
  list-style: none;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 4px;
}
#search .results li { display: flex; align-items: baseline; gap: var(--space-2); }
#search .results li + li { border-top: 1px solid var(--rule); }
#search .results a { flex: 1 1 auto; padding: .35rem .6rem; font-size: .9rem;
                     text-decoration: none; }
#search .results a:hover, #search .results a:focus { background: var(--mark); }
/* What kind of thing a result is, said once at the end of the row rather than under it. */
.kind { padding-right: .6rem; font-size: var(--step-xs); letter-spacing: .06em;
        text-transform: uppercase; color: var(--muted); }
.disclaimer {
  margin: var(--space-3) 0 0;
  padding: .8rem 1rem;
  max-width: var(--measure);
  border-left: 3px solid var(--accent);
  background: var(--mark);
  font-size: .92rem;
}
footer {
  max-width: 62rem;
  margin: var(--space-5) auto 0;
  padding: var(--space-3) 1.25rem 0;
  border-top: 1px solid var(--rule);
  font-size: var(--step-sm);
  color: var(--muted);
}
footer p { max-width: var(--measure); }
"""
