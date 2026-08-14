"""The model-layer sections of the eval report: grounding, the retry, the fallback, faithfulness.

One report, layered sections: the deterministic numbers and the model numbers are written into
the same dated file so a regression localises to a layer instead of to "the pipeline". Split out
of `report.py`, which renders the deterministic layer, because both together would be one
500-line module.

Two rules this module exists to enforce:

- **Grounding and faithfulness never share a row, a heading or a sentence.** They are printed
  under separate headings with their own caveats, in that order, and the grounding heading says
  in its first line that it measures citation validity and not explanation quality.
- **A rate produced by a stub is labelled where it is printed**, not in a footnote. When the
  subset's cassettes are synthetic every grounding number carries the warning inline, and the
  faithfulness rate is withheld outright — `FaithfulnessReport.publishable` decides, not this
  renderer's judgement about what looks acceptable.

No clock: everything here is a pure function of the numbers it is handed.
"""

from __future__ import annotations

from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.model_metrics import ModelMetrics
from emendrix.eval_.signoff import PENDING
from emendrix.explain import rate_for

__all__ = ["render_faithfulness", "render_model_layer"]

_SIGNOFF = (
    " The line above is a person's own, transcribed into the newest "
    "`reports/faithfulness-signoff-<date>.json` with their verdict on each of the sampled "
    "triples, and it is published only while that file's digest still matches the sample this "
    "run built. Re-record a cassette or re-pin the subset and it goes back to `pending` on its "
    "own."
)
"""Where a review claim comes from, printed only when there is one. A report that says a review
happened has to say what would make that claim stop being true."""

_SYNTHETIC_WARNING = (
    "> **These numbers were measured over synthetic cassettes.** The pinned subset was recorded "
    "from a stub model because no API key was available, and every cassette says `synthetic: "
    "true` in its own JSON. What they measure is the *gate*: that every citation it was offered "
    "was checked, that every rejection was retried once, and that every change that failed twice "
    "shipped a verbatim quotation instead. They say nothing whatsoever about the pinned model. "
    "Re-record the subset against it and this warning disappears on its own."
)

_MEANING = """\
**What this measures.** Citation grounding is a property of the *pipeline*, not of the
explanation: a sentence passes when every key it cites was one of the keys this change offered,
and it is checked against the two provision trees the run already fetched. A factually wrong
sentence with a valid citation passes, and it is meant to — whether a sentence follows from the
texts is faithfulness, measured further down and against a different reference.

**What "no retry" means.** The grounding rate below counts changes whose *first* explanation
passed. The gate then asks once more, with its own complaint attached, and quotes the provision
verbatim if that fails too — so the fallback rate is where the losses go, and no change is ever
dropped for failing this check.
"""


_SHARED_VENDOR = "Not independent of it: same vendor, same lineage, shared blind spots."
_CROSS_VENDOR = (
    "A different vendor as well, which is the strongest form of this claim the project has "
    "and still not independence: both models read the same English, so a shared misreading "
    "remains available to them."
)
_VENDOR_UNKNOWN = (
    "Not independent of it: a second model reading the same English, with a shared misreading "
    "still available to it."
)


def _vendor(model_id: str) -> str:
    """The vendor segment of a provider-qualified id, or empty when it has no such shape.

    `openrouter:anthropic/claude-sonnet-5` is the vendor `anthropic` reached through the
    provider `openrouter`, and the distinction is the whole point of the sentence this feeds:
    routing two models through one gateway does not make them one lineage.
    """
    _, _, rest = model_id.partition(":")
    vendor, separator, _ = rest.partition("/")
    return vendor if separator else ""


def _independence(judge: str, explainer: str) -> str:
    """What the judge and the explainer being these two models does and does not buy.

    Derived from the two ids rather than written down, because a written-down claim goes on
    asserting a shared vendor after the judge has moved to another one.
    """
    judge_vendor, explainer_vendor = _vendor(judge), _vendor(explainer)
    if not judge_vendor or not explainer_vendor:
        return _VENDOR_UNKNOWN
    return _SHARED_VENDOR if judge_vendor == explainer_vendor else _CROSS_VENDOR


