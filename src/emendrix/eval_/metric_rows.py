"""The published metrics table, as data: one row per measure, with its caveat attached.

Two artifacts publish these figures, the README's metrics section (`readme_table.py`) and the
site's methodology page (`site_/pages/methodology.py`), and they must publish the *same* figures
with the *same* qualifications. Splitting the rows out of the Markdown renderer is what makes
that structural rather than a thing to remember: a caveat softened here softens in both places,
and neither renderer can quote a number without the sentence that says what it does not mean,
because the number and the sentence are fields of one frozen object.

Three rules the rows keep:

- **A rate that was not measured is `not measured`, never `0`.** `None` and zero are different
  answers and the difference is the whole point of publishing at all.
- **A withheld rate stays withheld.** `FaithfulnessReport.rate` is `None` while any judgement in
  it came from a stub, and the row then prints `**not published**` and says why in the same cell.
- **Citation grounding is never merged with explanation faithfulness.** They are separate rows
  with separate n, because the third is a deterministic property of the gate and the fourth is a
  judgement.

Pure: no clock, no I/O, no formatting decisions beyond the fixed decimal places. Only the
`EvalRun` handed in decides what the rows say.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from emendrix.eval_.prose import count
from emendrix.eval_.runner import EvalRun

__all__ = ["MetricRow", "metric_rows", "synthetic_caveats"]


class MetricRow(BaseModel):
    """One published measure: what it is, what it came out as, over what, and what it is not."""

    model_config = ConfigDict(frozen=True)

    measure: str
    result: str
    n: str
    meaning: str


def _pct(value: float | None, places: int = 3) -> str:
    """`—` is "not measured", which is not the same as zero and never rendered as one."""
    return "—" if value is None else f"{value:.{places}f}"


def _deterministic_rows(run: EvalRun) -> list[MetricRow]:
    metrics = run.metrics
    localisation = metrics.localisation
    instruction = metrics.instruction_agreement
    return [
        MetricRow(
            measure="**Localisation** (which provisions changed)",
            result="—"
            if localisation is None
            else f"P {localisation.micro_precision:.3f} / R {localisation.micro_recall:.3f} / "
            f"**F1 {localisation.micro_f1:.3f}**",
            n=count(0 if localisation is None else localisation.cases, "transition"),
            meaning="Structural diff against the corpus's own modification metadata, at "
            "article-or-annex granularity. Not a measure of whether the explanation is any good; "
            "precision is dragged down by blanket amendments the reference set annotates only "
            "once.",
        ),
        MetricRow(
            measure="Instruction-parse agreement (cross-check)",
            result="—"
            if instruction is None
            else f"P {instruction.micro_precision:.3f} / R {instruction.micro_recall:.3f} / "
            f"F1 {instruction.micro_f1:.3f}",
            n=count(0 if instruction is None else instruction.cases, "transition"),
            meaning="A third, independent reading of the same question, from the amending act's "
            "own prose. Weaker by construction: it cannot read a range or an instruction that "
            "delegates to an annex, and those are counted as unread, never approximated.",
        ),
        MetricRow(
            measure="Disputed changes (signals disagree)",
            result=f"{metrics.dispute_rate:.3f}",
            n=count(metrics.changes, "change"),
            meaning="Changes at least one signal named and another did not. They ship marked "
            "`disputed`; a high rate is a data-quality finding, not a hidden failure.",
        ),
        MetricRow(
            measure="Change classification",
            result=f"accuracy {_pct(metrics.classification_accuracy)}",
            n=count(metrics.classification_units, "unit"),
            meaning="Insert / modify / delete against the metadata's role codes, on units both "
            "signals named. The role semantics are empirical — the authority tables publish no "
            "labels.",
        ),
    ]


def _model_rows(run: EvalRun) -> list[MetricRow]:
    model = run.model
    if model is None or model.settled.changes == 0:
        return [
            MetricRow(
                measure="Citation grounding (gate pass, no retry)",
                result="not measured",
                n="—",
                meaning="No model-layer run is recorded in this report.",
            )
        ]
    stub = " Measured over **synthetic** cassettes: this is a fact about the gate, not about "
    stub += "the pinned model."
    caveat = stub if model.synthetic else ""
    return [
        MetricRow(
            measure="Citation grounding (gate pass, no retry)",
            result=_pct(model.grounding_rate),
            n=count(model.checked, "change"),
            meaning="Of the changes with an explanation to check, the share whose first answer "
            "cited only provisions it had been offered. **Citation validity, not explanation "
            f"quality** — a wrong sentence with a good citation passes.{caveat}",
        ),
        MetricRow(
            measure="Quote-fallback rate",
            result=_pct(model.fallback_rate),
            n=count(model.checked, "change"),
            meaning="The share where the gate replaced the model's prose with a verbatim "
            "quotation of the provision after one failed retry. Correct by construction and "
            "visibly marked; this is where grounding losses go, and no change is ever dropped.",
        ),
    ]


def _faithfulness_row(run: EvalRun) -> list[MetricRow]:
    report = run.faithfulness
    if report is None:
        return [
            MetricRow(
                measure="Explanation faithfulness (sampled)",
                result="not measured",
                n="—",
                meaning="No sampled faithfulness check is recorded in this report.",
            )
        ]
    rate = report.rate
    result = "**not published**" if rate is None else f"{rate:.3f}"
    reason = (
        f"Withheld: {report.synthetic} of {report.judged} recorded judgements came from a stub "
        "model, which is a test of the judging machinery and no evidence about faithfulness."
        if rate is None
        else "The raw fraction, no confidence interval — at this n an interval would be wider "
        "than the number is useful."
    )
    return [
        MetricRow(
            measure="Explanation faithfulness (sampled)",
            result=result,
            n=f"n = {report.judged}, LLM judge + spot review ({report.human_review})",
            meaning=f"Whether the shipped sentences follow from the evidence the writer was "
            f"given: the prompt's deterministic-facts header and the two capped texts (the "
            f"header joined the evidence base on 2026-08-09, so earlier rates answer a narrower "
            f"question and are not comparable). The weakest number here: a sampled judgement by "
            f"`{report.judge_model or 'no judge'}`, which is a "
            f"different and stronger model than the explainer but not an independent one. "
            f"{reason}",
        )
    ]


def metric_rows(run: EvalRun) -> tuple[MetricRow, ...]:
    """Every published measure of one run, in the order the table prints them."""
    return (*_deterministic_rows(run), *_model_rows(run), *_faithfulness_row(run))


def synthetic_caveats(run: EvalRun) -> tuple[str, ...]:
    """The standing qualifications on this run's model layer, read off the run itself.

    The methodology page states these *above* the table as well as inside it, because a visitor
    with ninety seconds reads the sentence over the numbers before reading the cells. They are
    derived rather than written down twice: a run recorded against a real provider produces
    neither.
    """
    caveats: list[str] = []
    model = run.model
    if model is not None and model.synthetic:
        caveats.append(
            f"The {model.synthetic} recorded model responses behind the grounding and "
            f"quote-fallback figures are synthetic — recorded from a stub because no API key was "
            f"available — so those two rates describe the citation gate, not "
            f"`{model.model_id or 'the pinned model'}`."
        )
    report = run.faithfulness
    if report is not None and report.rate is None:
        caveats.append(
            f"The explanation-faithfulness rate is withheld outright rather than published: "
            f"{report.synthetic} of {report.judged} judgements came from the same stub, and the "
            f"human spot review is {report.human_review}."
        )
    return tuple(caveats)
