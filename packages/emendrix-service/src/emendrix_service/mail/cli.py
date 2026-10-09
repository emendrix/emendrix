"""`emendrix-service mail ...`: send what the outbox holds."""

from __future__ import annotations

from typing import Annotated

import typer

from emendrix_service.stop import not_built

__all__ = ["app", "drain"]

app = typer.Typer(no_args_is_help=True, help="Send queued email.")


@app.command("drain")
def drain(
    limit: Annotated[int, typer.Option(min=1, help="The most rows to send in this run.")] = 200,
) -> None:
    """Send queued outbox rows that are due, retrying transient refusals on schedule."""
    not_built("mail drain")
