"""The faithfulness layer's vocabulary and its sampling rule: everything the judge is *not*.

Faithfulness is the fourth row of the rigour table (`prose.py`) and the only one with no free
ground truth: whether a shipped sentence is a true account of the difference between two texts is
a question no deterministic check answers. This project's answer is deliberately weak and
deliberately labelled as such, a sampled LLM judge plus a human spot-review worksheet the author
fills in by hand, and it is reported apart from citation grounding, never merged into it.
Blurring the two would make the grounding number mean nothing.

What lives here: the triple, the verdict, the report and the sampling rule. What lives in
`judgements.py`: the on-disk cassette, its key and the replay path. What lives in
`faithfulness.py`: the judge agent itself, which is the only reason a model client may be
imported under `eval_/` at all. The last split is load-bearing rather than tidy, because
`emendrix eval run` replays committed judgements and must not import one to do it, exactly as the
explain stage does not in `CassetteMode.REPLAY`.

**What the judge sees is the evidence the writer was given**: the deterministic-facts header the
writer's prompt opened with, the before text, the after text, the sentences that shipped, and the
surrounding-provision block when the prompt carried one. The header joined that list on
2026-08-09, so a rate recorded before that date answers a narrower question than one recorded
after it. `rubric.py` records the measurement behind the change and holds the boundary that keeps
it honest: header facts ground claims about which provisions changed, and only the two texts
ground claims about what the words say. The citation keys reach neither the judge nor the reviewer.

Those texts are the texts **as the model was shown them**, capped by the explain settings' own
`text_char_cap` (and `context_char_cap` for the fourth) and carrying that stage's truncation
marker. This is load-bearing rather than tidy: the judge is asked whether the sentences follow
from the evidence the model had, so a second, shorter cap here would silently change the question
on every provision long enough to trip it. See `rubric.py` for what that costs when it happens,
and for the reading of `context` that follows from it.

**n is small by design.** Twenty triples, sampled by the same seedless `sample_indices` as
everything else in this package, because each one is a paid call to a stronger model than the
explainer. The report prints the raw fraction and no confidence interval: with n = 20 an
interval would be wider than the number is useful, and dressing it up would be the kind of
false precision this project exists to avoid.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.eval_.corpus import sample_indices
from emendrix.eval_.rubric import judge_prompt

__all__ = [
    "DEFAULT_JUDGE_MODEL",
    "JUDGE_MODEL_ENV",
    "SAMPLE_SIZE",
    "FaithfulnessReport",
    "Judgement",
    "Triple",
    "Verdict",
    "judge_model",
    "prompt_for",
    "sample",
]

DEFAULT_JUDGE_MODEL: Final = "openrouter:openai/gpt-5.6-sol"
"""The judge: stronger than the explainer and, since 2026-08-08, from a different vendor
(`faithfulness.py` explains what that does and does not buy). Read off OpenRouter's own
`/api/v1/models` on 2026-08-08: listed and active, canonical slug `openai/gpt-5.6-sol-20260709`,
1 050 000-token context, $5.00 in / $30.00 out per 1M tokens, `structured_outputs` advertised and
`temperature` not.

Editing this constant is what switches the judge. Exporting `EMENDRIX_JUDGE_MODEL` also works,
because `judge_model` reads it, but the committed judgement cassettes are recorded under whatever
is written here, so the two must agree or the replay finds nothing."""

JUDGE_MODEL_ENV: Final = "EMENDRIX_JUDGE_MODEL"
"""Point it at another vendor and the independence claim gets stronger. Same weak signal."""

SAMPLE_SIZE: Final = 20
"""Triples judged. Small because each one costs a call to a model stronger than the explainer."""


class Triple(BaseModel):
    """One (before, after, explanation) the judge is asked about, and where it came from."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    unit: str
    outcome: str = Field(description="The gate outcome that produced these sentences.")
    change_type: str
    before: str = Field(
        default="",
        description="As shown to the model, truncation marker included; empty for an insertion.",
    )
    after: str = Field(
        default="",
        description="As shown to the model, truncation marker included; empty for a deletion.",
    )
    context: str = Field(
        default="",
        description="The surrounding-provision block the prompt carried, as shown; usually empty.",
    )
    header: str = Field(
        default="",
        description="The deterministic-facts header of the writer's prompt, byte for byte; "
        "empty only on triples recorded before it entered the evidence base (2026-08-09).",
    )
    sentences: tuple[str, ...] = Field(min_length=1, description="Exactly what shipped.")
    fallback: bool = Field(
        default=False, description="At least one sentence was written by the gate, not the model."
    )

    @property
    def slug(self) -> str:
        """Stable identity of the triple, for the worksheet and for a reviewer's notes."""
        return f"{self.case_id} {self.unit}"


