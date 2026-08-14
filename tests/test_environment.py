"""The suite's own environment, asserted rather than assumed.

`explain/settings.py` states the principle: a test whose result depends on the shell it ran in
is not a test. `conftest.py` enforces it by scrubbing every `EMENDRIX_*` variable for the
session; this file is what keeps the enforcement from being quietly removed, and what a
developer's local overrides run into before they reach a cassette lookup.
"""

from __future__ import annotations

import os


def test_no_emendrix_variable_is_visible_from_inside_a_test() -> None:
    """A configuration override in the shell must change no measurement in this suite.

    Measured 2026-08-08: with `EMENDRIX_MODEL` and `EMENDRIX_JUDGE_MODEL` exported the suite was
    19 failed, 883 passed, 18 errors; with the same tree and neither variable, 920 passed. The
    committed cassettes are pinned to the constants in `explain/settings.py` and `eval_/judge.py`,
    so a run that resolves a different model looks for recordings nobody made.
    """
    assert [key for key in os.environ if key.startswith("EMENDRIX_")] == []
