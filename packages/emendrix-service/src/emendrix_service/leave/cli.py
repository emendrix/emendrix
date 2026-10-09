"""`emendrix-service retention`: apply the retention table."""

from __future__ import annotations

from emendrix_service.stop import not_built

__all__ = ["retention"]


def retention() -> None:
    """Delete or blank every row past its retention period."""
    not_built("retention")
