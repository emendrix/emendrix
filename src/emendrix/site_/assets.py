"""The three static assets: checked in and copied, never generated at build time.

A checked-in file is reviewable as itself and diffable as itself; a Python string holding
JavaScript is neither. `importlib.resources` rather than `__file__` so the read works from
a wheel as well as a checkout.

`search.js` and `icon.svg` are text and hold to that bargain exactly. `og.png` cannot: a
link-preview card is a raster image, and the only honest form of it in the tree is bytes. So
it ships with `scripts/make_og_image.py`, which regenerates it, and the imaging library that
script needs stays a development dependency. The site build imports nothing to write the card;
it copies the committed bytes, which is what keeps a deployment free of a rasteriser and keeps
the published image a thing somebody chose rather than a thing a build produced.
"""

from __future__ import annotations

from importlib.resources import files

__all__ = ["icon_svg", "og_png", "search_js"]


def search_js() -> str:
    """The script's bytes as text, exactly as committed."""
    return (files("emendrix.site_.static") / "search.js").read_text(encoding="utf-8")


def icon_svg() -> str:
    """The favicon, exactly as committed. Text, so it reviews and diffs as itself."""
    return (files("emendrix.site_.static") / "icon.svg").read_text(encoding="utf-8")


def og_png() -> bytes:
    """The link-preview card, exactly as committed. The one binary the site publishes."""
    return (files("emendrix.site_.static") / "og.png").read_bytes()
