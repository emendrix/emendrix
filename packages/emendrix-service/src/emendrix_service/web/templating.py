"""One Jinja environment over every feature's templates, and the two ways a feature uses it.

Templates are addressed as `<feature>/<name>` (`auth/signin.html`). A feature whose
`templates/` directory does not exist yet is left out of the loader, so a feature adds pages by
adding files, without editing this module. HTML templates are autoescaped; text templates (the
plain-text part of an email) are not, because nothing reads them as markup.

`render_page` wraps a template in the account shell. `render_mail` renders the text and HTML
parts of one email from `<base>.txt` and `<base>.html`.
"""

from __future__ import annotations

import html
from functools import cache
from importlib.resources import files
from typing import Final

from fastapi import Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from jinja2 import (
    BaseLoader,
    Environment,
    PackageLoader,
    PrefixLoader,
    StrictUndefined,
    select_autoescape,
)
from markupsafe import Markup

from emendrix_service import DISCLAIMER
from emendrix_service.web.csrf import csrf_field
from emendrix_service.web.identity import account_slot
from emendrix_service.web.session import reader_email
from emendrix_service.web.shell import Shell, ShellSource

__all__ = [
    "ACCOUNT_CURRENT",
    "FEATURES",
    "UNAVAILABLE",
    "environment",
    "render_mail",
    "render_page",
]

FEATURES: Final = ("web", "auth", "watch", "notify", "leave", "feed")

ACCOUNT_CURRENT: Final = "account_current"
"""The `render_page` keyword that marks the header's account link as the current page."""

UNAVAILABLE: Final = f"The account pages are not available at the moment.\n\n{DISCLAIMER}\n"
"""What a page answers, as plain text with a 503, while no shell has ever been read."""


@cache
def environment() -> Environment:
    """The process's one environment; templates are read once and kept."""
    package = files("emendrix_service")
    loaders: dict[str, BaseLoader] = {
        feature: PackageLoader("emendrix_service", f"{feature}/templates")
        for feature in FEATURES
        if package.joinpath(feature, "templates").is_dir()
    }
    env = Environment(
        loader=PrefixLoader(loaders),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # `quote=False` leaves the apostrophe as written, so the sentence stays verbatim in HTML.
    env.globals["disclaimer"] = Markup(html.escape(DISCLAIMER, quote=False))
    env.globals["disclaimer_text"] = DISCLAIMER
    env.globals["csrf_field"] = csrf_field
    return env


def render_page(
    request: Request,
    template: str,
    *,
    title: str,
    status: int = 200,
    **context: object,
) -> Response:
    """`template` rendered into the account shell, as the page's response.

    The header names the reader `remember_reader` noted for this request. `account_current=True`
    marks that link as the current page, for the Account tab; it is taken out of `context`
    rather than declared, because callers spread `dict[str, object]` wording into `context` and
    a declared `bool` would not accept it.
    """
    account_current = context.pop(ACCOUNT_CURRENT, False) is True
    source: ShellSource | None = request.app.state.shell
    shell = source.get() if source is not None else None
    if not isinstance(shell, Shell):
        return PlainTextResponse(UNAVAILABLE, status_code=503)
    body = (
        environment()
        .get_template(template)
        .render(request=request, site_url=request.app.state.settings.site_url, **context)
    )
    account = account_slot(reader_email(request), current=account_current)
    page = shell.render(title=title, content=Markup(body), account=account)
    return HTMLResponse(page, status_code=status)


def render_mail(template_base: str, *, site_url: str, **context: object) -> tuple[str, str]:
    """The text and HTML parts of one email, from `<template_base>.txt` and `.html`."""
    env = environment()
    values = {"site_url": site_url, **context}
    text = env.get_template(f"{template_base}.txt").render(**values)
    markup = env.get_template(f"{template_base}.html").render(**values)
    return text, markup
