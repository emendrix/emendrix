"""The README's metrics section is generated, and this is what makes that true.

The first test is the important one and it is deliberately blunt: regenerate the section from the
newest committed report and assert the file on disk is byte-identical. A number nudged upward by
hand does not survive it, which is the only enforcement mechanism honesty rule 1 can actually
have in a repository where the author is also the reviewer.

The rest check the properties the table must keep: every row carries the sentence saying what it
does and does not mean, a withheld faithfulness rate stays withheld, and the section is spliced
rather than appended.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from emendrix.eval_.aggregate import EvalMetrics
from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.model_metrics import ModelMetrics
from emendrix.eval_.readme_table import (
    END,
    START,
    latest_report,
    regenerate,
    render_metrics,
    splice,
)
from emendrix.eval_.runner import EvalRun
from emendrix.gate import GateStats

REPO = Path(__file__).resolve().parents[2]


def test_the_committed_readme_section_is_what_the_newest_report_renders() -> None:
    """`uv run emendrix eval publish-readme` is the only way a number reaches the README."""
    current, updated, report = regenerate(REPO / "README.md", REPO / "reports" / "eval")
    assert current == updated, (
        f"README.md is out of date with {report.name}; run `uv run emendrix eval publish-readme` "
        f"rather than editing between the sentinels"
    )


def test_regenerating_twice_changes_nothing_the_second_time() -> None:
    current, updated, _ = regenerate(REPO / "README.md", REPO / "reports" / "eval")
    assert splice(updated, _section(updated)) == current


def _section(readme: str) -> str:
    return readme[readme.index(START) : readme.index(END) + len(END)]


def _run(**updates: object) -> EvalRun:
    return EvalRun(
        run_date=date(2026, 8, 6),
        revision="abc1234",
        corpus_built_on=date(2026, 8, 6),
        metrics=EvalMetrics(cases=18, cases_scored=18, changes=100, disputed=30),
        **updates,  # type: ignore[arg-type]
    )


def test_every_row_carries_the_sentence_that_says_what_it_does_not_mean() -> None:
    settled = GateStats(changes=10, passed_first=9, fallback=1, retries=1)
    section = render_metrics(
        _run(
            model=ModelMetrics(model_id="m", changes=10, first_round=settled, settled=settled),
            faithfulness=FaithfulnessReport(judge_model="j", sampled=20, judged=20, faithful=18),
        ),
        Path("reports/eval/2026-08-06-abc1234.json"),
    )
    rows = [line for line in section.splitlines() if line.startswith("| ") and "---" not in line]
    header, body = rows[0], rows[1:]

    assert "What it means — and what it does not" in header
    assert len(body) == 7  # localisation, cross-check, disputed, classification, 2 model, 1 judge
    for row in body:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert len(cells) == 4, row
        assert len(cells[3]) > 60, f"row without a meaning sentence: {cells[0]}"


def test_the_grounding_row_never_claims_to_be_about_explanation_quality() -> None:
    settled = GateStats(changes=10, passed_first=9, fallback=1, retries=1)
    section = render_metrics(
        _run(model=ModelMetrics(model_id="m", changes=10, first_round=settled, settled=settled)),
        Path("reports/eval/2026-08-06-abc1234.json"),
    )
    grounding = next(
        line for line in section.splitlines() if line.startswith("| Citation grounding")
    )
    assert "Citation validity, not explanation quality" in grounding.replace("**", "")
    assert "0.900" in grounding


def test_a_synthetic_run_says_so_in_the_row_rather_than_in_a_footnote() -> None:
    settled = GateStats(changes=10, passed_first=9, fallback=1, retries=1)
    section = render_metrics(
        _run(
            model=ModelMetrics(
                model_id="m", changes=10, synthetic=10, first_round=settled, settled=settled
            )
        ),
        Path("reports/eval/2026-08-06-abc1234.json"),
    )
    grounding = next(
        line for line in section.splitlines() if line.startswith("| Citation grounding")
    )
    assert "synthetic" in grounding


def test_a_withheld_faithfulness_rate_stays_withheld_in_the_table() -> None:
    section = render_metrics(
        _run(
            faithfulness=FaithfulnessReport(
                judge_model="j", sampled=20, judged=20, faithful=20, synthetic=20
            )
        ),
        Path("reports/eval/2026-08-06-abc1234.json"),
    )
    row = next(line for line in section.splitlines() if line.startswith("| Explanation"))
    assert "not published" in row
    assert "1.000" not in row


def test_a_readme_without_the_sentinels_is_a_loud_error() -> None:
    with pytest.raises(ValueError, match="no <!-- emendrix:metrics:start"):
        splice("# a readme with no markers\n", "section")


def test_two_reports_dated_the_same_day_are_refused_rather_than_guessed(tmp_path: Path) -> None:
    """Picking alphabetically would eventually publish the older of the two.

    The date comes out of the copied report rather than off its filename, because `latest_report`
    reads the date inside the file and the two only agree by convention.
    """
    source = min((REPO / "reports" / "eval").glob("*.json"))
    day = str(json.loads(source.read_bytes())["run_date"])
    (tmp_path / f"{day}-aaaaaaa.json").write_bytes(source.read_bytes())
    assert latest_report(tmp_path).name == f"{day}-aaaaaaa.json"
    (tmp_path / f"{day}-bbbbbbb.json").write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match=f"reports are dated {day}"):
        latest_report(tmp_path)
