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
palette because an image cannot follow `prefers-color-scheme`. The type is Pillow's bundled
font rather than the site's Georgia: loading a system font by path would make the output depend
on the machine that ran this, and committing a font file would add a second binary nobody
reviews. The card is therefore sans-serif where the site's display face is a serif.

It carries "Not legal advice." because a link preview is a user-facing output and every one of
them states the limit alongside the claim.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 630
"""The size link previews are cropped to, on every platform that reads Open Graph."""

BACKGROUND = "#fcfcfa"
INK = "#1c1c1a"
MUTED = "#5d5d58"
ACCENT = "#7a4b1e"
"""The light palette of `src/emendrix/site_/style/tokens.py`. A card cannot follow a theme."""

BAR_WIDTH = 12
LEFT = 96
"""The accent bar down the left edge, and where the text starts clear of it."""

WORDMARK = "emendrix"
TAGLINE = "Provision-level changelogs for EU legislation"
DISCLAIMER = "Not legal advice."

TARGET = Path(__file__).resolve().parents[1] / "src/emendrix/site_/static/og.png"


def draw_card() -> Image.Image:
    """The finished card. Pure: same Pillow, same bytes, no clock and no input."""
    card = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    pen = ImageDraw.Draw(card)
    pen.rectangle((0, 0, BAR_WIDTH - 1, HEIGHT - 1), fill=ACCENT)
    pen.text((LEFT, 202), WORDMARK, font=ImageFont.load_default(size=96), fill=INK)
    pen.text((LEFT, 322), TAGLINE, font=ImageFont.load_default(size=36), fill=MUTED)
    pen.text((LEFT, 414), DISCLAIMER, font=ImageFont.load_default(size=24), fill=MUTED)
    return card


def main() -> None:
    """Write the card over the committed one and say what landed."""
    draw_card().save(TARGET, format="PNG", optimize=True)
    print(f"{TARGET}: {TARGET.stat().st_size} bytes")


if __name__ == "__main__":
    main()
