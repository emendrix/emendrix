"""Stub models for the graph tests: canned explanations, driven through the real engine.

Nothing here fakes `ExplainEngine`. Every stub is a pydantic-ai `FunctionModel` handed to the
real engine in `CassetteMode.LIVE`, so the graph exercises the actual explain code path
(prompt construction, the semaphore, usage accounting, `ExplainedChange` assembly, the
`revise` call) with the provider replaced by a function in this file. A hand-rolled fake
engine would test the fake.

What the stubs decide is only *what the model says*, which is precisely the thing the graph is
not allowed to depend on. `citing_offered` copies a key back out of the prompt (the grounded
case); `citing_nothing_real` invents one (the rejected case); `citing_badly_then_well` does the
first on its second call, which is how the gate→explain cycle gets exercised end to end.

The sentences are placeholders, not plausible legal prose. These tests assert routing, counting
and grounding, never explanation quality, which no stub can be evidence about.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from emendrix.explain import CassetteMode, ExplainEngine, ExplainSettings

__all__ = [
    "INVENTED_KEY",
    "citing_badly_then_well",
    "citing_nothing_real",
    "citing_offered",
    "engine",
    "offered_keys",
    "prompt_of",
    "revision_count",
]

INVENTED_KEY = "AR 9999@nowhere"
"""A key no context can ever offer, so a sentence citing it fails containment by construction."""

_OFFERED = re.compile(r"^ {2}(.+?)\s+= ", re.MULTILINE)

Answer = Callable[[list[ModelMessage]], dict[str, object]]


def prompt_of(messages: list[ModelMessage]) -> str:
    """The user prompt as the model actually received it.

    Read off the parts rather than `str(message)`: the repr escapes newlines, so a regex over
    it silently matches nothing, which looks exactly like a model that answered badly.
    """
    return "\n".join(
        str(part.content)
        for message in messages
        for part in message.parts
        if isinstance(part, UserPromptPart)
    )


def offered_keys(prompt: str) -> list[str]:
    """The keys the prompt offered, parsed back out of `explain/prompt.py`'s own block.

    Deliberately re-derived from the prompt instead of taken from the `ExplainContext`: a stub
    that read the context could cite a key the model was never shown, and the whole point of
    the gate is that those two sets are the same one.
    """
    return _OFFERED.findall(prompt)


def sentences(*texts_and_keys: tuple[str, str]) -> dict[str, object]:
    return {"sentences": [{"text": text, "citations": [key]} for text, key in texts_and_keys]}


def _model(answer: Answer) -> FunctionModel:
    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        assert info.output_tools, "the explain agent must ask for structured output"
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, answer(messages))])

    return FunctionModel(call)


def citing_offered(text: str = "The wording changed.") -> FunctionModel:
    """Cites the first key it was offered, so the gate passes it without a revision."""

    def answer(messages: list[ModelMessage]) -> dict[str, object]:
        return sentences((text, offered_keys(prompt_of(messages))[0]))

    return _model(answer)


def citing_nothing_real() -> FunctionModel:
    """Cites a key nobody offered, twice. Fails the gate, fails the revision, falls back."""
    return _model(lambda _: sentences(("A confident sentence about nothing.", INVENTED_KEY)))


def citing_badly_then_well() -> FunctionModel:
    """Invents a key first and copies a real one when told off. Passes on retry.

    The revision is recognised by the complaint `explain/prompt.py` appends, which is the same
    string a real retry carries, so this stub cannot accidentally "fix itself" on a first call.
    """

    def answer(messages: list[ModelMessage]) -> dict[str, object]:
        prompt = prompt_of(messages)
        if "REJECTED BY THE CITATION GATE" not in prompt:
            return sentences(("A confident sentence about nothing.", INVENTED_KEY))
        return sentences(("Corrected on the second attempt.", offered_keys(prompt)[0]))

    return _model(answer)


def revision_count(prompts: list[str]) -> int:
    """How many of the recorded prompts were revisions rather than first attempts."""
    return sum(1 for prompt in prompts if "REJECTED BY THE CITATION GATE" in prompt)


def recording(inner: FunctionModel, prompts: list[str]) -> FunctionModel:
    """`inner`, with every prompt it is shown appended to `prompts`. For counting calls."""

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompts.append(prompt_of(messages))
        return await inner.request(messages, info.model_settings, info.model_request_parameters)

    return FunctionModel(call)


def engine(model: FunctionModel, *, max_concurrency: int = 4) -> ExplainEngine:
    """The real engine, with the provider replaced. `LIVE` here means "call what you were given"."""
    return ExplainEngine(
        ExplainSettings(cassette_mode=CassetteMode.LIVE, max_concurrency=max_concurrency),
        model=model,
    )
