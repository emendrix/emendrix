"""Which sector an act sits in, and in what order the sectors are listed.

A sector is the watchlist's `domain` label and nothing else. Nothing here infers a subject area
from an act's title or its identifier: an act whose operator declared no domain lands under
`Other`, which is honest, where a guess would be a claim this project has no evidence for.
`Other` sorts last for the same reason it exists, that it is the absence of an answer rather
than a group.

Every page that lists acts by sector reads this module, the acts roster and the feeds page
among them. One sort in one place is what keeps two pages from disagreeing about where an act
sits or which sector comes first; the id each sector's heading carries is `urls.domain_anchor`,
which is the same one place for the address.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from emendrix.site_.inputs import ActSite

__all__ = ["UNGROUPED", "groups", "sector_key", "sector_of"]

UNGROUPED: Final = "Other"
"""Where an act with no declared domain lands, and the sector that always sorts last."""


def sector_of(act: ActSite) -> str:
    """The sector one act is listed under: its declared domain, or `Other`."""
    return act.domain or UNGROUPED


def sector_key(name: str) -> tuple[bool, str, str]:
    """The order sectors are listed in: `Other` last, then case-folded, then the raw name.

    The raw name breaks a tie between two labels that fold alike, so the order is total and two
    builds of one repository state agree by construction.
    """
    return (name == UNGROUPED, name.casefold(), name)


def groups(acts: Iterable[ActSite]) -> list[tuple[str, list[ActSite]]]:
    """The acts by sector, sectors in `sector_key` order, acts in the order they arrived.

    The site hands acts over already sorted by label, so the order inside a sector is that one
    and nothing here re-sorts it.
    """
    grouped: dict[str, list[ActSite]] = {}
    for act in acts:
        grouped.setdefault(sector_of(act), []).append(act)
    return sorted(grouped.items(), key=lambda item: sector_key(item[0]))
