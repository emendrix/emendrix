"""The one page that argues. Everything the front page shed, with nothing softened.

The rest of the site shows: an act page states what moved, and each event's own page puts the
verbatim text under it.
This page is where the claims live, and it is deliberately one page rather than a section on
each, because a caveat that is easy to meet is easy to skip past, and a reader who wants to
know how much to trust a number should find every qualification in one place.

Two rules hold the page together:

- **Every figure is generated, never typed here.** The measured rows come from the committed
  report through `metric_rows`, the same rows the README publishes, so the two cannot disagree;
  the corpus rows are rolled up from the committed entries this build renders, through
  `corpus_rows`. A number neither could produce is simply absent.
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
from emendrix.site_.entries import corpus_rows, counted
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, count, escape, inline, join
from emendrix.site_.pitch import PITCH
from emendrix.site_.sources import repo_file

__all__ = ["render_methodology"]

_PATH = "methodology/"
"""Where this page lives, relative to the site root. The shell derives the climb back from it."""

_LICENCE_NOTICE = "LICENCE-NOTICE.md"
"""The file at the changelog repository's root stating the terms of each of its two layers.

A path inside that repository, so it is rendered by the same rule as every other one: a link
only where the home's file layout is known, and the bare path otherwise.
"""

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


_MAGNITUDE = (
    "Each change carries a figure such as <code>+1,204 −318</code>. Those are <b>characters</b>: "
    "the characters inside the inserted and deleted spans of the word-level comparison shown "
    "under that change, or, for a provision too large to compare word by word, the characters "
    "in the whole lines that changed. The site computes it at build time from the committed "
    "texts, which is why it is not in the table above: it measures this page's own rendering "
    "and evaluates nothing. <b>It is not a measure of legal effect.</b> A two-character change "
    "can move a deadline by sixteen months and a two-thousand-character one can renumber a "
    "list, so nothing on the site calls a change minor, significant or substantial on the "
    "strength of it."
)
"""What the size beside every change counts, and the thing it must never be read as.

