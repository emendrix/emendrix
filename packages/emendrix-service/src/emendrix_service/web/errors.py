"""Error pages in the site's look, and the one place an unexpected failure is caught.

Each status a reader can meet has one plain page. The page says what happened and what to do,
never why in the code's terms. An unexpected failure is logged with a short error id and the
place of each frame it passed through, but neither its message nor any source line, because a
database error's message can quote the values of the statement, an address among them. The
page shows the same id, so a reader's report can be matched to the log line.
"""

from __future__ import annotations

import logging
import secrets
import traceback
from typing import Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from emendrix_service.web.session import SignInRequired
from emendrix_service.web.templating import render_page

__all__ = ["MESSAGES", "CatchAll", "install_handlers", "render_error"]

MESSAGES: Final[dict[int, tuple[str, str]]] = {
    400: ("Bad request", "The form could not be read. Go back and try again."),
    403: (
        "This form has expired",
        "The form could not be checked. Go back, reload the page and send it again.",
    ),
    404: ("Page not found", "There is no account page at this address."),
    405: ("Not allowed", "This address does not answer that kind of request."),
    410: ("Gone", "This address has been replaced and no longer answers."),
    429: ("Too many requests", "Too many requests came from your address. Wait a while."),
    500: ("Something went wrong", "The page could not be made. Try again in a moment."),
    503: ("Unavailable", "The account service is not available at the moment."),
}

logger = logging.getLogger(__name__)


def render_error(request: Request, status: int, *, error_id: str | None = None) -> Response:
    """The error page for `status`, through the shell."""
    title, message = MESSAGES.get(status, MESSAGES[400 if status < 500 else 500])
    return render_page(
        request,
        "web/error.html",
        title=title,
        status=status,
        heading=title,
        message=message,
        error_id=error_id,
    )


async def _http_error(request: Request, error: Exception) -> Response:
    status = error.status_code if isinstance(error, StarletteHTTPException) else 500
    response = render_error(request, status)
    if isinstance(error, StarletteHTTPException) and error.headers:
        for name, value in error.headers.items():
            response.headers.setdefault(name, value)
    return response


async def _invalid_form(request: Request, error: Exception) -> Response:
    return render_error(request, 400)


async def _sign_in(request: Request, error: Exception) -> Response:
    location = error.location() if isinstance(error, SignInRequired) else "/account/signin"
    return RedirectResponse(location, status_code=303)


def install_handlers(app: FastAPI) -> None:
    """Answer HTTP errors, unreadable forms and a missing sign-in with pages of their own."""
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _invalid_form)
    app.add_exception_handler(SignInRequired, _sign_in)


class CatchAll:
    """Turns an exception nothing else answered into the 500 page and one log line.

    Nothing is raised further, so the server logs no traceback with a message of its own. A
    failure after the response has started can only be logged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = [False]

        async def tracking(message: Message) -> None:
            if message["type"] == "http.response.start":
                started[0] = True
            await send(message)

        try:
            await self.app(scope, receive, tracking)
        except Exception as error:
            error_id = secrets.token_hex(4)
            frames = "\n".join(
                f"  {frame.filename}:{frame.lineno} in {frame.name}"
                for frame in traceback.extract_tb(error.__traceback__)
            )
            logger.error("error %s: %s\n%s", error_id, type(error).__name__, frames)
            if not started[0]:
                response = render_error(Request(scope, receive), 500, error_id=error_id)
                await response(scope, receive, send)
