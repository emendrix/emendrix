"""`emendrix.backfill`: the loop, run over an act's history instead of over a poll window.

The watcher answers "what changed since the last time I looked?". Backfill answers "what has
changed over this act's whole published history?", which is the question a new installation
asks once and never again. It is the same graph, the same output repository and the same
first-class states; only the source of the events differs.

Layout:

```
plan     which pairs of versions a run covers. Pure, and generic over any corpus.
ledger   which pairs already produced an answer, so an interrupted run resumes.
runner   the loop itself: transitions in, one outcome per transition out.
render   the selection table an operator decides from, before anything is spent.
cli      `emendrix backfill`: the EU composition root, the lock and the progress lines.
```
"""

from emendrix.backfill.ledger import (
    DEFAULT_LEDGER,
    DEFAULT_RETRY_LIMIT,
    Attempt,
    Ledger,
    LedgerBusy,
    LedgerLoad,
    ledger_lock,
    load_ledger,
    save_ledger,
)
from emendrix.backfill.plan import DEFAULT_LANGUAGE, Transition, TransitionPlan, plan_transitions
from emendrix.backfill.render import report_plans
from emendrix.backfill.runner import TRIGGER, Outcome, run_transitions

__all__ = [
    "DEFAULT_LANGUAGE",
    "DEFAULT_LEDGER",
    "DEFAULT_RETRY_LIMIT",
    "TRIGGER",
    "Attempt",
    "Ledger",
    "LedgerBusy",
    "LedgerLoad",
    "Outcome",
    "Transition",
    "TransitionPlan",
    "ledger_lock",
    "load_ledger",
    "plan_transitions",
    "report_plans",
    "run_transitions",
    "save_ledger",
]