class Verdict(BaseModel):
    """What the judge may return. Two fields, and it cannot decide anything else.

    One verdict per entry rather than one per sentence, and it stays that way for one reason:
    twenty judgements are committed under this shape, they are the labelled set the judge is
    scored against, and a `faithful` derived from a per-sentence list would read every one of
    them as an empty list and answer `True`. Silently relabelling the benchmark to sharpen the
    instrument is the wrong trade. The per-entry shape does round away a single bad sentence in
    an otherwise sound entry, so `rubric.py` asks for the discipline instead: take the sentences
    one at a time, and name the failing one by its number in `issue`.
    """

    model_config = ConfigDict(frozen=True)

    faithful: bool = Field(
        description="True only if every sentence follows from the evidence as given."
    )
    issue: str | None = Field(
        default=None, description="One sentence naming the problem, when there is one."
    )


class Judgement(BaseModel):
    """One judged triple: what shipped, what the judge said, and whether to believe it."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    unit: str
    outcome: str
    fallback: bool = False
    verdict: Verdict | None = Field(
        default=None, description="`None` when no judgement was recorded for this triple."
    )
    synthetic: bool = Field(
        default=False, description="A stub produced it. Never evidence about faithfulness."
    )
    judge_model: str = ""


class FaithfulnessReport(BaseModel):
    """The sampled faithfulness layer, as it appears in the eval report.

    `publishable` is the honesty switch. A verdict recorded from a stub model exercises the
    plumbing and says nothing about faithfulness, so when any sampled judgement is synthetic the
    report prints the mechanics and withholds the rate rather than printing a number that does
    not mean what its name says. Grounding is treated differently on purpose: the gate is
    deterministic, so its counts are real whatever produced the sentences it rejected.
    """

    model_config = ConfigDict(frozen=True)

    judge_model: str = ""
    sampled: int = Field(default=0, ge=0)
    judged: int = Field(default=0, ge=0, description="Triples a recorded verdict exists for.")
    faithful: int = Field(default=0, ge=0)
    synthetic: int = Field(default=0, ge=0)
    fallback_triples: int = Field(
        default=0, ge=0, description="Sampled triples carrying a gate-written quotation."
    )
    human_review: str = Field(
        default="pending", description="`pending` until the author fills in the worksheet."
    )
    worksheet: str = Field(default="", description="Path of the spot-review worksheet.")
    judgements: tuple[Judgement, ...] = ()

    @property
    def publishable(self) -> bool:
        """Whether a faithfulness rate may be published at all."""
        return self.judged > 0 and self.synthetic == 0

    @property
    def rate(self) -> float | None:
        """The raw fraction, or `None` when nothing may be published from it."""
        if not self.publishable:
            return None
        return self.faithful / self.judged


def judge_model(env: Mapping[str, str] | None = None) -> str:
    """The configured judge. `env=None` reads the process, like `ExplainSettings.from_env`.

    Here rather than in `faithfulness.py` so that replaying committed judgements — which is what
    `emendrix eval run` does — needs no model client to know whose cassettes to look for.
    """
    source = os.environ if env is None else env
    return source.get(JUDGE_MODEL_ENV, DEFAULT_JUDGE_MODEL)


def sample(triples: tuple[Triple, ...], size: int = SAMPLE_SIZE) -> tuple[Triple, ...]:
    """`size` triples spread evenly over the subset's own order. No seed, no clock, no shuffle.

    Evenly spread rather than randomly drawn so the sample covers the whole subset — the
    flagship transition's forty-odd changes *and* the tail sampled from the other acts — and so
    re-running it on the same subset returns the same twenty triples.
    """
    return tuple(triples[index] for index in sample_indices(len(triples), size))


def prompt_for(triple: Triple) -> str:
    """The exact prompt one triple becomes — the string the cassette key is taken over."""
    return judge_prompt(
        triple.before, triple.after, triple.sentences, triple.context, header=triple.header
    )
