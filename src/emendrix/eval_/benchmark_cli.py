"""`emendrix eval judge-benchmark` and the dated report it writes.

The command that turns the committed hand review into a score for whichever judge is pinned:

```bash
uv run emendrix eval judge-benchmark          # offline: writes reports/judge-benchmark-<date>.md
```

Offline, like everything else that publishes a number here. It reads a person's verdicts from a
committed sign-off and two directories of committed judgements, joins them on the judge prompt and
writes the comparison. Recording a challenger's verdicts is the one part that costs anything, and
it happens in the recorder under `tests/`, never here.

The sign-off it defaults to is the labelled one, not the newest: the committed judgements answer
that sample's prompts and no other, so a later review is a different set of questions and needs
its own recordings before any judge can be scored on it.

Its own module rather than another command on `cli.py`, the same split `corpus_cli.py` makes: a
command that owns one artifact keeps that artifact's rendering beside it.

No clock below the command function: the date lands in the filename and in the header, and it is
read once at the boundary like every other dated artifact in this package.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Final

import typer

from emendrix.eu.http import today_utc
from emendrix.eval_.benchmark import (
    BENCHMARK_CASSETTE_DIR,
    LABELLED_JUDGE_MODEL,
    LABELLED_SIGNOFF_PATH,
    BenchmarkRow,
    JudgeScore,
    load_recorded,
    score,
)
from emendrix.eval_.judge import judge_model
from emendrix.eval_.judgements import JUDGE_CASSETTE_DIR, RUBRIC_SHA
from emendrix.eval_.prose import DISCLAIMER, count
from emendrix.eval_.signoff import ReviewSignoff, load_signoff

__all__ = ["DEFAULT_BENCHMARK_DIR", "benchmark_path", "judge_benchmark", "render_benchmark"]

DEFAULT_BENCHMARK_DIR: Final = Path("reports")

_WHAT_IT_IS = """\
**What this is.** Twenty entries, one reviewer, one afternoon, one sample of one corpus. It is a
benchmark in the sense of "the only evidence this project has about how far a judge can be
trusted", not in the sense of "a benchmark". Nothing here generalises to other prose, other
corpora or other reviewers, and at n = 20 a single entry moves the rate by 0.05, so no confidence
interval is printed: an interval would be wider than the number is useful.

**What this is not.** It is not the faithfulness rate. Faithfulness asks whether the shipped
sentences follow from the two texts; this asks whether a judge agrees with a person about that.
The two are reported in separate artifacts on purpose and neither is folded into the other. The
prose these twenty entries rule on was recorded on 2026-08-08 and superseded the same day, so this
is not a measurement of what ships now either: it is a measurement of the instrument."""

_DIRECTIONS = """\
**Lenient** means the judge called an entry faithful where the reviewer did not. It is the
direction that matters, because a lenient judge inflates every faithfulness rate it ever produces,
always upward and never visibly. **Strict** is the reverse and costs the project nothing but a
worse-looking number."""

_CRITERIA = """\
**How to read the result**, stated before it is given so that it cannot be chosen after the fact.
If the challenger beats the labelled judge's agreement *and* its misses are not systematically
lenient, the change of model did what it was chosen to do. If it does not, the rubric changes made
since the labels were taken mattered more than the model did, and that is the honest finding: the
project keeps whichever judge the evidence favours, in a separate deliberate change, and never
tries a third judge until one scores well."""


def benchmark_path(run_date: date, directory: Path = DEFAULT_BENCHMARK_DIR) -> Path:
    """`reports/judge-benchmark-YYYY-MM-DD.md`, named by the date it was written for."""
    return directory / f"judge-benchmark-{run_date.isoformat()}.md"


def _rubric(score_: JudgeScore) -> str:
    """What rubric a judge's committed verdicts were taken under, as far as they record it."""
    shown = [
        "not recorded (taken before the rubric entered the cassette key on 2026-08-08)"
        if digest == ""
        else f"`{digest[:12]}`{' (the rubric in git)' if digest == RUBRIC_SHA else ''}"
        for digest in score_.rubric_shas
    ]
    return "; ".join(shown) if shown else "no judgements"


