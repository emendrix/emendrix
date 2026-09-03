"""The one page that argues. Everything the front page shed, with nothing softened.

The rest of the site shows: an act page states what moved, and each event's own page puts the
verbatim text under it.
This page is where the claims live, and it is deliberately one page rather than a section on
each, because a caveat that is easy to meet is easy to skip past, and a reader who wants to
know how much to trust a number should find every qualification in one place.

Two rules hold the page together:

- **Every figure renders from the committed report**, through `metric_rows`. The same rows the
  README publishes, from the same report, so the two cannot disagree; none of them is typed in
  here, and a number this module could not read out is simply absent.
- **No number is quoted without the sentence saying what it is not.** The result and its
  meaning are fields of one frozen row, so the table cannot print half of a measure. Citation
  grounding stays a separate row from explanation faithfulness: one is a deterministic property
  of the gate and the other is a sampled judgement, and merging them would flatter both.

The loop is stated last because it explains how the numbers came about, and a reader who does
not care can stop above it.

No clock, no network, no model call: `generated_on` arrives from the caller and every other
value on the page was read off an artifact somebody committed.
"""

from __future__ import annotations

from emendrix.eval_.metric_rows import metric_rows, synthetic_caveats
from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, count, escape, inline, join
from emendrix.site_.pitch import PITCH

__all__ = ["render_methodology"]

_PATH = "methodology/"
"""Where this page lives, relative to the site root. The shell derives the climb back from it."""

_LOOP: tuple[tuple[str, str], ...] = (
    (
        "1 · Watch",
        "A watchlist of acts, matched against the Publications Office notification feed by "
        "identifier. Deterministic.",
    ),
    (
        "2 · Fetch",
        "Both consolidated versions and the amending act, as structured Formex 4 XML, through a "
        "disk cache. Deterministic.",
    ),
    (
        "3 · Delta",
        "A structural diff over the provision trees: which articles and annexes were inserted, "
        "modified, deleted. No model.",
    ),
    (
        "4 · Explain",
        "The only model call in the loop, constrained to the two verbatim texts it is handed. It "
        "never decides what changed.",
    ),
    (
        "5 · Gate",
        "Every citation must resolve to a provision that was offered, or the sentence is "
        "replaced by a verbatim quotation. Deterministic.",
    ),
)

_LOOP_NOTE = (
    "Between <b>Delta</b> and <b>Explain</b> the changes are corroborated against two "
    "independent signals — the corpus's own modification metadata and a parse of the amending "
    "act's instruction prose — and anything they disagree about ships marked <em>disputed</em> "
    "rather than dropped. After <b>Gate</b> the result is committed to a git repository as "
    "Markdown and JSON. Every stage except <b>Explain</b> is deterministic Python."
)


def _source(path: str, repo_url: str) -> Html:
    """A path inside the repository: a link when there is a public one, plain text otherwise.

    An unset repository URL producing a dead link would be worse than no link at all, so the
    default is the honest one, the path as text, for a reader who has the checkout.
    """
    shown = Html(f"<code>{escape(path)}</code>")
    if not repo_url:
        return shown
    return Html(f'<a href="{escape(repo_url.rstrip("/") + "/" + path)}">{shown}</a>')


def _headline_sentence(site: SiteInputs) -> Html:
    """The measured claim, in the opening paragraph, with its limitation in the same sentence."""
    pair = site.run.metrics.localisation
    if pair is None:
        return Html(
            "No localisation figure is recorded in the report this page was built from, so none "
            "is claimed here."
        )
    return Html(
        f"Finding <em>which</em> provisions an amendment touched scores micro-F1 "
        f"<strong>{pair.micro_f1:.3f}</strong> over {count(pair.cases, 'transition')} against "
        f"labels the legislation publishes about itself — that is agreement with a reference "
        f"set at article-or-annex granularity, and it is not a measure of whether any "
        f"explanation is good. Every figure below is generated from a committed report; none is "
        f"typed in by hand."
    )


