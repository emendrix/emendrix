"""The web process: `create_app` builds it, `serve` listens. The only module that listens.

The app carries its settings, clock and mailer on `app.state`, so every route and dependency
reads them from the request and a test swaps all three by building its own app. The web layer
is installed by `web.install`, and each feature mounts one router; this module wires them and
holds no page of its own.

There is no API documentation route: the service serves pages and token-addressed endpoints,
and a schema of them is not something a reader of the record can use. `GET /healthz` says the
process answers; `GET /readyz` says it can serve. Neither is proxied to the public.

Readiness is a list of checks on `app.state.ready_checks`, each answering `None` or a reason;
`/readyz` answers `503` with the first reason. The database's checks join the list when the
lifespan opens the database and leave it when the lifespan closes, and the web layer adds its own
through `web.install`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from emendrix_service import __version__, web
from emendrix_service.auth import routes as auth_routes
from emendrix_service.clock import Clock, SystemClock
from emendrix_service.db import Db
from emendrix_service.db.ready import ReadyCheck, ready_checks
from emendrix_service.feed import routes as feed_routes
from emendrix_service.leave import routes as leave_routes
from emendrix_service.mail import hooks as mail_hooks
from emendrix_service.mail.port import Mailer
from emendrix_service.mail.transport import SmtpMailer
from emendrix_service.settings import ServiceSettings
from emendrix_service.watch import routes as watch_routes

__all__ = ["HEALTH_PATH", "READY_PATH", "create_app", "serve"]

HEALTH_PATH: Final = "/healthz"
READY_PATH: Final = "/readyz"


def create_app(
    settings: ServiceSettings, *, clock: Clock, mailer: Mailer, db: Db | None = None
) -> FastAPI:
    """The ASGI app for one deployment, reading the time from `clock`, sending through `mailer`.

    Without `db`, the lifespan opens a pool over the configured database and closes it on
    shutdown; a `db` given here belongs to the caller, which closes it.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = db if db is not None else Db.connect(settings)
        app.state.db = database
        checks = ready_checks(database)
        app.state.ready_checks[:0] = checks
        try:
            yield
        finally:
            for check in checks:
                app.state.ready_checks.remove(check)
            app.state.db = db
            if db is None:
                await database.dispose()

    app = FastAPI(
        lifespan=lifespan,
        title="emendrix-service",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.clock = clock
    app.state.mailer = mailer
    app.state.db = db
    app.state.ready_checks = list[ReadyCheck]()

    @app.api_route(HEALTH_PATH, methods=["GET", "HEAD"], response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.api_route(READY_PATH, methods=["GET", "HEAD"], response_class=PlainTextResponse)
    async def readyz() -> PlainTextResponse:
        checks: list[ReadyCheck] = app.state.ready_checks
        for check in tuple(checks):
            reason = await check()
            if reason is not None:
                return PlainTextResponse(reason, status_code=503)
        return PlainTextResponse("ok")

    web.install(app)
    for router in (
        auth_routes.router,
        watch_routes.router,
        leave_routes.router,
        feed_routes.router,
        mail_hooks.router,
    ):
        app.include_router(router)
    return app


def serve(settings: ServiceSettings) -> None:
    """Listen on the configured address until the process is stopped."""
    clock = SystemClock()
    app = create_app(settings, clock=clock, mailer=SmtpMailer(settings, clock))
    # The access log would print token-bearing paths under `/u/`; the web layer logs requests
    # itself. `log_config=None` leaves uvicorn's own records to the JSON handler.
    uvicorn.run(
        app,
        host=settings.bind,
        port=settings.port,
        server_header=False,
        proxy_headers=False,
        access_log=False,
        log_config=None,
    )
