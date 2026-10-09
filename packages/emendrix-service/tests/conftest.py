"""Fixtures every service test shares: settings, a fixed clock and a recording mailer.

None of them reads the environment or the system clock, so a test's result cannot depend on the
shell it ran in or the time it ran at. `settings` is built through `model_validate`, which reads
no variable, and every address in it is a reserved example name.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from emendrix_service.clock import FixedClock
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ENV_PREFIX, ServiceSettings

SITE_URL = "https://example.org"

SECRET_KEY = base64.b64encode(bytes(range(32))).decode("ascii")
"""A fixed 32-byte key, so a token minted in one test run verifies in the next."""

NOW = datetime(2026, 10, 12, 5, 0, tzinfo=UTC)
"""A Monday, 07:00 in Brussels: the default weekly digest falls due at this instant."""

DATABASE_URL = "postgresql+psycopg://service:service@localhost:5432/service"
"""A placeholder no test connects to."""


def settings_values() -> dict[str, object]:
    """The keyword arguments of a valid `ServiceSettings`, for a test to vary one of."""
    return {
        "database_url": DATABASE_URL,
        "site_url": SITE_URL,
        "allowed_hosts": ("example.org",),
        "secret_key": SECRET_KEY,
    }


@pytest.fixture
def settings() -> ServiceSettings:
    return ServiceSettings.model_validate(settings_values())


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def mailer() -> RecordingMailer:
    return RecordingMailer()


@pytest.fixture
def no_service_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every `EMENDRIX_SERVICE_*` variable removed for one test, for tests that read the
    environment on purpose and must not see the developer's shell."""
    for name in [key for key in os.environ if key.upper().startswith(ENV_PREFIX)]:
        monkeypatch.delenv(name)
    yield


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
