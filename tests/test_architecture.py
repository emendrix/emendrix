"""The invariants that are grep-checkable, checked by grep.

The project states them as rules; a rule nobody checks is a wish. Each test below fails the
build the moment a network call, a clock read or a model call appears somewhere the design
says it cannot be, including in code that has not been written yet, which is the point.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "emendrix"


def modules() -> Iterator[tuple[str, str]]:
    """Every shipped module, as `(path relative to the package, source)`."""
    for path in sorted(SRC.rglob("*.py")):
        yield path.relative_to(SRC).as_posix(), path.read_text(encoding="utf-8")


def offenders(pattern: str, allowed: set[str]) -> list[str]:
    expression = re.compile(pattern)
    return [name for name, source in modules() if name not in allowed and expression.search(source)]


def test_only_the_http_module_speaks_http() -> None:
    """Network lives in `eu/http.py`, behind the cache in `eu/cache.py`. Nothing else.

    `eu/feed.py` is the third module allowed to reach the network, and it does so through
    `CellarHttp`, so the transport allow-list does not widen for it. That is deliberate:
    one client, one cache, one retry policy.
    """
    assert offenders(r"\bimport httpx\b|\bhttpx\.", {"eu/http.py"}) == []


def test_the_atom_feed_is_never_handed_to_a_generic_parser() -> None:
    """The feed's standard Atom fields ship unrendered Velocity variables (verified 2026-08-06).

    `feedparser` would read `<title>$item.title</title>` and `<link href="$item.cellarUri"/>`
    as a title and a link, and everything downstream would be confidently wrong. The only
    honest read is the `notifEntry:` namespace, by hand, in `eu/feed_atom.py`, which says so in
    its own docstring: hence matching the import rather than the name.
    """
    assert offenders(r"import feedparser\b|\bfeedparser\.", set()) == []


def test_untrusted_xml_never_reaches_the_stdlib_parser() -> None:
    """ElementTree expands internal entities, and every document here came off a socket.

    The rule is on the *parsing* entry points, not on the module: `Element` is a type and
    importing it parses nothing, which is why four modules still name `xml.etree.ElementTree`
    and are right to. `eu/packages.py` is the one exception and carries its reason: it needs
    `XMLPullParser`, which `defusedxml` does not wrap, so it guards on `DOCTYPE` instead.

    `tests/eu/test_xml.py` measures both halves: what the stdlib expands, and that no committed
    document is refused by the swap.
    """
    entry_points = r"fromstring|iterparse|XMLParser|\bparse\b"
    pattern = (
        rf"(?mx) \bET\.(?:{entry_points})"
        rf"| ^\s*from\s+xml\.etree\.ElementTree\s+import\s+[^\n]*(?:{entry_points})"
    )
    assert offenders(pattern, {"eu/packages.py"}) == []


def test_the_hardened_parser_is_configured_in_exactly_one_module() -> None:
    """A parsing policy is only worth having if there is one place it can be read and changed."""
    expression = re.compile(r"^\s*(?:from|import)\s+defusedxml\b", re.MULTILINE)
    importers = [name for name, source in modules() if expression.search(source)]
    assert importers == ["eu/xml_.py"]


def test_only_two_modules_decide_where_files_live_outside_the_repo() -> None:
    """The cache is disposable and the watch state is not, so they are different directories.

    Two modules, on purpose and no further: `eu/cache.py` owns
    the cache directory, `watch/state.py` owns the user-data directory, and each may name only
    its own.
    """
    assert offenders(r"\bplatformdirs\b", {"eu/cache.py", "watch/state.py"}) == []
    assert offenders(r"user_cache_dir", {"eu/cache.py"}) == []
    assert offenders(r"user_data_dir", {"watch/state.py"}) == []


def test_the_clock_is_read_in_exactly_one_place() -> None:
    """A wall-clock read is provenance in the fetch path and a bug everywhere else.

    The dates that matter, the observation date on every first-class state and the poll window,
    are passed in from the CLI boundary, which is what makes diff, classification, gating and
    rendering reproducible.
    """
    pattern = r"datetime\.now\(|date\.today\(|time\.time\(|utcnow\("
    assert offenders(pattern, {"eu/http.py"}) == []


def test_a_notice_is_never_fetched_without_a_freshness_policy() -> None:
    """A notice is a listing about an act and its whole purpose is to change.

    Cached without a life it becomes a standing claim that nothing new exists, and the one
    resource that reports a new version is then the one frozen hardest. Verified 2026-09-11
    against a deployment whose poller had not observed a consolidation in six days while every
    stage of the chain it ran reported success.

    Three reads in the package: the act's version inventory, its amendment graph, and an
    amending act's own published dates. A fourth is an event worth noticing here.
    """
    marker = re.compile(r"accept=ACCEPT_(?:TREE|BRANCH)_NOTICE\b")
    sites = 0
    for name, source in modules():
        lines = source.splitlines()
        for number, line in enumerate(lines):
            if not marker.search(line):
                continue
            sites += 1
            request = "\n".join(lines[number : number + 3])
            assert "volatile=True" in request, f"{name}:{number + 1} reads a notice forever"
    assert sites == 3


def test_the_watch_stage_takes_its_window_rather_than_asking_the_clock() -> None:
    """`poll_once` is deterministic given its inputs, and `watch/cli.py` is the boundary.

    The rest of `watch/` may not even reach the one sanctioned clock read, which is what makes
    the crash-restart and overlapping-window tests mean something.
    """
    for name, source in modules():
        if name.startswith("watch/") and name != "watch/cli.py":
            assert "today_utc" not in source, name


@pytest.mark.parametrize(
    ("package", "allowed_prefixes"),
    [
        ("pydantic_ai", ("explain/", "eval_/faithfulness.py")),
        ("langgraph", ("graph/",)),
    ],
)
def test_the_model_and_the_orchestrator_stay_where_the_design_puts_them(
    package: str, allowed_prefixes: tuple[str, ...]
) -> None:
    """The model appears in exactly one stage of the loop; the graph wires, it does not think."""
    expression = re.compile(rf"\b{package}\b")
    bad = [
        name
        for name, source in modules()
        if expression.search(source) and not name.startswith(allowed_prefixes)
    ]
    assert bad == []


def test_the_graph_framework_lives_in_exactly_one_module() -> None:
    """Tighter than the package rule above, and the tightness is the point.

    `graph/` is allowed to import `langgraph`; only `graph/build.py` actually does. Everything
    else in the package is ordinary Python that the tests call directly, which is what keeps
    the framework a wiring detail rather than the way the pipeline is written, and what makes
    "LangGraph could be dropped and the loop would stand" a claim with evidence behind it.
    """
    expression = re.compile(r"^\s*(?:from|import)\s+langgraph\b", re.MULTILINE)
    importers = [name for name, source in modules() if expression.search(source)]
    assert importers == ["graph/build.py"]


def test_the_nodes_are_adapters_and_stay_short_enough_to_be_obvious() -> None:
    """The graph is orchestration, not agency. A node that grew a rule is the failure mode.

    Length is a proxy, but it is the proxy that catches the real thing: logic arrives in a node
    as extra lines. The cap is per function body in `graph/nodes.py`, at roughly 20 lines. If a
    node needs more, the package it calls was incomplete.
    """
    source = (SRC / "graph" / "nodes.py").read_text(encoding="utf-8")
    bodies = re.split(r"\n(?=    (?:async )?def )", source)[1:]
    too_long = {
        body.split("(")[0].strip().removeprefix("async ").removeprefix("def "): len(
            body.splitlines()
        )
        for body in bodies
        if len(body.splitlines()) > 22
    }
    assert too_long == {}


def test_only_the_composition_root_knows_which_corpus_the_loop_is_running() -> None:
    """The whole loop runs over `tests/toy_corpus.py`, which is not law, so it must stay generic.

    `graph/cli.py` is the exception because it is a command line: it names the notification
    channel, the one sanctioned clock read and how a CELEX parses. Every other module in `graph/`
    sees `CorpusAdapter` and core types only, which is what `tests/graph/test_pipeline_toy.py`
    then demonstrates. Building the adapter itself happens outside the package altogether, in
    `session.py`, which the test below holds to one module.
    """
    for name, source in modules():
        if not name.startswith("graph/") or name == "graph/cli.py":
            continue
        assert "emendrix.eu" not in source, name
        assert not re.search(r"\bCELEX\b|\bFormex\b|\bCELLAR\b", source), name


def test_the_loop_is_wired_to_the_eu_corpus_in_exactly_one_module() -> None:
    """Three commands run the same graph, so they must not each decide what feeds it.

    `session.py` builds the adapter, the signal source and the explain engine; `run`, `explain`
    and `backfill` ask it. The other allowed builders do not run the loop: `cli.py` is `diff`,
    which reaches the corpus without a pipeline, and `watch/cli.py` polls without explaining.
    `eval_/model_run.py` builds the replay engine for the pinned subset. A further construction
    site is a further chance for the scheduled path and the manual one to drift apart, which is
    the failure mode where a tool's demo works and its cron job does not.

    The pattern is on `.build`, so it deliberately does not match `eval_/cli.py`'s
    `EuCorpusAdapter(reader.client)`: the question here is who decides how the loop's adapter is
    configured, and that call rides on a reader that has already been built.
    """
    assert offenders(r"EuCorpusAdapter\.build", {"session.py", "cli.py", "watch/cli.py"}) == []
    assert offenders(r"\bExplainEngine\(", {"session.py", "eval_/model_run.py"}) == []


def test_the_gate_is_deterministic_by_construction() -> None:
    """No model, no network, no corpus. The gate decides, so nothing in it may be negotiable."""
    for name, source in modules():
        if not name.startswith("gate/"):
            continue
        assert "pydantic_ai" not in source, name
        assert "emendrix.eu" not in source, name
        assert "emendrix.explain.engine" not in source, f"{name} may not reach the model"
        assert not re.search(r"\brandom\b|\buuid\b", source), name


def test_only_two_modules_run_a_subprocess() -> None:
    """`output/git.py` is the changelog writer; `eval_/cli.py` reads the revision a report is
    stamped with. Both are deliberate, both are narrow, and a third one appearing is worth a
    look: shelling out is how a typed pipeline grows an untyped edge.
    """
    assert offenders(r"\bsubprocess\b", {"output/git.py", "eval_/cli.py"}) == []


def test_the_site_is_generated_and_not_fetched() -> None:
    """The published site is a rendering of committed artifacts; that is why it can be static.

    `site_/cli.py` is the composition root: it names the one sanctioned clock read, resolves
    where the changelog repository lives, and is the one module allowed to know which corpus
    publishes document URLs. Every other module in the package is a pure function of the
    artifacts it is handed. No page can therefore show a figure it did not read out of a
    committed file, which is a property of the imports rather than a promise.

    Unlike the packages below, `site_/` is *not* held to "the word Formex may not appear": the
    methodology page is prose about one running deployment and being vague about what it parses
    would be worse documentation, not better architecture. What keeps the code generic is the
    import rule here plus `tests/site_/test_site_build.py`, which builds the whole site over
    the toy corpus, not law at all, through the same functions.
    """
    for name, source in modules():
        if not name.startswith("site_/") or name == "site_/cli.py":
            continue
        assert "emendrix.eu" not in source, name
        assert "today_utc" not in source, name


def test_a_repair_reaches_the_corpus_only_from_its_own_command_line() -> None:
    """A repair addresses a committed document, and a document is not a corpus.

    `repair/cli.py` is the composition root: it names the one sanctioned clock read and is the
    one module allowed to know which corpus published the amending act whose instructions the
    corroboration repair re-parses, which is a cache read through the same client everything
    else uses. Every other module in the package sees the committed entry and core types only,
    so the whole spine would run over a corpus that is not law, exactly as `backfill/` does.
    """
    for name, source in modules():
        if not name.startswith("repair/") or name == "repair/cli.py":
            continue
        assert "emendrix.eu" not in source, name
        assert "today_utc" not in source, name
        assert not re.search(r"\bCELEX\b|\bFormex\b|\bCELLAR\b", source), name


def test_the_site_writes_no_script_of_its_own() -> None:
    """The one script is a committed asset loaded by `src`, never markup a generator wrote.

    An inline `<script>` is the one way a static artifact could grow a fetch and start showing a
    number with no provenance, which is the thing the whole design forbids. The search script is
    checked in, copied rather than generated, and reviewable as itself;
    `tests/site_/test_golden.py` holds the built pages to loading that file and no other.

    `type="application/ld+json"` is the one allowed exception, and it is narrow on purpose. An
    `ld+json` element is inert data: no browser executes it and it cannot fetch anything, which
    is precisely the property the rule above exists to protect, so the rule is widened rather
    than broken. The executable-script rule is unchanged for every other tag. Which module may
    mint such an element is pinned here too, because one place that knows the JSON-LD escaping
    rule is reviewable and two places are a rule waiting to be half-remembered.

    The `src` is asserted to be the `SCRIPT` name rather than a literal, because the file the
    build writes carries a digest of its own bytes and no source may spell that name a second
    time. `tests/site_/test_golden.py` holds the built pages to the file the tree actually
    holds, which is the other half of the same rule.
    """
    for name, source in modules():
        for tag in re.findall(r"<script[^>]*>", source):
            if 'type="application/ld+json"' in tag:
                assert name == "site_/seo.py", f"{name}: JSON-LD belongs in one module"
                continue
            assert "src=" in tag and "{SCRIPT}" in tag, f"{name}: {tag}"


def test_the_renderers_cannot_reach_the_model_or_the_corpus() -> None:
    """The changelog is rendered from `graph.report`'s document and from nothing else.

    That is what lets `emendrix diff --markdown` run with no API key and no cassettes, and what
    lets the same renderer produce a changelog for `tests/toy_corpus.py`, which is not law. The
    package-wide `pydantic_ai` rule already covers the model import; this covers the two
    subtler ways the seam could be lost.
    """
    for name, source in modules():
        if not name.startswith("output/"):
            continue
        assert "emendrix.explain.engine" not in source, f"{name} may not reach the model"
        assert "emendrix.eu" not in source, name


@pytest.mark.parametrize(
    "package", ["core/", "diff/", "corroborate/", "explain/", "gate/", "output/"]
)
def test_the_generic_engine_knows_nothing_about_any_particular_corpus(package: str) -> None:
    """If `CELEX` or `Formex` appears in these packages, the seam is broken.

    These are the packages that must run unchanged on the toy corpus. `diff` in particular is
    the primary shipped signal and it is generic core machinery, not EU machinery: a fact that
    is cheap to assert and expensive to discover having lost.

    `explain/` is the interesting one. The model is shown *opaque citation keys* minted by the
    caller rather than anything a corpus would recognise, so the prompt has nothing EU-shaped
    in it and the stage runs on the toy corpus unchanged. Keys that were EUR-Lex URLs would
    fail this test, which is the point of writing it.
    """
    for name, source in modules():
        if not name.startswith(package):
            continue
        assert "emendrix.eu" not in source, name
        assert not re.search(r"\bCELEX\b|\bFormex\b|\bCELLAR\b", source), name


def test_modules_stay_under_the_line_cap() -> None:
    """~300 lines, split at a real seam. Docstrings count: they are part of the reading."""
    too_long = {
        name: len(source.splitlines())
        for name, source in modules()
        if len(source.splitlines()) > 330
    }
    assert too_long == {}
