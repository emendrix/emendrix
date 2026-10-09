"""`/readyz` reports the database: reachable and migrated, or the first reason it is not."""

from __future__ import annotations

import anyio.to_thread
import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient

from emendrix_service.app import create_app
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.migrate import alembic_config, current_matches_head
from emendrix_service.db.ready import NOT_ANSWERING, NOT_MIGRATED
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ServiceSettings
from tests.conftest import SITE_URL, service_settings

pytestmark = pytest.mark.anyio


async def readyz(
    app_settings: ServiceSettings, clock: FixedClock, db: Db | None
) -> tuple[int, str]:
    app = create_app(app_settings, clock=clock, mailer=RecordingMailer(), db=db)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=SITE_URL) as http,
    ):
        response = await http.get("/readyz")
    return response.status_code, response.text


async def test_svc_readyz_is_ok_on_a_migrated_database(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert (response.status_code, response.text) == (200, "ok")


async def test_svc_readyz_names_a_database_behind_its_migrations(
    scratch_url: str, clock: FixedClock
) -> None:
    # Alembic runs its own event loop, so it cannot run on this test's.
    await anyio.to_thread.run_sync(
        command.stamp, alembic_config(service_settings(scratch_url)), "base"
    )
    scratch = Db.connect(service_settings(scratch_url))
    try:
        assert not await current_matches_head(scratch)
        assert await readyz(service_settings(scratch_url), clock, scratch) == (503, NOT_MIGRATED)
    finally:
        await scratch.dispose()


async def test_svc_readyz_names_a_database_that_does_not_answer(clock: FixedClock) -> None:
    url = "postgresql+psycopg://service:service@127.0.0.1:1/service"
    assert await readyz(service_settings(url), clock, None) == (503, NOT_ANSWERING)
