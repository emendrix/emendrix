"""What the service must never do, checked over its source rather than promised.

The service sits beside the pipeline: it filters the published record for its users and can
change nothing about what changed. So it imports nothing of `emendrix`, reads the record only
through `emendrix_record`, and calls no model. Each side effect it does have sits in one place a
reader can find: the clock in `clock.py`, the environment in `settings.py`, the database under
`db/`, outbound connections in `mail/transport.py` and `ops/ship.py`, the listener in `app.py`.
No module carries an address, because the host is the deployment's. Each test fails the moment
one of these appears anywhere else, including in modules not yet written.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "emendrix_service"

LINE_CAP = 330
"""The backstop above the house limit of about 300 lines, the same one the pipeline uses."""

PACKAGES = frozenset(
    {"db", "web", "auth", "load", "mail", "watch", "notify", "leave", "feed", "ops"}
)
"""Every feature package of the member. Each exists from the start, so every rule below already
has the directory it constrains in view."""

OUTBOUND = frozenset({"mail/transport.py", "ops/ship.py"})
"""The two modules that may open a connection: the mail relay, and the backup upload."""

NAMESPACES = ("http://www.w3.org/2005/Atom", "http://www.w3.org/1999/xhtml")
"""The two URLs a literal may carry, and only in `feed/render.py`: they are XML namespace names,
not addresses anything fetches."""

Allowed = Callable[[str], bool]


def nowhere(path: str) -> bool:
    return False


def only(*paths: str) -> Allowed:
    return lambda path: path in paths


def under_db(path: str) -> bool:
    return path.startswith("db/")


def modules() -> Iterator[tuple[str, str]]:
    """Every module of the member, as `(path relative to the package, source)`."""
    for path in sorted(SRC.rglob("*.py")):
        yield path.relative_to(SRC).as_posix(), path.read_text(encoding="utf-8")


def imported(source: str) -> set[str]:
    """Every module name an `import` or `from ... import` statement names."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def importers(roots: tuple[str, ...], allowed: Allowed = nowhere) -> list[str]:
    def hits(name: str) -> bool:
        return any(name == root or name.startswith(f"{root}.") for root in roots)

    return [
        path
        for path, source in modules()
        if not allowed(path) and any(hits(name) for name in imported(source))
    ]


def offenders(pattern: str, allowed: Allowed = nowhere) -> list[str]:
    expression = re.compile(pattern)
    return [path for path, source in modules() if not allowed(path) and expression.search(source)]


def literals(source: str) -> Iterator[str]:
    """Every string constant in `source`, docstrings and f-string parts included."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def test_svc_the_scan_sees_every_package() -> None:
    seen = {path.split("/")[0] for path, _ in modules() if "/" in path}
    assert seen >= PACKAGES
    for package in PACKAGES:
        assert (SRC / package / "__init__.py").is_file(), package
    assert {"app.py", "cli.py", "clock.py", "settings.py", "signing.py", "log.py"} <= {
        path for path, _ in modules()
    }


def test_svc_nothing_imports_the_pipeline() -> None:
    """The pipeline's wheel carries the model stage; the service must not be able to reach it."""
    assert importers(("emendrix",)) == []
    assert importers(("emendrix_record",)) != []


PUBLISHED_MODEL = (
    r"(?m)^class (RootIndex|ActIndex|ActRow|EventRow|ProvisionRow|Catalogue\w*|Payload)\b"
)
"""A class named for a model of a published file, which only `emendrix_record` declares."""


def test_svc_the_record_is_read_only_through_its_own_member() -> None:
    assert offenders(PUBLISHED_MODEL) == []
    assert re.search(PUBLISHED_MODEL, "x = 1\nclass Payload(BaseModel):\n    pass\n")


def test_svc_the_database_is_reached_only_from_db() -> None:
    assert importers(("sqlalchemy", "alembic", "psycopg", "psycopg_pool"), under_db) == []


def test_svc_only_two_modules_connect_out() -> None:
    roots = (
        "aiosmtplib",
        "smtplib",
        "httpx",
        "httpx2",
        "requests",
        "urllib.request",
        "aiohttp",
        "asyncssh",
        "socket",
    )
    assert importers(roots, lambda path: path in OUTBOUND) == []


def test_svc_only_the_app_listens() -> None:
    assert importers(("uvicorn", "hypercorn", "socketserver"), only("app.py")) == []
    assert offenders(r"\buvicorn\.run\b|start_server|\.listen\(", only("app.py")) == []


ENVIRONMENT = r"\benviron\b|getenv|BaseSettings|pydantic_settings|dotenv"


def test_svc_only_the_settings_read_the_environment() -> None:
    assert offenders(ENVIRONMENT, only("settings.py")) == []


def test_svc_the_environment_scan_sees_a_settings_class() -> None:
    assert re.search(ENVIRONMENT, "class Other(BaseSettings):\n    pass\n")
    assert re.search(ENVIRONMENT, "value = os.environ['X']")


CLOCK = (
    r"datetime\.now|datetime\.today|date\.today|utcnow|\btime\.time\b|\btime\.monotonic"
    r"|perf_counter|from time import"
)


def test_svc_only_the_clock_reads_the_clock() -> None:
    """A rate-limit window reads `Clock.monotonic()`, never `time.monotonic()`, so a test can
    step it; calling a clock's own `monotonic` is not a read and is not matched."""
    assert offenders(CLOCK, only("clock.py")) == []
    assert importers(("time",), only("clock.py")) == []


def test_svc_the_clock_scan_sees_a_read() -> None:
    assert re.search(CLOCK, "at = datetime.now(UTC)")
    assert re.search(CLOCK, "start = time.monotonic()")
    assert not re.search(CLOCK, "start = clock.monotonic()")


def test_svc_no_model_is_called() -> None:
    assert importers(("pydantic_ai", "langgraph", "anthropic", "openai")) == []


def test_svc_no_address_is_written_into_the_service() -> None:
    """The host is the deployment's: links are built on `site_url` from the settings."""
    address = re.compile(r"emendrix\.eu|https?://")

    def stated(path: str, text: str) -> bool:
        if path == "feed/render.py":
            for namespace in NAMESPACES:
                text = text.replace(namespace, "")
        return bool(address.search(text))

    found = [
        (path, text)
        for path, source in modules()
        for text in literals(source)
        if stated(path, text)
    ]
    assert found == []


def test_svc_the_address_scan_sees_a_url() -> None:
    assert list(literals('x = f"https://{host}/account/"')) == ["https://", "/account/"]


def test_svc_every_module_stays_under_the_line_cap() -> None:
    long = {path: source.count("\n") for path, source in modules() if source.count("\n") > LINE_CAP}
    assert long == {}


@pytest.mark.parametrize("package", sorted(PACKAGES))
def test_svc_every_package_says_what_it_is(package: str) -> None:
    source = (SRC / package / "__init__.py").read_text(encoding="utf-8")
    assert ast.get_docstring(ast.parse(source))
