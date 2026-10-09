"""The mail provider's delivery events, received under `/u/hooks/`."""

from __future__ import annotations

from fastapi import APIRouter

__all__ = ["router"]

router = APIRouter()
