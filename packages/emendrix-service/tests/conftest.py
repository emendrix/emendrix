"""Fixtures every service test shares: settings, a fixed clock, a recording mailer, the shell
the pages fill, and a migrated Postgres per test.

None of them reads the system clock, so a test's result cannot depend on the time it ran at.
`settings` is built through `model_validate`, which reads no variable, and every address in it
is a reserved example name. The one variable read here is
`EMENDRIX_SERVICE_TEST_DATABASE_URL`, which points the database fixtures at a server the
developer already runs instead of a container.

**The database.** One Postgres serves the whole session. Under xdist the first worker to need it
starts the pinned image, migrates a template database to head and writes the server's address to
a file every other worker reads, all behind a file lock; each worker then clones the template
into its own database, so workers never see each other's rows. `db` truncates every table after
each test, pass or fail. Without Docker and without the variable the database fixtures fail
with a sentence naming both, and are never skipped.

The container is removed by testcontainers' reaper once the last worker holding a connection to
the reaper has exited; no worker stops it, because the one that started it may finish while
others still run. Each worker that did not start it opens its own reaper connection, so the
reaper waits for all of them.
"""

from __future__ import annotations

import atexit
import base64
import html
import json
import os
import socket
import sys
from collections.abc import AsyncIterator, Iterator
from contextlib import AbstractContextManager, nullcontext, suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import anyio
import psycopg
import pytest
from fastapi import FastAPI
from filelock import FileLock
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.config import testcontainers_config
from testcontainers.core.container import Reaper
from testcontainers.core.labels import LABEL_SESSION_ID, SESSION_ID

from emendrix_service import DISCLAIMER
from emendrix_service.app import create_app
from emendrix_service.clock import FixedClock
from emendrix_service.db import COMMAND_POOL, Db
from emendrix_service.db.migrate import upgrade_head
from emendrix_service.db.tables import Base
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ENV_PREFIX, ServiceSettings

SITE_URL = "https://example.org"

SECRET_KEY = base64.b64encode(bytes(range(32))).decode("ascii")
"""A fixed 32-byte key, so a token minted in one test run verifies in the next."""

NOW = datetime(2026, 10, 12, 5, 0, tzinfo=UTC)
"""A Monday, 07:00 in Brussels: the default weekly digest falls due at this instant."""

DATABASE_URL = "postgresql+psycopg://service:service@localhost:5432/service"
"""A placeholder no test connects to; the database fixtures put the real address in."""

SHELL_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title><!--emendrix:title--></title>
<meta name="description" content="">
<link rel="stylesheet" href="/style.test.css">
<script defer src="/search.test.js"></script>
</head>
<body>
<header class="bar"><a class="wordmark" href="/">emendrix</a><nav aria-label="Site"></nav>
<div id="search" data-root="/"></div><!--emendrix:account--></header>
<main id="content"><!--emendrix:content--></main>
<footer><p>{html.escape(DISCLAIMER)}</p><!--emendrix:footer-note--></footer>
</body>
</html>
"""
"""A reduced account shell: the four markers a built site's shell carries, one of them optional
(the account slot, at the end of the header), one stylesheet and one script, so every app a
test builds can render a page without a site build."""

POSTGRES_IMAGE = (
    "postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"
)
"""Resolved with `docker buildx imagetools inspect postgres:17-alpine` on 2026-10-09. The
deployment runs the same digest, so the tests exercise the server the service meets."""

TEST_DATABASE = f"{ENV_PREFIX}TEST_DATABASE_URL"

NO_DATABASE = "the service tests need Docker or EMENDRIX_SERVICE_TEST_DATABASE_URL"

TEMPLATE = "svc_template"
"""The database migrated to head once per session, which every worker's database is cloned from."""

TRUNCATE = (
    "TRUNCATE "
    + ", ".join(table.fullname for table in Base.metadata.sorted_tables)
    + " RESTART IDENTITY CASCADE"
)
"""Every table of the three schemas, schema-qualified in one statement, so no foreign key's
order matters."""


def settings_values() -> dict[str, object]:
    """The keyword arguments of a valid `ServiceSettings`, for a test to vary one of."""
    return {
        "database_url": DATABASE_URL,
        "site_url": SITE_URL,
        "allowed_hosts": ("example.org",),
        "secret_key": SECRET_KEY,
    }


@pytest.fixture
def settings(shell_file: Path) -> ServiceSettings:
    return ServiceSettings.model_validate({**settings_values(), "shell": shell_file})


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


@pytest.fixture(scope="session")
def shell_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("shell") / "account-shell.html"
    path.write_text(SHELL_HTML, encoding="utf-8")
    return path


# --- the database --------------------------------------------------------------------------


@dataclass(frozen=True)
class Server:
    """A Postgres the session uses: its address, and the reaper keeping it alive, if any."""

    url: str
    reaper_host: str | None = None
    reaper_port: int | None = None
    session: str | None = None


def database_url(server_url: str, database: str) -> str:
    """The address of `database` on the server at `server_url`, with the service's driver."""
    url = make_url(server_url).set(drivername="postgresql+psycopg", database=database)
    return url.render_as_string(hide_password=False)


def service_settings(url: str) -> ServiceSettings:
    return ServiceSettings.model_validate({**settings_values(), "database_url": url})


def execute(server_url: str, *statements: str) -> None:
    """Run `statements` outside a transaction, as `CREATE DATABASE` requires."""
    url = make_url(server_url).set(drivername="postgresql")
    with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as conn:
        for statement in statements:
            conn.execute(statement.encode())


