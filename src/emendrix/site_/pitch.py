"""The one sentence that says what emendrix is, for every page that opens with it.

It lives in a module of its own because two pages lead with it, the methodology page and the
about page, and a product description written twice is a product description that drifts. It
claims nothing measured: the figures are the methodology page's, and this is the sentence a
reader meets before any of them.
"""

from __future__ import annotations

from typing import Final

__all__ = ["PITCH"]

PITCH: Final = (
    "Your regulatory dependencies, with a changelog. emendrix watches EU legislation, computes "
    "provision-level diffs when it is amended, and explains what changed in plain English where "
    "every sentence cites a provision you can click."
)
