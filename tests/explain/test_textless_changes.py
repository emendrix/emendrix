"""A change with no text is routine output, so it may not raise. Regression test.

`corroborate.merge` appends one change per unit that the corpus metadata or the instruction
parse named and the structural diff did not. The diff is the only signal carrying text, so
those changes have a location, a kind, `disputed=True` and nothing to quote. They are common:
the REACH transition produces 32 of them.

Contexts are built before a single coroutine exists, so a stage that raised on one of these
would destroy the explanations of every other change in the delta as well. That is the opposite
of both non-negotiables this stage sits between, "a change is never dropped" and "first-class
states, never exceptions", so it gets both a fast unit test of the shape and, at the end, the
real thing: the REACH corroboration, whose `TIT XI` is a genuine metadata-only unit the diff
cannot key at all.

The second change no model is asked about lives here too: one whose two texts are identical once
the prompt's character cap has cut them, so the prompt carries no evidence of the difference at
all. Same family, same rules, and the model must never see it.
"""

from __future__ import annotations

import asyncio
from datetime import date

from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from emendrix.core import (
    ActId,
    Change,
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionRef,
    ProvisionText,
    Signal,
    SignalObservation,
    SignalReport,
    SignalSet,
    SignalStatus,
    VersionId,
)
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.eu.identifiers import Celex
from emendrix.eu.modmeta import metadata_signal, parse_branch_modifications
from emendrix.explain import (
    MODEL_FAILED,
    NO_EVIDENCE_PAST_CAP,
    NOTHING_TO_EXPLAIN,
    CassetteMode,
    ExplainEngine,
    ExplainSettings,
    contexts_for_delta,
    explainable,
)
from eu_pins import REACH, REACH_2008, REACH_2009, package

ACT = ActId(corpus="toy", key="house-rules")
V1, V2 = VersionId("v1"), VersionId("v2")
ANSWER: dict[str, object] = {"sentences": [{"text": "It changed.", "citations": ["k"]}]}

SEEN = SignalObservation(status=SignalStatus.OBSERVED, detail=Signal.CORPUS_METADATA.value)
NOT_SEEN = SignalObservation(status=SignalStatus.ABSENT, detail=Signal.STRUCTURAL_DIFF.value)


def textless(location: str) -> Change:
    """The exact shape `corroborate.merge._missing_units` appends: a unit, a kind, no text."""
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(act=ACT, version=V2, location=ProvisionLocation.parse(location)),
        signals=SignalSet(structural_diff=NOT_SEEN, corpus_metadata=SEEN),
    )


def with_text(location: str) -> Change:
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(act=ACT, version=V2, location=ProvisionLocation.parse(location)),
        before=ProvisionText("old"),
        after=ProvisionText("new"),
    )


def stub() -> FunctionModel:
    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, ANSWER)])

    return FunctionModel(call)


def engine() -> ExplainEngine:
    return ExplainEngine(ExplainSettings(cassette_mode=CassetteMode.LIVE), model=stub())


def test_a_textless_disputed_change_really_is_constructible() -> None:
    """If `core` ever forbids this shape, this whole module is obsolete, so check first."""
    change = textless("AR 12")
    assert change.disputed
    assert not explainable(change)
    assert explainable(with_text("AR 5"))


def test_contexts_for_delta_answers_none_rather_than_raising() -> None:
    delta = Delta(
        act=ACT,
        from_version=V1,
        to_version=V2,
        changes=(with_text("AR 5"), textless("AR 12"), with_text("AR 20")),
    )
    contexts = contexts_for_delta(delta)
    assert [context is None for context in contexts] == [False, True, False]


def test_one_textless_change_does_not_destroy_the_batch() -> None:
    """The regression. Every other change is still explained, and the slot is kept."""
    delta = Delta(
        act=ACT,
        from_version=V1,
        to_version=V2,
        changes=(with_text("AR 5"), textless("AR 12"), with_text("AR 20")),
    )
    run = asyncio.run(engine().explain_delta(delta))

    assert len(run.results) == 3
    assert [result.provision.location.canonical for result in run.results] == [
        "AR 5",
        "AR 12",
        "AR 20",
    ]
    assert run.stats.explained == 2
    assert run.stats.unavailable == 1
    assert run.results[0].ok and run.results[2].ok

    skipped = run.results[1]
    assert not skipped.ok
    assert skipped.unavailable is not None
    assert skipped.unavailable.kind == "nothing_to_explain"
    assert skipped.unavailable.reason == NOTHING_TO_EXPLAIN
    assert skipped.cassette_key == "", "no call was made, so there is no exchange to key"
    assert skipped.usage.requests == 0