def clone_template(server_url: str, database: str) -> str:
    execute(
        server_url,
        f"DROP DATABASE IF EXISTS {database} WITH (FORCE)",
        f"CREATE DATABASE {database} TEMPLATE {TEMPLATE}",
    )
    return database_url(server_url, database)


def drop(server_url: str, database: str) -> None:
    with suppress(psycopg.Error):
        execute(server_url, f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")


def start_container() -> Server:
    if "TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE" not in os.environ and sys.platform == "darwin":
        # The reaper mounts the daemon's socket; on macOS the client's socket is a path on the
        # host the Docker VM cannot mount, and the VM's own socket is at the Linux default.
        testcontainers_config.ryuk_docker_socket = "/var/run/docker.sock"
    try:
        container = PostgresContainer(
            POSTGRES_IMAGE,
            username="service",
            password="service",
            dbname="service",
            driver="psycopg",
        ).start()
    except Exception as error:
        problem = f"{type(error).__name__}: {error}"
    else:
        return started(container)
    pytest.fail(f"{NO_DATABASE} ({problem})", pytrace=False)


def started(container: PostgresContainer) -> Server:
    # testcontainers' own exit hook removes the reaper before it can reap, which would leave
    # the database running after the session; without it the reaper removes the database once
    # the last connection to it closes.
    atexit.unregister(Reaper.delete_instance)
    reaper = Reaper._container
    if reaper is None:
        return Server(url=container.get_connection_url())
    return Server(
        url=container.get_connection_url(),
        reaper_host=reaper.get_container_host_ip(),
        reaper_port=int(reaper.get_exposed_port(8080)),
        session=SESSION_ID,
    )


def provision() -> Server:
    """A server with a template database at head: the configured one, else a new container."""
    configured = os.environ.get(TEST_DATABASE)
    server = Server(url=configured) if configured else start_container()
    execute(
        server.url,
        f"DROP DATABASE IF EXISTS {TEMPLATE} WITH (FORCE)",
        f"CREATE DATABASE {TEMPLATE}",
    )
    anyio.run(upgrade_head, service_settings(database_url(server.url, TEMPLATE)))
    return server


def hold(server: Server) -> socket.socket | None:
    """A connection to the reaper that keeps the container alive while this worker runs.

    Raises `OSError` when the reaper is gone, and with it the container.
    """
    if server.reaper_host is None or server.reaper_port is None or server.session == SESSION_ID:
        return None
    connection = socket.create_connection((server.reaper_host, server.reaper_port), timeout=5)
    try:
        connection.sendall(f"label={LABEL_SESSION_ID}={server.session}\r\n".encode())
        if not connection.recv(16).startswith(b"ACK"):
            raise OSError("the reaper did not acknowledge")
    except OSError:
        connection.close()
        raise
    return connection


@pytest.fixture(scope="session")
def worker_lock(
    tmp_path_factory: pytest.TempPathFactory, worker_id: str
) -> AbstractContextManager[object]:
    """What serialises the workers of one xdist session; nothing to serialise without xdist."""
    if worker_id == "master":
        return nullcontext()
    return FileLock(tmp_path_factory.getbasetemp().parent / "svc-postgres.lock")


@pytest.fixture(scope="session")
def pg_url(
    tmp_path_factory: pytest.TempPathFactory,
    worker_id: str,
    worker_lock: AbstractContextManager[object],
) -> Iterator[str]:
    """The session's server, as an address on its maintenance database."""
    if worker_id == "master":
        yield provision().url
        return
    state = tmp_path_factory.getbasetemp().parent / "svc-postgres.json"
    keeper: socket.socket | None = None
    with worker_lock:
        server = Server(**json.loads(state.read_text("utf-8"))) if state.exists() else None
        if server is not None:
            try:
                keeper = hold(server)
            except OSError:
                server = None
        if server is None:
            server = provision()
            state.write_text(json.dumps(asdict(server)), "utf-8")
    try:
        yield server.url
    finally:
        if keeper is not None:
            keeper.close()


@pytest.fixture(scope="session")
def worker_url(
    pg_url: str, worker_id: str, worker_lock: AbstractContextManager[object]
) -> Iterator[str]:
    """This worker's own database, cloned from the migrated template."""
    name = f"svc_{worker_id}"
    with worker_lock:
        url = clone_template(pg_url, name)
    yield url
    drop(pg_url, name)


@pytest.fixture
def scratch_url(
    pg_url: str, worker_id: str, worker_lock: AbstractContextManager[object]
) -> Iterator[str]:
    """A second, migrated database for one test that needs to break its schema."""
    name = f"svc_{worker_id}_scratch"
    with worker_lock:
        url = clone_template(pg_url, name)
    yield url
    drop(pg_url, name)


@pytest.fixture
async def db(worker_url: str) -> AsyncIterator[Db]:
    """This worker's database, emptied of every row after the test whatever its outcome."""
    database = Db.connect(service_settings(worker_url), pool_size=COMMAND_POOL)
    try:
        yield database
    finally:
        try:
            async with database.transaction() as tx:
                await tx.execute(text(TRUNCATE))
        finally:
            await database.dispose()


@pytest.fixture
async def service_app(
    settings: ServiceSettings,
    clock: FixedClock,
    mailer: RecordingMailer,
    db: Db,
    worker_url: str,
) -> AsyncIterator[FastAPI]:
    """The app over this worker's database, its lifespan open for the test."""
    configured = settings.model_copy(update={"database_url": SecretStr(worker_url)})
    app = create_app(configured, clock=clock, mailer=mailer, db=db)
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(service_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A client of `service_app`; httpx's ASGI transport does not run the lifespan itself."""
    transport = ASGITransport(app=service_app)
    async with AsyncClient(transport=transport, base_url=SITE_URL) as http:
        yield http
