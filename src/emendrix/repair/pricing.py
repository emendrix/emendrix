"""What a repair would address and what it would cost, computed before anything is spent.

Split from `explanations.py` along the line the command itself draws: `--dry-run` selects,
rebuilds the prompts, prices them and stops, and it must be able to do all of that with no
engine, no API key and no provider client anywhere in the process. Everything on this side of
the line is a pure function of the committed entries and the explain settings; everything on
the other side awaits a model. Keeping the two in one module would put the paid half one import
away from the mode whose whole promise is that it cannot spend.

The estimate is a **floor**, and deliberately so: one call per change at the size of the prompt
this repair rebuilds, which counts neither the gate's single retry nor a schema repair, each of
which is a further request against the same provider. An operator shown a floor who then pays
more can read the difference off what the pass recorded on the entries it wrote; a figure padded
to feel safe would say nothing about either number.

Core types, the committed document and the explain settings. No corpus, no clock, no network.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import VersionId
from emendrix.explain import CallUsage, ExplainSettings, build_context, build_prompt, rate_for
from emendrix.repair.entry import RepairTarget
from emendrix.repair.explanations import selected

__all__ = [
    "CHARS_PER_INPUT_TOKEN",
    "OUTPUT_TOKENS_PER_CHANGE",
    "Estimate",
    "Selection",
    "estimate_over",
    "plan",
    "selection_of",
]

CHARS_PER_INPUT_TOKEN: Final = 2.25
"""Prompt characters per input token, for an estimate made before any call.

Measured 2026-09-04 over the 71 committed exchanges recorded against a real model: 1 052 838
characters of system and user message against the 468 485 input tokens the provider billed.
"""

OUTPUT_TOKENS_PER_CHANGE: Final = 351
"""Output tokens one explanation costs, the mean of those same 71 exchanges.

The median is 336 and the longest is 1 121. An estimate needs one number per change, and the
mean is the one that sums to the right total over a batch.
"""


class Selection(BaseModel):
    """What a repair would address in one entry, and the prompt it would send for it.

    `prompt_chars` is both messages of every change selected, which is what the estimate is
    computed over and what a measured cost can be checked against once a pass has run.
    """

    model_config = ConfigDict(frozen=True)

    act: str = Field(min_length=1)
    from_version: VersionId
    to_version: VersionId
    units: tuple[str, ...] = Field(description="The changes this pass would ask about, in order.")
    prompt_chars: int = Field(default=0, ge=0)


class Estimate(BaseModel):
    """What a pass would cost before it runs, at the rate this repository has on file."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    entries: int = Field(default=0, ge=0)
    changes: int = Field(default=0, ge=0)
    prompt_chars: int = Field(default=0, ge=0)
    usage: CallUsage = CallUsage()
    cost_usd: float | None = Field(
        default=None, ge=0.0, description="None where this repository has no rate on file."
    )


def selection_of(
    target: RepairTarget, settings: ExplainSettings, *, limit: int | None = None
) -> Selection | None:
    """One entry's selection with its prompts rebuilt and measured, or None for nothing to do.

    The prompts are built and thrown away, which is the point of building them: it costs
    nothing and it is the only honest way to say how much text a pass would pay to send.
    """
    entry = target.entry
    indices = selected(entry)[:limit]
    if not indices:
        return None
    chars = 0
    units: list[str] = []
    for index in indices:
        change = entry.changes[index].change
        context = build_context(
            change, from_version=entry.from_version, to_version=entry.to_version
        )
        parts = build_prompt(change, context, settings)
        chars += len(parts.system) + len(parts.user)
        units.append(change.location.canonical)
    return Selection(
        act=entry.act.key,
        from_version=entry.from_version,
        to_version=entry.to_version,
        units=tuple(units),
        prompt_chars=chars,
    )


def plan(
    targets: Sequence[RepairTarget], settings: ExplainSettings, *, limit: int | None = None
) -> tuple[tuple[Selection, ...], int]:
    """Every entry a repair would address, and how many entries it looked at to find them.

    `limit` counts changes rather than entries, because a change is what costs money and one
    large entry would otherwise take a whole budget with it. The number examined is returned
    rather than derived, so a limited pass never reports itself as a whole-repository one.
    """
    selections: list[Selection] = []
    examined = 0
    budget = limit
    for target in targets:
        if budget is not None and budget <= 0:
            break
        examined += 1
        item = selection_of(target, settings, limit=budget)
        if item is None:
            continue
        selections.append(item)
        budget = None if budget is None else budget - len(item.units)
    return tuple(selections), examined


def estimate_over(selections: Sequence[Selection], *, model_id: str) -> Estimate:
    """Price a selection at the rate this repository has on file, or say it is unpriced.

    A model with no published rate here is left unpriced rather than priced at a guess: a cost
    computed from a number nobody checked is worse than no cost at all.
    """
    chars = sum(item.prompt_chars for item in selections)
    changes = sum(len(item.units) for item in selections)
    usage = CallUsage(
        input_tokens=round(chars / CHARS_PER_INPUT_TOKEN),
        output_tokens=changes * OUTPUT_TOKENS_PER_CHANGE,
        requests=changes,
    )
    rate = rate_for(model_id)
    return Estimate(
        model_id=model_id,
        entries=len(selections),
        changes=changes,
        prompt_chars=chars,
        usage=usage,
        cost_usd=None
        if rate is None
        else usage.cost_usd(
            input_per_mtok=rate.input_per_mtok, output_per_mtok=rate.output_per_mtok
        ),
    )
