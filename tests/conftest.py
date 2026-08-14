"""Test configuration, and the offline wiring every EU test runs on.

Its presence puts `tests/` on `sys.path`, so shared test doubles that are not part of the
shipped package import by name from anywhere under `tests/`: `toy_corpus.py`, the second
implementor of the corpus seam, and `eu_pins.py`, what the EU tests are pinned to.

The EU fixtures below install `FixtureResponseCache`, which has no code path to a socket. A
test that asks for a document nobody pinned fails with `FixtureMissing` naming the request,
not with a network call, which is what makes "CI never touches the network" a property of
the design rather than a promise. (One conftest, not one per directory: two modules named
`conftest` are ambiguous to `mypy --strict`.)

`_no_ambient_configuration` does the same job for configuration that the fixture cache does for
the network: it takes the developer's shell out of the answer.

`changelog_repo` is here rather than beside the suites that use it for the same reason: a
second `conftest` module would be ambiguous to `mypy --strict`, and fixtures are lazy, so a
suite that never asks for it never pays the seconds it costs.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emendrix.cli import app
from emendrix.eu.cache import FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from eu_pins import FIXTURE_DIR, OBSERVED_ON
from run_pins import RUN_CASSETTE_DIR, TRANSITION

runner = CliRunner()

ENV_PREFIX = "EMENDRIX_"
"""Every configuration variable this project reads is under it. API keys deliberately are not:
the cassette recorders read `OPENROUTER_API_KEY` and `ANTHROPIC_API_KEY` to decide between a real
recording and an honestly-labelled stub, and scrubbing those would break that choice."""


@pytest.fixture(autouse=True, scope="session")
def _no_ambient_configuration() -> Iterator[None]:
    """Every `EMENDRIX_*` override removed for the session. The suite is not a shell script.

    `ExplainSettings` reads no environment by construction, but two call sites do: the pipeline
    CLI builds the explain settings with `from_env`, and the eval layer resolves the judge from
    `EMENDRIX_JUDGE_MODEL`. The suite drives both. Measured 2026-08-08: with `EMENDRIX_MODEL` and
    `EMENDRIX_JUDGE_MODEL` exported the suite was 19 failed, 883 passed, 18 errors, every failure
    a cassette lookup under a model nothing was recorded against; with the same tree and neither
    variable, 920 passed. What a committed cassette contains may not depend on who ran the tests.

    Function-scoped `monkeypatch.setenv` still layers on top, so a test that sets a variable to
    prove an override works keeps working, and gets it back to nothing when it finishes.
    """
    with pytest.MonkeyPatch.context() as patch:
        for name in [key for key in os.environ if key.startswith(ENV_PREFIX)]:
            patch.delenv(name, raising=False)
        yield


@pytest.fixture
def fixture_cache() -> FixtureResponseCache:
    return FixtureResponseCache(FIXTURE_DIR)


@pytest.fixture
def http(fixture_cache: FixtureResponseCache) -> CellarHttp:
    return CellarHttp(cache=fixture_cache)


@pytest.fixture
def client(http: CellarHttp) -> CellarClient:
    return CellarClient(http, observed_on=OBSERVED_ON)


@pytest.fixture(scope="module")
def changelog_repo(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The MDR transition committed into an output repository, offline, exactly as `run` does.

    The patches are undone through the context manager rather than a trailing `patch.undo()`,
    because the assertion below sits between the two: a failing command would otherwise leave
    `EMENDRIX_EXPLAIN_*` set for the rest of the session, turning one broken fixture into a
    second, unrelated failure in the test that asserts the suite reads no ambient configuration.

    Module-scoped: the explain invocation takes seconds, and a function scope would pay them
    again for every test that asks.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", str(RUN_CASSETTE_DIR))
        patch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "replay")
        patch.delenv("EMENDRIX_OUTPUT_REPO", raising=False)
        for variable in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
            patch.delenv(variable, raising=False)
        repo = tmp_path_factory.mktemp("changelogs") / "repo"
        result = runner.invoke(
            app,
            [
                "explain",
                TRANSITION.celex,
                TRANSITION.from_version,
                TRANSITION.to_version,
                "--fixture-dir",
                str(FIXTURE_DIR),
                "--observed-on",
                TRANSITION.observed_on.isoformat(),
                "--json-out",
                str(repo.parent / "report.json"),
                "--output-repo",
                str(repo),
            ],
        )
        assert result.exit_code == 0, result.output
        yield repo