def _metrics(site: SiteInputs) -> list[Html]:
    """The published table, its standing caveats, and where the figures were read from."""
    run = site.run
    lines = [
        Html("<h2>Measured, not asserted</h2>"),
        Html(
            '<p class="small muted">Every row carries what it means and what it does not. The '
            "rows are the same ones the repository's README publishes, rendered from the same "
            "committed report, so the two cannot disagree.</p>"
        ),
        Html('<div class="scroll">'),
        Html("<table>"),
        Html(
            "<thead><tr><th>Measure</th><th>Result</th><th>n</th>"
            "<th>What it means — and what it does not</th></tr></thead>"
        ),
        Html("<tbody>"),
    ]
    for row in metric_rows(run):
        lines.append(
            Html(
                f"<tr><td>{inline(row.measure)}</td>"
                f'<td class="result">{inline(row.result)}</td>'
                f"<td>{inline(row.n)}</td>"
                f'<td class="meaning">{inline(row.meaning)}</td></tr>'
            )
        )
    lines.extend((Html("</tbody>"), Html("</table>"), Html("</div>")))
    caveats = synthetic_caveats(run)
    if caveats:
        lines.append(Html('<ul class="caveats">'))
        lines.extend(Html(f"<li>{inline(caveat)}</li>") for caveat in caveats)
        lines.append(Html("</ul>"))
    lines.append(
        Html(
            f'<p class="small muted">Measured on {run.run_date.isoformat()} at revision '
            f"<code>{escape(run.revision)}</code>, from "
            f"{_source(site.report_markdown, site.repo_url)}. The deterministic rows cover every "
            f"transition in the committed corpus ({run.metrics.cases_scored} of "
            f"{run.metrics.cases} scored); the model rows cover the pinned explanation subset "
            f"only, because each change in it is one recorded call to a provider.</p>"
        )
    )
    return lines


def _how_it_works() -> list[Html]:
    """The five stages, and the sentence that says which one of them a model is allowed in."""
    lines = [Html("<h2>How it works</h2>"), Html('<ul class="loop">')]
    lines.extend(Html(f"<li><b>{escape(name)}</b>{escape(text)}</li>") for name, text in _LOOP)
    lines.extend((Html("</ul>"), Html(f'<p class="small muted">{_LOOP_NOTE}</p>')))
    return lines


def _how_this_site_is_built(site: SiteInputs) -> list[Html]:
    """What the reader is looking at, and why it can answer nothing its inputs do not hold.

    The changelog repository gets a whole sentence rather than the footer's linked-or-plain
    phrase, because the two configurations say different true things: a deployment that
    passes `--changelogs-url` publishes the repository and says where, and one that does not
    keeps the repository the operator's own. What never varies is the rule that its path on
    the operator's machine is not printed; only the sentence stating that rule changes shape.
    """
    source = (
        Html(f'<a href="{escape(site.repo_url)}">the emendrix repository</a>')
        if site.repo_url
        else Html("the emendrix repository")
    )
    if site.changelogs_url:
        changelogs = Html(f'<a href="{escape(site.changelogs_url)}">the changelog repository</a>')
        built_from = Html(
            f"<p>A directory of static files, generated by <code>emendrix site build</code> "
            f"from artifacts committed in {source} and in a changelog repository: the "
            f"changelog documents this tool wrote and the dated evaluation report it was "
            f"scored against. This deployment publishes that repository as {changelogs}; "
            f"where it lives on the operator's machine is still never printed here.</p>"
        )
    else:
        built_from = Html(
            f"<p>A directory of static files, generated by <code>emendrix site build</code> "
            f"from artifacts committed in {source} and in a changelog repository the operator "
            f"owns: the changelog documents this tool wrote and the dated evaluation report "
            f"it was scored against. Where that repository lives is deliberately not printed "
            f"here.</p>"
        )
    return [
        Html("<h2>How this site is built</h2>"),
        built_from,
        Html(
            "<p>Every page is a rendering of things already committed, so the site can answer no "
            "question its inputs do not already contain, which is what makes "
            "<em>no number here lacks provenance</em> structural rather than aspirational. Two "
            "builds of one repository state produce the same bytes: nothing on the site reads a "
            "clock, reaches the network, or calls a model. One small script adds search; no "
            "link leaves the site except to EUR-Lex and the repositories this page names.</p>"
        ),
    ]


def render_methodology(site: SiteInputs) -> Html:
    """The whole argument, in order. Deterministic: same inputs, same bytes."""
    body = join(
        (
            Html("<h1>Methodology</h1>"),
            Html(f'<p class="lede">{escape(PITCH)}</p>'),
            Html(f'<p class="lede muted">{_headline_sentence(site)}</p>'),
            *_metrics(site),
            *_how_it_works(),
            *_how_this_site_is_built(site),
        ),
        "\n",
    )
    return page(
        title="Methodology — emendrix",
        description=(
            "How emendrix measures itself: every published figure, over what, and what each one "
            "does not mean."
        ),
        body=body,
        path=_PATH,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
    )