def _comparison(challenger: JudgeScore) -> str:
    """Which of the two comparisons this run is, read off the digests rather than asserted."""
    if challenger.rubric_shas == (RUBRIC_SHA,):
        return (
            "**Which comparison this is.** The challenger answered under the rubric currently in "
            "git and the labelled judge answered under the rubric of 2026-08-08, before rubric "
            "digests were recorded and before four failure classes were spelled out in it. This "
            "therefore measures the **pair** (this model under this rubric) against the pair that "
            "produced the labels, and not the model on its own."
        )
    return (
        "**Which comparison this is.** The challenger answered under a rubric other than the one "
        "currently in git, named by digest in the table below. That is the like-for-like run: it "
        "holds the instruction fixed and **isolates the model**."
    )


def _cell(text: str) -> str:
    """One Markdown table cell: no pipe may end the column early, no newline the row."""
    return text.replace("|", "\\|").replace("\n", " ").strip() or "—"


def _tick(value: bool) -> str:
    return "faithful" if value else "**not faithful**"


def _judge_row(score_: JudgeScore) -> str:
    rate = "—" if score_.agreement_rate is None else f"{score_.agreement_rate:.3f}"
    return (
        f"| `{score_.judge_model}` | {_rubric(score_)} | {score_.agreements} / "
        f"{score_.entries} ({rate}) | {score_.misses} | {score_.lenient} | {score_.strict} |"
    )


def _misses(score_: JudgeScore) -> list[str]:
    """Every entry one judge got wrong, with the direction and what it said instead."""
    wrong = [row for row in score_.rows if not row.agrees]
    if not wrong:
        return [f"`{score_.judge_model}` disagreed with the reviewer on none of the entries.", ""]
    lines = [f"`{score_.judge_model}` disagreed with the reviewer on {len(wrong)}:", ""]
    lines.extend(
        f"- **{row.number}. {row.slug}** — {'lenient' if row.lenient else 'strict'}; the judge "
        f"said `faithful={str(row.judge).lower()}`"
        f"{f' ({row.issue})' if row.issue else ''}. The reviewer said "
        f"`faithful={str(row.human).lower()}`{f': {row.note}' if row.note else '.'}"
        for row in wrong
    )
    lines.append("")
    return lines


def _entry_rows(labelled: JudgeScore, challenger: JudgeScore) -> list[str]:
    """The per-entry table. Joined by sheet position, which both scores carry from the sign-off."""
    challenged = {row.number: row for row in challenger.rows}
    lines = [
        f"| # | Change | Reviewer | `{labelled.judge_model}` | `{challenger.judge_model}` | "
        "Reviewer's note |",
        "|---|---|---|---|---|---|",
    ]
    for row in labelled.rows:
        other: BenchmarkRow | None = challenged.get(row.number)
        lines.append(
            f"| {row.number} | `{_cell(row.slug)}` | {_tick(row.human)} | {_tick(row.judge)} | "
            f"{'—' if other is None else _tick(other.judge)} | {_cell(row.note)} |"
        )
    return lines


def _entries(number: int) -> str:
    """`entry`/`entries`, the one noun in these reports that plus-`s` gets wrong."""
    return count(number, "entry", "entries")


def _verdict(labelled: JudgeScore, challenger: JudgeScore) -> str:
    """The result in one sentence, derived from the counts and never softened."""
    lead = (
        f"**The result.** The challenger agreed with the reviewer on {challenger.agreements} of "
        f"{challenger.entries} where the labelled judge agreed on {labelled.agreements} of "
        f"{labelled.entries}"
    )
    if challenger.agreements > labelled.agreements:
        direction = (
            "systematically lenient still"
            if challenger.lenient > challenger.strict
            else "not systematically lenient"
        )
        return (
            f"{lead}, so it is **better** on this set, and its misses are {direction} "
            f"({challenger.lenient} lenient, {challenger.strict} strict). A difference of "
            f"{_entries(challenger.agreements - labelled.agreements)} at n = "
            f"{challenger.entries} is weak evidence, and it is the only evidence there is."
        )
    if challenger.agreements < labelled.agreements:
        return (
            f"{lead}, so it is **worse** on this set by "
            f"{_entries(labelled.agreements - challenger.agreements)} "
            f"({challenger.lenient} lenient, {challenger.strict} strict). The rubric changes "
            "mattered more than the model did, and this is published as measured."
        )
    return (
        f"{lead}, so the two are **indistinguishable** on this set "
        f"({challenger.lenient} lenient, {challenger.strict} strict against the labelled judge's "
        f"{labelled.lenient} and {labelled.strict}). At n = 20 an equal count is not evidence "
        "that the two judges are alike, only that this sample did not separate them."
    )


