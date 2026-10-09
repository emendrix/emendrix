"""Which backup copies to keep: seven daily and four weekly, decided by the date in each name.

A copy is named `emendrix-app-YYYYMMDD.dump.age`, dated the day it was shipped. On `today`:

- every copy dated within the last seven days, `today` included, is kept;
- for each of the four ISO weeks before the week holding `today`, the earliest copy dated in
  that week is kept (the Monday's, when the Monday's job ran).

A copy dated after `today` is kept, so a clock that ran ahead never deletes a newer dump. Every
other copy is pruned. The oldest copy this keeps is the Monday four weeks before the current
week's Monday, at most 34 days old on a Sunday, which is what lets the privacy notice say that
deleted data leaves the backups within 35 days. A partial upload of an earlier day
(`<copy name>.part`) is pruned too. Any other name is never pruned, because nothing says this
command wrote it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Final

__all__ = ["DAILY", "PARTIAL", "PATTERN", "WEEKLY", "backup_name", "dated", "keep", "prunable"]

DAILY: Final = 7
WEEKLY: Final = 4

PATTERN: Final = re.compile(r"emendrix-app-(\d{8})\.dump\.age")

PARTIAL: Final = ".part"
"""The suffix a copy carries while it uploads; an upload that died leaves one behind."""


def backup_name(day: date) -> str:
    """The name of the copy shipped on `day`."""
    return f"emendrix-app-{day:%Y%m%d}.dump.age"


def dated(name: str) -> date | None:
    """The date in a copy's name, or `None` for a name that is not a copy's."""
    found = PATTERN.fullmatch(name)
    if found is None:
        return None
    try:
        return datetime.strptime(found.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def keep(names: Iterable[str], today: date) -> set[str]:
    """The copies among `names` to keep on `today`; every other copy may be pruned."""
    copies = {name: day for name in names if (day := dated(name)) is not None}
    kept = {name for name, day in copies.items() if day > today - timedelta(days=DAILY)}
    this_week = _monday(today)
    for weeks_back in range(1, WEEKLY + 1):
        start = this_week - timedelta(weeks=weeks_back)
        in_week = [
            (day, name) for name, day in copies.items() if start <= day < start + timedelta(weeks=1)
        ]
        if in_week:
            kept.add(min(in_week)[1])
    return kept


def _stale_partial(name: str, today: date) -> bool:
    if not name.endswith(PARTIAL):
        return False
    day = dated(name.removesuffix(PARTIAL))
    return day is not None and day < today


def prunable(names: Iterable[str], today: date) -> list[str]:
    """The copies among `names` that `keep` does not keep, and the partial uploads of earlier
    days, sorted; never a foreign name. A partial upload holds encrypted data like a copy, so it
    must age out like one."""
    listed = list(names)
    kept = keep(listed, today)
    return sorted(
        name
        for name in listed
        if (dated(name) is not None and name not in kept) or _stale_partial(name, today)
    )
