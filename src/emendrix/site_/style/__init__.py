"""The site's whole stylesheet, as one constant, written out under one file name.

One file, shared by every page, because the site is a *tree* of pages: inlining the same
few kilobytes into every act page would grow with the corpus and defeat the browser cache.
It is a constant in Python rather than a checked-in `.css` asset so that the one thing the
builder copies verbatim stays the search script, and so a stylesheet change is reviewed as a
diff in the same package as the markup it styles.

It became a package on 2026-09-03, when the sheet outgrew the ~300-line module cap. The seam is
one file per concern, concatenated in cascade order: `fonts` (the `@font-face` rules and their
metric-matched fallbacks), `tokens` (the two palettes, the two faces, the type scale, the
shell, the measures and the spacing steps), `base` (reset, body, headings, links, code, the
shared text classes, the header bar, search, the footer, the disclaimer and the focus ring),
`identity` (the masthead every page below home opens with, its caption and trail, and the
header bar's current section), `pages` (home, the acts roster, methodology), `timeline` (the
act, event and amendment pages as documents: header lines, the two columns and the sidebar, the
rail, the event card, the act's dates list and the pager), `evidence` (one change: the block
and its heading, the touched index, the disagreement badge, the gathered rows with no text, the
diff and verbatim blocks, tables) and `media` (print and forced colours). A rule in a later
module may rely on an earlier one and never the reverse, which is what makes the order a
contract rather than a preference. A class used by more than one page family lives in `base`; a
class one page owns lives with that page. `timeline` was split off `evidence` on 2026-09-05,
when gathering an event's changes with no text to show needed rules that module had no room for
under the cap, and `media` on 2026-09-18, when forced colours joined print.

This text is minted, not escaped. It is the repository's own writing, not anything a legal
document or a model produced, so it never passes through `markup.escape`; nothing in it is
interpolated but the fonts' file names, which are hex digests of committed bytes, and that is
what makes it safe rather than merely convenient. The rule holds for
every module of the package.

Deliberately plain and deliberately not minified: view-source is part of what the site
claims about itself. Both themes come from `color-scheme` and one `prefers-color-scheme` block,
so the site reads correctly light and dark without a toggle, without JavaScript and without
storing anything about the reader.

Fonts, chosen on 2026-09-18: two families, self-hosted. Each face is an open-licence WOFF2,
subset to the characters the corpus and the site use, committed with its licence under
`static/fonts/`, written to the site root under a name carrying a digest of its bytes, and
loaded by a relative `url()`. A font is therefore a request to the site itself and to no one
else, which is why the footer's promise of no third-party requests still holds. The serif is
only ever the law's own words and the sans is always the site speaking, and every face has a
metric-matched system fallback, so a reader whose browser refuses the file reads the same
layout.

Colour, chosen on 2026-09-18: every colour is a lower-case `#rrggbb` token declared in
`tokens` in both schemes, and nothing else in the sheet names a hex value. Colour is spent
semantically and nowhere else, in five families: the ground and its text; the `ins`/`del`
tints of a diff; one hue for links and one, kept visibly apart from it, for an alert; one
colour per kind of change, with a neutral pair for provenance; and one colour per page type.
Every text pair clears 4.5:1 and every component boundary 3:1, in both schemes, and colour is
never the only carrier of meaning: a word, a glyph, an underline or a border style always says
the same thing. The diff tints are backgrounds under `--fg` text, so the evidence's contrast
never depends on a coloured foreground surviving a theme swap.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.style.base import BASE
from emendrix.site_.style.evidence import EVIDENCE
from emendrix.site_.style.fonts import FONTS_CSS
from emendrix.site_.style.identity import IDENTITY
from emendrix.site_.style.media import MEDIA
from emendrix.site_.style.pages import PAGES
from emendrix.site_.style.timeline import TIMELINE
from emendrix.site_.style.tokens import TOKENS

__all__ = ["STYLE"]

STYLE: Final = FONTS_CSS + TOKENS + BASE + IDENTITY + PAGES + TIMELINE + EVIDENCE + MEDIA
"""The whole sheet, in cascade order. `build.py` writes exactly this, and `fingerprint`
names the file from these bytes so a page never loads a cached sheet from another build."""
