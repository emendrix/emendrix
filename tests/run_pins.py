"""What the offline `emendrix explain` test is pinned to. One place, so a re-pin moves once.

The recorder (`tests/graph/test_record_run_cassettes.py`) and the replay
(`tests/graph/test_run_cli.py`) must agree byte for byte on which transition is being asked
about, or the cassette keys diverge and every replay misses. So both import the pins from here
rather than repeating a CELEX, and so does `tests/output/`, whose golden changelog is this
same transition rendered by the whole shipped command, which is why this file sits beside
`eu_pins.py` at the top of `tests/` rather than inside one suite.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from emendrix.core import ActId, VersionId
from emendrix.eu.identifiers import Celex, act_id
from emendrix.watch.events import AmendmentEvent
from eu_pins import FIXTURE_DIR, MDR, MDR_V1, MDR_V2, OBSERVED_ON

RUN_CASSETTE_DIR = FIXTURE_DIR.parents[1] / "cassettes-run"
"""Kept apart from `tests/cassettes/` so the four pinned prompt-shape exchanges stay
readable as a set of four. Same format, same store, different purpose."""


class Transition(BaseModel):
    """One act, two versions, and what the pipeline is known to produce for the pair."""

    model_config = ConfigDict(frozen=True)

    celex: str
    from_version: str
    to_version: str
    changes: int
    observed_on: date

    @property
    def act(self) -> ActId:
        return act_id(Celex.parse(self.celex))


TRANSITION = Transition(
    celex=MDR,
    from_version=MDR_V1,
    to_version=MDR_V2,
    changes=9,
    observed_on=OBSERVED_ON,
)
"""The MDR postponement: 0 inserted · 3 modified · 0 deleted · 6 deferred = 9 touched units,
asserted independently in `tests/diff/test_cli.py`. The smallest real transition pinned."""

RETRY_RECORDING = Transition(
    celex=MDR,
    from_version="02017R0745-20230311",
    to_version="02017R0745-20230320",
    changes=3,
    observed_on=date(2026, 8, 11),
)
"""Three exchanges recorded 2026-08-11, when a backfill failure on Art. 123 (pydantic-ai's
output retries exhausted) did not reproduce: all three changes passed the gate first time,
with Art. 120 needing one schema repair. A failure that does not reproduce is a rate the
first-class unavailable state absorbs, not a bug. The exchanges stay committed and are counted
by the store guard in `tests/graph/test_run_cli.py`; nothing replays them offline, because the
two versions are deliberately not pinned as fixtures."""


def manual_event() -> AmendmentEvent:
    """The event `emendrix explain` synthesises, rebuilt here so the recorder sees the same one."""
    return AmendmentEvent(
        act=TRANSITION.act,
        target_version=VersionId(TRANSITION.to_version),
        new_version=VersionId(TRANSITION.to_version),
        previous_version=VersionId(TRANSITION.from_version),
        trigger="manual: emendrix explain",
        observed_on=TRANSITION.observed_on,
    )
