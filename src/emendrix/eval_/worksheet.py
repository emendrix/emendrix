"""The human spot-review worksheet: the only genuinely independent check on faithfulness.

An LLM judge and the model it judges share a training lineage; a person reading the two texts
does not. So every sampled triple is also written out as a Markdown checklist for the author to
work through by hand, and the report says `human review: pending` until that has happened.

**It is generated unticked, and nothing in this repository ticks it.** A review the tool marks
as done on its own behalf would be worth less than no review at all, which is why the state is
in the report, in the open, alongside the judged numbers it is supposed to keep honest.

Nothing here unticks one either: `write_worksheet` refuses to overwrite a sheet that carries a
tick. The sheet is named by the run date, so without that refusal a second `eval run` on the day
of a review would erase the review.

Byte-stable and clock-free: the date in the filename comes from the CLI boundary, and every text
is quoted exactly as the model was shown it, carrying the explain stage's own truncation marker
where the cap bit. The reviewer is answering "do these sentences follow from the evidence the
writer was given?", so quoting more of the provision than the model got would invite a tick the
run does not deserve, and quoting less invites a cross for text the model was right about. The
surrounding-provision block is quoted for the same reason and under the same heading the judge
sees, and it is omitted rather than shown empty on the changes that carry none, which is all of
them in this corpus so far. The pipeline header is quoted first and under the judge's own heading
for it, because the writer's prompt opened with it and a reviewer not shown it would be asked to
cross every sentence resting on it; it joined the sheet on 2026-08-09.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

from emendrix.eval_.judge import FaithfulnessReport, Triple
from emendrix.eval_.prose import DISCLAIMER
from emendrix.eval_.rubric import CONTEXT_LABEL, HEADER_LABEL, JUDGE_RUBRIC

__all__ = [
    "DEFAULT_WORKSHEET_DIR",
    "render_worksheet",
    "worksheet_is_reviewed",
    "worksheet_path",
    "write_worksheet",
]

DEFAULT_WORKSHEET_DIR = Path("reports")

_TICKS: Final = ("- [x]", "- [X]")
"""A ticked checkbox, in either case. Nothing in this package writes one."""


def worksheet_path(run_date: date, directory: Path = DEFAULT_WORKSHEET_DIR) -> Path:
    """`reports/faithfulness-review-YYYY-MM-DD.md`, named by the date it was generated for."""
    return directory / f"faithfulness-review-{run_date.isoformat()}.md"


def worksheet_is_reviewed(path: Path) -> bool:
    """Whether a sheet at this path carries a tick, and is therefore somebody's work."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return any(tick in text for tick in _TICKS)


def _quote(label: str, text: str) -> list[str]:
    """One side of the change, as shown to the model. Any truncation marker is already in it."""
    if not text:
        return [f"**{label}** — none (this side of the change does not exist).", ""]
    return [f"**{label}**", "", "```", text, "```", ""]


def render_worksheet(
    triples: Sequence[Triple], report: FaithfulnessReport, run_date: date, revision: str
) -> str:
    """The whole worksheet as one Markdown string. Deterministic given its inputs."""
    verdicts = {(item.case_id, item.unit): item for item in report.judgements}
    lines = [
        f"# Faithfulness spot review — {run_date.isoformat()}",
        "",
        f"- **Revision** — `{revision}`",
        f"- **Judge** — `{report.judge_model or 'none recorded'}`",
        f"- **Sampled** — {len(triples)} of the pinned explanation subset",
        "- **Status** — unticked. This sheet is generated empty and filled in by a person; "
        "nothing in emendrix ticks a box on its own behalf.",
        "",
        "For each entry below: read the evidence the writer was given (the pipeline header, "
        "the two texts, and the surrounding context when there is one), read the sentences "
        "that shipped, and tick **Faithful** only if every published sentence follows from "
        "the evidence the writer was given. The header states what a structural diff "
        "established: which provision this is, what type of change it is, and which "
        "sub-provisions differ. Treat it as true. It grounds a claim about which provisions "
        "changed. It grounds no claim about what the words say: for that, only the two texts "
        "count. A sentence that reports a coordinate from the header and declines to describe "
        "it is faithful. The judge's own verdict is printed beside each entry so the two can "
        "be compared; read the evidence first.",
        "",
        "The rubric the LLM judge was given, verbatim:",
        "",
        "```",
        JUDGE_RUBRIC,
        "```",
        "",
        "---",
        "",
    ]
    for index, triple in enumerate(triples, start=1):
        judged = verdicts.get((triple.case_id, triple.unit))
        verdict = (
            "no judgement recorded"
            if judged is None or judged.verdict is None
            else (
                f"`faithful={str(judged.verdict.faithful).lower()}`"
                f"{'' if judged.verdict.issue is None else f' — {judged.verdict.issue}'}"
                f"{' *(synthetic — a stub produced it)*' if judged.synthetic else ''}"
            )
        )
        lines.extend(
            [
                f"## {index}. `{triple.case_id}` — `{triple.unit}`",
                "",
                f"- Change type: `{triple.change_type}` · gate outcome: `{triple.outcome}`"
                f"{' · carries a gate-written quotation' if triple.fallback else ''}",
                f"- LLM judge: {verdict}",
                "",
                *(_quote(HEADER_LABEL, triple.header) if triple.header else ()),
                *_quote("Before", triple.before),
                *_quote("After", triple.after),
                *(_quote(CONTEXT_LABEL, triple.context) if triple.context else ()),
                "**Shipped sentences**",
                "",
                *(f"{number}. {text}" for number, text in enumerate(triple.sentences, start=1)),
                "",
                "- [ ] Faithful",
                "- [ ] Not faithful — reason: ",
                "",
            ]
        )
    lines.extend(("---", "", DISCLAIMER, ""))
    return "\n".join(lines)


def write_worksheet(
    triples: Sequence[Triple],
    report: FaithfulnessReport,
    *,
    run_date: date,
    revision: str,
    directory: Path = DEFAULT_WORKSHEET_DIR,
) -> Path:
    """Write the worksheet and return its path. A sheet somebody has ticked is left alone.

    Re-running at one date would otherwise rewrite the sheet under that date, and the sheet is
    the only genuinely independent evidence the faithfulness row has: an afternoon of reading two
    texts per entry, unrecoverable except from git. A generated artifact never outranks a
    hand-made one, so a ticked sheet wins and this returns its path untouched.

    Not an error, deliberately. `emendrix eval run` is a routine command and failing it on the
    day of a review would push people towards `--no-write`, which writes no report either.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = worksheet_path(run_date, directory)
    if worksheet_is_reviewed(path):
        return path
    path.write_text(render_worksheet(triples, report, run_date, revision), encoding="utf-8")
    return path
