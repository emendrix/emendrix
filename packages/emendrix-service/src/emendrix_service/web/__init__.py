"""The web layer every page goes through: the account shell, templating, security headers,
CSRF, the session dependency and the error pages. `install` is called once by `create_app`.

Nothing serves static files: an account page links the site's own stylesheet, icon and fonts
by root-absolute paths, which the site's server answers.
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI

from emendrix_service.db.ready import ReadyCheck
from emendrix_service.settings import ServiceSettings, variable
from emendrix_service.web.errors import CatchAll, install_handlers
from emendrix_service.web.security import CookieWriter, HostCheck, RequestLog, SecurityHeaders
from emendrix_service.web.shell import Shell, ShellSource

__all__ = ["PROBES", "install"]

PROBES: Final = frozenset({"/healthz", "/readyz"})
"""Asked by the cluster at the pod's own address: no host check, no request log line."""


def _shell_check(source: ShellSource | None) -> ReadyCheck:
    async def shell_ready() -> str | None:
        if source is None:
            return f"{variable('shell')} is not set"
        shell = source.get()
        return None if isinstance(shell, Shell) else shell

    return shell_ready


def install(app: FastAPI) -> None:
    """Add the shell, its ready check, the middleware and the error handlers to `app`.

    Middleware added later wraps what was added earlier, so a response passes, inside out:
    the catch-all, the host check, the cookies, the request log, then the security headers,
    which therefore reach every answer, a refused host and the 500 page included.
    """
    settings: ServiceSettings = app.state.settings
    source = ShellSource(settings.shell) if settings.shell is not None else None
    app.state.shell = source
    app.state.ready_checks.append(_shell_check(source))
    install_handlers(app)
    app.add_middleware(CatchAll)
    app.add_middleware(HostCheck, allowed_hosts=settings.allowed_hosts, exempt=PROBES)
    app.add_middleware(CookieWriter)
    app.add_middleware(RequestLog, quiet=PROBES)
    app.add_middleware(SecurityHeaders)
