"""Regenerate `src/emendrix/site_/static/og.png`, the site's link-preview card.

Run it from the repository root:

    uv run --with pillow python scripts/make_og_image.py

Pillow is a development dependency and nothing under `src/emendrix/` imports it. The site
build copies the committed PNG byte for byte, so a deployment never rasterises anything and
the wheel's runtime dependencies stay free of an imaging library. What that costs is a binary
in the tree, which is why this script exists: a committed image with no reproducer is a file
nobody can review, the same bargain `src/emendrix/eu/fetch_fixtures.py` makes for the corpus
fixtures. Regeneration is deliberate and rare, so the exact bytes depending on the installed
Pillow version is accepted.

The card is 1200x630, the size every link preview crops to, and it uses the stylesheet's light
palette because an image cannot follow `prefers-color-scheme`. The type is the site's own sans,
read from the subset WOFF2 files the repository already commits under
`src/emendrix/site_/static/fonts/` (Pillow's FreeType reads WOFF2), so the card and the header
set the wordmark in one face. A system font loaded by path would make the output depend on the
machine that ran this; the committed files make it depend only on the repository.

It carries "Not legal advice." because a link preview is a user-facing output and every one of
them states the limit alongside the claim.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 630
"""The size link previews are cropped to, on every platform that reads Open Graph."""

BACKGROUND = "#f6f7f9"
INK = "#161a21"
MUTED = "#4e5664"
ACCENT = "#2a5fd6"
"""The light `--bg`, `--fg`, `--muted` and `--link` of `src/emendrix/site_/style/tokens.py`.
A card cannot follow a theme."""

BAR_WIDTH = 12
LEFT = 96
"""The accent bar down the left edge, and where the text starts clear of it."""

WORDMARK = "emendrix"
TAGLINE = "Provision-level changelogs for EU legislation"
DISCLAIMER = "Not legal advice."

STATIC = Path(__file__).resolve().parents[1] / "src/emendrix/site_/static"
TARGET = STATIC / "og.png"
REGULAR = STATIC / "fonts/sans-400.woff2"
SEMIBOLD = STATIC / "fonts/sans-600.woff2"


def draw_card() -> Image.Image:
    """The finished card. Pure: same Pillow and fonts, same bytes, no clock and no input."""
    card = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    pen = ImageDraw.Draw(card)
    pen.rectangle((0, 0, BAR_WIDTH - 1, HEIGHT - 1), fill=ACCENT)
    pen.text((LEFT, 202), WORDMARK, font=ImageFont.truetype(SEMIBOLD, 96), fill=INK)
    pen.text((LEFT, 322), TAGLINE, font=ImageFont.truetype(REGULAR, 36), fill=MUTED)
    pen.text((LEFT, 414), DISCLAIMER, font=ImageFont.truetype(REGULAR, 24), fill=MUTED)
    return card


def main() -> None:
    """Write the card over the committed one and say what landed."""
    draw_card().save(TARGET, format="PNG", optimize=True)
    print(f"{TARGET}: {TARGET.stat().st_size} bytes")


if __name__ == "__main__":
    main()
