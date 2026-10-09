"""The web layer every page goes through: the account shell, templating, security headers,
CSRF, the session dependency and the error pages. `install` is called once by `create_app`."""

from __future__ import annotations

from fastapi import FastAPI

__all__ = ["install"]


def install(app: FastAPI) -> None:
    """Add the web layer's middleware, handlers and ready checks to `app`.

    This version installs nothing, so the app answers only its probes and its routers.
    """
