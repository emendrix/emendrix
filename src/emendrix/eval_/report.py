"""Writing the dated report: `reports/eval/YYYY-MM-DD-<sha>.{md,json}`, committed.

Two files, one run. The JSON is the machine-readable record every published number is generated
from: `readme_table.py` builds the README's metrics section out of the latest committed one and
never by hand. The Markdown is the same run written for a person, and it carries the
disagreement list verbatim because a disagreement is either a bug or a data-quality find and
both are publishable.

**Byte-stable by construction.** Nothing here reads a clock: the date in the filename and in the
header is passed in from the CLI boundary and the revision comes from git, so two runs of the same
corpus at the same commit produce identical bytes. Floats are formatted to a fixed number of
decimals in the Markdown and left exact in the JSON.

The report is **layered**: the deterministic sections first, then the model layer's grounding
figures and the sampled faithfulness check, in one file so a regression localises to a layer
rather than to "the pipeline". `model_report.py` renders the last two.

What the report *says*, as opposed to what it counts, lives in `prose.py`: the rigour table, the
five caveats and the four known classes of disagreement are fixed text that does not soften when
the numbers come out well.
"""

from __future__ import annotations

from pathlib import Path

from emendrix.core import Signal
from emendrix.eval_.aggregate import EvalMetrics, PairMetrics
from emendrix.eval_.corpus import EvalCorpus
from emendrix.eval_.model_report import render_faithfulness, render_model_layer
from emendrix.eval_.prose import DISCLAIMER, KNOWN_CLASSES, MEANING
from emendrix.eval_.runner import EvalRun

__all__ = ["DEFAULT_REPORT_DIR", "render_markdown", "write_report"]

DEFAULT_REPORT_DIR = Path("reports/eval")


def _pct(value: float | None, places: int = 3) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def _pair_row(label: str, pair: PairMetrics | None) -> str:
    if pair is None:
        return f"| {label} | — | — | — | — | 0 |"
    return (
        f"| {label} | {pair.micro_precision:.3f} | {pair.micro_recall:.3f} "
        f"| {pair.micro_f1:.3f} | {pair.macro_f1:.3f} | {pair.cases} |"
    )


def _headline(metrics: EvalMetrics) -> list[str]:
    return [
        "## Headline",
        "",
        "At top-level-provision granularity (article or annex), over the committed corpus.",
        "",
        "| Pairing | Micro P | Micro R | Micro F1 | Macro F1 | n transitions |",
        "|---|---|---|---|---|---|",
        _pair_row("Localisation — diff vs corpus metadata", metrics.localisation),
        _pair_row("Cross-check — diff vs instruction parse", metrics.instruction_agreement),
        _pair_row("Cross-check — metadata vs instruction parse", metrics.metadata_instruction),
        "",
        f"- **Change classification** — accuracy {_pct(metrics.classification_accuracy)} "
        f"over {metrics.classification_units} units both signals named.",
        f"- **Disputed changes** — {metrics.disputed} of {metrics.changes} shipped changes "
        f"({metrics.dispute_rate:.3f}); nothing was dropped to reach that number.",
        f"- **Diff-only units** — {metrics.diff_only_units}, reported as their own class and "
        "**not** as false positives (see point 2 above).",
        f"- **Metadata-only units** — {metrics.metadata_only_units}, shipped as changes with a "
        "location, a kind and no text.",
        f"- **Reference labels consumed** — {metrics.annotations} modification annotations.",
        "",
    ]


def _coverage(run: EvalRun, corpus: EvalCorpus) -> list[str]:
    metrics = run.metrics
    parser = metrics.parser
    lines = [
        "## Coverage",
        "",
        f"- **Corpus** — {metrics.cases} transitions of the "
        f"{run.corpus_transitions_possible} the four acts offer "
        f"({run.corpus_coverage:.3f}); {metrics.cases_scored} scored.",
        f"- **Third signal** — read on {metrics.instruction_cases} of {metrics.cases} "
        f"transitions, with {metrics.instruction_unread} instruction-looking clauses unread.",
        f"- **Parser** — {parser.documents} documents, {parser.units} units, {parser.nodes} "
        f"located nodes; {parser.unknown_elements} unknown elements, "
        f"{parser.unmapped_identifiers} unmapped identifiers, "
        f"{parser.documents_unreadable} unreadable documents.",
        "",
        "### Versions the corpus could not read",
        "",
    ]
    if not corpus.skips:
        lines.extend(("None.", ""))
        return lines
    lines.extend(("| Act | Version | State | Detail |", "|---|---|---|---|"))
    lines.extend(
        f"| {skip.act} | {skip.version} | `{skip.reason}` | {skip.detail} |"
        for skip in corpus.skips
    )
    lines.append("")
    return lines


