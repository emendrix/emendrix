"""The batch: bounded, order-preserving, and survivable.

Changes are independent, so `explain_delta` runs them concurrently. Three properties are worth
a test each, because all three fail silently:

- the semaphore is honoured, or a 45-change delta opens 45 provider connections at once;
- order is preserved, or the right sentence lands under the wrong article;
- one failure does not sink the batch, or a single provider hiccup drops 44 good explanations.

Everything here runs on `FunctionModel`, driven through the exact code path a real provider
takes. No network, no key, no cassettes: `CassetteMode.LIVE` here means "call the model you
were handed", and the model handed over is a function in this file.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import AgentInfo, FunctionModel

from emendrix.core import (
    ActId,
    Change,
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionRef,
    ProvisionText,
    VersionId,
)
from emendrix.explain import (
    MODEL_FAILED,
    PROVIDER_UNAVAILABLE,
    CassetteMode,
    ExplainEngine,
    ExplainSettings,
    build_context,
    contexts_for_delta,
)

ACT = ActId(corpus="toy", key="house-rules")
V1, V2 = VersionId("v1"), VersionId("v2")

ANSWER: dict[str, object] = {"sentences": [{"text": "The wording changed.", "citations": ["k"]}]}


def change(number: int) -> Change:
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(
            act=ACT, version=V2, location=ProvisionLocation.parse(f"AR {number}")
        ),
        before=ProvisionText(f"old {number}"),
        after=ProvisionText(f"new {number}"),
    )


def delta(count: int) -> Delta:
    return Delta(
        act=ACT, from_version=V1, to_version=V2, changes=tuple(change(n) for n in range(count))
    )


def responder(body: Callable[[list[ModelMessage]], dict[str, object]]) -> FunctionModel:
    """A `FunctionModel` that answers the structured-output tool call `body` computes."""

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        assert info.output_tools, "the explain agent must ask for structured output"
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, body(messages))])

    return FunctionModel(call)


def engine(model: FunctionModel, *, max_concurrency: int = 4) -> ExplainEngine:
    return ExplainEngine(
        ExplainSettings(cassette_mode=CassetteMode.LIVE, max_concurrency=max_concurrency),
        model=model,
    )


def test_the_semaphore_is_honoured() -> None:
    """Ten changes, a limit of three: never more than three in flight."""
    in_flight = 0
    peak = 0

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, ANSWER)])

    run = asyncio.run(engine(FunctionModel(call), max_concurrency=3).explain_delta(delta(10)))
    assert peak == 3
    assert run.stats.explained == 10


def test_a_single_call_at_a_time_is_a_legal_setting() -> None:
    in_flight = 0
    peak = 0

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.005)
        in_flight -= 1
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, ANSWER)])

    asyncio.run(engine(FunctionModel(call), max_concurrency=1).explain_delta(delta(4)))
    assert peak == 1


def test_order_is_preserved_even_when_the_calls_finish_out_of_order() -> None:
    """The slowest change is first, so a batch that returned in completion order would fail."""

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = str(messages[-1])
        number = next(n for n in reversed(range(6)) if f"new {n}" in prompt)
        await asyncio.sleep(0.02 - 0.003 * number)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"sentences": [{"text": f"answer {number}", "citations": ["k"]}]},
                )
            ]
        )

    run = asyncio.run(engine(FunctionModel(call), max_concurrency=6).explain_delta(delta(6)))
    assert [result.provision.location.canonical for result in run.results] == [
        f"AR {n}" for n in range(6)
    ]
    texts = [result.explanation.sentences[0].text for result in run.results if result.explanation]
    assert texts == [f"answer {n}" for n in range(6)]


def test_one_failure_does_not_sink_the_batch() -> None:
    """The failed change ships an `ExplanationUnavailable` marker for the gate to handle.

    The reason is the curated `MODEL_FAILED` sentence, never the exception's own text: what the
    library called its failure is for the operator's log, and a reader-facing field carrying
    `RuntimeError: provider said no` would ship a crash message into a published document.
    """

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if "new 2" in str(messages[-1]):
            raise RuntimeError("provider said no")
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, ANSWER)])

    run = asyncio.run(engine(FunctionModel(call)).explain_delta(delta(5)))
    assert len(run.results) == 5
    assert run.stats.explained == 4
    assert run.stats.unavailable == 1
    assert run.stats.model_failed == 1
    failed = run.results[2]
    assert failed.explanation is None
    assert failed.unavailable is not None
    assert failed.unavailable.kind == "model_failed"
    assert failed.unavailable.reason == MODEL_FAILED
    assert "provider said no" not in failed.unavailable.reason
    assert "RuntimeError" not in failed.unavailable.reason
    assert not failed.ok


@pytest.mark.parametrize("status", [401, 402, 429, 500, 503])
def test_a_provider_that_never_answered_leaves_the_entry_unfinished(status: int) -> None:
    """Out of credit is not an answer about the change, so it must not settle it.

    The kind is what `OutputRepo.holds_finished` reads, and it is the whole reason this is a
    separate value rather than one more way to be `model_failed`: an installation whose balance
    ran out mid-backfill publishes the gap once and would otherwise skip past it for ever.
    """

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if "new 2" in str(messages[-1]):
            raise ModelHTTPError(status_code=status, model_name="m", body={"message": "no"})
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, ANSWER)])

    run = asyncio.run(engine(FunctionModel(call)).explain_delta(delta(5)))
    assert run.stats.explained == 4
    assert run.stats.provider_unavailable == 1
    assert run.stats.model_failed == 0
    failed = run.results[2]
    assert failed.unavailable is not None
    assert failed.unavailable.kind == "provider_unavailable"
    assert failed.unavailable.reason == PROVIDER_UNAVAILABLE
    assert str(status) not in failed.unavailable.reason


def test_an_unknown_http_status_settles_the_change_rather_than_re_running_for_ever() -> None:
    """Marking one unfinished wrongly costs a re-run on every backfill; the other way costs
    a thinner entry once. So an unrecognised status falls through to `model_failed`."""

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if "new 2" in str(messages[-1]):
            raise ModelHTTPError(status_code=418, model_name="m", body={"message": "no"})
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, ANSWER)])

    run = asyncio.run(engine(FunctionModel(call)).explain_delta(delta(5)))
    assert run.stats.model_failed == 1
    assert run.stats.provider_unavailable == 0
    assert run.results[2].unavailable is not None
    assert run.results[2].unavailable.kind == "model_failed"


def test_usage_is_accounted_per_call_and_summed_for_the_run() -> None:
    """Cost control is a stated goal, so spend is a number the run carries, not a log line."""
    run = asyncio.run(engine(responder(lambda _: ANSWER)).explain_delta(delta(3)))
    assert run.stats.changes == 3
    assert run.stats.usage.requests == 3
    assert run.stats.usage.input_tokens == sum(r.usage.input_tokens for r in run.results)
    assert run.stats.usage.output_tokens > 0
    assert run.stats.usage.schema_repairs == 0
    assert run.stats.usage.cost_usd(input_per_mtok=1.0, output_per_mtok=5.0) > 0


def test_everything_a_stub_produced_is_marked_synthetic() -> None:
    """A stub's output is a test of the machinery and never evidence about the pinned model."""
    run = asyncio.run(engine(responder(lambda _: ANSWER)).explain_delta(delta(2)))
    assert run.stats.synthetic == 2
    assert all(result.synthetic for result in run.results)
    assert run.stats.replayed == 0


