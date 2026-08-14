"""Recording a second judge's answers to the twenty prompts a person also read.

    # against the configured judge: costs money, needs a key, hits the network
    OPENROUTER_API_KEY=sk-or-v1-... uv run pytest -m "record and live" -k judge_benchmark tests/eval

    # offline, deterministic, produces cassettes marked `synthetic: true`
    uv run pytest -m "record and live" -k judge_benchmark tests/eval

Same command either way, like the other recorders: the difference is the environment rather than
a flag, and every cassette says what produced it.

**The prompts come off disk, not out of a sample.** The twenty entries a reviewer worked through
on 2026-08-08 are strings in `tests/cassettes-judge/`, and they are the only prompts on which a
human verdict exists. The current faithfulness sample is a different twenty strings about
different prose, so rebuilding the sample would ask a new judge questions nobody has labelled.
That is also why this writes into `tests/cassettes-judge-benchmark/`: the other directory holds
exactly the current sample, and a test asserts it.

A judgement is keyed on the rubric as well as the prompt, so editing the rubric and re-running
this writes a **second** answer to each question beside the first rather than replacing it. The
answers to the rubric nobody chose are deleted by hand, and scoring refuses a set that holds two
answers to one prompt rather than picking between them.

**What the default run measures is the pair**, this judge under the rubric in git against the
judge that produced the labels under the rubric of that day. To isolate the model instead, take
the rubric as it was from git history, put it in a file outside the repository and pass its text
as `rubric=` below. The repository deliberately keeps one copy of the rubric: two would be two
instructions a reader has to tell apart, and the older one is a revision away in any case.
"""

from __future__ import annotations

import asyncio

import pytest

from emendrix.eval_.benchmark import (
    BENCHMARK_CASSETTE_DIR,
    LABELLED_JUDGE_MODEL,
    load_recorded,
)
from emendrix.eval_.faithfulness import judge_prompts
from emendrix.eval_.judge import SAMPLE_SIZE, judge_model
from emendrix.eval_.judgements import JUDGE_CASSETTE_DIR, JudgeCassetteStore
from emendrix.explain import ExplainSettings, rate_for
from recording import stub_when_unkeyed


@pytest.mark.record
@pytest.mark.live
def test_record_the_judge_benchmark() -> None:
    """Ask the configured judge every labelled prompt and commit its answers."""
    labelled = load_recorded(JUDGE_CASSETTE_DIR, LABELLED_JUDGE_MODEL)
    prompts = [cassette.prompt for cassette in labelled]
    assert len(prompts) == SAMPLE_SIZE, (
        f"the labelled set is {SAMPLE_SIZE} prompts; found {len(prompts)}. These are the only "
        f"judgements that exist on prose a person also read and they are not reproducible."
    )

    challenger = judge_model()
    model, synthetic = stub_when_unkeyed(ExplainSettings(model_id=challenger))
    verdicts, usage = asyncio.run(
        judge_prompts(
            prompts,
            model_id=challenger,
            store=JudgeCassetteStore(BENCHMARK_CASSETTE_DIR),
            model=model,
            synthetic=synthetic,
        )
    )

    assert len(verdicts) == len(prompts)
    rate = rate_for(challenger)
    spent = (
        None
        if rate is None
        else usage.cost_usd(
            input_per_mtok=rate.input_per_mtok, output_per_mtok=rate.output_per_mtok
        )
    )
    cost = "unpriced" if spent is None else f"${spent:.4f}"
    print(
        f"\n{challenger}: {len(verdicts)} judgements, "
        f"{usage.input_tokens} in / {usage.output_tokens} out tokens, {cost}"
        f"{' (synthetic)' if synthetic else ''}"
    )
