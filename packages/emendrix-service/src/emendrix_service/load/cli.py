"""`emendrix-service load`: read the published record into the `content` schema."""

from __future__ import annotations

from typing import Annotated

import typer

from emendrix_service.stop import not_built

__all__ = ["load"]


def load(
    rebuild: Annotated[
        bool, typer.Option("--rebuild", help="Empty the content schema and load it afresh.")
    ] = False,
) -> None:
    """Upsert every published event into the content schema."""
    not_built("load")
