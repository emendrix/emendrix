"""The EXPLAIN stage. The only module in emendrix that calls a model.

One bounded call per `Change`: no tools, no memory, no multi-turn, no chance to go looking for
anything. What it is given is what `prompt.py` built, and what it may return is what
`schema.py` allows. The single retry pydantic-ai is permitted is *schema repair* — a
malformed structured output — and not a second opinion; the gate's one retry on a citation
failure belongs to the gate, and it comes back through `revise`.

**Concurrency.** Changes are independent, so a delta is explained under a semaphore rather
than one at a time. `asyncio.gather` preserves order, so result *i* is change *i* — a property
the tests assert, because a batch that silently reorders would attach the right sentence to
the wrong article.

**Failure is a value.** A provider error, a refusal, or an exhausted repair budget yields
`ExplanationUnavailable` on that one change and the batch continues; a change is never dropped
because the model failed on it. The exceptions are the two cassette faults — `CassetteMiss`
and `CassetteCorrupt` — which propagate: an unrecorded prompt and a cassette that is not the
exchange its name claims are both build faults, not answers about a change. Turning either
into a counted value would let CI go green while explaining nothing, and a corrupt one is the
worse of the two because it also shrinks the denominator every published rate is computed
over (see `eval_/thresholds.py`, whose floors all move with it and so never catch it).

**Two changes are answered without a call.** One the diff never saw carries no text at all
(`NOTHING_TO_EXPLAIN`); one whose whole difference falls past the prompt's character cap carries
two identical texts (`NO_EVIDENCE_PAST_CAP`). Both are counted states rather than failures, and
both keep their slot in the batch.

**Replay touches nothing.** In `CassetteMode.REPLAY` the provider agent is never constructed,
so no API key is read and no client exists to make a request. That is why CI can run this
stage at all.
"""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from emendrix.core import Change, Delta
from emendrix.explain.capping import NO_EVIDENCE_PAST_CAP
from emendrix.explain.cassette import (
    Cassette,
    CassetteCorrupt,
    CassetteMiss,
    CassetteStore,
    cassette_key,
)
from emendrix.explain.context import NOTHING_TO_EXPLAIN, ExplainContext, contexts_for_delta
from emendrix.explain.prompt import PromptParts, build_prompt, revision_note
from emendrix.explain.results import CallUsage, ExplainedChange, ExplainRun, RunStats
from emendrix.explain.schema import SCHEMA_VERSION, Explanation, ExplanationUnavailable
from emendrix.explain.settings import CassetteMode, ExplainSettings

__all__ = ["ExplainEngine"]


