"""`emendrix-service status` and `backup ship`: what an operator runs and reads."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from emendrix_service.stop import not_built

__all__ = ["backup_app", "ship", "status"]

backup_app = typer.Typer(no_args_is_help=True, help="Ship database backups off the host.")


def status(
    email: Annotated[
        bool, typer.Option("--email", help="Also send the block to the operator address.")
    ] = False,
) -> None:
    """Print one status block: the last load, notify and drain, the queue and the bounces."""
    not_built("status")


@backup_app.command("ship")
def ship(
    dump: Annotated[Path, typer.Argument(help="The database dump to encrypt and upload.")],
) -> None:
    """Encrypt a dump to the age recipient, upload it over SFTP and prune old copies."""
    not_built("backup ship")
