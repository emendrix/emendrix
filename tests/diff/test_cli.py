"""`emendrix diff` from the outside, offline, against the pinned fixture set.

`--fixture-dir` installs `FixtureResponseCache`, which has no code path to a socket: this is
the whole command, argument parsing through fetch, parse, diff and render, with the network
physically absent, which is how CI runs it.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from emendrix.cli import DISCLAIMER, app
from eu_pins import FIXTURE_DIR, MDR, MDR_V1, MDR_V2, OBSERVED_ON

runner = CliRunner()


def run(*arguments: str) -> str:
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
            *arguments,
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_the_plain_dump_states_the_counts_and_the_disclaimer() -> None:
    output = run()
    assert "0 inserted · 3 modified · 0 deleted · 0 renumbered · 6 deferred" in output
    assert "9 touched units · 131 unchanged · 0 disputed" in output
    assert "@ DEFERRED   AR 1 — Subject matter and scope" in output
    assert "applies from: 2021-05-26" in output
    assert DISCLAIMER in output


def test_the_json_dump_is_the_serialised_delta() -> None:
    payload = json.loads(run("--json"))
    assert payload["from_version"] == MDR_V1
    assert payload["to_version"] == MDR_V2
    assert payload["summary"]["deferred"] == 6
    first = payload["changes"][0]
    assert first["change_type"] == "DEFERRED"
    assert first["applies_from"] == "2021-05-26"
    assert first["before"] is not None and first["after"] is not None


def test_two_runs_print_the_same_bytes() -> None:
    """No timestamp, no set iteration order, no clock: the output is diffable in git."""
    assert run("--json") == run("--json")
    assert run() == run()


def test_a_version_with_no_english_text_prints_the_version_it_was_actually_served() -> None:
    """`02024R1689-20240712` exists in eleven languages, English not among them.

    The fetch falls back to the act as published and the tree is labelled with what was
    served, not with what was asked for, so the header of the dump reports `32024R1689`. A
    header that echoed the request would be a lie about which two texts were compared.
    """
    result = runner.invoke(
        app,
        [
            "diff",
            "32024R1689",
            "02024R1689-20240712",
            "02024R1689-20260727",
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--observed-on",
            OBSERVED_ON.isoformat(),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.startswith("eu:32024R1689 32024R1689 -> 02024R1689-20260727")
    assert "02024R1689-20240712" not in result.output


@pytest.mark.parametrize("arguments", [[], ["diff"]])
def test_the_command_is_self_documenting(arguments: list[str]) -> None:
    result = runner.invoke(app, [*arguments, "--help"])
    assert result.exit_code == 0
    assert "diff" in result.output
