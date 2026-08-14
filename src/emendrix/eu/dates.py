"""Reading the dates CELLAR writes, in the two spellings it writes them in.

`YYYY-MM-DD` in notices — and `2007/11/23` in 27 of REACH's 391 `START_OF_VALIDITY` values
(measured 2026-08-05; the 391 is asserted by
`tests/eu/test_modmeta.py`), which is why the slash spelling is not a legacy curiosity to drop
but a spelling to read. `YYYYMMDD` in Formex attributes, where
the attribute that carries it is confusingly named `ISO` (`<DATE ISO="20271202">`) and is
nothing of the sort; hence `compact_date` rather than a second `iso_date`.

**Both answer `None` rather than raising**, for anything unreadable — including a well-formed
but impossible date like `2026-02-30`, where the regex checks only the spelling and only
`date()` knows the calendar. That is not leniency. A date nobody can read is a coverage gap to
count, not an exception to propagate out of a parse and take down an act's whole version
inventory; the callers here are the version inventory (`notices`), the reference label set
(`modmeta`), the second clock (`formex/text`) and consolidation provenance (`packages`), and
every one of them counts what it could not read.

Sentinels are not this module's business. `END.DATE="99999999"` means "still current" to
`packages.py` and nothing at all to anyone else, so it is read there — see `_end_of_validity` —
rather than baked in here as a default nobody else wants. It would parse as `None` in any case.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final

__all__ = ["compact_date", "iso_date"]

_ISO: Final = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_COMPACT: Final = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def _build(matched: re.Match[str] | None) -> date | None:
    if matched is None:
        return None
    try:
        return date(int(matched[1]), int(matched[2]), int(matched[3]))
    except ValueError:
        return None


def iso_date(raw: str | None) -> date | None:
    """`'2026-07-27'`, and the slash spelling `'2007/11/23'`. `None` when unreadable."""
    if raw is None:
        return None
    return _build(_ISO.fullmatch(raw.strip().replace("/", "-")))


def compact_date(raw: str | None) -> date | None:
    """`'20271202'` → `2027-12-02`, the Formex attribute spelling. `None` when unreadable."""
    if raw is None:
        return None
    return _build(_COMPACT.fullmatch(raw.strip()))
