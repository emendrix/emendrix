"""The three self-hosted faces and their metric-matched fallbacks.

First in the cascade, because an `@font-face` rule declares a family the rest of the sheet names
and nothing downstream may redefine one. The rule, chosen on 2026-09-18: a web font is served
from the site itself or not at all. Each face is a subset WOFF2 committed under
`static/fonts/` with its licence beside it, written to the site root under a name carrying a
digest of its bytes (`digest.FONTS`), and loaded here by a bare relative `url()`. A relative
URL resolves against the stylesheet, which sits at the root beside the fonts, so the same rule
works from every page depth, from `file://` and from a subpath, and the site still makes no
request to anyone but itself.

The typeface says who is speaking. "Emendrix Serif" (Source Serif 4) is only ever the law's own
words, verbatim from EUR-Lex: official titles, provision text and diffs. "Emendrix Sans" (IBM
Plex Sans) is the site speaking: headings, counts, navigation and the model's explanation. No
italic and no bold is loaded, and the base rules set `font-synthesis: none`, because a
synthesised oblique of verbatim text would misrepresent it.

Every face is `font-display: swap`, so text is readable before the font arrives. The fallback
faces are system fonts under their own family names, scaled so a line set in them takes the
width and height the web font will: `size-adjust` is the ratio of summed advance widths over a
sample of the site's own prose, and each override is the web font's `hhea` metric divided by
it, computed with fontTools on 2026-09-18 against Arial, Arial Bold and Georgia. Liberation
Sans and Arimo are metric-compatible with Arial, so the same numbers hold on Linux. They matter
beyond the first paint: wherever a font is refused (Firefox under `file://` for a page below
the root, or a server whose policy does not yet allow fonts), the fallback is what a reader
sees, and it keeps the layout the page was designed at.

This text is minted, not escaped, like every module of the package. The only interpolations
are the fingerprinted file names, which are hex digests of committed bytes.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.digest import FONTS

__all__ = ["FONTS_CSS"]

_SANS_RANGE: Final = (
    "U+0020-007E, U+00A0-00FF, U+0100-017F, U+0218-021B, U+2010-2027, U+202F,\n"
    "    U+2032-2034, U+20AC, U+2190-2193, U+2197, U+2208, U+2212, U+221A, U+2260, U+2264-2265"
)
_SERIF_RANGE: Final = (
    "U+0020-007E, U+00A0-00FF, U+0100-017F, U+0218-021B, U+0370-03FF, U+0400-045F,\n"
    "    U+2010-2027, U+202F, U+2032-2034, U+20AC, U+2190-2193, U+2197, U+2208, U+2212, U+221A,\n"
    "    U+2260, U+2264-2265"
)
"""The characters each subset holds (`scripts/subset_fonts.py`), so a browser asks for the
file only when a page uses one of them and never falls into a face that lacks a glyph."""


def _face(family: str, file: str, weight: int, ranges: str) -> str:
    return (
        "@font-face {\n"
        f'  font-family: "{family}";\n'
        f'  src: url({FONTS[file]}) format("woff2");\n'
        f"  font-weight: {weight};\n"
        "  font-style: normal;\n"
        "  font-display: swap;\n"
        f"  unicode-range: {ranges};\n"
        "}\n"
    )


_FALLBACKS: Final = """\
@font-face {
  font-family: "Emendrix Sans Fallback";
  src: local("Arial"), local("ArialMT"), local("Liberation Sans"), local("Arimo");
  font-weight: 400;
  size-adjust: 101.53%;
  ascent-override: 100.96%;
  descent-override: 27.09%;
  line-gap-override: 0%;
}
@font-face {
  font-family: "Emendrix Sans Fallback";
  src: local("Arial Bold"), local("Arial-BoldMT"), local("Liberation Sans Bold"),
    local("Arimo Bold");
  font-weight: 600;
  size-adjust: 98.06%;
  ascent-override: 104.53%;
  descent-override: 28.05%;
  line-gap-override: 0%;
}
@font-face {
  font-family: "Emendrix Serif Fallback";
  src: local("Georgia");
  font-weight: 400;
  size-adjust: 100.07%;
  ascent-override: 103.53%;
  descent-override: 33.48%;
  line-gap-override: 0%;
}
"""

FONTS_CSS: Final = (
    _face("Emendrix Sans", "sans-400.woff2", 400, _SANS_RANGE)
    + _face("Emendrix Sans", "sans-600.woff2", 600, _SANS_RANGE)
    + _face("Emendrix Serif", "serif-400.woff2", 400, _SERIF_RANGE)
    + _FALLBACKS
)
"""Every `@font-face` the sheet declares, the web faces first."""