def render_benchmark(
    signoff: ReviewSignoff,
    labelled: JudgeScore,
    challenger: JudgeScore,
    run_date: date,
    *,
    signoff_path: Path = LABELLED_SIGNOFF_PATH,
) -> str:
    """The whole report as one Markdown string. Deterministic given its inputs.

    `signoff_path` is named in the header so a reader can open the labels: sign-offs accumulate
    one per review, and "the sign-off" stopped being an address on 2026-08-08.
    """
    lines = [
        f"# Judge benchmark — {run_date.isoformat()}",
        "",
        f"- **Labels** — {signoff.worksheet}, reviewed by {signoff.reviewer} on "
        f"{signoff.reviewed_on.isoformat()}, transcribed verdict by verdict into "
        f"`{signoff_path.name}` beside it.",
        f"- **Entries** — {len(signoff.entries)}, joined to each judge by `sha256` of the judge "
        "prompt, so a judge is scored on the exact strings the reviewer read.",
        f"- **Recorded judgements no entry claims** — {len(labelled.unmapped)} for the labelled "
        f"judge, {len(challenger.unmapped)} for the challenger; counted here rather than dropped.",
        "",
        _WHAT_IT_IS,
        "",
        _comparison(challenger),
        "",
        "## Judges",
        "",
        "| Judge | Rubric | Agreement | Misses | Lenient | Strict |",
        "|---|---|---|---|---|---|",
        _judge_row(labelled),
        _judge_row(challenger),
        "",
        _DIRECTIONS,
        "",
        _CRITERIA,
        "",
        _verdict(labelled, challenger),
        "",
        "## Where each judge disagreed with the reviewer",
        "",
        *_misses(labelled),
        *_misses(challenger),
        "## Entry by entry",
        "",
        *_entry_rows(labelled, challenger),
        "",
        "---",
        "",
        DISCLAIMER,
        "",
    ]
    return "\n".join(lines)


def judge_benchmark(
    challenger: Annotated[
        str | None,
        typer.Option("--challenger", help="Judge to score. Defaults to the configured one."),
    ] = None,
    signoff_path: Annotated[
        Path, typer.Option("--signoff", help="The committed hand review, and the label set.")
    ] = LABELLED_SIGNOFF_PATH,
    report_dir: Annotated[
        Path, typer.Option("--report-dir", help="Where the dated report is written.")
    ] = DEFAULT_BENCHMARK_DIR,
    run_date: Annotated[
        datetime | None,
        typer.Option("--date", formats=["%Y-%m-%d"], help="Report date. Defaults to today (UTC)."),
    ] = None,
    write: Annotated[
        bool, typer.Option("--write/--no-write", help="Write the dated Markdown report.")
    ] = True,
) -> None:
    """Score the judges against the committed hand review and write the dated comparison.

    Offline: two directories of committed judgements and one sign-off, joined on the prompt. A
    judge with no recorded answer for every labelled entry is refused rather than scored over
    the entries it happens to have.
    """
    signoff = load_signoff(signoff_path)
    if signoff is None or not signoff.entries:
        typer.echo(f"no hand review with per-entry verdicts at {signoff_path}", err=True)
        raise typer.Exit(code=1)
    other = challenger if challenger is not None else judge_model()
    labelled = score(
        signoff,
        load_recorded(JUDGE_CASSETTE_DIR, LABELLED_JUDGE_MODEL),
        judge_model=LABELLED_JUDGE_MODEL,
    )
    scored = score(signoff, load_recorded(BENCHMARK_CASSETTE_DIR, other), judge_model=other)
    stamp = run_date.date() if run_date is not None else today_utc()
    typer.echo(
        f"{labelled.judge_model} {labelled.agreements}/{labelled.entries} · "
        f"{scored.judge_model} {scored.agreements}/{scored.entries} · "
        f"lenient {labelled.lenient} vs {scored.lenient}"
    )
    if not write:
        return
    report_dir.mkdir(parents=True, exist_ok=True)
    path = benchmark_path(stamp, report_dir)
    path.write_text(
        render_benchmark(signoff, labelled, scored, stamp, signoff_path=signoff_path),
        encoding="utf-8",
    )
    typer.echo(str(path))
