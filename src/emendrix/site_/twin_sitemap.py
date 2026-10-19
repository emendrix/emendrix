"""What the third sitemap lists: the twins index, each pair of acts' index and each twin page.

A twin page's dates are the dates of the two versions its pair was computed on and of every
recorded change it lists; a pair index's are its pages' and its own two versions'; the index's
are every pair's. Never the build's: which of these dates a build may publish is `discovery`'s
rule, applied there to these and to every other page alike.
"""

from __future__ import annotations

from datetime import date

from emendrix.site_.clocks import event_dated
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.twin_model import TwinPageView, twin_views
from emendrix.site_.urls import twins_href

__all__ = ["twin_entries"]


def _dates(view: TwinPageView) -> tuple[date, ...]:
    paired = tuple(side.paired_on for side in (view.a, view.b) if side.paired_on is not None)
    return (*paired, *(event_dated(change.step.entry) for change in view.changes))


def twin_entries(site: SiteInputs) -> tuple[tuple[str, tuple[date, ...]], ...]:
    """Every page the twins sitemap lists, with every date its content moved on."""
    views = twin_views(site)
    if not views:
        return ()
    found: list[tuple[str, tuple[date, ...]]] = []
    every: list[date] = []
    for view in views:
        own = tuple(
            day
            for side in (view.document.a, view.document.b)
            if (day := site.twins.dates.get(side.version)) is not None
        )
        pages = [(shown.path, _dates(shown)) for shown in view.pages]
        dated = (*own, *(day for _, days in pages for day in days))
        every.extend(dated)
        found.append((view.path, dated))
        found.extend(pages)
    return ((twins_href(), tuple(every)), *found)
