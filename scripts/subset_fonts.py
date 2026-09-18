"""Regenerate `src/emendrix/site_/static/fonts/*.woff2`, the site's three self-hosted faces.

Run it from the repository root, pointing it at a directory holding the two upstream release
archives unpacked side by side:

    uv run python scripts/subset_fonts.py <upstream-dir>

The archives are the IBM Plex Sans release `@ibm/plex-sans@1.1.0`
(https://github.com/IBM/plex/releases/download/%40ibm/plex-sans%401.1.0/ibm-plex-sans.zip) and
the Source Serif 4 release `4.005R`
(https://github.com/adobe-fonts/source-serif/releases/download/4.005R/source-serif-4.005_WOFF2.zip).
The three upstream files read are named in `SOURCES` below with their SHA-256, and every one is
verified before anything is written: a subset of a file nobody can identify is a binary nobody
can review, the same bargain `scripts/make_og_image.py` makes for the link-preview card.

`fontTools` and `brotli` are development dependencies and only this script imports them. The
site build copies the committed WOFF2 bytes and subsets nothing, so the wheel's runtime
dependencies stay free of a font toolchain. The exact output bytes depend on the installed
fontTools version, which is accepted: regeneration is deliberate and rare, and the glyph set,
the features and the names are what this script fixes.

What each output keeps, chosen on 2026-09-18:

- **Characters.** Latin, Latin-1, Latin Extended-A, the Romanian comma-below letters and the
  typographic marks the corpus and the site's own prose use. The serif adds Greek and basic
  Cyrillic, because stored provision text quotes both and a fallback face swapped in
  mid-sentence would break the one register that must look uniform.
- **Layout features.** Kerning, mark positioning, composition, localised forms and the figure
  features. `liga`, `dlig`, `calt` and every stylistic set are dropped, so no two characters of
  verbatim legal text can ever render as one glyph.
- **Names.** A subset is a Modified Version under the SIL Open Font License 1.1, and both
  families reserve their names ("Plex", "Source"). So the family, full and PostScript names are
  rewritten to "Emendrix Sans" and "Emendrix Serif", and the copyright, trademark, vendor,
  designer, URL and licence records are kept as upstream wrote them.

Output names are stable (`sans-400.woff2`); the site build adds the digest of the bytes.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Final, NamedTuple

from fontTools import subset
from fontTools.ttLib import TTFont

TARGET: Final = Path(__file__).resolve().parents[1] / "src/emendrix/site_/static/fonts"

_LATIN: Final = (
    "U+0020-007E, U+00A0-00FF, U+0100-017F, U+0218-021B, "
    "U+2010-2027, U+202F, U+2032-2034, U+20AC, U+2190-2193, U+2197, "
    "U+2208, U+2212, U+221A, U+2260, U+2264-2265"
)
SANS_RANGES: Final = _LATIN
SERIF_RANGES: Final = _LATIN + ", U+0370-03FF, U+0400-045F"
"""Written in `unicode-range` syntax, the form `style/fonts.py` declares them in."""

SANS_FEATURES: Final = ("kern", "mark", "mkmk", "ccmp", "locl", "zero", "lnum", "tnum")
SERIF_FEATURES: Final = ("kern", "mark", "mkmk", "ccmp", "locl", "lnum", "tnum", "pnum")

_KEPT_NAME_IDS: Final = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17)
"""Copyright, the rewritten names, version, trademark, vendor, designer, URLs and licence."""


class Source(NamedTuple):
    """One upstream file and the subset written from it."""

    path: str
    sha256: str
    output: str
    family: str
    style: str
    ranges: str
    features: tuple[str, ...]


SOURCES: Final = (
    Source(
        "ibm-plex-sans/fonts/complete/woff2/IBMPlexSans-Regular.woff2",
        "ba711a3085ff9f27440b6b9c4550cfc47c97bf36591d5da958b975bb3add8c1a",
        "sans-400.woff2",
        "Emendrix Sans",
        "Regular",
        SANS_RANGES,
        SANS_FEATURES,
    ),
    Source(
        "ibm-plex-sans/fonts/complete/woff2/IBMPlexSans-SemiBold.woff2",
        "f78048030eab62e860efa39a0df79e2e5581bf122eb95b9bc42c0b8a4988d205",
        "sans-600.woff2",
        "Emendrix Sans",
        "SemiBold",
        SANS_RANGES,
        SANS_FEATURES,
    ),
    Source(
        "source-serif-4.005_WOFF2/TTF/SourceSerif4-Regular.ttf.woff2",
        "6b053e98f0838afe81f3e784727be4583a7c13bb42f198dc5202ecffee0aaee0",
        "serif-400.woff2",
        "Emendrix Serif",
        "Regular",
        SERIF_RANGES,
        SERIF_FEATURES,
    ),
)


def _codepoints(ranges: str) -> list[int]:
    points: list[int] = []
    for part in ranges.split(","):
        first, _, last = part.strip().removeprefix("U+").partition("-")
        points.extend(range(int(first, 16), int(last or first, 16) + 1))
    return points


def _rename(font: TTFont, source: Source) -> None:
    """Replace the reserved names, keeping every record that states ownership or terms."""
    postscript = f"{source.family.replace(' ', '')}-{source.style}"
    regular = source.style == "Regular"
    legacy_family = source.family if regular else f"{source.family} {source.style}"
    names = {
        1: legacy_family,
        2: "Regular",
        3: f"{postscript};subset",
        4: f"{source.family} {source.style}",
        6: postscript,
        16: source.family,
        17: source.style,
    }
    table = font["name"]
    for name_id in names:
        table.removeNames(nameID=name_id)
    for name_id, value in names.items():
        table.setName(value, name_id, 3, 1, 0x409)


def _subset(upstream: Path, source: Source) -> bytes:
    path = upstream / source.path
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = list(source.features)
    options.hinting = False
    options.desubroutinize = True
    options.name_IDs = list(_KEPT_NAME_IDS)
    options.name_languages = ["*"]
    font = TTFont(path)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=_codepoints(source.ranges))
    subsetter.subset(font)
    _rename(font, source)
    target = TARGET / source.output
    font.flavor = "woff2"
    font.save(target)
    return target.read_bytes()


def main() -> None:
    """Verify all three upstream files, then write each subset and say what landed."""
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    upstream = Path(sys.argv[1])
    for source in SOURCES:
        path = upstream / source.path
        if not path.is_file():
            raise SystemExit(f"{path}: not found; unpack both release archives here")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source.sha256:
            raise SystemExit(f"{path}: SHA-256 {digest}, expected {source.sha256}")
    TARGET.mkdir(parents=True, exist_ok=True)
    total = 0
    for source in SOURCES:
        content = _subset(upstream, source)
        total += len(content)
        digest = hashlib.sha256(content).hexdigest()
        print(f"{source.output}: {len(content)} bytes, sha256 {digest}")
    print(f"total: {total} bytes")


if __name__ == "__main__":
    main()