def test_a_delta_of_nothing_but_textless_changes_still_returns_a_run() -> None:
    """A corroboration where the diff saw nothing at all is a legitimate, reportable outcome."""
    delta = Delta(
        act=ACT, from_version=V1, to_version=V2, changes=(textless("AR 1"), textless("AR 2"))
    )
    run = asyncio.run(engine().explain_delta(delta))
    assert run.stats.changes == 2
    assert run.stats.explained == 0
    assert run.stats.unavailable == 2
    assert run.stats.nothing_to_explain == 2
    assert run.stats.usage.requests == 0


# --------------------------------------------------- the other change no model is asked about


SHARED = "Kitchen: Bo.   Bathroom: Cy.   Hallway: Ada. " * 4
"""Long enough to fill the cap below on both sides, so the whole difference falls past it."""


def unreachable() -> FunctionModel:
    """A model that cannot answer, so a test asserting it was not called proves it."""

    async def call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise AssertionError("the explain stage called a model for a prompt with no evidence in it")

    return FunctionModel(call)


def past_the_cap(location: str) -> Change:
    """A modification whose two texts differ only after the first `len(SHARED)` characters."""
    return Change(
        change_type=ChangeType.MODIFIED,
        provision=ProvisionRef(act=ACT, version=V2, location=ProvisionLocation.parse(location)),
        before=ProvisionText(SHARED + "Bo empties the hallway bin."),
        after=ProvisionText(SHARED + "Cy empties the hallway bin."),
    )


def test_a_change_with_no_evidence_in_its_prompt_never_reaches_the_model() -> None:
    """The refusal is deterministic, so the provider is never asked and never has to be right.

    The engine turns any provider failure into the counted `model_failed` state, so a raising
    model shows up under that kind if the call happened. The reason below is the one the stage
    writes when it declines to make the call at all, and the two kinds telling the cases apart
    is the point of having kinds.
    """
    delta = Delta(
        act=ACT, from_version=V1, to_version=V2, changes=(past_the_cap("AR 5"), with_text("AR 20"))
    )
    settings = ExplainSettings(cassette_mode=CassetteMode.LIVE, text_char_cap=len(SHARED))
    engine = ExplainEngine(settings, model=unreachable())
    run = asyncio.run(engine.explain_delta(delta))

    refused = run.results[0]
    assert refused.no_evidence
    assert refused.unavailable is not None
    assert refused.unavailable.kind == "no_evidence_past_cap"
    assert refused.unavailable.reason == NO_EVIDENCE_PAST_CAP
    assert refused.cassette_key == "", "no call was made, so there is no exchange to key"
    assert refused.usage.requests == 0
    assert refused.dropped_chars > 0, "the cap is what removed the evidence, and it says how much"
    assert run.stats.no_evidence == 1

    called = run.results[1]
    assert called.unavailable is not None
    assert called.unavailable.kind == "model_failed", (
        "the control change reached the model and was refused there, which is what makes the "
        "first change's reason evidence that no call was attempted for it"
    )
    assert called.unavailable.reason == MODEL_FAILED
    assert "AssertionError" not in called.unavailable.reason, (
        "the exception's own text is for the log, never for a field that reaches a document"
    )
    assert called.no_evidence is False


# --------------------------------------------------- and now the real corroboration


def test_the_real_reach_corroboration_explains_around_its_metadata_only_unit(
    client: CellarClient,
) -> None:
    """`TIT XI` is a title, not an article or an annex, so the diff has no unit for it.

    It reaches this stage from the actual corroborator, over the actual fixtures, exactly as
    the loop hands it over. Everything else in that delta is still explained.
    """
    computed = compute_delta(
        parse_act(package(client, REACH, REACH_2008)).tree,
        parse_act(package(client, REACH, REACH_2009)).tree,
    )
    notice = parse_branch_modifications(client.branch_notice(Celex.parse(REACH)))
    merged = corroborate(
        computed,
        metadata=metadata_signal(notice.between(date(2008, 10, 12), date(2009, 1, 20))),
        instructions=SignalReport.unavailable(Signal.INSTRUCTION_PARSE, note="unpinned amender"),
    )
    stray = next(c for c in merged.delta.changes if c.unit.canonical == "TIT XI")
    assert stray.before is None and stray.after is None and stray.disputed

    run = asyncio.run(engine().explain_delta(merged.delta))
    assert run.stats.changes == len(merged.delta.changes)
    skipped = next(r for r in run.results if r.provision.location.canonical == "TIT XI")
    assert skipped.unavailable is not None
    assert skipped.unavailable.reason == NOTHING_TO_EXPLAIN
    assert run.stats.explained == len(merged.delta.changes) - 1