def test_a_context_list_of_the_wrong_length_is_rejected_rather_than_silently_paired() -> None:
    """Zipping a short context list would attach the wrong citations to the wrong change."""
    computed = delta(3)
    short = contexts_for_delta(computed)[:2]
    with pytest.raises(ValueError, match="3 changes but 2 contexts"):
        asyncio.run(engine(responder(lambda _: ANSWER)).explain_delta(computed, short))


def test_revise_sends_the_gates_complaint_and_keeps_the_original_prompt() -> None:
    """The gate's one retry: same change, same keys, plus the specific failure."""
    seen: list[str] = []

    def body(messages: list[ModelMessage]) -> dict[str, object]:
        seen.append(str(messages[-1]))
        return ANSWER

    computed = delta(1)
    one = engine(responder(body))
    context = build_context(
        computed.changes[0], from_version=computed.from_version, to_version=computed.to_version
    )
    first = asyncio.run(one.explain_change(computed.changes[0], context))
    assert first.explanation is not None
    asyncio.run(one.revise(computed.changes[0], context, first.explanation, "cited AR 9@v2"))
    assert len(seen) == 2
    assert "REJECTED BY THE CITATION GATE" not in seen[0]
    assert "REJECTED BY THE CITATION GATE" in seen[1]
    assert "cited AR 9@v2" in seen[1]
    assert "AR 0@v2" in seen[1], "the offered keys must still be in front of the model"