def _rate(value: float | None, places: int = 3) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def _row(label: str, value: float | None, n: str, meaning: str) -> str:
    return f"| {label} | {_rate(value)} | {n} | {meaning} |"


def render_model_layer(metrics: ModelMetrics | None) -> list[str]:
    """The grounding section. Empty when no model-layer run was made."""
    if metrics is None or metrics.settled.changes == 0:
        return []
    checked = metrics.checked
    lines = [
        "## Model layer — citation grounding",
        "",
        f"Over the pinned explanation subset ({metrics.changes} changes of "
        f"{len(metrics.cases)} transitions), replayed from committed cassettes with model "
        f"`{metrics.model_id}`.",
        "",
    ]
    if metrics.synthetic:
        lines.extend((_SYNTHETIC_WARNING, ""))
    lines.extend(
        (
            _MEANING,
            "",
            "| Measure | Rate | n | What it does and does not mean |",
            "|---|---|---|---|",
            _row(
                "Citation grounding (gate pass, no retry)",
                metrics.grounding_rate,
                f"{checked} changes",
                "Of the changes with an explanation to check, the share whose first answer "
                "cited only keys it had been offered. Not explanation quality.",
            ),
            _row(
                "Retry recovery",
                metrics.retry_recovery_rate,
                f"{metrics.settled.retries} retried",
                "Of the changes the gate sent back with a complaint, the share that came back "
                "grounded. One retry is the policy; there is never a third attempt.",
            ),
            _row(
                "Quote fallback",
                metrics.fallback_rate,
                f"{checked} changes",
                "The share that shipped the gate's own verbatim quotation of the provision "
                "instead of the model's prose. Correct by construction, and visibly marked.",
            ),
            _row(
                "Citation validity (first round)",
                metrics.citation_validity,
                f"{metrics.first_round.citations} keys",
                "Individual citation keys that resolved, rather than whole sentences. A "
                "sentence fails if any one of its keys does.",
            ),
            "",
            f"- **Changes with nothing to explain** — {metrics.unexplained} of "
            f"{metrics.settled.changes}; they keep their slot and ship without sentences.",
            f"- **Schema repairs** — {metrics.schema_repairs} malformed structured outputs "
            "pydantic-ai had to ask again for.",
            f"- **Prompts a character cap trimmed** — {metrics.truncated}, each marked in the "
            "prompt the model saw.",
            f"- **Prompts the cap left with no evidence in them** — {metrics.no_evidence}; the "
            "whole difference fell beyond the characters the stage can show, so the two texts "
            "were identical, no model was asked, and the change ships with its verbatim before "
            "and after and no sentences.",
            f"- **Applicability notes dropped** — {metrics.settled.notes_dropped}; a note the "
            "model wrote that does not appear in the after text it was shown, dropped rather "
            "than published.",
            f"- **Coordinates named without support** — "
            f"{metrics.settled.coordinates_unsupported}; paragraph coordinates a shipped "
            "sentence names that neither the structural diff localised nor the capped text "
            "the model was shown contains, on either side. Counted per coordinate, not per "
            "sentence, and counted only: no sentence is dropped or rewritten for it. The "
            "number is a floor, twice over. The recogniser reads coordinates off model "
            "prose alone, and a mention it misses is never counted. And a coordinate whose "
            "own text was visible on one shown side counts as supported, so a false claim "
            "about a visible paragraph is not counted here: whether a sentence follows "
            "from the texts is measured further down, against a different reference. A "
            "zero is a fact about this corpus, not about the check: at a cap the texts "
            "rarely overrun, nearly every coordinate is visible, so a zero means the "
            "prompts stopped exercising the check, and synthetic tests are what keep it "
            "able to fire.",
            f"- **Pinned units this run's deltas no longer contain** — {metrics.missing_units}.",
            f"- **Every change settled** — {'yes' if metrics.settled_all else 'NO — a bug'}; "
            f"{metrics.settled.settled} of {metrics.settled.changes} left the gate with a final "
            "answer.",
            _cost(metrics),
            "",
        )
    )
    return lines


