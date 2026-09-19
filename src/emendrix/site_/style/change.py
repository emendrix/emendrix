"""One change on a page: its heading, its facts, where its sources differ, and who is speaking.

Eighth in the cascade, after `timeline` and before `evidence`: this module dresses the change as
a statement, and `evidence` dresses the text it quotes. Split from `evidence` on 2026-09-18,
when the change block gained a register label, a facts line, a note graded by shape and a key
to its citations, and the two together had no room left under the size cap. The seam is the
one a reader sees: everything here is emendrix or a model speaking about a change, and
everything in `evidence` is EUR-Lex's own text and the map over it.

A version page's blocks and a provision page's steps are one component. A step is one change,
stated the way every other change on the site is stated, drawn on the rail an act's timeline
uses, so the heading, the facts line, the note and the register rules name both.

Three decisions carry the look:

- **The coordinate leads the heading**, then the title, then the kind of change as a tag, and
  the permalink is pushed to the end. How much moved is a fact about the change rather than
  part of its name, so it opens the facts line under the heading.
- **The machine's words are labelled as such.** The explanation sits under a small label
  saying a model wrote it and what checked it, behind a rule, in the sans at the largest size
  on the block. The law's words are `evidence`'s and never look like these.
- **Only a contradiction takes the alert colour.** Where the sources differ, the note is
  plain text beside the shape's tag, whose look lives in `tags`; only where they name
  different kinds does the note take the alert's tint and rule as well.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["CHANGE"]

CHANGE: Final = """\
.chg {
  padding: var(--space-4) 0 var(--space-3);
  border-top: 1px solid var(--rule);
  scroll-margin-top: var(--space-3);
}
.chg:target { background: var(--mark); box-shadow: 0 0 0 var(--space-3) var(--mark); }
.chg h3, .chg.step h2 { margin: 0 0 var(--space-2); display: flex; flex-wrap: wrap;
                        align-items: baseline; gap: .15rem .6rem; padding: 0; border: 0;
                        font-size: var(--text-h3); line-height: 1.3; }
.chg h3 .tag, .chg.step h2 .tag { align-self: center; }
.chg .loc { font-weight: 600; }
/* The coordinate in a change heading leads to that provision's own history. It keeps the
   weight and the colour it had as a span: it is still the heading of the block, not an
   invitation to leave it. */
a.loc { color: inherit; font-weight: 600; }
.chg .ttl { font-weight: 600; color: var(--fg); }
/* A title printed in capitals, as Formex prints an annex's subject, set in small capitals so
   it does not shout. The characters stay the law's; only their size changes. The faces carry
   no small capitals, so this one synthesis is let back in: scaled capitals are the same
   letters, where a synthesised weight or slant would not be. */
.ttl--caps { font-variant-caps: all-small-caps; font-synthesis-small-caps: auto;
             letter-spacing: .02em; }
.chg.step h2 .mag { font-size: var(--text-meta); }
/* The source that named a row with no text, on the heading that is the whole of that row
   until it is opened. Smaller and muted, so the heading stays one coordinate. */
.chg .by { font-weight: 400; font-size: var(--text-meta); color: var(--muted); }
/* One change's own address, at the end of the heading that names it: furniture beside a
   coordinate that is not, so muted and pushed to the end of the row by the heading's flex. */
.permalink { margin-left: auto; padding: 0 .25rem; color: var(--muted); font-weight: 400;
             font-size: var(--text-meta); text-decoration: none; }
.permalink:hover, .permalink:focus { color: var(--link); }
/* How much moved and when it applies, one line of facts under the heading. A real date is
   lifted out of the muted colour; the two stated non-answers keep it. */
.chg .meta { margin: 0 0 var(--space-2); font-size: var(--text-meta); color: var(--muted); }
.chg .meta .date { color: var(--fg); }
.chg .amending { margin-bottom: var(--space-1); font-size: var(--text-meta); color: var(--muted); }
/* The dates a change moved, set like the facts line above them and in tabular figures, so a
   column of ISO dates reads as a column. */
.dates { margin: var(--space-1) 0 var(--space-2); font-size: var(--text-meta);
         color: var(--muted); font-variant-numeric: tabular-nums lining-nums; }
/* Where the sources differ: the shape's tag, then the lead and the detail. Plain text for the
   two presence shapes; only the contradiction takes the alert's tint and rule. */
.differ { margin: var(--space-2) 0; font-size: var(--text-meta); line-height: 1.5;
          color: var(--fg); }
.differ-kind .differ { padding: var(--space-2) var(--space-3); background: var(--alert-tint);
                       border-left: 3px solid var(--alert); }
.differ-kind .differ strong { color: var(--alert); }
/* The machine's register: a label saying who wrote the sentences under it, drawn with a small
   open diamond, then the sentences in the sans behind a rule, the largest text on the block. */
.register {
  display: flex;
  align-items: center;
  gap: .45rem;
  margin: var(--space-3) 0 var(--space-2);
  font-size: var(--text-label);
  font-weight: 600;
  color: var(--muted);
}
.register::before {
  content: "";
  width: .8rem;
  height: .8rem;
  border: 2px solid var(--muted);
  border-radius: 2px;
  transform: rotate(45deg) scale(.75);
}
.register ~ p:not([class]) {
  max-width: 64ch;
  margin: 0;
  padding: 0 0 var(--space-2) var(--space-3);
  border-left: 3px solid var(--edge);
  font-size: var(--text-explain);
  line-height: 1.55;
}
/* The citations of one change, once, under its sentences, and what `v1` and `v2` in them
   mean, under the row that uses them. */
.cites { margin: var(--space-3) 0 0; font-size: var(--text-meta); color: var(--muted); }
.cites-key { margin-bottom: var(--space-3); color: var(--muted); }
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
/* How much of the provision moved, in characters. Never wrapped: `+1,204` alone at the end
   of a row would read as the whole count. */
.mag { font-size: var(--text-label); font-weight: 400; color: var(--muted);
       white-space: nowrap; }
"""
