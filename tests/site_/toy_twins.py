"""A small twin map over the toy act and a sister copy of it, for the twin note's suites.

The toy transition changes `AR 2` (localised to the unit only), deletes `AR 3`, inserts `AR 4`
and changes `AN I` within `AN I SLOT 2`, all attributed to one toy amendment. The sister act is
the same entries under another key, so the record holds an event of it from the same instrument
whenever the entry handed in is attributed; an unattributed one gives the sister no such event.

The map is written as `emendrix twins build` would write one between the two, by hand only in
which units it pairs: the suites here test what the site says about a pair, not the pairing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from emendrix import DISCLAIMER
from emendrix.core import ActId
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.twin_inputs import TwinMaps
from emendrix.twins.model import (
    AlignedChild,
    TwinMap,
    TwinMethod,
    TwinPair,
    TwinSide,
)
from toy_corpus import HOUSE_RULES

__all__ = ["SISTER", "pair", "sister_of", "toy_map", "toy_site"]

REPORTS = Path(__file__).resolve().parents[2] / "reports" / "eval"
SISTER = ActId(corpus="toy", key="house-rules-sister")
"""Sorts after `house-rules`, so the toy act is side A of every map here."""


def pair(
    a: str,
    b: str,
    ratio: float = 0.95,
    *,
    identical: bool = False,
    children: tuple[tuple[str, str, float], ...] = (),
) -> TwinPair:
    return TwinPair(
        a=a,
        b=b,
        ratio=ratio,
        identical=identical,
        children=tuple(AlignedChild(a=x, b=y, ratio=r) for x, y, r in children),
        passages=(),
        passages_omitted=0,
        passages_withheld=False,
        headings_equal=True,
    )


def toy_map(*pairs: TwinPair, b: ActId = SISTER, version_b: str = "v2") -> TwinMap:
    return TwinMap(
        twins_schema="1.0",
        disclaimer=DISCLAIMER,
        method=TwinMethod(measure="word-ratio", floor=0.9, verified_on="2026-10-19"),
        a=TwinSide(corpus=HOUSE_RULES.corpus, key=HOUSE_RULES.key, version="v2"),
        b=TwinSide(corpus=b.corpus, key=b.key, version=version_b),
        pairs=pairs,
        unpaired_a=(),
        unpaired_b=(),
    )


def sister_of(entry: ChangelogEntry) -> ChangelogEntry:
    """The same entry recorded under the sister act."""
    return entry.model_copy(update={"act": SISTER})


def toy_site(*entries: ChangelogEntry, maps: TwinMaps) -> SiteInputs:
    return collect_site(
        generated_on=date(2026, 8, 9),
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=entries,
        twin_maps=maps,
    )
