"""The two palettes, the two faces, the type scale and the measurements the rest reads.

Second in the cascade, after the `@font-face` rules, and the only module that may name a colour
by its hex value: every rule downstream reaches a colour through a custom property, so a palette
is one block to read and one block to check. `tests/site_/test_style.py` computes WCAG 2.1
contrast over the pairs the sheet paints, in both schemes, and fails the build under 4.5:1 for
anything carrying text and under 3:1 for a component boundary. It also asserts that no
`#rrggbb` appears outside a custom-property declaration here, which is what keeps that check
total, and that every value is lower-case six-digit hex, the only form it can read.

The palette was redrawn on 2026-09-18, dark designed on its own rather than inverted. Colour
comes in five families, each carrying one thing:

- **Ground and text:** `--bg`, `--fg`, `--muted`, the raised `--panel`, the `:target` and hover
  `--mark`, and `--notice`, the not-legal-advice surface, which no other block shares.
- **Diff marks:** `--ins` and `--del`, backgrounds under `--fg` text, each paired with an
  underline or a strike-through so the tint never carries the mark alone.
- **Links and alerts:** `--link` for every link and the focus ring, and `--alert` with its tint
  for the one disagreement that is a contradiction. They are 1.64:1 apart light and 1.72:1 dark,
  asserted, because a link and an alert that share a colour cannot be told apart by it.
- **Change kinds and provenance:** one colour and one tint per kind of change, and a neutral
  `--provenance` pair for a note about where a record came from.
- **Page types:** one colour and one tint per object a page can be about (act, version,
  provision history, amending act). The rosters and the prose pages take none.

There are two line colours because a line does two different jobs. `--rule` is a hairline that
separates things a reader can already see apart, and it is held to no ratio. `--edge` is the
boundary of a component whose extent is the information: a tag, a form control, the elision
chip, the notice. It clears 3:1 on every surface it is drawn on, the floor WCAG 2.1 SC 1.4.11
sets, and the search box and the elision chip moved to it on 2026-09-18 from `--rule`, which
drew them at 1.35:1.

`:root` is the light palette and `color-scheme: light dark` tells the browser so; the dark
block is a `prefers-color-scheme` override of the same names. No toggle, no script, nothing
stored about the reader. Measured on 2026-09-18, the lowest text pair is a link on the
amending-act and version tints at 4.67:1 light, and an alert on `--mark` at 5.02:1 dark. Four
light values, `--bg`, `--fg`, `--muted` and `--link`, are copied by hand into
`scripts/make_og_image.py`, which draws the link-preview card and cannot follow a theme.
`static/icon.svg` copies the light `--fg` for its tile, the light `--bg` for its bars and the
dark `--link` for its one accent bar, the value that reads on an ink tile. One of those moving
here moves there in the same commit.

The type scale is a major third on a 17px body, written as named roles (`--text-h1` down to
`--text-label`) so no rule writes an ad-hoc size. H1, H2, the lede and legal text are
`clamp()`ed against the viewport and the rest is fixed. `--shell` is the width the header, the
page and the footer hold their content to. `--measure` is the prose column and
`--legal-measure` the column verbatim text is held to, in `rem` rather than `ch` so the label
strip above a diff, set smaller, is exactly as wide as the text under it.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["TOKENS"]

TOKENS: Final = """\
:root {
  color-scheme: light dark;
  --bg: #f6f7f9;
  --fg: #161a21;
  --muted: #4e5664;
  --rule: #dde1e7;
  --edge: #7b8392;
  --panel: #ffffff;
  --mark: #e7ecf6;
  --notice: #eceef2;
  --ins: #d8efdf;
  --del: #f8dfe1;
  --link: #2a5fd6;
  --alert: #8a1c0e;
  --alert-tint: #fbe9e4;
  --provenance: #4e5664;
  --provenance-tint: #eef0f4;
  --kind-inserted: #17692f;
  --kind-inserted-tint: #e3f3e7;
  --kind-deleted: #a3244f;
  --kind-deleted-tint: #f9e6ed;
  --kind-modified: #3a4a66;
  --kind-modified-tint: #e8ecf3;
  --kind-deferred: #7a4f00;
  --kind-deferred-tint: #f8eed8;
  --type-act: #0c6b5f;
  --type-act-tint: #e2f0ec;
  --type-version: #5a3db0;
  --type-version-tint: #ebe7f7;
  --type-provision: #8a4b00;
  --type-provision-tint: #f6ebdb;
  --type-amending: #7e2a64;
  --type-amending-tint: #f4e5ef;

  --sans: "Emendrix Sans", "Emendrix Sans Fallback", -apple-system, BlinkMacSystemFont,
    "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --serif: "Emendrix Serif", "Emendrix Serif Fallback", Georgia, "Times New Roman", serif;

  --text-caption: .875rem;
  --text-h1: clamp(1.95rem, 1.45rem + 2vw, 2.75rem);
  --text-h2: clamp(1.4rem, 1.25rem + .6vw, 1.65rem);
  --text-h3: 1.3rem;
  --text-lede: clamp(1.125rem, 1.05rem + .35vw, 1.3rem);
  --text-explain: 1.125rem;
  --text-body: 1.0625rem;
  --text-meta: .875rem;
  --text-label: .8125rem;
  --text-legal: clamp(1rem, .96rem + .2vw, 1.0625rem);
  --text-code: .8125rem;

  --space-1: .25rem;
  --space-2: .5rem;
  --space-3: 1rem;
  --space-4: 1.5rem;
  --space-5: 2.5rem;
  --space-6: 4rem;

  --shell: 76rem;
  --gutter: clamp(1rem, 3vw, 2rem);
  --measure: 68ch;
  --legal-measure: 40rem;
  --index-width: 19rem;
  --context-height: 2.75rem;
  --radius: 4px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #171a21;
    --fg: #e7e9ee;
    --muted: #a4acba;
    --rule: #2c313c;
    --edge: #788192;
    --panel: #1e222b;
    --mark: #222a3f;
    --notice: #232833;
    --ins: #1d3d29;
    --del: #4a2230;
    --link: #b0caff;
    --alert: #f7704f;
    --alert-tint: #3a1e19;
    --provenance: #b2bac8;
    --provenance-tint: #232833;
    --kind-inserted: #70d18f;
    --kind-inserted-tint: #173222;
    --kind-deleted: #f490b4;
    --kind-deleted-tint: #3a1d2a;
    --kind-modified: #aebbd6;
    --kind-modified-tint: #252c3c;
    --kind-deferred: #e5b660;
    --kind-deferred-tint: #352a15;
    --type-act: #5fcfbb;
    --type-act-tint: #15282a;
    --type-version: #b9a8ff;
    --type-version-tint: #211f38;
    --type-provision: #eab46a;
    --type-provision-tint: #2c2418;
    --type-amending: #f19bd2;
    --type-amending-tint: #301c2c;
  }
}
"""