It sits in the build section rather than in the metrics table on purpose. The table is the eval
harness's, generated row by row from the committed report; this number is the site measuring its
own rendering, and a row here would be a figure with no provenance in the one place that exists
to refuse them.
"""


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
        f"explanation is good. Every figure below is generated from a committed artifact, the "
        f"dated report or the changelog documents themselves; none is typed in by hand."
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
            f"{repo_file(site.report_markdown, site.repo_url)}. The deterministic rows cover every "
            f"transition in the labelled evaluation corpus ({run.metrics.cases_scored} of "
            f"{run.metrics.cases} scored), which is a pinned set of transitions and not the "
            f"corpus counted above; the model rows cover the pinned explanation subset only, "
            f"because each change in it is one recorded call to a provider.</p>"
        )
    )
    return lines


def _corpus(site: SiteInputs) -> list[Html]:
    """What the reader is browsing, counted, above the table that scores a labelled subset.

    Above it rather than below because these rates describe the corpus on screen and those
    below it do not: a reader who met the pinned figures first would carry them onto every
    page they opened next. Every figure is rolled up at build time from the committed entries
    this build renders, and each arrives with its own caveat attached, by the same rule the
    measured table lives under: the result and its meaning are fields of one frozen row, so
    the table cannot print half of a measure.
    """
    counts = site.corpus
    lines = [Html("<h2>The corpus on this site, counted</h2>")]
    if counts.changes == 0:
        lines.append(
            Html(
                '<p class="small muted">This build was given no committed changelog entries, so '
                "there is nothing here to count.</p>"
            )
        )
        return lines
    lines.extend(
        (
            Html(
                f'<p class="small muted">Counted over the {escape(counted(counts.events, "event"))}'
                f" and {escape(counted(counts.changes, 'change'))} this site renders, and over "
                f"nothing else. The measured table below scores emendrix against a small labelled "
                f"set of transitions instead: a different question over a different denominator, "
                f"so a figure there is not a better reading of one here, and neither is adjusted "
                f"for the other.</p>"
            ),
            Html('<div class="scroll">'),
            Html("<table>"),
            Html(
                "<thead><tr><th>Over the published corpus</th><th>Result</th><th>n</th>"
                "<th>What it means — and what it does not</th></tr></thead>"
            ),
            Html("<tbody>"),
        )
    )
    lines.extend(
        Html(
            f"<tr><td>{inline(row.measure)}</td>"
            f'<td class="result">{escape(row.result)}</td>'
            f"<td>{escape(row.n)}</td>"
            f'<td class="meaning">{inline(row.meaning)}</td></tr>'
        )
        for row in corpus_rows(counts)
    )
    lines.extend((Html("</tbody>"), Html("</table>"), Html("</div>")))
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

    The terms follow the same conditional, for the same reason. A published repository can be
    reused by a stranger, so the page says on what terms and separates the two layers; an
    unpublished one is the operator's to license, and a licence stated on their behalf would
    be this tool choosing for them.
    """
    source = (
        Html(f'<a href="{escape(site.repo_url)}">the emendrix repository</a>')
        if site.repo_url
        else Html("the emendrix repository")
    )
    built_from: tuple[Html, ...]
    if site.changelogs_url:
        changelogs = Html(f'<a href="{escape(site.changelogs_url)}">the changelog repository</a>')
        notice = repo_file(_LICENCE_NOTICE, site.changelogs_url)
        built_from = (
            Html(
                f"<p>A directory of static files, generated by <code>emendrix site build</code> "
                f"from artifacts committed in {source} and in a changelog repository: the "
                f"changelog documents this tool wrote and the dated evaluation report it was "
                f"scored against. This deployment publishes that repository as {changelogs}; "
                f"where it lives on the operator's machine is still never printed here.</p>"
            ),
            Html(
                f"<p>That repository holds two layers and licenses them separately. The "
                f"provision texts, titles, identifiers and dates quoted in it are "
                f"© European Union, reused under Commission Decision 2011/833/EU, which permits "
                f"reuse provided the source is acknowledged, and only the versions published in "
                f"the Official Journal are authentic. Everything emendrix computed rather than "
                f"quoted, the structural diffs, the classifications, the corroboration verdicts "
                f"and the explanations, is licensed <b>Creative Commons Attribution 4.0 "
                f"International (CC BY 4.0)</b>: reuse it, commercially or not, provided the "
                f"project is credited and changes are indicated. {notice} in that repository "
                f"states both layers and gives a citation form that pins a commit rather than a "
                f"branch.</p>"
            ),
        )
    else:
        built_from = (
            Html(
                f"<p>A directory of static files, generated by <code>emendrix site build</code> "
                f"from artifacts committed in {source} and in a changelog repository the "
                f"operator owns: the changelog documents this tool wrote and the dated "
                f"evaluation report it was scored against. Where that repository lives is "
                f"deliberately not printed here.</p>"
            ),
        )
    return [
        Html("<h2>How this site is built</h2>"),
        *built_from,
        Html(
            "<p>Every page is a rendering of things already committed, so the site can answer no "
            "question its inputs do not already contain, which is what makes "
            "<em>no number here lacks provenance</em> structural rather than aspirational. Two "
            "builds of one repository state produce the same bytes: nothing on the site reads a "
            "clock, reaches the network, or calls a model. One small script adds search; no "
            "link leaves the site except to EUR-Lex and the repositories this page names.</p>"
        ),
        Html(f"<p>{_MAGNITUDE}</p>"),
    ]


def render_methodology(site: SiteInputs) -> Html:
    """The whole argument, in order. Deterministic: same inputs, same bytes."""
    body = join(
        (
            Html("<h1>Methodology</h1>"),
            Html(f'<p class="lede">{escape(PITCH)}</p>'),
            Html(f'<p class="lede muted">{_headline_sentence(site)}</p>'),
            *_corpus(site),
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
