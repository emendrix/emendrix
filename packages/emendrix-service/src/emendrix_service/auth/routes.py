"""The sign-in pages under `/account/`.

Every POST here passes the router's CSRF check. A link request always answers the same "check
your inbox" page, whatever happened, so the page never says whether an address has an account.
The confirm page's GET only shows a button; its POST is what consumes the link.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response

from emendrix_service.auth.confirm import Confirmed, confirm
from emendrix_service.auth.logic import local_path, normalise_email
from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.auth.service import request_link_from
from emendrix_service.db import Db
from emendrix_service.db.accounts import audit, delete_session, delete_sessions_for
from emendrix_service.db.enums import AuditAction, TokenPurpose
from emendrix_service.web.csrf import PRE_COOKIE, csrf_protect
from emendrix_service.web.session import (
    REFRESH,
    SignedIn,
    clear_session_cookie,
    current_user,
    set_session_cookie,
)
from emendrix_service.web.templating import render_page

__all__ = ["router"]

router = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])

SIGNIN_TITLE = "Sign in"
INVALID_ADDRESS = "That is not an email address this service can send to."

FormText = Annotated[str, Form()]


def _signin_page(
    request: Request, *, next_path: str | None, email: str = "", errors: tuple[str, ...] = ()
) -> Response:
    return render_page(
        request,
        "auth/signin.html",
        title=SIGNIN_TITLE,
        status=400 if errors else 200,
        next_path=next_path or "",
        email=email,
        errors=errors,
    )


@router.get("/signin")
async def signin_form(
    request: Request,
    signed_in: Annotated[SignedIn | None, Depends(current_user)],
    next: str | None = None,
) -> Response:
    if signed_in is not None:
        return RedirectResponse(local_path(next) or "/account/", status_code=303)
    return _signin_page(request, next_path=local_path(next))


@router.post("/signin")
async def signin(request: Request, email: FormText = "", next: FormText = "") -> Response:
    address = normalise_email(email)
    if address is None:
        return _signin_page(
            request, next_path=local_path(next), email=email, errors=(INVALID_ADDRESS,)
        )
    send = await request_link_from(
        request, email=address, purpose=TokenPurpose.SIGNIN, next_path=local_path(next)
    )
    response = render_page(request, "auth/check_inbox.html", title="Check your inbox")
    response.background = send
    return response


@router.get("/confirm/{token}")
async def confirm_page(request: Request, token: str, next: str | None = None) -> Response:
    return render_page(
        request,
        "auth/confirm.html",
        title="Confirm and sign in",
        next_path=local_path(next) or "",
    )


@router.post("/confirm/{token}", dependencies=[Depends(post_limit)])
async def confirm_link(request: Request, token: str, next: FormText = "") -> Response:
    state = request.app.state
    outcome = await confirm(state.db, state.settings, state.clock, token, next_path=next)
    if not isinstance(outcome, Confirmed):
        return render_page(
            request, "auth/link_refused.html", title="This link cannot be used", status=410
        )
    response = RedirectResponse(outcome.next_path, status_code=303)
    set_session_cookie(response, outcome.session_token)
    response.delete_cookie(PRE_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response


def _signed_out(request: Request) -> Response:
    # A slide decided earlier in this request would set the cookie again after the clearing.
    if hasattr(request.state, REFRESH):
        delattr(request.state, REFRESH)
    response = RedirectResponse("/account/signin", status_code=303)
    clear_session_cookie(response)
    return response


@router.post("/signout", dependencies=[Depends(post_limit)])
async def signout(
    request: Request, signed_in: Annotated[SignedIn | None, Depends(current_user)]
) -> Response:
    if signed_in is not None:
        db: Db = request.app.state.db
        async with db.transaction() as tx:
            await delete_session(tx, signed_in.session_hash)
    return _signed_out(request)


@router.post("/signout-everywhere", dependencies=[Depends(post_limit)])
async def signout_everywhere(
    request: Request, signed_in: Annotated[SignedIn | None, Depends(current_user)]
) -> Response:
    if signed_in is not None:
        db: Db = request.app.state.db
        async with db.transaction() as tx:
            await delete_sessions_for(tx, signed_in.user_id)
            await audit(
                tx, signed_in.user_id, AuditAction.SIGNOUT_ALL, request.app.state.clock.now()
            )
    return _signed_out(request)
