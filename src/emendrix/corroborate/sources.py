"""Where the two non-diff signals come from, expressed without naming a corpus.

`corroborate()` takes two `SignalReport`s and has no idea how they were obtained. That is
correct, and it leaves an orchestrator holding a question the seam deliberately does not answer:
*for this act, between these two versions, what do the other signals say?*

`SignalSource` is that question as a Protocol. It is **not** part of `CorpusAdapter` and it
never will be: modification metadata and amending-act instructions are capabilities of the EU
adapter (`eu/signals.py`), not obligations of every corpus. A corpus with neither satisfies
this by answering with two empty slots, and two empty slots mean `UNAVAILABLE`, which is
silence and not dissent.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from emendrix.core import ActId, SignalReport, VersionId

__all__ = ["SignalSource", "TransitionSignals"]


class TransitionSignals(BaseModel):
    """What the non-diff signals say about one version pair. `None` means "this corpus cannot"."""

    model_config = ConfigDict(frozen=True)

    metadata: SignalReport | None = None
    instructions: SignalReport | None = None


class SignalSource(Protocol):
    """The two second opinions for one transition, however the corpus happens to hold them."""

    def signals_for(
        self, act: ActId, from_version: VersionId, to_version: VersionId
    ) -> TransitionSignals: ...
