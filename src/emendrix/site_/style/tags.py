"""Tags: the adjectives a version and a change carry, one fixed look per kind.

Fifth in the cascade, after `identity` and before the page families, because a tag appears on
every kind of page and each page family may place one without restyling it. A tag is never a
link and never looks like one: no underline and never the link colour. Each kind has one look
wherever it appears, and the look is always said twice: a change kind has its own colour and a
glyph or border style, the three ways sources differ are told apart by border style, and only
the one that is a contradiction, kinds differ, takes the alert colour, with a `≠` glyph and a
double-weight border. The tally's own categories are quiet, muted words in a bordered box,
because they are counts rather than findings. Beside a sources-differ tag sits a small
`.define` link to its definition, so the tag itself stays an adjective.

A list of tags wraps as a row, and the tally sentence it follows sits on the same line where
there is room. Print and forced colours for tags live in `media`.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["TAGS"]

TAGS: Final = """\
.tags { display: flex; flex-wrap: wrap; gap: var(--space-2); list-style: none; padding: 0;
        margin: 0 0 var(--space-3); }
.tag {
  display: inline-flex;
  align-items: center;
  gap: .3em;
  font: 600 var(--text-label)/1.25 var(--sans);
  padding: .12rem .45rem;
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
  white-space: nowrap;
  vertical-align: .1em;
  font-variant-numeric: tabular-nums;
}
.tag--kind-inserted { color: var(--kind-inserted); background: var(--kind-inserted-tint);
                      border-color: var(--kind-inserted); }
.tag--kind-inserted::before { content: "+"; }
.tag--kind-deleted { color: var(--kind-deleted); background: var(--kind-deleted-tint);
                     border-color: var(--kind-deleted); }
.tag--kind-deleted::before { content: "\\2212"; }
.tag--kind-modified { color: var(--kind-modified); background: var(--kind-modified-tint);
                      border-color: var(--kind-modified); }
.tag--kind-renumbered { color: var(--kind-modified); background: transparent;
                        border: 1px dashed var(--kind-modified); }
.tag--kind-deferred { color: var(--kind-deferred); background: var(--kind-deferred-tint);
                      border: 1px dotted var(--kind-deferred); }
.tag--differ, .tag--differ-text { color: var(--provenance); background: var(--provenance-tint);
                                  border-color: var(--edge); }
.tag--no-text, .tag--differ-none { color: var(--provenance); background: var(--provenance-tint);
                                   border: 1px dashed var(--edge); }
.tag--differ-kind { color: var(--alert); background: var(--alert-tint);
                    border: 2px solid var(--alert); padding: .06rem .4rem; }
.tag--differ-kind::before { content: "\\2260"; }
.tag--unattributed { color: var(--provenance); background: transparent;
                     border: 1px dashed var(--edge); }
.tag--substantive, .tag--dates-only, .tag--all-explained, .tag--unexplained, .tag--quoted,
.tag--diff-only { color: var(--muted); background: transparent; border-color: var(--edge); }
.tags-help { font-size: var(--text-meta); margin: 0 0 var(--space-3); }
/* The small link to a definition, beside the tag or the value it defines; never the tag. */
.define { margin-left: var(--space-2); font-size: var(--text-meta); font-weight: 400; }
"""
