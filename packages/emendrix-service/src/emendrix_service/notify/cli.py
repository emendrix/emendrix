"""`emendrix-service notify`, `digest` and `tick`: announce new events and plan deliveries."""

from __future__ import annotations

from typing import Annotated

import typer

from emendrix_service.stop import not_built

__all__ = ["digest", "notify", "tick"]


def notify() -> None:
    """Announce new events once each, and write their matches and instant deliveries."""
    not_built("notify")


def digest(
    now: Annotated[
        str | None,
        typer.Option(
            "--now",
            help="Plan as if it were this ISO 8601 instant, with an offset; default the clock.",
        ),
    ] = None,
) -> None:
    """Plan the daily, weekly and heartbeat deliveries that are due."""
    not_built("digest")


def tick() -> None:
    """Load, notify, digest and drain, each step logged, in one run."""
    not_built("tick")
