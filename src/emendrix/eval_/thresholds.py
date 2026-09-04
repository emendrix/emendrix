"""The regression teeth: floors a measured number may never fall below, committed in git.

CI runs the full deterministic eval on every push and compares it against these. **A number may
rise silently; it may never fall.** When one does, the build fails and somebody has to say in a
commit message why — either the change is a regression or the floor moves, and both are decisions
worth leaving a record of.

Each floor **is** the value the report named in `source` measured, and `TOLERANCE` is the slack
allowed below it. They are deliberately not aspirational targets: a floor above what the corpus
actually scores would fail every build, and a floor far below it would catch nothing.

`TOLERANCE` exists for float arithmetic and for the fact that a corpus rebuild can shift a
transition by one unit; it is not a licence to lose a provision.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.eval_.aggregate import EvalMetrics
from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.model_metrics import ModelMetrics

__all__ = [
    "FLOORS",
    "MODEL_FLOORS",
    "TOLERANCE",
    "Breach",
    "Floors",
    "ModelFloors",
    "check",
    "check_model",
]

TOLERANCE: Final = 0.005


class Floors(BaseModel):
    """What the deterministic layers must keep clearing."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="The report these numbers were read off.")
    localisation_micro_f1: float = Field(ge=0.0, le=1.0)
    localisation_micro_recall: float = Field(ge=0.0, le=1.0)
    localisation_macro_f1: float = Field(ge=0.0, le=1.0)
    classification_accuracy: float = Field(ge=0.0, le=1.0)
    cases_scored: int = Field(ge=0)
    max_parser_unknown_elements: int = Field(ge=0)
    max_documents_unreadable: int = Field(ge=0)


FLOORS: Final = Floors(
    source="reports/eval/2026-09-04-984347f.md",
    # Recall is the number that matters most: across every transition traced since 2026-08-05 the
    # structural diff has missed exactly the provisions the two location vocabularies spell
    # differently (`AN 4` vs `AN IV`, that report's known-class 3) and no others. Micro precision
    # is deliberately *not* floored: it is dominated by blanket amendments, where a low number is
    # one annotation standing for dozens of touched provisions rather than the diff being wrong.
    #
    # The two F1 floors moved on 2026-08-12 and they are not the old ones improved. Until that
    # date a window the corpus annotated nowhere was scored as a reference set that contradicted
    # every unit the diff found, so the MDR's corrigendum consolidation entered the pairing with
    # zero precision over 15 units. It has no reference set and is now left out of the pairing
    # instead, which is a different denominator: 17 transitions and 83 diff units where
    # 2026-08-08 read 18 and 98. Recall, classification and the case count are computed the same
    # way as before and did not move.
    #
    # `source` has moved twice since without one deterministic figure moving with it. First to
    # the report of the recording pass that followed the boundary-separator fix of 2026-08-12:
    # the whole `EvalRun` over the committed corpus serialises to the same bytes on either side
    # of that fix, because the diff reads `comparison_text` and never the verbatim form. Then to
    # the report of 2026-08-13, which scores the same recording and differs only in publishing a
    # transcribed hand review. There is one report per date, because a second report of one date
    # is a re-score of the same corpus rather than a second measurement of it.
    #
    # It moved a third time on 2026-09-04, to a report that scores 101 changes where the previous
    # source scored 104, and again no floor value moved with it. An amending article carrying no
    # `LIST` had its own heading read as the provision its instruction named, so the third signal
    # claimed the amending act's article numbers rather than the amended act's. Nothing floored
    # here consults that signal: localisation pairs the structural diff against the metadata and
    # never reads the instruction parse, and classification is computed over the units those same
    # two signals both named. Neither the disputed rate nor either instruction pairing is floored
    # at all, deliberately, because the instruction parse is a measured cross-check rather than a
    # reference set, which is why the largest movement of that day is absent from this list.
    localisation_micro_f1=0.963,
    localisation_micro_recall=0.975,
    localisation_macro_f1=0.915,
    classification_accuracy=1.000,
    cases_scored=18,
    max_parser_unknown_elements=0,
    # One member of REACH `02006R1907-20150323` is a TIFF page scan shipped with an `.xml`
    # filename (verified 2026-08-06). The parser counts it as unreadable, which is the designed
    # behaviour; the fixture keeps it, because a trimmed package that quietly drops it would no
    # longer be what the corpus published.
    max_documents_unreadable=1,
)


