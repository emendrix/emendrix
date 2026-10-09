"""`emendrix-service migrate`: bring the database schema to the newest migration."""

from __future__ import annotations

from emendrix_service.stop import not_built

__all__ = ["migrate"]


def migrate() -> None:
    """Upgrade the database to the newest migration."""
    not_built("migrate")
