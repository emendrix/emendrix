"""The two generated-name assets: a stylesheet and a script named for their own bytes.

A cache is right by construction when the name changes with the content. The edge in front of
this site gives an asset a one-day lifetime, and on 2026-09-04 it served a stylesheet of 14 424
bytes against an origin holding 22 056: the file had changed, the address had not, and readers
had new pages with yesterday's rules. A name carrying a digest of the file's own bytes removes
the class: a build that changes the bytes writes a different URL, and a build that does not
leaves the URL alone, so nothing has to be purged by hand and nothing has to be told not to
cache.

`icon.svg`, `og.png` and `search-index.json` keep fixed names on purpose. The first two are
identity rather than code, an `og:image` address that moves breaks the previews social sites
have already cached, and both change rarely enough that a purge is the cheaper answer. The
index changes on every build, carries the short lifetime the pages carry, and is fetched by the
script through a path relative to `data-root`, which is a name the script would otherwise have
to be told.

The digest is the first eight hex characters of SHA-256 over exactly the bytes the builder
writes: `write_site` writes text as UTF-8 with `newline="\\n"`, so the encoding here is that
file and not a re-rendering of it, and `tests/site_/test_site_build.py` checks the written file
against its own name rather than trusting that sentence. Eight characters is a name a person
can still read in a directory listing and in a page's source, and the digest identifies a
build's bytes rather than defending against anyone choosing them; it is a cache key, never a
security claim. The separator is a dot, with the extension left last, so every server, editor
and browser keeps reading the type off the suffix.

Both names are computed once at import: they are pure functions of two constants in this
package, so two builds of one checkout name one file one way. `chrome.page` links them and
`build.py` writes them, and they read the name from here rather than each spelling it, because
a link and a file that disagree is the defect this module exists to make unrepresentable.
"""

from __future__ import annotations

import hashlib
from typing import Final

from emendrix.site_.assets import search_js
from emendrix.site_.style import STYLE

__all__ = ["SCRIPT", "STYLESHEET", "fingerprinted"]

_DIGEST_LENGTH: Final = 8


def fingerprinted(name: str, content: str) -> str:
    """`("style.css", sheet)` -> `style.<digest>.css`. The suffix stays the suffix."""
    stem, _, suffix = name.rpartition(".")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:_DIGEST_LENGTH]
    return f"{stem}.{digest}.{suffix}"


STYLESHEET: Final = fingerprinted("style.css", STYLE)
"""Where `chrome.page` says the stylesheet is. Both ends of that link are in this package."""

SCRIPT: Final = fingerprinted("search.js", search_js())
"""The one script, at the root the script is handed as `data-root` and fetches its index from."""