class ExplainEngine:
    """Holds the settings, the cassette store and (lazily) the one agent.

    `model` overrides the configured provider — the seam the tests and the recorder use to
    push a `TestModel` or a `FunctionModel` through the identical code path. Supplying one
    marks every result `synthetic` unless the caller says otherwise, because output that did
    not come from the pinned model is not evidence about the pinned model.
    """

    def __init__(
        self,
        settings: ExplainSettings | None = None,
        *,
        cassettes: CassetteStore | None = None,
        model: Model | None = None,
        synthetic: bool | None = None,
    ) -> None:
        self.settings = settings or ExplainSettings()
        self.cassettes = cassettes or CassetteStore(self.settings.cassette_dir)
        self._model = model
        self.synthetic = (model is not None) if synthetic is None else synthetic
        self._agent: Agent[None, Explanation] | None = None

    @property
    def recorded_with(self) -> str:
        """What a cassette recorded by this engine should say produced it."""
        return type(self._model).__name__ if self._model is not None else self.settings.model_id

    @property
    def model_settings(self) -> ModelSettings:
        """The sampling parameters this engine would send. Public for the same reason
        `recorded_with` is: it is a question about the engine that is worth asking from outside.

        `temperature` is omitted when it is `None`, which is the default since 2026-08-08:
        the pinned model's OpenRouter listing does not advertise the parameter, and sending one a
        provider does not accept is how a recording run dies twenty calls in. `settings.py` holds
        the reading and the date.
        """
        settings = ModelSettings(max_tokens=self.settings.max_output_tokens)
        if self.settings.temperature is not None:
            settings["temperature"] = self.settings.temperature
        return settings

    def _build_agent(self) -> Agent[None, Explanation]:
        """Construct the agent on first live use — never in replay.

        `defer_model_check` is off: a wrong provider id or a missing key surfaces here, at the
        one place that made the choice, rather than inside a gather.
        """
        if self._agent is None:
            self._agent = Agent(
                model=self._model if self._model is not None else self.settings.model_id,
                output_type=Explanation,
                retries={"output": self.settings.output_retries},
                model_settings=self.model_settings,
            )
        return self._agent

    async def _call_model(self, parts: PromptParts) -> tuple[Explanation, CallUsage]:
        """The explain-call boundary itself: two strings in, one typed answer out."""
        agent = self._build_agent()
        result = await agent.run(parts.user, instructions=parts.system)
        usage = result.usage
        return result.output, CallUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            requests=usage.requests,
            # Anything past the first request in a toolless, single-turn run is pydantic-ai
            # handing back a malformed structured output for repair.
            schema_repairs=max(usage.requests - 1, 0),
        )

    async def _resolve(self, parts: PromptParts) -> tuple[Explanation, CallUsage, str, bool, bool]:
        """`(explanation, usage, key, replayed, synthetic)` for one prompt, per cassette mode."""
        key = cassette_key(self.settings.model_id, parts.system, parts.user, SCHEMA_VERSION)
        mode = self.settings.cassette_mode
        if mode is CassetteMode.REPLAY:
            cassette = self.cassettes.require(self.settings.model_id, key)
            # `requests=0`: the tokens were spent once, at recording time. Charging them again
            # on every CI run would misreport what this project costs to operate.
            return (
                cassette.output,
                cassette.usage.model_copy(update={"requests": 0}),
                key,
                True,
                (cassette.synthetic),
            )
        explanation, usage = await self._call_model(parts)
        if mode is CassetteMode.RECORD:
            self.cassettes.save(
                Cassette(
                    model_id=self.settings.model_id,
                    key=key,
                    synthetic=self.synthetic,
                    recorded_with=self.recorded_with,
                    system=parts.system,
                    user=parts.user,
                    output=explanation,
                    usage=usage,
                )
            )
        return explanation, usage, key, False, self.synthetic

    async def _run(self, change: Change, parts: PromptParts) -> ExplainedChange:
        if parts.no_evidence:
            return self._no_evidence(change, parts)
        try:
            explanation, usage, key, replayed, synthetic = await self._resolve(parts)
        except (CassetteMiss, CassetteCorrupt):
            # The two cassette faults are the replay layer's own alarms, and they must ring.
            # A corrupt cassette caught below would be counted as one more unexplained change,
            # which every model-layer floor absorbs without moving.
            raise
        except Exception as error:
            # Deliberately broad: every way a provider can fail — timeout, refusal, rate
            # limit, exhausted repair budget — is one counted value, not five call sites.
            return ExplainedChange(
                provision=change.provision,
                unavailable=ExplanationUnavailable(reason=f"{type(error).__name__}: {error}"),
                cassette_key=cassette_key(
                    self.settings.model_id, parts.system, parts.user, SCHEMA_VERSION
                ),
                synthetic=self.synthetic,
                dropped_chars=parts.dropped_chars,
            )
        return ExplainedChange(
            provision=change.provision,
            explanation=explanation,
            usage=usage,
            cassette_key=key,
            replayed=replayed,
            synthetic=synthetic,
            dropped_chars=parts.dropped_chars,
        )

    async def explain_change(self, change: Change, context: ExplainContext) -> ExplainedChange:
        """Explain one change. Never raises for a model failure — it returns the state."""
        return await self._run(change, build_prompt(change, context, self.settings))

    async def revise(
        self, change: Change, context: ExplainContext, prior: Explanation, failure: str
    ) -> ExplainedChange:
        """The gate's single retry, with its specific complaint attached.

        Exactly one revision is ever asked for: if this one fails the gate too, the gate
        substitutes a verbatim quotation, correct by construction, and counts the
        substitution. This method has no opinion about that policy; it just makes the call.
        """
        parts = build_prompt(change, context, self.settings)
        revised = parts.model_copy(update={"user": parts.user + revision_note(prior, failure)})
        return await self._run(change, revised)

    def _nothing_to_explain(self, change: Change) -> ExplainedChange:
        """A change the diff never saw: a disputed unit with no text (`NOTHING_TO_EXPLAIN`).

        No prompt is built and no model is called, so there is no cassette key — but the change
        still ships, carrying the reason, because the corroborator produces these routinely and
        dropping them would undo the whole point of shipping a disagreement.
        """
        return ExplainedChange(
            provision=change.provision,
            unavailable=ExplanationUnavailable(reason=NOTHING_TO_EXPLAIN),
        )

    def _no_evidence(self, change: Change, parts: PromptParts) -> ExplainedChange:
        """A prompt the character cap emptied: both texts identical, nothing to describe.

        The refusal is deterministic and it is made here rather than asked of the model, which
        has no way to answer it: shown two identical prefixes it can only say "no visible
        difference", which is a vacuous claim about a change that really happened. No exchange
        takes place, so there is no cassette key; the change keeps its slot and ships with its
        verbatim before and after, which are the parts of the entry a reader can check, and
        `dropped_chars` says how much of them the model never saw.
        """
        return ExplainedChange(
            provision=change.provision,
            unavailable=ExplanationUnavailable(reason=NO_EVIDENCE_PAST_CAP),
            dropped_chars=parts.dropped_chars,
            no_evidence=True,
        )

    async def explain_delta(
        self, delta: Delta, contexts: tuple[ExplainContext | None, ...] | None = None
    ) -> ExplainRun:
        """Explain every change of a delta concurrently, in order, under the semaphore.

        A `None` context means the change has nothing to explain; it is answered without a
        model call and keeps its slot, so `run.results[i]` is always `delta.changes[i]`.
        """
        resolved = contexts_for_delta(delta) if contexts is None else contexts
        if len(resolved) != len(delta.changes):
            # Checked before a single coroutine exists: pairing a short context list positionally
            # would offer one change's citation keys to another, which the gate would then
            # reject as a hallucination. A caller error, so it raises.
            raise ValueError(
                f"{len(delta.changes)} changes but {len(resolved)} contexts; they are paired "
                f"positionally and must be the same length"
            )
        semaphore = asyncio.Semaphore(self.settings.max_concurrency)

        async def bounded(change: Change, context: ExplainContext | None) -> ExplainedChange:
            if context is None:
                return self._nothing_to_explain(change)
            async with semaphore:
                return await self.explain_change(change, context)

        results = tuple(
            await asyncio.gather(
                *(
                    bounded(change, context)
                    for change, context in zip(delta.changes, resolved, strict=True)
                )
            )
        )
        return ExplainRun(results=results, stats=RunStats.over(self.settings.model_id, results))
