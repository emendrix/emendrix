"""The web layer around every page: headers, hosts, CSRF, client address, errors, readiness,
and the header's account slot.

Only the signed-in slot needs the database: a visitor with no session cookie is never looked up.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Iterator, Sequence
from pathlib import Path

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient, Headers
from starlette.routing import BaseRoute

from emendrix_service import DISCLAIMER
from emendrix_service.app import create_app
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ServiceSettings
from emendrix_service.web.client import client_ip
from emendrix_service.web.csrf import PRE_COOKIE, csrf_protect
from emendrix_service.web.security import CONTENT_SECURITY_POLICY, loggable_path
from emendrix_service.web.session import remember_reader
from emendrix_service.web.shell import CONTENT_MARKER
from emendrix_service.web.templating import render_page
from tests.conftest import SHELL_HTML, SITE_URL, settings_values
from tests.test_svc_watch_fixtures import loaded as loaded
from tests.test_svc_watch_fixtures import sign_in

pytestmark = pytest.mark.anyio

TOKEN = re.compile(r'name="csrf" value="([^"]+)"')

SLOT = re.compile(r'<div id="search" data-root="/"></div>(.*?)</header>', re.DOTALL)


def header_slot(page: str) -> str:
    """What the service wrote into the shell's account slot."""
    found = SLOT.search(page)
    assert found is not None, page
    return found.group(1)


@pytest.fixture
def app(settings: ServiceSettings, clock: FixedClock, mailer: RecordingMailer) -> FastAPI:
    return create_app(settings, clock=clock, mailer=mailer)


@pytest.fixture
async def http(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=SITE_URL) as client:
        yield client


def assert_secured(headers: Headers) -> None:
    assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "same-origin"
    assert headers["cache-control"] == "private, no-store"
    assert "camera=()" in headers["permissions-policy"]


async def test_svc_web_a_page_is_the_shell_with_headers_and_no_script(http: AsyncClient) -> None:
    response = await http.get("/account/signin")
    assert response.status_code == 200
    assert_secured(response.headers)
    assert "<title>Sign in</title>" in response.text
    assert "<script" not in response.text
    assert "sets one cookie" in response.text
    assert "<!--emendrix:" not in response.text


def test_svc_web_the_policy_allows_own_forms_and_no_script() -> None:
    assert "form-action 'self'" in CONTENT_SECURITY_POLICY
    assert "script-src" not in CONTENT_SECURITY_POLICY


async def test_svc_web_a_404_is_a_page_with_headers(http: AsyncClient) -> None:
    response = await http.get("/account/nowhere")
    assert response.status_code == 404
    assert_secured(response.headers)
    assert "Page not found" in response.text
    assert "<!--emendrix:" not in response.text


async def test_svc_web_a_redirect_carries_the_headers(http: AsyncClient) -> None:
    token = TOKEN.findall((await http.get("/account/signin")).text)[0]
    response = await http.post("/account/signout", data={"csrf": token})
    assert response.status_code == 303
    assert_secured(response.headers)


async def test_svc_web_a_foreign_host_is_refused_but_probes_answer(app: FastAPI) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://elsewhere.example.org") as http:
        refused = await http.get("/account/signin")
        assert refused.status_code == 400
        assert_secured(refused.headers)
        assert (await http.get("/healthz")).status_code == 200
        assert (await http.get("/readyz")).status_code == 200


async def test_svc_web_a_post_without_or_with_a_wrong_token_is_403(http: AsyncClient) -> None:
    await http.get("/account/signin")
    missing = await http.post("/account/signout", data={})
    assert missing.status_code == 403
    assert_secured(missing.headers)
    wrong = await http.post("/account/signout", data={"csrf": "e30.AAAA"})
    assert wrong.status_code == 403


async def test_svc_web_a_token_from_another_browser_is_403(app: FastAPI) -> None:
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url=SITE_URL) as first,
        AsyncClient(transport=transport, base_url=SITE_URL) as second,
    ):
        token = TOKEN.findall((await first.get("/account/signin")).text)[0]
        await second.get("/account/signin")
        assert (await second.post("/account/signout", data={"csrf": token})).status_code == 403
        assert (await first.post("/account/signout", data={"csrf": token})).status_code == 303


async def test_svc_web_a_get_sets_the_pre_cookie_once(http: AsyncClient) -> None:
    first = await http.get("/account/signin")
    cookies = first.headers.get_list("set-cookie")
    assert len(cookies) == 1
    assert cookies[0].startswith(f"{PRE_COOKIE}=")
    for attribute in ("HttpOnly", "Path=/", "SameSite=lax", "Secure"):
        assert attribute in cookies[0]
    assert "Domain" not in cookies[0]
    second = await http.get("/account/signin")
    assert second.headers.get_list("set-cookie") == []
    assert TOKEN.findall(first.text) == TOKEN.findall(second.text)


