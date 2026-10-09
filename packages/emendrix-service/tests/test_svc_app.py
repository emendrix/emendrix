"""The app answers its probes and publishes no API description."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from emendrix_service.app import create_app
from emendrix_service.clock import FixedClock
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ServiceSettings

pytestmark = pytest.mark.anyio


def client(settings: ServiceSettings, clock: FixedClock, mailer: RecordingMailer) -> AsyncClient:
    app = create_app(settings, clock=clock, mailer=mailer)
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://example.org")


async def test_svc_healthz_answers_ok(
    settings: ServiceSettings, clock: FixedClock, mailer: RecordingMailer
) -> None:
    async with client(settings, clock, mailer) as http:
        for path in ("/healthz", "/readyz"):
            response = await http.get(path)
            assert (response.status_code, response.text) == (200, "ok")
        assert (await http.head("/healthz")).status_code == 200


async def test_svc_no_api_description_is_served(
    settings: ServiceSettings, clock: FixedClock, mailer: RecordingMailer
) -> None:
    async with client(settings, clock, mailer) as http:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await http.get(path)).status_code == 404


def test_svc_the_app_carries_what_it_was_given(
    settings: ServiceSettings, clock: FixedClock, mailer: RecordingMailer
) -> None:
    app = create_app(settings, clock=clock, mailer=mailer)
    assert app.state.settings is settings
    assert app.state.clock is clock
    assert app.state.mailer is mailer
