"""Running the planned transitions, one at a time, with a value for every outcome.

Generic on purpose: this module takes `PipelineDeps` and core types and knows nothing about the
EU, so the loop is exercised over a corpus that is not law. Which acts a run covers, where the
adapter comes from and where the changelog lands belong to whatever command drives it.

**One transition at a time, and no concurrency.** The fetch path shares one disk cache and one
connection pool, the explain stage already parallelises across the changes inside a single
transition, and a second concurrency model for one effect is one too many. A backfill is a
background job whose wall-clock time nobody is waiting on.

**A failure is a value, and the run continues.** Every other stage in this project turns a state
the corpus reported into a value rather than an exception, and the same discipline has to hold
for the thing a batch job actually meets: a socket that closed, a provider that refused, a
document that parsed into nothing. Three hundred transitions must not end because one of them
had a bad afternoon, so the broad catch below is deliberate and the detail it records is what
the ledger and the summary print. It is the boundary of the loop, and nothing below it catches
this widely.

**An interruption is not a failure and is not caught.** `KeyboardInterrupt` and `SystemExit`
derive from `BaseException`, so `except Exception` lets them through, which is the intended
behaviour and not an accident of the hierarchy: Ctrl-C is an operator saying stop, and recording
it as three hundred failed transitions would be the opposite of obeying it. The command that
drives this loop catches the interruption once, prints the totals it had earned, and leaves the
in-flight transition unrecorded so the next run tries it again.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict

from emendrix.backfill.ledger import Attempt, AttemptStatus
from emendrix.backfill.plan import Transition
from emendrix.graph import PipelineDeps, PipelineState, RunReport
from emendrix.session import execute, manual_event

__all__ = ["TRIGGER", "Outcome", "run_transitions"]

TRIGGER: Final = "manual: emendrix backfill"
"""What the event says about where it came from, so a backfilled entry never reads as a poll's."""


class Outcome(BaseModel):
    """What became of one transition, and the report if it produced one."""

    model_config = ConfigDict(frozen=True)

    transition: Transition
    status: AttemptStatus
    detail: str = ""
    report: RunReport | None = None

    @property
    def attempt(self) -> Attempt:
        """The ledger row for this outcome."""
        return Attempt(
            key=self.transition.key,
            act=str(self.transition.act),
            from_version=str(self.transition.from_version),
            to_version=str(self.transition.to_version),
            status=self.status,
            detail=self.detail,
        )


def run_transitions(
    deps: PipelineDeps, transitions: Sequence[Transition], *, observed_on: date
) -> Iterator[Outcome]:
    """One outcome per transition, in the order given, as each one finishes.

    A generator rather than a list: the caller writes the ledger and the changelog after each
    outcome, so a run killed halfway keeps everything it had already earned.
    """
    for transition in transitions:
        yield _one(deps, transition, observed_on)


def _one(deps: PipelineDeps, transition: Transition, observed_on: date) -> Outcome:
    """One transition through the same graph a poll drives, with its answer as a value."""
    state = PipelineState(
        observed_on=observed_on,
        events=(
            manual_event(
                transition.act,
                str(transition.from_version),
                str(transition.to_version),
                observed_on,
                trigger=TRIGGER,
            ),
        ),
    )
    try:
        report = execute(deps, state, watch=False)
    except Exception as error:  # the boundary of a batch job: see the module docstring
        return Outcome(
            transition=transition, status="failed", detail=f"{type(error).__name__}: {error}"
        )
    if report.deltas:
        return Outcome(transition=transition, status="emitted", report=report)
    return Outcome(transition=transition, status="skipped", detail=_why(report), report=report)


def _why(report: RunReport) -> str:
    """The loop's own reason for producing no delta, or the honest absence of one."""
    reasons = "; ".join(item.reason for item in report.skipped if item.reason)
    return reasons or "the loop produced no delta and gave no reason"
