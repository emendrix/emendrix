"""The committed changelog repository, read off disk and put in the site's one order.

Split out of `inputs.py` on 2026-09-03, when that module reached the size cap while gaining
the act's published-document link and the roster's kinds. The seam is the one the two halves
already had: this module turns files into `ChangelogEntry` values and orders them, and knows
nothing about acts, labels or pages; `inputs.py` resolves what the site renders and never
touches the filesystem.

Ordering lives here rather than beside the pages because two builds of one repository state
have to produce one tree, and the rule that makes them is a property of the events themselves:
newest first by `sort_date`, the consolidated version's own date where the corpus resolved
one, else the detection date, with the version tag breaking a shared date. Why the two clocks
may never share a sort key is `clocks`' own story.
"""

from __future__ import annotations

from pathlib import Path

from emendrix.output import ChangelogEntry
from emendrix.site_.clocks import VersionDates, sort_date

__all__ = ["read_entries", "sorted_entries"]


def read_entries(root: Path) -> tuple[ChangelogEntry, ...]:
    """Every committed event in one output repository, in sorted path order.

    The layout and the documents are the output repository writer's own, so a file that does
    not validate means the repository was edited by hand or written by a different version of
    the schema: loud, named, and not something to skip quietly.
    """
    entries: list[ChangelogEntry] = []
    for path in sorted(root.glob("*/*/changes/*.json")):
        try:
            entries.append(ChangelogEntry.model_validate_json(path.read_bytes()))
        except ValueError as error:
            raise ValueError(f"{path} is not a changelog document emendrix wrote: {error}") from (
                error
            )
    return tuple(entries)


def sorted_entries(
    entries: list[ChangelogEntry], version_dates: VersionDates
) -> tuple[ChangelogEntry, ...]:
    """One act's events, newest first by `sort_date`, the version tag breaking a shared date."""
    return tuple(
        sorted(
            entries,
            key=lambda e: (sort_date(e, version_dates).isoformat(), e.key),
            reverse=True,
        )
    )
