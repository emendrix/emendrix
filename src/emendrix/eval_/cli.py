"""`emendrix eval` — score the labelled corpus, and publish what it measured.

Six commands on one app, split across three modules by the job they do. Building the labelled set
lives in `corpus_cli.py`, which owns the network boundary; scoring a judge against the committed
hand review lives in `benchmark_cli.py`, which owns that report; scoring the corpus and publishing
the result lives here and touches nothing but committed files:

```bash
uv run emendrix eval build-corpus            # network: walks the notices, pins the documents
uv run emendrix eval build-subset            # offline: pick the changes the model layer measures
uv run emendrix eval run --fixture-dir tests/fixtures/eu   # offline: what CI runs
uv run emendrix eval sample-digest           # offline: identify the faithfulness sample
uv run emendrix eval judge-benchmark         # offline: score the judges against the hand review
uv run emendrix eval publish-readme          # offline: regenerate the README's metrics section
```

`run` reads the committed corpus and the committed fixtures and touches nothing else: the fixture
cache has no code path to a socket, and that is the default rather than a flag somebody has to
remember. `--from-cache` exists for debugging a corpus that has been selected but not yet pinned,
and says so in its name.

`run` scores both layers: the deterministic one over every transition, and the model one over the
pinned explanation subset, from committed cassettes, in replay, with no provider client ever
constructed. `publish-readme` then regenerates the README section from the report `run` wrote,
which is the only way a number reaches the README.

This module is a composition root, like `emendrix.cli`: it reads the clock once, at the boundary,
and passes the date down as a value. Nothing under it ever asks what time it is.
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import DiskResponseCache, FixtureResponseCache, ResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp, today_utc
from emendrix.eval_.benchmark_cli import judge_benchmark
from emendrix.eval_.corpus import CORPUS_PATH, EvalCorpus, load_corpus
from emendrix.eval_.corpus_cli import DEFAULT_FIXTURES, build, build_subset
from emendrix.eval_.judge import sample
from emendrix.eval_.model_run import SubsetRun, attach_model_layer, replay_engine, run_subset
from emendrix.eval_.readme_table import publish, regenerate
from emendrix.eval_.report import DEFAULT_REPORT_DIR, write_report
from emendrix.eval_.runner import CorpusReader, run_corpus
from emendrix.eval_.signoff import prompt_sha, sample_digest
from emendrix.eval_.thresholds import check, check_model

__all__ = ["app", "git_revision"]

app = typer.Typer(
    name="eval",
    help="Build the labelled corpus and score the deterministic layers against it.",
    no_args_is_help=True,
)

app.command("build-corpus")(build)
app.command("build-subset")(build_subset)
app.command("judge-benchmark")(judge_benchmark)


def git_revision(root: Path | None = None) -> str:
    """The short commit the run scored, for the report filename. `unknown` outside a checkout."""
    try:
        found = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=root,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return found.stdout.strip() or "unknown"


def _show(value: float | None) -> str:
    """A rate for the terminal line. `—` is "not measured", which is not the same as zero."""
    return "—" if value is None else f"{value:.3f}"


def _cache(fixture_dir: Path, from_cache: bool) -> ResponseCache:
    """Where `eval run` reads from. Fixtures by default: a run that can fetch is not an eval."""
    return DiskResponseCache() if from_cache else FixtureResponseCache(fixture_dir)


def _model_layer(reader: CorpusReader, corpus: EvalCorpus, stamp: date) -> SubsetRun | None:
    """The pinned explanation subset through the shipped pipeline, replayed from cassettes.

    One wiring, two callers: `run` scores it and `sample-digest` asks what it sampled. A second
    path here would let the digest a person copies into the sign-off describe a sample no run
    ever produced.
    """
    if corpus.explain_subset is None:
        return None
    return asyncio.run(
        run_subset(
            reader,
            corpus,
            engine=replay_engine(),
            adapter=EuCorpusAdapter(reader.client),
            observed_on=stamp,
        )
    )


@app.command("sample-digest")
def sample_digest_command(
    corpus_path: Annotated[
        Path, typer.Option("--corpus", help="The committed labelled set.")
    ] = CORPUS_PATH,
    fixture_dir: Annotated[
        Path, typer.Option("--fixture-dir", help="The pinned fixture set to score from.")
    ] = DEFAULT_FIXTURES,
    run_date: Annotated[
        datetime | None,
        typer.Option("--date", formats=["%Y-%m-%d"], help="Observation date. Defaults to today."),
    ] = None,
) -> None:
    """Identify the faithfulness sample: its digest, and the triples it covers. Writes nothing.

    A hand review is published only while its committed sign-off names the sample it was of, and
    the sign-off is written by a person. This is how that person gets the two hashes without
    guessing: the sample digest that guards the whole review, and one judge-prompt hash per
    entry, printed in the order the worksheet numbers them.
    """
    corpus = load_corpus(corpus_path)
    stamp = run_date.date() if run_date is not None else today_utc()
    http = CellarHttp(cache=FixtureResponseCache(fixture_dir))
    with http:
        reader = CorpusReader(CellarClient(http, observed_on=stamp))
        subset = _model_layer(reader, corpus, stamp)
    if subset is None:
        typer.echo("no explanation subset is pinned; run `emendrix eval build-subset`", err=True)
        raise typer.Exit(code=1)
    triples = sample(subset.triples)
    typer.echo(f"sample_digest {sample_digest(triples)}")
    for index, triple in enumerate(triples, start=1):
        typer.echo(f"{index:>3}. {prompt_sha(triple)}  {triple.slug}")


@app.command("publish-readme")
def publish_readme(
    readme: Annotated[
        Path, typer.Option("--readme", help="The file whose metrics section is regenerated.")
    ] = Path("README.md"),
    report_dir: Annotated[
        Path, typer.Option("--report-dir", help="Where committed reports are read from.")
    ] = DEFAULT_REPORT_DIR,
    enforce: Annotated[
        bool,
        typer.Option(
            "--check/--write",
            help="Fail if the section is out of date instead of rewriting it.",
        ),
    ] = False,
) -> None:
    """Regenerate the README's metrics section from the latest committed report.

    `--check` is what a build runs: it fails when the section and the report disagree, which is
    how a hand-edited number gets caught. Every published figure comes from a committed report,
    so the workflow is `eval run` and then this.
    """
    current, updated, report = regenerate(readme, report_dir)
    if enforce:
        if updated != current:
            typer.echo(
                f"{readme} is out of date with {report}; run `emendrix eval publish-readme`",
                err=True,
            )
            raise typer.Exit(code=1)
        typer.echo(f"{readme} matches {report}")
        return
    changed, _ = publish(readme, report_dir)
    typer.echo(f"{'rewrote' if changed else 'unchanged'} {readme} from {report}")


@app.command("run")
def run(
    corpus_path: Annotated[
        Path, typer.Option("--corpus", help="The committed labelled set.")
    ] = CORPUS_PATH,
    fixture_dir: Annotated[
        Path,
        typer.Option("--fixture-dir", help="The pinned fixture set to score from."),
    ] = DEFAULT_FIXTURES,
    from_cache: Annotated[
        bool,
        typer.Option(
            "--from-cache/--from-fixtures",
            help="Read the disk cache instead of the fixtures. May reach the network.",
        ),
    ] = False,
    transition: Annotated[
        str | None, typer.Option("--transition", help="Score one case, by its corpus id.")
    ] = None,
    report_dir: Annotated[
        Path, typer.Option("--report-dir", help="Where dated reports are written.")
    ] = DEFAULT_REPORT_DIR,
    write: Annotated[
        bool, typer.Option("--write/--no-write", help="Write the dated Markdown + JSON report.")
    ] = True,
    enforce: Annotated[
        bool, typer.Option("--check/--no-check", help="Fail if a committed floor is breached.")
    ] = True,
    run_date: Annotated[
        datetime | None,
        typer.Option("--date", formats=["%Y-%m-%d"], help="Report date. Defaults to today (UTC)."),
    ] = None,
    revision: Annotated[
        str | None, typer.Option("--revision", help="Revision label. Defaults to the git HEAD.")
    ] = None,
    model: Annotated[
        bool,
        typer.Option(
            "--model/--no-model",
            help="Also replay the model layer over the pinned explanation subset.",
        ),
    ] = True,
) -> None:
    """Score the committed corpus and write the dated report.

    The model layer runs too, in cassette replay: it constructs no provider client, reads no API
    key and reaches no network, which is what lets CI publish grounding numbers offline. Pass
    `--no-model` to score the deterministic layers alone.
    """
    corpus = load_corpus(corpus_path)
    stamp = run_date.date() if run_date is not None else today_utc()
    http = CellarHttp(cache=_cache(fixture_dir, from_cache))
    with http:
        reader = CorpusReader(CellarClient(http, observed_on=stamp))
        result = run_corpus(
            reader,
            corpus,
            run_date=stamp,
            revision=revision if revision is not None else git_revision(),
            only=transition,
        )
        subset = _model_layer(reader, corpus, stamp) if model else None
    result = attach_model_layer(result, subset, directory=report_dir.parent, write=write)
    metrics = result.metrics
    localisation = metrics.localisation
    typer.echo(
        f"{metrics.cases_scored}/{metrics.cases} transitions scored · "
        f"localisation micro F1 "
        f"{'—' if localisation is None else format(localisation.micro_f1, '.3f')} · "
        f"{metrics.disputed} disputed of {metrics.changes} changes"
    )
    if result.model is not None:
        typer.echo(
            f"{result.model.settled.changes} subset changes gated · grounding "
            f"{_show(result.model.grounding_rate)} · fallback {_show(result.model.fallback_rate)}"
            f"{' · SYNTHETIC cassettes' if result.model.synthetic else ''}"
        )
    if write:
        markdown, payload = write_report(result, corpus, report_dir)
        typer.echo(f"{markdown}\n{payload}")
    breaches = (*check(metrics), *check_model(result.model, result.faithfulness)) if enforce else ()
    for breach in breaches:
        typer.echo(f"FLOOR BREACHED — {breach}", err=True)
    if breaches:
        raise typer.Exit(code=1)
