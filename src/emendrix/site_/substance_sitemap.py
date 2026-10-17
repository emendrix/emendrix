"""What the second sitemap lists: each act's list of numbers, and every canonical number page.

An EC page that defers to a CAS page is written and left out here, because a sitemap entry for a
page whose canonical names another address is a contradiction handed to a crawler. A page's
dates are the in-force dates of the versions its recorded changes were read from, never the
build's: a number only a register names has no such date, and its entry carries none. Which of
those dates a build may publish is `discovery`'s rule, applied there to these and to every other
page alike.
"""

from __future__ import annotations

from datetime import date

from emendrix.site_.inputs import SiteInputs
from emendrix.site_.pages.substances_index import PER_PAGE, act_lists
from emendrix.site_.substance_inputs import Substance
from emendrix.site_.urls import substance_href, substance_list_href

__all__ = ["substance_entries"]


def _dates(substance: Substance) -> tuple[date, ...]:
    return tuple(max(moved.event.in_force) for moved in substance.history if moved.event.in_force)


def substance_entries(site: SiteInputs) -> tuple[tuple[str, tuple[date, ...]], ...]:
    """Every page the second sitemap lists, with every date its content moved on."""
    found: list[tuple[str, tuple[date, ...]]] = []
    for act, numbers in act_lists(site):
        for start in range(0, len(numbers), PER_PAGE):
            shown = numbers[start : start + PER_PAGE]
            dated = tuple(day for one in shown for day in _dates(one))
            found.append((substance_list_href(act.slug, start // PER_PAGE + 1), dated))
    found.extend(
        (substance_href(one.scheme, one.value), _dates(one))
        for one in site.substances.substances
        if one.canonical is None
    )
    return tuple(found)
