"""What a page is and where it sits: the masthead, the caption, the trail, the current section.

Fourth in the cascade, after `base`, because it restyles two things `base` sets up: the heading
inside the masthead and the header bar's links. It is its own module because these rules answer
one question for every page type at once, and a reader should be able to find them together.

**The masthead** is a band the full width of the window, tinted by page type, with a 4px rule
in the type's colour along its top. Act, version, provision history and amending act each get
a colour; the rosters and the pages about the site share a neutral hairline and no tint,
because they are not objects a reader follows between and a fifth hue would mean only "a
page". The band bleeds past the shell by `box-shadow` and a `border-image` outset, both ink
overflow, and `clip-path` trims the shadow to the band's own height, so it paints the margins
without widening the page or adding a horizontal scroll.

**The caption** names the page type in the type's colour, after a small shape drawn in CSS:
a square for an act, a disc for a version, an upright bar for a provision history and a
diamond for an amending act. The shape and the colour say the same thing as the word, which is
always there, so neither is the only carrier.

**The trail** is quiet, the page's own rung in the text colour. On a phone it collapses to its
parent rung behind a left arrow, which is a way back and fits one line, by hiding every item
but the second to last; nothing in the markup changes with the width.

**The current section** in the header bar is marked by weight and a link-coloured underline,
never by colour alone. Print and forced colours for all of these live in `media`.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["IDENTITY"]

IDENTITY: Final = """\
header.bar nav a[aria-current="page"] { font-weight: 600; border-bottom-color: var(--link); }
.masthead {
  --type: var(--muted);
  --type-tint: var(--bg);
  padding: var(--space-4) 0;
  margin-bottom: var(--space-4);
  background: var(--type-tint);
  border-top: 4px solid var(--type);
  border-image: conic-gradient(var(--type) 0 0) 1 / 4px 0 0 0 / 0 100vmax;
  box-shadow: 0 0 0 100vmax var(--type-tint);
  clip-path: inset(0 -100vmax);
}
/* The band meets the header bar: `main`'s top padding is for pages that open without one. */
main > .masthead:first-child { margin-top: calc(-1 * var(--space-5)); }
.masthead--act { --type: var(--type-act); --type-tint: var(--type-act-tint); }
.masthead--version { --type: var(--type-version); --type-tint: var(--type-version-tint); }
.masthead--provision { --type: var(--type-provision); --type-tint: var(--type-provision-tint); }
.masthead--amending { --type: var(--type-amending); --type-tint: var(--type-amending-tint); }
.masthead--index, .masthead--prose {
  --type: var(--muted);
  --type-tint: var(--bg);
  border-image: conic-gradient(var(--rule) 0 0) 1 / 4px 0 0 0 / 0 100vmax;
}
.masthead h1 { max-width: 21em; margin: 0; }
.masthead--provision h1 { max-width: 24em; }
.trail ol {
  display: flex; flex-wrap: wrap; gap: 0 .45rem;
  list-style: none; padding: 0; margin: 0 0 var(--space-4);
  font-size: var(--text-meta); line-height: 1.5; color: var(--muted);
}
.trail li + li::before { content: "\\203A"; content: "\\203A" / ""; margin-right: .45rem;
                         color: var(--muted); }
.trail a { color: var(--muted); text-decoration-color: var(--edge); }
.trail a:hover { color: var(--link); text-decoration-color: currentColor; }
.trail [aria-current="page"] { color: var(--fg); }
.caption {
  display: flex; align-items: center; gap: .5rem;
  font: 600 var(--text-caption)/1.3 var(--sans);
  color: var(--type);
  margin: 0 0 var(--space-2);
  letter-spacing: .01em;
}
.caption::before {
  content: "";
  flex: none;
  width: .7rem;
  height: .7rem;
  border: 2px solid var(--type);
  background: var(--type);
}
.masthead--act .caption::before { border-radius: 1px; }
.masthead--version .caption::before { border-radius: 50%; }
.masthead--provision .caption::before { width: .45rem; height: .9rem; border-radius: 1px; }
.masthead--amending .caption::before { transform: rotate(45deg) scale(.85); border-radius: 1px; }
.masthead--index .caption::before, .masthead--prose .caption::before { display: none; }
.caption a { color: var(--link); font-weight: 600; }
@media (max-width: 40rem) {
  .trail li { display: none; }
  .trail li:nth-last-child(2) { display: block; }
  .trail li:nth-last-child(2)::before { content: "\\2190"; content: "\\2190" / "";
                                        margin-right: .35rem; }
  .trail ol { margin-bottom: var(--space-3); }
  .masthead { padding: var(--space-3) 0 var(--space-4); }
}
"""
