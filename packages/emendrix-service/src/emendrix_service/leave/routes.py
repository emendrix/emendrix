"""Unsubscribe under `/u/`, and export, delete and privacy under `/account/`.

**One-click unsubscribe (RFC 8058).** The link in every email is a signed watchlist id. Its GET
only shows a page with one button, because link scanners fetch every GET; its POST stops the
email. A mail provider's one-click POST carries no cookie, no `Origin` and a body that may be
form-encoded or multipart, so the POST reads neither the body nor any cookie: the signed path
alone decides, and posting it twice changes nothing the second time.

**Deleting an account** answers the result page directly rather than redirecting to the sign-in
page, so the sentence about backups is shown without a notice code on another feature's page.
"""

from __future__ import annotations

import json
from typing import Annotated, Final
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from markupsafe import Markup

from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.db import Db
from emendrix_service.db.accounts import audit
from emendrix_service.db.enums import AuditAction
from emendrix_service.db.leave import delete_user, export_rows, unsubscribe, unsubscribe_target
from emendrix_service.signing import verify
from emendrix_service.watch.pages import Holder, account_holder
from emendrix_service.web.csrf import csrf_protect
from emendrix_service.web.errors import render_error
from emendrix_service.web.session import REFRESH, clear_session_cookie
from emendrix_service.web.templating import render_page

__all__ = ["export_bytes", "router"]

UNSUBSCRIBE_TITLE: Final = "Stop the email"

Owner = Annotated[Holder, Depends(account_holder)]
"""The signed-in account, a suspended one included: suspension stops mail, not leaving."""

links = APIRouter(prefix="/u")
account = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])


def _watchlist_of(request: Request, token: str) -> UUID | None:
    payload = verify("unsub", token, secret=request.app.state.settings.secret_key)
    if payload is None:
        return None
    try:
        return UUID(payload)
    except ValueError:
        return None


def _gone(request: Request) -> Response:
    return render_page(
        request, "leave/unsubscribe_gone.html", title="Watchlist deleted", status=410
    )


@links.get("/unsubscribe/{token}")
async def unsubscribe_page(request: Request, token: str) -> Response:
    watchlist_id = _watchlist_of(request, token)
    if watchlist_id is None:
        return render_error(request, 404)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        target = await unsubscribe_target(tx, watchlist_id)
    if target is None:
        return _gone(request)
    return render_page(request, "leave/unsubscribe.html", title=UNSUBSCRIBE_TITLE, target=target)


@links.post("/unsubscribe/{token}")
async def unsubscribe_now(request: Request, token: str) -> Response:
    watchlist_id = _watchlist_of(request, token)
    if watchlist_id is None:
        return render_error(request, 404)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        target = await unsubscribe_target(tx, watchlist_id)
        done = await unsubscribe(tx, watchlist_id, request.app.state.clock.now())
    if target is None or done == "gone":
        return _gone(request)
    return render_page(request, "leave/unsubscribed.html", title="Email stopped", target=target)


def export_bytes(document: object) -> bytes:
    """The export file: sorted keys, indented, UTF-8, ending in a newline."""
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


@account.get("/export")
async def export(request: Request, user: Owner) -> Response:
    db: Db = request.app.state.db
    now = request.app.state.clock.now()
    async with db.transaction() as tx:
        document = await export_rows(tx, user.user_id)
        if document is not None:
            await audit(tx, user.user_id, AuditAction.EXPORT, now)
    if document is None:
        return render_error(request, 404)
    return Response(
        export_bytes(document.model_dump(mode="json")),
        media_type="application/json",
        headers={
            "content-disposition": (
                f'attachment; filename="emendrix-export-{now.date().isoformat()}.json"'
            )
        },
    )


@account.get("/delete")
async def delete_page(request: Request, user: Owner) -> Response:
    return render_page(request, "leave/delete.html", title="Delete your account")


@account.post("/delete", dependencies=[Depends(post_limit)])
async def delete_account(request: Request, user: Owner) -> Response:
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        await delete_user(tx, user.user_id, request.app.state.clock.now())
    # A slide decided earlier in this request would set the cookie again after the clearing.
    if hasattr(request.state, REFRESH):
        delattr(request.state, REFRESH)
    response = render_page(request, "leave/deleted.html", title="Account deleted")
    clear_session_cookie(response)
    return response


@account.get("/privacy")
async def privacy(request: Request) -> Response:
    """The operator's privacy notice inside the shell.

    The fragment is operator-authored HTML from the deployment's own configuration, trusted as
    the shell is, so it is inserted unescaped. It is read on each request, so the operator can
    change it without a restart; a notice that is unset or unreadable answers 404.
    """
    path = request.app.state.settings.privacy_notice
    notice: str | None = None
    if path is not None:
        try:
            notice = await anyio.Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            notice = None
    if notice is None:
        return render_page(request, "leave/no_privacy.html", title="Privacy notice", status=404)
    return render_page(request, "leave/privacy.html", title="Privacy notice", notice=Markup(notice))


router = APIRouter()
router.include_router(links)
router.include_router(account)
