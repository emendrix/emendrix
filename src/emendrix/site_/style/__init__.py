"""The site's whole stylesheet, as one constant, written to `style.css` by the builder.

One file, shared by every page, because the site is a *tree* of pages: inlining the same
few kilobytes into every act page would grow with the corpus and defeat the browser cache.
It is a constant in Python rather than a checked-in `.css` asset so that the one thing the
builder copies verbatim stays the search script, and so a stylesheet change is reviewed as a
diff in the same package as the markup it styles.

It became a package on 2026-09-03, when the sheet outgrew the ~300-line module cap. The seam
is one file per concern, concatenated in cascade order: `tokens` (the two palettes, the three
faces, the type scale, the measure and the spacing steps), `base` (reset, body, headings,
links, code, the shared text classes, the header bar, search, the footer, the disclaimer, the
focus ring and the print rules), `pages` (home, the acts roster, methodology) and `evidence`
(the act page's layout and sidebar, timeline cards, the change blocks, the touched index, the
diff and verbatim blocks, tables). A rule in a later module may rely on an earlier one and
never the reverse, which is what makes the order a contract rather than a preference. A class
used by more than one page family lives in `base`; a class one page owns lives with that page.

This text is minted, not escaped. It is the repository's own writing, not anything a legal
document or a model produced, so it never passes through `markup.escape`; nothing in it is
interpolated, which is what makes that safe rather than merely convenient. The rule holds for
every module of the package.

Deliberately plain and deliberately not minified: view-source is part of what the site
claims about itself. System fonts and a system serif only, because a web font is a
third-party request and this site makes none. Both themes come from `color-scheme` and one
`prefers-color-scheme` block, so the site reads correctly light and dark without a toggle,
without JavaScript and without storing anything about the reader.

Colour is spent on exactly three things: the `ins`/`del` tints in a diff, the disputed flag,
and links. The tints are backgrounds and the text on them stays `--fg` in both themes, so
contrast never depends on a coloured foreground surviving a theme swap.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.style.base import BASE
from emendrix.site_.style.evidence import EVIDENCE
from emendrix.site_.style.pages import PAGES
from emendrix.site_.style.tokens import TOKENS

__all__ = ["STYLE"]

STYLE: Final = TOKENS + BASE + PAGES + EVIDENCE
"""The whole sheet, in cascade order. `build.py` writes exactly this to `style.css`."""
