"""How a command refuses to run: one line on stderr naming the program, then exit code 2.

Exit 2 is what a scheduler reads as "this job cannot run as configured", which is a different
fact from a run that started and failed (exit 1, with a `failed` marker). Nothing here logs: a
refusal happens before there is anything to report.
"""

from __future__ import annotations

import sys
from typing import Final, NoReturn

__all__ = ["PROGRAM", "REFUSED", "stop"]

PROGRAM: Final = "emendrix-service"

REFUSED: Final = 2
"""The exit code of a command that refused to start."""


def stop(message: str) -> NoReturn:
    """Print `emendrix-service: <message>` on stderr and exit with code 2."""
    print(f"{PROGRAM}: {message}", file=sys.stderr)
    raise SystemExit(REFUSED)
