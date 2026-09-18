"""The two media that replace the screen's colours: paper and forced colours.

Last in the cascade, and here rather than with the chrome and the evidence they mostly undo
for one reason: an override beats a screen rule of the same specificity only by coming after
it, and the screen rules these override are spread across every module before this one. They
were split off `evidence` on 2026-09-18, when the forced-colours block joined the print block
and the two together had no room left there under the size cap. The seam is the medium: every
rule here answers "what happens when the page is not a screen in the site's own palette".

**Print.** Coming last is not enough on its own: a two-class or pseudo-class selector outranks
a one-class one whatever the order, so `.chg:target`, the two tinted verbatim blocks, the named
sides and the tinted note of the alert shape are named again rather than left to the blanket
line. The block takes the header's navigation, the search mount and the pager off the page,
drops the background tints that cost ink and say nothing on paper, and keeps the disclaimer,
which every user-facing output of this project carries. Paper is white and ink is black, the
one place the sheet names a colour that is not a token, because a printed page has no scheme
to follow.

**Forced colours.** The reader's system palette replaces every token, and anything drawn only
as a background vanishes, as the timeline's nodes once did. So every boundary that carries
meaning is redrawn in `CanvasText`, and the nodes on both rails are rings in the system colours
with `forced-color-adjust: none`, the newest still filled. The diff marks keep their underline
and strike-through, which is what they always said themselves with.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["MEDIA"]

MEDIA: Final = """\
@media print {
  #search, header.bar nav, .skip { display: none; }
  body { background: white; color: black; }
  main, header.bar, footer { max-width: none; padding-left: 0; padding-right: 0; }
  /* A scroll box cannot be scrolled on paper, so both indexes print whole. */
  .sidebar { max-height: none; overflow: visible; }
  .event-layout .touched { position: static; max-height: none; overflow: visible; }
  /* Navigation, like the header's: a permalink and a way back to the top of a sheet of paper
     are both instructions a printed page cannot carry out. */
  .permalink, .backtop, .pager, .tags-help, .define { display: none; }
  /* A row cannot be opened on paper either, so the gathered ones print whole, for the reason
     both indexes do. Named with the same two classes the screen rule uses, since a shorter
     selector would not outrank it. */
  .quiet .chg > *:not(h3) { display: block; }
  .stat, .disclaimer, .sidebar, .touched, .diff, .verbatim, .lbl, .loop li, .tag
    { background: transparent; }
  /* Named again because a two-class or pseudo-class selector outranks a one-class one
     whatever the order: what these tints say is already written beside them, in the label
     above a whole inserted or deleted provision, in the name of each side, and in the
     fragment that brought a reader to one block. */
  .verbatim.ins, .verbatim.del, .lbl .side-before, .lbl .side-after, .chg:target
    { background: transparent; }
  .chg:target, .chg.step:target > h2 { box-shadow: none; }
  .glossary dt:target { background: transparent; box-shadow: none; }
  /* And the tinted note of the one shape that is an alert, for the same reason and by the
     same rule: what its tint says is written in it, in its lead and beside it in its tag. */
  .differ-kind .differ { background: transparent; }
  /* The tints inside a diff are the only ones that say something no word beside them does,
     so they stay, and nothing is redeclared for them: the screen rules already underline an
     insertion and strike a deletion, which is what a printer with no colour reads. */
  a { color: inherit; }
  /* The band is a tint and costs ink; its top rule is what says where the page begins. */
  .masthead { background: none; box-shadow: none; clip-path: none; border-image: none;
              border-top: 2px solid currentColor; }
  .version-masthead { background: none; box-shadow: none; clip-path: none; }
}
/* Forced colours replace every colour with the reader's own, and a mark drawn only as a
   background vanishes. So every boundary that is the information becomes `CanvasText`, and the
   rail's nodes are drawn as rings the system palette keeps, the newest still filled. */
@media (forced-colors: active) {
  .tag, .elided, .disclaimer, .touched, .sidebar, .diff, .verbatim, #search input
    { border-color: CanvasText; }
  .tag--differ-kind, .differ-kind .differ { border-width: 2px; }
  .differ-kind .differ { border-left-width: 3px; border-left-color: CanvasText; }
  .event::before, .chg.step::before {
    background: Canvas; border-color: CanvasText; forced-color-adjust: none;
  }
  .event:first-of-type::before, .chg.step:first-of-type::before
    { background: CanvasText; }
  .diff ins { text-decoration: underline; }
  .diff del { text-decoration: line-through; }
  /* The caption's shape is a fill, so it is drawn as a ring the system palette keeps. */
  .caption::before { background: Canvas; border-color: CanvasText; forced-color-adjust: none; }
  .masthead { border-image: none; border-top-color: CanvasText; }
  header.bar nav a[aria-current="page"] { border-bottom-color: CanvasText; }
}
"""
