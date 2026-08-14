"""The one page that argues. Every figure on it is the committed report's own.

Two directions matter and both are asserted here: a rate that drifts from the report, and a
stub's verdict reaching a visitor. The withheld path is built from a report constructed in the
test body rather than the committed one, so it keeps guarding the machinery whatever the newest
committed report happens to say.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.metric_rows import metric_rows
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.markup import inline
from emendrix.site_.pages.methodology import render_methodology

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _site() -> SiteInputs:
    return collect_site(generated_on=OBSERVED, run=_run(), report=latest_report(REPORTS))


def test_every_published_figure_came_out_of_the_committed_report() -> None:
    site = _site()
    rendered = render_methodology(site)
    for row in metric_rows(site.run):
        assert inline(row.result) in rendered, row.measure
        assert inline(row.meaning) in rendered, row.measure


def test_the_faithfulness_rate_is_the_reports_own() -> None:
    site = _site()
    rendered = render_methodology(site)
    report = site.run.faithfulness
    assert report is not None and report.rate is not None
    assert f"{report.rate:.3f}" in rendered
    assert f"n = {report.judged}, LLM judge + spot review ({report.human_review})" in rendered


def test_a_withheld_rate_is_still_withheld_when_it_has_to_be() -> None:
    stub = FaithfulnessReport(judge_model="j", sampled=20, judged=20, faithful=20, synthetic=20)
    assert stub.rate is None, "a stub's verdicts are not a rate"
    run = _run().model_copy(update={"faithfulness": stub})
    rows = metric_rows(run)
    faithfulness = [row for row in rows if row.measure.startswith("Explanation faithfulness")]
    assert len(faithfulness) == 1
    assert faithfulness[0].result == "**not published**"


def test_the_page_never_claims_a_stub_recorded_what_a_model_did() -> None:
    """The caveat block is computed from the `synthetic` flag, so it appears and disappears alone.

    The committed cassettes are real, so the block must be absent: a page still carrying it
    would mean the flag stopped being read, which is the same failure as a page missing it when
    the cassettes are stubs.
    """
    rendered = render_methodology(_site())
    assert "recorded from a stub because no API key was available" not in rendered
    assert "is withheld outright" not in rendered
    assert '<ul class="caveats">' not in rendered


def test_grounding_is_never_merged_with_faithfulness() -> None:
    rendered = render_methodology(_site()).replace("<strong>", "").replace("</strong>", "")
    assert "Citation validity, not explanation quality" in rendered
    assert rendered.count("Explanation faithfulness (sampled)") == 1


def test_no_absolute_path_of_this_machine_reaches_the_page() -> None:
    """A build in a checkout and a build in a container publish the same provenance."""
    rendered = render_methodology(_site())
    assert str(REPO) not in rendered
    assert f"reports/eval/{latest_report(REPORTS).stem}.md" in rendered


def test_a_configured_build_links_both_repositories_in_how_built() -> None:
    """With both URLs set, the how-built section links each repository by name.

    The two hosts are distinct so each assertion can only be satisfied by its own link, and
    the filesystem-path rule must survive the linked form as a stated rule.
    """
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=latest_report(REPORTS),
        repo_url="https://example.invalid/emendrix",
        changelogs_url="https://data.example.invalid/changelogs",
    )
    section = render_methodology(site).split("How this site is built")[1]
    assert '<a href="https://example.invalid/emendrix">the emendrix repository</a>' in section
    assert (
        '<a href="https://data.example.invalid/changelogs">the changelog repository</a>' in section
    )
    assert "where it lives on the operator's machine is still never printed here" in section
    assert "no link leaves the site except to EUR-Lex and the repositories this page names" in (
        section
    )


def test_an_unset_build_keeps_the_old_sentence_and_names_no_host() -> None:
    """With neither URL set, the section degrades to the old meaning, not a broken reference.

    No `github.com` may appear anywhere in the rendered page: the URLs are deployment facts
    injected at the CLI boundary, never hardcoded into the site sources.
    """
    rendered = render_methodology(_site())
    assert "github.com" not in rendered
    section = rendered.split("How this site is built")[1]
    assert "in a changelog repository the operator owns" in section
    assert "Where that repository lives is deliberately not printed here." in section
    assert "no link leaves the site except to EUR-Lex and the repositories this page names" in (
        section
    )
