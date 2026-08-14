"""The commands that produce the artifacts: `diff --markdown`, and `--output-repo` on the loop.

Two things are being checked, and they are different in kind.

**Diff-only is a product mode.** `emendrix diff --markdown` renders the changelog entry with no
prose in it, and it does so with no API key, no cassette directory and no network. The
deterministic half of the loop is the half with measured numbers behind it, and it is useful on
its own.

**The loop ends in a commit.** `emendrix explain --output-repo` runs the whole pipeline offline
and finishes with a git commit somebody can review, which is the product claim of the project
made executable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.output import OUTPUT_REPO_ENV, resolve_repo_path
from eu_pins import FIXTURE_DIR, MDR, MDR_V1, MDR_V2, OBSERVED_ON
from run_pins import RUN_CASSETTE_DIR, TRANSITION

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_ambient_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(OUTPUT_REPO_ENV, raising=False)
    for variable in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(variable, raising=False)


# ------------------------------------------------------------------ emendrix diff --markdown


def diff(*extra: str) -> str:
    result = runner.invoke(
        app,
        [
            "diff",
            MDR,
            MDR_V1,
            MDR_V2,
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--observed-on",
            OBSERVED_ON.isoformat(),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    return result.output


def test_the_diff_renders_a_changelog_entry_with_no_prose_in_it() -> None:
    output = diff("--markdown")
    assert "**DEFERRED · Art. 1 — Subject matter and scope** · applies from: 2021-05-26" in output
    assert "**Diff only**" in output
    assert "Quoted verbatim by the citation gate" not in output
    assert DISCLAIMER.split(":")[0] in output


def test_the_diff_only_path_needs_no_model_and_no_cassettes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pointed at a cassette store that does not exist: a model call would fail loudly."""
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", "/nonexistent/cassettes")
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "replay")
    assert "**Diff only**" in diff("--markdown")


def test_two_renderings_of_one_answer_are_not_both_asked_for_at_once() -> None:
    result = runner.invoke(app, ["diff", MDR, MDR_V1, MDR_V2, "--json", "--markdown"])
    assert result.exit_code == 2
    assert "pick one" in result.output


def test_the_markdown_diff_is_byte_stable() -> None:
    assert diff("--markdown") == diff("--markdown")


# ------------------------------------------------------------------ the loop's commit


def loop(tmp_path: Path, *extra: str) -> None:
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
            OBSERVED_ON.isoformat(),
            "--json-out",
            str(tmp_path / "report.json"),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)


@pytest.fixture
def _replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", str(RUN_CASSETTE_DIR))
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "replay")


@pytest.mark.usefixtures("_replay")
def test_the_loop_ends_in_a_reviewable_git_commit(tmp_path: Path) -> None:
    target = tmp_path / "changelog"
    loop(tmp_path, "--output-repo", str(target))
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=target, capture_output=True, text=True, check=True
    ).stdout
    assert f"{TRANSITION.celex}: {TRANSITION.from_version} -> {TRANSITION.to_version}" in log
    assert (target / "eu" / TRANSITION.celex / "CHANGELOG.md").is_file()
    assert (
        target / "eu" / TRANSITION.celex / "changes" / f"{TRANSITION.to_version}.json"
    ).is_file()


@pytest.mark.usefixtures("_replay")
def test_with_no_repository_configured_nothing_is_written_anywhere(tmp_path: Path) -> None:
    """There is no default path, on purpose: a git repository is not a cache directory."""
    loop(tmp_path)
    assert sorted(item.name for item in tmp_path.iterdir()) == ["report.json"]


@pytest.mark.usefixtures("_replay")
def test_the_environment_configures_it_when_the_flag_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OUTPUT_REPO_ENV, str(tmp_path / "from-env"))
    loop(tmp_path)
    assert (tmp_path / "from-env" / ".git").is_dir()


@pytest.mark.usefixtures("_replay")
def test_a_repository_inside_another_one_is_a_message_and_not_a_traceback(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
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
            OBSERVED_ON.isoformat(),
            "--json-out",
            str(tmp_path / "report.json"),
            "--output-repo",
            str(tmp_path / "nested"),
        ],
    )
    assert result.exit_code == 2
    assert "must be a repository of its own" in result.output


# ------------------------------------------------------------------ precedence


def test_the_flag_beats_the_environment_which_beats_the_file() -> None:
    """Stated once in `output/config.py`; asserted here so it stays stated."""
    environment = {OUTPUT_REPO_ENV: "/from/env"}
    assert resolve_repo_path(Path("/from/flag"), Path("/from/file"), environment=environment) == (
        Path("/from/flag")
    )
    assert resolve_repo_path(None, Path("/from/file"), environment=environment) == Path("/from/env")
    assert resolve_repo_path(None, Path("/from/file"), environment={}) == Path("/from/file")
    assert resolve_repo_path(None, None, environment={}) is None
