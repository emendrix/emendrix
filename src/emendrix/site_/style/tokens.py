"""The two palettes, the three faces, and the measurements the rest of the sheet reads.

First in the cascade, and the only module that may name a colour by its hex value: every rule
downstream reaches a colour through a custom property, so a palette is one block to read and
one block to check. `tests/site_/test_style.py` computes WCAG 2.1 contrast over these pairs in
both schemes and fails the build under 4.5:1, and it also asserts that no `#rrggbb` appears
outside a custom-property declaration here, which is what keeps that check total.

`:root` is the light palette and `color-scheme: light dark` tells the browser so; the dark
block is a `prefers-color-scheme` override of the same names. No toggle, no script, nothing
stored about the reader. Both schemes were measured on 2026-09-03 and no value moved: the
lowest of the fourteen checked pairs is muted on mark, at 5.66 light and 5.32 dark. The four
light values are copied by hand into `scripts/make_og_image.py`, which draws the link-preview
card and cannot follow a theme, so a hex that moves here moves there in the same commit.

The scale exists so no rule writes an ad-hoc size. `--step-2` and `--step-3` are `clamp()`ed
against the viewport: the H1 lands at 1.6rem on a 390px phone, where the old fixed 2rem was
larger than a narrow column needs, and reaches 2.4rem past about 1110px. `--measure` is the
reading column, applied to prose rather than to `main`, which stays wide for tables and for
the act page's two columns; before it, prose on a 1440px event page ran the full width.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["TOKENS"]

TOKENS: Final = """\
:root {
  color-scheme: light dark;
  --bg: #fcfcfa;
  --fg: #1c1c1a;
  --muted: #5d5d58;
  --rule: #e0ded6;
  --panel: #ffffff;
  --accent: #7a4b1e;
  --mark: #f1ede3;
  --ins: #e3efe4;
  --del: #f6e2e2;
  --warn: #8a3d10;
  --display: Georgia, "Times New Roman", serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --step-xs: .72rem;
  --step-sm: .85rem;
  --step-0: 1rem;
  --step-1: 1.1rem;
  --step-2: clamp(1.25rem, 1.1rem + .6vw, 1.5rem);
  --step-3: clamp(1.6rem, 1.15rem + 1.8vw, 2.4rem);
  --measure: 68ch;
  --space-1: .25rem;
  --space-2: .5rem;
  --space-3: 1rem;
  --space-4: 1.5rem;
  --space-5: 2.5rem;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16171a;
    --fg: #e6e5e1;
    --muted: #a0a09a;
    --rule: #33353a;
    --panel: #1e2024;
    --accent: #d9a066;
    --mark: #2a2c31;
    --ins: #26402c;
    --del: #4a2626;
    --warn: #e0a35a;
  }
}
"""
