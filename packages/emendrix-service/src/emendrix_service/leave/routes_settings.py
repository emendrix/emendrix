"""`GET /account/settings`, the Account tab, for any account holding a live session."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from emendrix_service.leave.settings import settings_page
from emendrix_service.watch.pages import Holder, account_holder
from emendrix_service.web.csrf import csrf_protect

__all__ = ["settings"]

settings = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])


@settings.get("/settings")
async def account_settings(
    request: Request, holder: Annotated[Holder, Depends(account_holder)]
) -> Response:
    return await settings_page(request, holder)