class ModelFloors(BaseModel):
    """What the model layer must keep clearing, over the pinned explanation subset.

    Two kinds of floor live here and they are worth telling apart. The **invariants** —
    everything settles, everything replays, no pinned unit goes missing — have teeth today and
    will keep them forever: a breach means the pipeline dropped a change, reached for a provider
    during an eval, or lost a unit under a pinned set. The **rates** are pinned to what the
    committed cassettes measure, which is what every floor in this file means.

    Both rates sit at their extreme, and that is a real floor rather than a strict one. Replay is
    byte-stable, so a rate computed over committed cassettes cannot drift: it moves only when
    somebody re-records or edits a prompt, and then a human is supposed to look at what moved. A
    single grounding failure in the 55 changes that reach the model is 0.018, well outside
    `TOLERANCE`, so it fails the build. That is the intent. The gate either accepts every
    citation the model offered or it does not, and "it does not, a bit" is exactly the state
    worth stopping for.
    """

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="The report these numbers were read off.")
    subset_changes: int = Field(ge=0, description="Changes the subset must still measure.")
    min_grounding_rate: float = Field(ge=0.0, le=1.0)
    max_fallback_rate: float = Field(ge=0.0, le=1.0)
    max_missing_units: int = Field(ge=0)
    min_judged: int = Field(ge=0, description="Sampled triples that must carry a judgement.")


MODEL_FLOORS: Final = ModelFloors(
    source="reports/eval/2026-09-04-984347f.md",
    subset_changes=55,
    # Measured over the cassettes recorded on 2026-08-12 against
    # `openrouter:anthropic/claude-sonnet-5`, at the 40 000-character prompt cap. All 55 of them
    # were recorded that day, because the boundary-separator fix landed a space wherever the
    # markup opened a block and so moved every one of the 55 prompts by at least one byte. All 55
    # first attempts cited only offered keys, so the gate never asked for a revision and never
    # had to quote a provision itself: 179 of 179 individual keys resolved, where the 2026-08-09
    # recording of the same 55 changes offered 187 and the partly re-recorded set of earlier on
    # 2026-08-12 offered 184. Those key counts are not one measurement moving. Each counts the
    # keys one recording's prose happened to cite, and the three recordings were given
    # differently formed evidence.
    #
    # Four of those 55 were re-recorded on 2026-09-01, when stored text stopped joining a
    # footnote to the sentence it interrupts and their prompts changed key. `source` follows that
    # recording from 2026-09-04 and no floored figure moved with it: grounding, fallback, the
    # missing-unit count and the judged 20 read exactly as before. What did move is not floored
    # and is a count of one recording rather than a rate: 7 schema repairs where the earlier
    # recording needed 9, over 365 757 in / 20 198 out tokens where it used 404 846 / 20 998.
    #
    # Every change of the subset reaches the model at this cap. The explain stage still refuses a
    # prompt a cap has left with two identical texts, and at 40 000 characters no subset change is
    # in that state, where one was at 8 000. These are the numbers of one recording of one
    # 55-change subset by one model, not a claim about models in general, and the report says so
    # where it prints them.
    min_grounding_rate=1.000,
    max_fallback_rate=0.000,
    max_missing_units=0,
    # The full sample: all twenty judgements were re-recorded on 2026-08-12 over this recording's
    # prose, so every one of the 20 sampled triples carries a verdict by the pinned judge under
    # the rubric in git.
    min_judged=20,
)


