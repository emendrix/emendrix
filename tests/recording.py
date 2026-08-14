"""Shared by the two cassette recorders: whether a real recording is possible at all.

Both recorders run the same command with or without a key, and the difference is the
environment rather than a flag; `tests/explain/test_record_cassettes.py` gives the reason. What
is *not* obvious is which key: the pinned model is reached through OpenRouter, so it is
`OPENROUTER_API_KEY`, and a recorder pointed at another provider changes the answer. So no
recorder names a variable; each asks `emendrix.explain.api_key_env` what the model it is about
to record would need, and stubs the model when that variable is absent.

**Every caller passes its own settings.** The question has to be about the model actually being
recorded: `ExplainSettings` reads no environment by construction, so a recorder building its
settings directly records under `DEFAULT_MODEL` whatever the shell says, and asking
`from_env()` instead would ask about a model nothing was recorded against. That mismatch is
silent, because both answers are usually `OPENROUTER_API_KEY`, and it stops being silent
exactly when a reviewer points one of the two at a different vendor.
"""

from __future__ import annotations

import os

from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel

from emendrix.explain import ExplainSettings, api_key_env

__all__ = ["stub_when_unkeyed"]


def stub_when_unkeyed(settings: ExplainSettings) -> tuple[Model | None, bool]:
    """`(model override, synthetic)`. A key means the pinned model; no key means a stub.

    `settings` is the recorder's own, not `from_env()`: the answer must be about the model whose
    id will be written into the cassettes. `None` as the override means "use whatever the
    settings say", which is the real provider. The second element rides all the way into
    `RunStats.synthetic`, so a published number can never quietly mix a stub's output with a
    model's.
    """
    needed = api_key_env(settings.model_id)
    if needed is not None and os.environ.get(needed):
        return None, False
    return TestModel(), True
