"""`emendrix-service migrate`: bring the database schema to the newest migration."""

from __future__ import annotations

import logging

import anyio
import typer

from emendrix_service.db.migrate import head_revisions, upgrade_head
from emendrix_service.log import marker
from emendrix_service.settings import load_settings

__all__ = ["migrate"]


def migrate() -> None:
    """Upgrade the database to the newest migration."""
    settings = load_settings()
    head = ",".join(sorted(head_revisions()))
    try:
        anyio.run(upgrade_head, settings)
    except Exception as error:
        logging.getLogger(__name__).exception("the migration did not complete")
        marker("migrate", status="failed", head=head, error=type(error).__name__)
        raise typer.Exit(1) from error
    marker("migrate", status="complete", head=head)
