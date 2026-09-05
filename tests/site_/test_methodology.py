"""The one page that argues. Every figure on it is a committed artifact's own.

Two directions matter and both are asserted here: a rate that drifts from the artifact it came
out of, and a stub's verdict reaching a visitor. The withheld path is built from a report
constructed in the test body rather than the committed one, so it keeps guarding the machinery
whatever the newest committed report happens to say.

The page publishes two sets of figures over two denominators, and which artifact each comes out
of is asserted separately: the measured rows are the committed report's, the corpus rows are
rolled up from the committed entries the build renders. A figure of one set standing in for the
other is the failure these tests exist to catch, and it is why the corpus assertions build a
site holding events rather than the empty one the rest of the module uses.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from site_entries import disputed_entry, some_textless_entry, textless_entry

from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.metric_rows import metric_rows
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.entries import corpus_rows
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.markup import escape, inline
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


def _report_path() -> str:
    return f"reports/eval/{latest_report(REPORTS).stem}.md"


def _linked(path: str) -> str:
    """The one shape a linked path is rendered in, so the assertions below can be exact."""
    return f'"><code>{path}</code></a>'


def test_a_github_home_links_the_report_that_proves_every_figure() -> None:
    """The page's whole argument is that no figure on it lacks provenance, so the link resolves.

    A bare join of the repository URL and the path answered 404 until 2026-09-03, which is that
    argument failing on the first click. GitHub serves a committed file under `blob/<ref>/`.
    """
    path = _report_path()
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=latest_report(REPORTS),
        repo_url="https://github.com/o/r",
    )
    rendered = render_methodology(site)
    assert f'<a href="https://github.com/o/r/blob/main/{path}"><code>{path}</code></a>' in rendered


def test_a_public_home_of_unknown_shape_shows_the_path_as_text() -> None:
    """A forge whose file layout nobody has checked gets no guessed link, only the path."""
    path = _report_path()
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=latest_report(REPORTS),
        repo_url="https://example.invalid/emendrix",
    )
    rendered = render_methodology(site)
    assert f"<code>{path}</code>" in rendered
    assert _linked(path) not in rendered
    assert f"https://example.invalid/emendrix/{path}" not in rendered


def test_a_build_with_no_public_home_shows_the_path_as_text() -> None:
    """The committed build passes no `--repo-url`, and the path is the honest answer for it."""
    path = _report_path()
    rendered = render_methodology(_site())
    assert f"<code>{path}</code>" in rendered
    assert _linked(path) not in rendered


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


def test_the_build_section_says_what_the_character_count_is_and_is_not() -> None:
    """The site prints a size beside every change, so this page says what a size is worth.

    Both halves are asserted, because either alone is the failure: what the number counts,
    and that it is not a measure of legal effect. The words appear in the build section, which
    is where the site describes its own rendering.
    """
    section = render_methodology(_site()).split("How this site is built")[1]
    assert "It is not a measure of legal effect." in section
    assert "the characters inside the inserted and deleted spans" in section
    assert "the characters in the whole lines that changed" in section
    assert "computes it at build time from the committed" in section


def test_the_character_count_never_becomes_a_row_of_the_measured_table() -> None:
    """The table is the eval harness's, generated row by row from the committed report.

    A row here would be a figure with no provenance in the one place on the site that exists
    to refuse them, so the body's row count is pinned to what `metric_rows` produced.
    """
    site = _site()
    rendered = render_methodology(site)
    body = rendered.split("<tbody>")[1].split("</tbody>")[0]
    assert body.count("<tr>") == len(metric_rows(site.run))
    assert "characters" not in body


def _configured(changelogs_url: str) -> str:
    """The how-built section of a build that publishes its changelog repository."""
    site = collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=latest_report(REPORTS),
        repo_url="https://example.invalid/emendrix",
        changelogs_url=changelogs_url,
    )
    return render_methodology(site).split("How this site is built")[1]


def test_a_published_changelog_repository_states_the_terms_of_both_its_layers() -> None:
    """A stranger who finds the data through the site learns the terms without leaving.

    Both layers are asserted, because either alone is the failure. The quoted provision texts
    are the Union's and are not this project's to relicense; only what the loop computed is
    offered under CC BY 4.0.
    """
    section = _configured("https://data.example.invalid/changelogs")
    assert "© European Union, reused under Commission Decision 2011/833/EU" in section
    assert "only the versions published in the Official Journal are authentic" in section
    assert "Creative Commons Attribution 4.0 International (CC BY 4.0)" in section
    assert "LICENCE-NOTICE.md" in section


def test_a_github_changelog_repository_links_the_licence_notice() -> None:
    """The notice is a path inside that repository, linked where the layout is known."""
    section = _configured("https://github.com/o/changelogs")
    assert (
        '<a href="https://github.com/o/changelogs/blob/main/LICENCE-NOTICE.md">'
        "<code>LICENCE-NOTICE.md</code></a>" in section
    )


def test_an_unset_build_states_no_licence_for_a_repository_it_does_not_publish() -> None:
    """The operator's own unpublished repository is theirs to license, so the page says nothing.

    This is also what keeps the licence out of the build with no `--changelogs-url`, which is
    the one the committed golden tree was rendered from.
    """
    rendered = render_methodology(_site())
    assert "CC BY" not in rendered
    assert "LICENCE-NOTICE" not in rendered
    assert "2011/833/EU" not in rendered


def _corpus_site() -> SiteInputs:
    """A build holding committed events, which is what the corpus rates are counted over.

    Three entries rather than one, because the rates have to be right over a corpus mixing the
    shapes: a change the comparison read and another source did not list, changes only another
    source named, and an event carrying both.
    """
    return collect_site(
        generated_on=OBSERVED,
        run=_run(),
        report=latest_report(REPORTS),
        entries=(disputed_entry(), textless_entry(), some_textless_entry()),
    )


def test_the_corpus_rates_are_counted_from_the_entries_this_build_renders() -> None:
    """The figures about the corpus a reader is browsing come off that corpus, not the report.

    Every cell is asserted against what the rollup produced, so a hand-typed number or a
    figure quietly read out of the eval run would fail here rather than ship.
    """
    site = _corpus_site()
    rendered = render_methodology(site)
    rows = corpus_rows(site.corpus)
    assert rows
    for row in rows:
        assert escape(row.result) in rendered, row.measure
        assert escape(row.n) in rendered, row.measure
        assert inline(row.meaning) in rendered, row.measure


def test_the_corpus_rates_and_the_pinned_ones_each_carry_their_own_n() -> None:
    """Two sets of figures on one page, over different denominators, neither borrowing the other.

    The corpus rows count changes in the committed entries; the measured rows count
    transitions in the labelled evaluation corpus. A reader can tell which is which because
    each row states what it was measured over.
    """
    site = _corpus_site()
    rendered = render_methodology(site)
    assert f"{site.corpus.changes:,} changes" in rendered
    for row in metric_rows(site.run):
        assert inline(row.n) in rendered, row.measure


def test_the_corpus_figures_come_before_the_pinned_ones() -> None:
    """They describe what the reader is looking at, so they are not subordinate to a subset."""
    rendered = render_methodology(_corpus_site())
    assert rendered.index("The corpus on this site, counted") < rendered.index(
        "Measured, not asserted"
    )


def test_the_caption_never_lets_the_evaluation_corpus_read_as_the_whole_corpus() -> None:
    """`the committed corpus` on a page that now counts the committed corpus was two things."""
    rendered = render_methodology(_corpus_site())
    assert "every transition in the committed corpus" not in rendered
    assert "labelled evaluation corpus" in rendered
    assert "a pinned set of transitions and not the corpus counted above" in rendered


def test_the_dispute_rate_is_broken_down_and_the_shapes_add_up_to_it() -> None:
    """One number invites a comparison that is not like for like; the breakdown is what makes
    the comparison honest. Every disputed change is in exactly one shape and none is dropped."""
    site = _corpus_site()
    counts = site.corpus
    assert counts.shapes.total == counts.disputed
    rendered = render_methodology(site)
    for part in (counts.shapes.evidenced, counts.shapes.no_text, counts.shapes.kind):
        assert f"{part:,} ({part / counts.disputed:.3f})" in rendered
    assert f"{counts.disputed:,} disputed changes" in rendered


def test_every_corpus_figure_says_what_it_does_not_mean() -> None:
    """The same rule the measured table lives under: no number without its qualification."""
    rendered = render_methodology(_corpus_site())
    assert "a fact about the detectors and not a statement about the law" in rendered
    assert "<strong>Not a change nobody could corroborate.</strong>" in rendered
    assert "<strong>Not a change whose text is withheld</strong>" in rendered
    assert "<strong>Coverage, not quality</strong>" in rendered


def test_a_build_with_no_committed_entries_states_that_instead_of_a_rate() -> None:
    """A rate over no changes is not zero, and `0.000` here would be a measurement nobody made."""
    rendered = render_methodology(_site())
    assert "there is nothing here to count" in rendered
    section = rendered.split("The corpus on this site, counted")[1].split("Measured, not")[0]
    assert "0.000" not in section
