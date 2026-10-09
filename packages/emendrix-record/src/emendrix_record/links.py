"""The fragment the site gives one change, computed from the keys the record states.

These mirror the site's anchor scheme rule for rule, because a reader beside the pipeline must
link to a change on the site without importing the pipeline. A test in the `emendrix` suite
holds each function here equal to the site's over every fixture location, so a change to the
scheme fails a test there rather than a link here.

A change's link is the catalogue's address for its event, `#`, and `change_anchor(...)`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

__all__ = ["change_anchor", "entry_anchors", "location_slug"]

_SEPARATORS: Final = re.compile(r"\s+")
_DROPPED: Final = re.compile(r"[()]")


def location_slug(canonical: str) -> str:
    """`AR 5 PA 1 ALN 1 PTA (bb)` becomes `ar-5-pa-1-aln-1-pta-bb`.

    Lowercase, every run of whitespace to one hyphen, parentheses dropped.
    """
    return _DROPPED.sub("", _SEPARATORS.sub("-", canonical.strip())).lower()


def change_anchor(entry_key: str, canonical: str, occurrence: int = 1) -> str:
    """The fragment of the `occurrence`-th change (from 1) at `canonical` in one entry.

    The first occurrence carries no suffix and a later one carries `-n`.
    """
    if occurrence < 1:
        raise ValueError(f"occurrence counts from 1, got {occurrence}")
    suffix = "" if occurrence == 1 else f"-{occurrence}"
    return f"{entry_key}-{location_slug(canonical)}{suffix}"


def entry_anchors(entry_key: str, canonicals: Iterable[str]) -> tuple[str, ...]:
    """Every anchor of one entry, one per change location given in entry order.

    The occurrence of a location is counted over the locations before it, as the site counts.
    """
    seen: dict[str, int] = {}
    anchors: list[str] = []
    for canonical in canonicals:
        seen[canonical] = seen.get(canonical, 0) + 1
        anchors.append(change_anchor(entry_key, canonical, seen[canonical]))
    return tuple(anchors)
