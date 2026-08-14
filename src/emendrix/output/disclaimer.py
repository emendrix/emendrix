"""The not-legal-advice line as it appears in a written artifact.

`emendrix.DISCLAIMER` is the sentence itself; this module is the two shapes it takes once it is
written to disk: a Markdown blockquote at the top of every `CHANGELOG.md`, and the `disclaimer`
field of every JSON document (`json_out.py`).

It is its own module because the disclaimer is an obligation of *every* user-facing output this
project produces, and an obligation that lives as a string literal repeated in two renderers is
one that goes missing the third time somebody adds a renderer. Here it has a name, both
renderers import it, and both shapes are derived from the one sentence rather than restated
beside it, so there is exactly one wording to keep true.
"""

from __future__ import annotations

import textwrap
from typing import Final

from emendrix import DISCLAIMER

__all__ = ["DISCLAIMER", "MARKDOWN_DISCLAIMER"]

_WRAP_AT: Final = 94
"""Chosen so the blockquote stays inside the repo's 100-column line budget with `> ` on it."""

MARKDOWN_DISCLAIMER: Final = "\n".join(
    f"> {line}" for line in textwrap.wrap(DISCLAIMER, width=_WRAP_AT)
)
"""The disclaimer as a Markdown blockquote. Deterministic: `textwrap` reads no clock and no
locale, so the same sentence produces the same bytes on every machine."""