class Breach(BaseModel):
    """One floor a run failed to clear."""

    model_config = ConfigDict(frozen=True)

    metric: str
    floor: float
    measured: float | None

    def __str__(self) -> str:
        got = "not measured" if self.measured is None else f"{self.measured:.3f}"
        return f"{self.metric}: floor {self.floor:.3f}, measured {got}"


def _below(metric: str, floor: float, measured: float | None) -> Breach | None:
    if measured is None or measured < floor - TOLERANCE:
        return Breach(metric=metric, floor=floor, measured=measured)
    return None


def _above(metric: str, ceiling: float, measured: float) -> Breach | None:
    """An upper bound. Slack works the same way here: only a real overrun is a breach."""
    if measured > ceiling + TOLERANCE:
        return Breach(metric=metric, floor=float(ceiling), measured=float(measured))
    return None


def check(metrics: EvalMetrics, floors: Floors = FLOORS) -> tuple[Breach, ...]:
    """Every floor this run failed to clear, in a fixed order. Empty is a pass."""
    localisation = metrics.localisation
    found = [
        _below(
            "localisation micro F1",
            floors.localisation_micro_f1,
            None if localisation is None else localisation.micro_f1,
        ),
        _below(
            "localisation micro recall",
            floors.localisation_micro_recall,
            None if localisation is None else localisation.micro_recall,
        ),
        _below(
            "localisation macro F1",
            floors.localisation_macro_f1,
            None if localisation is None else localisation.macro_f1,
        ),
        _below(
            "classification accuracy",
            floors.classification_accuracy,
            metrics.classification_accuracy,
        ),
        _below("transitions scored", float(floors.cases_scored), float(metrics.cases_scored)),
        _above(
            "parser unknown elements",
            floors.max_parser_unknown_elements,
            metrics.parser.unknown_elements,
        ),
        _above(
            "unreadable documents",
            floors.max_documents_unreadable,
            metrics.parser.documents_unreadable,
        ),
    ]
    return tuple(item for item in found if item is not None)


def _judgements_metric(faithfulness: FaithfulnessReport | None) -> str:
    """The judgements-recorded metric, naming the judge whose cassettes were looked for.

    A breach here almost always means the run resolved a judge nothing was ever recorded
    against, so the model id is the whole diagnosis: `floor 20.000, measured 0.000` on its own
    sends a reader looking for a lost cassette directory instead of at their own configuration.
    The name falls back to the bare string when no report was passed, because then there is no
    judge to name.
    """
    base = "faithfulness judgements recorded"
    if faithfulness is None or not faithfulness.judge_model:
        return base
    return f"{base} ({faithfulness.judge_model})"


def check_model(
    metrics: ModelMetrics | None,
    faithfulness: FaithfulnessReport | None = None,
    floors: ModelFloors = MODEL_FLOORS,
) -> tuple[Breach, ...]:
    """Every model-layer floor this run failed to clear. `None` metrics means it was not run.

    A run that skipped the model layer is not a breach — `emendrix eval run --no-model` is a
    legitimate thing to do while debugging the deterministic half. A run that *ran* it and lost
    a change, a cassette or a pinned unit is.
    """
    if metrics is None:
        return ()
    found = [
        _below(
            "subset changes measured",
            float(floors.subset_changes),
            float(metrics.settled.changes),
        ),
        _below("citation grounding", floors.min_grounding_rate, metrics.grounding_rate),
        _above("quote fallback", floors.max_fallback_rate, metrics.fallback_rate or 0.0),
        _above(
            "pinned units missing from the delta",
            floors.max_missing_units,
            metrics.missing_units,
        ),
        _below(
            "changes settled by the gate",
            float(metrics.settled.changes),
            float(metrics.settled.settled),
        ),
        _below(
            "explanations replayed from a cassette",
            float(metrics.changes - metrics.unexplained),
            float(metrics.replayed),
        ),
        _below(
            _judgements_metric(faithfulness),
            float(floors.min_judged),
            0.0 if faithfulness is None else float(faithfulness.judged),
        ),
    ]
    return tuple(item for item in found if item is not None)