def _per_act(metrics: EvalMetrics) -> list[str]:
    lines = [
        "## Per act",
        "",
        "| Act | Transitions | Micro F1 | Macro F1 | Changes | Disputed | Diff-only | Meta-only |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for act in metrics.per_act:
        pair = act.localisation
        lines.append(
            f"| `{act.act}` | {act.cases_scored}/{act.cases} "
            f"| {_pct(None if pair is None else pair.micro_f1)} "
            f"| {_pct(None if pair is None else pair.macro_f1)} "
            f"| {act.changes} | {act.disputed} | {act.diff_only_units} "
            f"| {act.metadata_only_units} |"
        )
    lines.append("")
    return lines


def _per_case(run: EvalRun) -> list[str]:
    lines = [
        "## Per transition",
        "",
        "| Transition | From | To | Diff | Metadata | Shared | P | R | F1 | Disputed |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for case in run.cases:
        if not case.scored or case.report is None:
            lines.append(
                f"| `{case.case_id}` | {case.from_version} | {case.to_version} | — | — | — "
                f"| — | — | — | not scored: `{case.state}` |"
            )
            continue
        pair = case.report.agreement_of(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA)
        numbers = (
            "— | — | — | — | —"
            if pair is None
            else (
                f"{pair.left_units} | {pair.right_units} | {pair.shared} "
                f"| {pair.precision:.3f} | {pair.recall:.3f} | {pair.f1:.3f}"
            )
        )
        lines.append(
            f"| `{case.case_id}` | {case.from_version} | {case.to_version} "
            f"| {numbers} | {case.disputed} |"
        )
    lines.append("")
    return lines


def _confusion(metrics: EvalMetrics) -> list[str]:
    if not metrics.confusion:
        return []
    lines = [
        "## Classification, cell by cell",
        "",
        "Rows are what the structural diff said, columns what the metadata said, on units both "
        "named. `MIXED` is a unit the metadata gives more than one role.",
        "",
        "| Diff | Metadata | Units |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| `{cell.diff}` | `{cell.metadata}` | {cell.count} |" for cell in metrics.confusion
    )
    lines.append("")
    return lines


def _disagreements(run: EvalRun) -> list[str]:
    lines = [
        "## Disagreements, verbatim",
        "",
        "Every unit the signals do not agree about. Each one is either a defect in a signal or a "
        "defect in the reference set, and which is an empirical question — none of them was "
        "curated out.",
        "",
    ]
    empty = True
    for case in run.cases:
        if case.report is None or not case.report.disagreements:
            continue
        empty = False
        lines.extend((f"### `{case.case_id}`", "", "| Unit | Reason |", "|---|---|"))
        lines.extend(
            f"| `{item.unit.canonical}` | {item.reason} |" for item in case.report.disagreements
        )
        lines.append("")
    if empty:
        lines.extend(("None.", ""))
    return lines


def _per_subset_case(run: EvalRun) -> list[str]:
    """The model layer transition by transition, so a rate can be traced to a delta."""
    if run.model is None or not run.model.cases:
        return []
    lines = [
        "### Model layer, transition by transition",
        "",
        "| Transition | Units | Passed | On retry | Fallback | Unexplained | Missing |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in run.model.cases:
        if not case.scored:
            lines.append(
                f"| `{case.case_id}` | {case.units} | — | — | — | — | not scored: `{case.state}` |"
            )
            continue
        stats = case.settled
        lines.append(
            f"| `{case.case_id}` | {case.units} | {stats.passed_first} "
            f"| {stats.passed_on_retry} | {stats.fallback} | {stats.unexplained} "
            f"| {len(case.missing_units)} |"
        )
    lines.append("")
    return lines


def render_markdown(run: EvalRun, corpus: EvalCorpus) -> str:
    """The whole report as one Markdown string. Deterministic: no clock, no set iteration."""
    header = [
        "# emendrix — eval report",
        "",
        f"- **Run date** — {run.run_date.isoformat()} (passed in, not read from a clock)",
        f"- **Revision** — `{run.revision}`",
        f"- **Corpus built** — {run.corpus_built_on.isoformat()}, "
        f"{len(corpus.cases)} transitions over {len(corpus.acts)} acts",
        "- **Reproduce** — `uv run emendrix eval run --fixture-dir tests/fixtures/eu`",
        "",
        MEANING,
    ]
    body = [
        *_headline(run.metrics),
        KNOWN_CLASSES,
        *_per_act(run.metrics),
        *_confusion(run.metrics),
        *_coverage(run, corpus),
        *_per_case(run),
        *_disagreements(run),
        *render_model_layer(run.model),
        *_per_subset_case(run),
        *render_faithfulness(run.faithfulness, "" if run.model is None else run.model.model_id),
        "---",
        "",
        DISCLAIMER,
        "",
    ]
    return "\n".join((*header, *body))


def write_report(
    run: EvalRun, corpus: EvalCorpus, directory: Path = DEFAULT_REPORT_DIR
) -> tuple[Path, Path]:
    """Write both files and return their paths. Re-running at one revision rewrites both."""
    directory.mkdir(parents=True, exist_ok=True)
    markdown = directory / f"{run.slug}.md"
    payload = directory / f"{run.slug}.json"
    markdown.write_text(render_markdown(run, corpus), encoding="utf-8")
    payload.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return markdown, payload
