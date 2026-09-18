"""Content-addressed names, and the fonts' names, in a module the stylesheet can import.

A name carrying the first eight hex characters of SHA-256 over a file's own bytes changes
exactly when the file does, which is what lets a cache in front of the site keep it for a day
without ever serving yesterday's bytes under today's page; `fingerprint` says why at length.

This is its own module because of one ordering constraint. The stylesheet names each font file
it loads, so `style` needs the fonts' fingerprinted names while it is being built, and
`fingerprint` names the stylesheet from `style`'s finished bytes. Were the font names computed
in `fingerprint`, `style` would import the module that imports it. Here they depend only on
`assets`, which reads committed files and imports nothing of this package, so `style/fonts.py`
and `fingerprint` both read `FONTS` from this one place and cannot come to disagree.
"""

from __future__ import annotations

import hashlib
from typing import Final

from emendrix.site_.assets import font_files

__all__ = ["DIGEST_LENGTH", "FONTS", "fingerprinted_bytes"]

DIGEST_LENGTH: Final = 8


def fingerprinted_bytes(name: str, content: bytes) -> str:
    """`("sans-400.woff2", data)` -> `sans-400.<digest>.woff2`. The suffix stays the suffix."""
    stem, _, suffix = name.rpartition(".")
    digest = hashlib.sha256(content).hexdigest()[:DIGEST_LENGTH]
    return f"{stem}.{digest}.{suffix}"


FONTS: Final[dict[str, str]] = {
    name: fingerprinted_bytes(name, content) for name, content in font_files()
}
"""Each committed font's file name -> the name the build writes it under at the site root."""
