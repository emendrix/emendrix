"""The account page and the watchlist pages under `/account/`.

Split along the seam between the two ways in: `routes_landing` answers a "Watch this" link,
signed in or not, and `routes_account` holds the account page and the editor, signed in only.
Both routers check CSRF on every POST.
"""

from __future__ import annotations

from fastapi import APIRouter

from emendrix_service.watch import routes_account, routes_landing

__all__ = ["router"]

router = APIRouter()
router.include_router(routes_landing.router)
router.include_router(routes_account.router)