def _cost(metrics: ModelMetrics) -> str:
    """What the recording run cost, at the rate `explain/settings.py` has written down.

    The date comes from the rate that produced the figure rather than from a literal, so
    re-verifying a price cannot leave a stale date standing next to a dollar amount.
    """
    usage = metrics.usage
    tokens = f"{usage.input_tokens} in / {usage.output_tokens} out"
    rate = rate_for(metrics.model_id)
    if metrics.recording_cost_usd is None or rate is None:
        return f"- **Recording run** — {tokens} tokens; unpriced (no published rate on file)."
    return (
        f"- **Recording run** — {tokens} tokens, **${metrics.recording_cost_usd:.4f}** at the "
        f"rate published for `{metrics.model_id}` and checked on "
        f"{rate.checked_on.isoformat()}. Replay costs nothing and the tokens are not charged "
        f"again."
    )


def render_faithfulness(report: FaithfulnessReport | None, explainer: str = "") -> list[str]:
    """The faithfulness section — printed apart from grounding, and never merged into it.

    `explainer` is the model whose prose is being judged, and it is here only so the
    independence caveat can be read off the two ids instead of asserted. An empty string is
    "this run scored no model layer", and the caveat then claims nothing about vendors.
    """
    if report is None:
        return []
    lines = [
        "## Model layer — explanation faithfulness (sampled, weak signal)",
        "",
        "A different question from the one above, with no free ground truth. Each sampled entry "
        "is shown to an LLM judge as the evidence the writer was given — the deterministic-facts "
        "header the writer's prompt opened with, the before text, the after text and the "
        "surrounding-context block when the entry carries one — plus the "
        "sentences that shipped, and to a human reviewer as the same strings in a worksheet. "
        "The question is whether every sentence follows from that evidence, with one boundary: "
        "the header grounds claims about *which* provisions changed, and only the two texts "
        "ground claims about *what the words say*. The citation keys reach neither auditor.",
        "",
        "The texts are the ones the explainer was shown, character cap and truncation "
        "marker included, so a sentence is judged against the evidence the model had. Judging "
        "it against more would credit the model for text it never read; judging it against "
        "less, which this harness did until the caps were made one, marks accurate sentences "
        "unfaithful on exactly the longest provisions and reports it as explanation quality. "
        "The header joined the evidence base on 2026-08-09; until then the judge was asked "
        "about the two texts alone, so a rate recorded before that date answers a narrower "
        "question and is not comparable with one recorded after it.",
        "",
        f"- **Judge** — `{report.judge_model or 'none'}`, a different and stronger model than "
        f"the explainer. {_independence(report.judge_model, explainer)}",
        f"- **Sampled** — {report.sampled} triples, spread evenly over the subset; "
        f"{report.judged} carry a recorded judgement.",
        f"- **Of those, gate-written quotations** — {report.fallback_triples}, which are "
        "faithful by construction and are counted rather than excluded.",
        f"- **Human spot review** — {report.human_review}"
        f"{f' ({report.worksheet})' if report.worksheet else ''}. Generated unticked; nothing "
        f"in emendrix ticks it.{_SIGNOFF if report.human_review != PENDING else ''}",
        "",
    ]
    if report.rate is None:
        lines.extend(
            (
                f"**No faithfulness rate is published.** {report.synthetic} of "
                f"{report.judged} recorded judgements came from a stub model, which is a test of "
                "the judging machinery and no evidence about faithfulness. A number here would "
                "be a number that does not mean what its name says, so there is none — the "
                "grounding figures above are treated differently on purpose, because the gate "
                "is deterministic whatever produced the sentences it ruled on.",
                "",
            )
        )
        return lines
    lines.extend(
        (
            f"**Faithful: {report.faithful} of {report.judged}** "
            f"({report.rate:.3f}). The raw fraction, with no confidence interval: at n = "
            f"{report.judged} an interval would be wider than the number is useful, and dressing "
            "it up would be false precision. This is the weakest number in the report and it is "
            "printed last on purpose.",
            "",
        )
    )
    return lines
