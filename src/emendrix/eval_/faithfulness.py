"""The faithfulness judge: the second, and last, place a model appears in this repository.

`pydantic_ai` may be imported here and under `src/emendrix/explain/` and nowhere else, which is
grep-enforced by `tests/test_architecture.py`. The exception exists because the fourth row of the
rigour table (`prose.py`) has no free ground truth: whether a shipped sentence is a faithful
account of the difference between two texts is a judgement, and this project's answer is a
sampled judgement by a *different* model plus a human spot review the author does by hand. Both
are reported as the weak signal they are, apart from citation grounding, which is deterministic
and means something else entirely.

## Independence, and its limits, stated rather than implied

The judge must not be the explainer: a model marking its own homework is not evidence about
itself. So the default judge is `openrouter:openai/gpt-5.6-sol` against the explainer's
`openrouter:anthropic/claude-sonnet-5`: a stronger model, a different one, and since 2026-08-08 a
different vendor. A cross-vendor pair is the strongest form of this claim the project has and it
still does not make the number independent: both models are trained on overlapping public text and
both are being asked to read English, so a shared misreading remains available to them. It is a
weak signal, and the human worksheet (`worksheet.py`) is the only genuinely independent check this
layer has.

Confirmed against OpenRouter's own `/api/v1/models` on **2026-08-08**: `openai/gpt-5.6-sol` is
listed and active (canonical slug `openai/gpt-5.6-sol-20260709`), 1 050 000-token context,
**$5.00 in / $30.00 out** per 1M tokens (priced in `explain/settings.py` beside the explainer's
rate), and it advertises `structured_outputs`, which is what lets `Verdict` be the interface. It
does *not* advertise `temperature`, so this module sets none: pinning a sampling parameter the
provider does not accept is how a recording run dies twenty calls in. The explainer sets none for
the same reason (`explain/settings.py`).

Recording is the only thing here that reaches a provider. `emendrix eval run` replays committed
judgements through `judgements.replay`, which imports none of this.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Final

from pydantic_ai import Agent
from pydantic_ai.models import Model

from emendrix.eval_.judge import (
    FaithfulnessReport,
    Judgement,
    Triple,
    Verdict,
    judge_model,
    prompt_for,
)
from emendrix.eval_.judgements import (
    JudgeCassette,
    JudgeCassetteStore,
    judgement_key,
    rubric_digest,
)
from emendrix.eval_.rubric import JUDGE_RUBRIC
from emendrix.explain import CallUsage

__all__ = ["build_agent", "judge_prompts", "record"]

_MAX_CONCURRENCY: Final = 4
"""Judgements in flight at once. They are independent, and twenty is not a load test."""


def build_agent(
    model_id: str, model: Model | None = None, rubric: str = JUDGE_RUBRIC
) -> Agent[None, Verdict]:
    """The judge agent: one bounded call, structured output, no tools and no memory.

    `model` overrides the provider — the seam the recorder uses to push a stub through the
    identical code path when no API key is present.

    `rubric` is a parameter rather than the constant so that a recording can name the
    instruction it ran under. The default is the rubric in git, which is what every shipped
    number is measured with; an older one is passed in only to hold the instruction fixed while
    the model changes, and the digest of whichever text was used rides into every cassette.
    """
    return Agent(
        model=model if model is not None else model_id,
        output_type=Verdict,
        instructions=rubric,
    )


async def _one(agent: Agent[None, Verdict], prompt: str) -> tuple[Verdict, CallUsage]:
    result = await agent.run(prompt)
    usage = result.usage
    return result.output, CallUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        requests=usage.requests,
        # Anything past the first request in a toolless, single-turn run is pydantic-ai handing
        # back a malformed structured output for repair, exactly as the explain stage counts it.
        schema_repairs=max(usage.requests - 1, 0),
    )


async def judge_prompts(
    prompts: Sequence[str],
    *,
    model_id: str,
    store: JudgeCassetteStore,
    model: Model | None = None,
    synthetic: bool = False,
    rubric: str = JUDGE_RUBRIC,
) -> tuple[tuple[Verdict, ...], CallUsage]:
    """Ask the judge every prompt and commit the exchanges. The one path that spends money.

    Prompts rather than triples, because a prompt is what a judgement is *about*: the twenty
    committed judgements a person also read are strings on disk, and asking a second judge the
    same questions means handing it those strings rather than rebuilding them from a sample that
    has since moved on.

    The returned `CallUsage` is what the run cost in tokens, so a recorder can price it against
    the rate `explain/settings.py` publishes instead of guessing.
    """
    agent = build_agent(model_id, model, rubric)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    digest = rubric_digest(rubric)

    async def bounded(prompt: str) -> tuple[Verdict, CallUsage]:
        async with semaphore:
            return await _one(agent, prompt)

    answered = await asyncio.gather(*(bounded(prompt) for prompt in prompts))
    total = CallUsage()
    for prompt, (verdict, usage) in zip(prompts, answered, strict=True):
        total = total.plus(usage)
        store.save(
            JudgeCassette(
                judge_model=model_id,
                key=judgement_key(model_id, prompt, rubric_sha=digest),
                synthetic=synthetic,
                recorded_with=type(model).__name__ if model is not None else model_id,
                prompt=prompt,
                rubric_sha=digest,
                output=verdict,
            )
        )
    return tuple(verdict for verdict, _ in answered), total


async def record(
    triples: Sequence[Triple],
    *,
    model_id: str | None = None,
    store: JudgeCassetteStore | None = None,
    model: Model | None = None,
    synthetic: bool | None = None,
    worksheet: str = "",
    rubric: str = JUDGE_RUBRIC,
) -> FaithfulnessReport:
    """Judge every sampled triple and commit the exchanges.

    Deliberately not wired into `emendrix eval run`: judgements are recorded once, by a person,
    and replayed from then on. `synthetic` follows the recording into every cassette and into
    the report, where it withholds the rate — a stub's verdict is a test of this function and
    nothing at all about faithfulness.
    """
    resolved = model_id if model_id is not None else judge_model()
    cassettes = store if store is not None else JudgeCassetteStore()
    is_synthetic = (model is not None) if synthetic is None else synthetic
    verdicts, _ = await judge_prompts(
        [prompt_for(triple) for triple in triples],
        model_id=resolved,
        store=cassettes,
        model=model,
        synthetic=is_synthetic,
        rubric=rubric,
    )
    judgements: list[Judgement] = []
    for triple, verdict in zip(triples, verdicts, strict=True):
        judgements.append(
            Judgement(
                case_id=triple.case_id,
                unit=triple.unit,
                outcome=triple.outcome,
                fallback=triple.fallback,
                verdict=verdict,
                synthetic=is_synthetic,
                judge_model=resolved,
            )
        )
    return FaithfulnessReport(
        judge_model=resolved,
        sampled=len(triples),
        judged=len(judgements),
        faithful=sum(
            1 for item in judgements if item.verdict is not None and item.verdict.faithful
        ),
        synthetic=sum(1 for item in judgements if item.synthetic),
        fallback_triples=sum(1 for triple in triples if triple.fallback),
        worksheet=worksheet,
        judgements=tuple(judgements),
    )
