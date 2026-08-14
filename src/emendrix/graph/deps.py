"""What the graph needs from the outside world, as four narrow seams and one date.

Deliberately *not* in the graph state: an HTTP client, a model engine and a poller are not
serialisable and have no business in a checkpoint. They are captured by the node closures
instead, so the state stays a plain document and a resumed run picks up the same dependencies
the process was started with.

Every field is either the `CorpusAdapter` Protocol or a Protocol declared here, so this package
never learns whose corpus it is orchestrating: the EU wiring lives in `emendrix.session`, the
composition root outside this package, and `graph/cli.py` is the only module here allowed to
name it. `tests/test_architecture.py` fails the build if it leaks anywhere else.
That is what lets the whole loop run over `tests/toy_corpus.py`, which is not law at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from emendrix.core import CorpusAdapter
from emendrix.corroborate.sources import SignalSource
from emendrix.explain import ExplainEngine
from emendrix.watch.events import PollResult, PollWindow

__all__ = ["PipelineDeps", "WatchSource"]


class WatchSource(Protocol):
    """One poll of whatever announces change, already deduplicated and persisted.

    The window is passed in, never asked for: the WATCH stage of this loop reads no clock
    (`watch/poll.py`), and the graph reads none either.
    """

    def poll(self, window: PollWindow) -> PollResult: ...


@dataclass(frozen=True)
class PipelineDeps:
    """The composition root's answer to "who supplies each stage?".

    `signals` and `watcher` are optional because both are capabilities rather than obligations:
    a corpus with no modification metadata corroborates against silence, and the manual
    `emendrix explain <act> <a> <b>` path has no feed to poll at all.
    """

    adapter: CorpusAdapter
    engine: ExplainEngine
    observed_on: date
    signals: SignalSource | None = None
    watcher: WatchSource | None = None