def test_svc_web_every_account_post_is_csrf_checked(app: FastAPI) -> None:
    def calls(dependant: Dependant) -> set[object]:
        found: set[object] = {dependant.call}
        for child in dependant.dependencies:
            found |= calls(child)
        return found

    def routes(candidates: Sequence[BaseRoute]) -> Iterator[APIRoute]:
        # FastAPI keeps an included router whole and resolves its routes lazily.
        for route in candidates:
            included = getattr(route, "original_router", None)
            if included is not None:
                yield from routes(included.routes)
            elif isinstance(route, APIRoute):
                yield route

    posts = [
        route
        for route in routes(app.routes)
        if route.path.startswith("/account/") and "POST" in (route.methods or ())
    ]
    assert posts
    for route in posts:
        assert csrf_protect in calls(route.dependant), route.path


def request_with(headers: list[tuple[bytes, bytes]], peer: tuple[str, int] | None) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": headers, "client": peer}
    return Request(scope)


def test_svc_web_client_ip_reads_the_configured_header_or_the_peer() -> None:
    plain = ServiceSettings.model_validate(settings_values())
    proxied = plain.model_copy(update={"client_ip_header": "X-Emendrix-Client-IP"})
    header = [(b"x-emendrix-client-ip", b" 203.0.113.7 , 10.0.0.1")]
    peer = ("10.0.0.9", 50000)
    assert client_ip(request_with(header, peer), plain) == "10.0.0.9"
    assert client_ip(request_with(header, peer), proxied) == "203.0.113.7"
    assert client_ip(request_with([], peer), proxied) == "10.0.0.9"
    assert client_ip(request_with([], None), plain) == "unknown"


async def test_svc_web_readyz_names_the_shell_problem(
    tmp_path: Path, clock: FixedClock, mailer: RecordingMailer
) -> None:
    broken = tmp_path / "account-shell.html"
    broken.write_text(SHELL_HTML.replace(CONTENT_MARKER, ""), encoding="utf-8")
    cases = {
        None: "EMENDRIX_SERVICE_SHELL is not set",
        broken: CONTENT_MARKER,
    }
    for shell, reason in cases.items():
        configured = ServiceSettings.model_validate({**settings_values(), "shell": shell})
        app = create_app(configured, clock=clock, mailer=mailer)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=SITE_URL) as http:
            response = await http.get("/readyz")
            assert response.status_code == 503
            assert reason in response.text
            page = await http.get("/account/signin")
            assert page.status_code == 503
            assert DISCLAIMER in page.text


async def test_svc_web_an_unexpected_error_is_a_page_with_an_id(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    async def boom() -> None:
        raise RuntimeError("alice@example.org")

    app.add_api_route("/account/boom", boom)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=SITE_URL) as http:
        with caplog.at_level(logging.INFO):
            response = await http.get("/account/boom")
    assert response.status_code == 500
    assert_secured(response.headers)
    reference = re.search(r"<code>([0-9a-f]{8})</code>", response.text)
    assert reference is not None
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert reference.group(1) in logged
    assert "RuntimeError" in logged
    assert "alice@example.org" not in logged


def test_svc_web_token_paths_are_not_logged() -> None:
    assert loggable_path("/account/confirm/abc.def") == "/account/confirm/-"
    assert loggable_path("/u/unsubscribe/abc") == "/u/unsubscribe/-"
    assert loggable_path("/u/feed/abc.xml") == "/u/feed/-"
    assert loggable_path("/account/signin") == "/account/signin"


async def test_svc_web_a_signed_out_page_shows_the_account_link(http: AsyncClient) -> None:
    page = (await http.get("/account/signin")).text
    assert header_slot(page) == '<a class="account" href="/account/">Account</a>'


async def test_svc_web_a_signed_in_page_names_the_reader(client: AsyncClient, loaded: Db) -> None:
    await sign_in(loaded, client, "owner@example.org")
    response = await client.get("/account/")
    assert response.status_code == 200
    slot = header_slot(response.text)
    assert 'class="account account--in"' in slot
    assert '<span class="account-initial" aria-hidden="true">O</span>' in slot
    assert '<span class="account-email">owner@example.org</span>' in slot
    assert 'aria-current="page"' not in slot
    assert "<script" not in slot


async def test_svc_web_render_page_marks_the_account_tab_current(app: FastAPI) -> None:
    async def tab(request: Request) -> Response:
        remember_reader(request, "owner@example.org")
        return render_page(
            request,
            "web/error.html",
            title="t",
            heading="h",
            message="m",
            error_id=None,
            account_current=True,
        )

    app.add_api_route("/account/tab", tab)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=SITE_URL) as http:
        page = (await http.get("/account/tab")).text
    slot = header_slot(page)
    assert 'class="account account--in"' in slot and 'aria-current="page"' in slot
    assert "account_current" not in page
