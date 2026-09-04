"""What the EU tests are pinned to: the fixture directory, the acts, the observation date.

Kept out of `conftest.py` so it imports by name (like `toy_corpus`), and in one place so a
re-pin of the fixtures (`uv run python -m emendrix.eu.fetch_fixtures`) has one thing to move.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from emendrix.core import VersionId
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex
from emendrix.eu.packages import FormexPackage

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "eu"

OBSERVED_ON = date(2026, 8, 6)
"""Passed in, never read from a clock: it is what the first-class states are stamped with."""

AI_ACT = "32024R1689"
AI_ACT_V1 = "02024R1689-20240712"
"""Exists in eleven languages, English not among them (verified 2026-08-05): the version that
drives the mandatory fallback chain, consolidated ENG to original OJ act ENG."""
AI_ACT_V2 = "02024R1689-20260727"
DIGITAL_OMNIBUS = "32026R1744"
MDR = "32017R0745"
MDR_POSTPONEMENT = "32020R0561"
"""The amending act of the MDR pair below. It names the MDR only in its own lead-in clause."""
MDR_ANNEX_AMENDER = "32025R2457"
"""Amends MDR Annex I through an article lead-in that names the annex once, with the list items
drafted relative to it: the scope the instruction parser must carry down (read 2026-08-11)."""
MDR_2023_AMENDER = "32023R0502"
"""The MDR's 2023 amender. One instruction article, stated in prose with no `LIST`."""
REACH = "32006R1907"
REACH_2008_AMENDER = "32008R0987"
"""REACH's 2007→2008 amender. Both of its instruction articles are prose, with no `LIST`."""
CLP = "32008R1272"
"""REACH's 2008→2009 amender. Its own Formex is 3.3 MB and is deliberately not pinned."""

MDR_V1 = "02017R0745-20170505"
MDR_V2 = "02017R0745-20200424"
REACH_2008 = "02006R1907-20081012"
REACH_2009 = "02006R1907-20090120"
"""The pair that measures whitespace-correct extraction: a naive one reports all 143 units
modified where a correct one finds 40, which is why a verbatim and a comparison text are both
stored."""

DSA = "32022R2065"
"""On the shipped example watchlist. Its notices are pinned and its Formex text is not: the act
the corpus annotates nowhere is what a metadata signal with no reference set is tested against,
and no consolidation of it is scored."""

FEED_WINDOW = (datetime(2026, 8, 5, 10, 0), datetime(2026, 8, 5, 10, 5))
"""Five pinned minutes of the ingestion feed. 46 entries, 4 of them the AI Act's
Digital Omnibus consolidation (`emendrix.eu.fetch_fixtures.FEED_PINNED`)."""

EMPTY_FEED_WINDOW = (datetime(2026, 8, 2, 0, 0), datetime(2026, 8, 2, 0, 5))
"""A window the corpus genuinely has nothing in: the "no hits" path, from real bytes."""

FEED_ENTRIES = 46
FEED_AI_ACT_ENTRIES = 4
"""Measured 2026-08-06 off the pinned window. Both are asserted, not assumed."""


def package(client: CellarClient, celex: str, version: str) -> FormexPackage:
    """The pinned Formex package of one version, through the real fetch path.

    The parser tests go through `CellarClient` rather than reading the zip off disk, so what
    they parse is exactly what the adapter hands the parser in production: provenance,
    fallback marking and all.
    """
    fetched = client.fetch_formex(Celex.parse(celex), VersionId(version))
    assert isinstance(fetched, FormexPackage), f"{celex} {version} answered {fetched!r}"
    return fetched
