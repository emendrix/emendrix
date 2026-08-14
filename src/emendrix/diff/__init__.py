"""The structural diff: two provision trees in, one typed `core.Delta` out.

The DELTA stage of WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT, and the primary
shipped signal: it is the only one of the three that carries the actual text, so the verbatim
before/after quotes everything downstream uses come from here.

Deterministic Python throughout: no model, no network, no clock, no dependency on anything
EU-specific. `compute_delta` runs unchanged on the toy corpus in `tests/toy_corpus.py`, which
is what keeps the corpus seam honest.
"""

from __future__ import annotations

from emendrix.diff.api import STRUCTURAL_ONLY, compute_delta
from emendrix.diff.deferred import DateVerdict, read_dates
from emendrix.diff.sub_localise import changed_sublocations, residual_text
from emendrix.diff.tree_diff import (
    RENUMBER_CANDIDATE_CAP,
    RENUMBER_MIN_LENGTH,
    RENUMBER_PREFIX_LIMIT,
    RENUMBER_SIMILARITY,
    UnitDiff,
    UnitMatch,
    diff_units,
)

__all__ = [
    "RENUMBER_CANDIDATE_CAP",
    "RENUMBER_MIN_LENGTH",
    "RENUMBER_PREFIX_LIMIT",
    "RENUMBER_SIMILARITY",
    "STRUCTURAL_ONLY",
    "DateVerdict",
    "UnitDiff",
    "UnitMatch",
    "changed_sublocations",
    "compute_delta",
    "diff_units",
    "read_dates",
    "residual_text",
]
