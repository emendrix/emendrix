"""What the server must never do, checked over its source rather than promised.

The server sits beside the pipeline: it reads published files and hands them to a calling
model, and it can change nothing about what changed. So it imports nothing of `emendrix`, opens
no outbound connection, reads no clock, calls no model and writes no file. Exactly one module
may listen (`app.py`) and exactly one may read the environment (`cli.py`), so each side effect
is in one place a reader can find. Each test fails the moment one of these appears anywhere
else, including in modules not yet written.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "emendrix_mcp"

LINE_CAP = 330
"""The backstop above the house limit of about 300 lines, the same one the pipeline uses."""

LISTENER = "app.py"
"""The one module allowed to bind a socket or import an ASGI server."""

CONFIGURATION = "cli.py"
"""The one module allowed to read the environment."""


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


def importers(roots: tuple[str, ...], allowed: AbstractSet[str] = frozenset()) -> list[str]:
    def hits(name: str) -> bool:
        return any(name == root or name.startswith(f"{root}.") for root in roots)

    return [
        path
        for path, source in modules()
        if path not in allowed and any(hits(name) for name in imported(source))
    ]


def offenders(pattern: str, allowed: AbstractSet[str] = frozenset()) -> list[str]:
    expression = re.compile(pattern)
    return [path for path, source in modules() if path not in allowed and expression.search(source)]


def test_the_scan_sees_the_modules() -> None:
    assert {"__init__.py", "models.py", "payload.py", "reasons.py", "record.py"} <= {
        path for path, _ in modules()
    }


def test_nothing_imports_the_pipeline() -> None:
    """The pipeline's wheel carries the model stage; the server must not be able to reach it."""
    assert importers(("emendrix",)) == []


@pytest.mark.parametrize(
    "roots",
    [("httpx", "httpx2", "requests", "urllib.request", "aiohttp"), ("pydantic_ai", "langgraph")],
    ids=["no-http-client", "no-pipeline-stage"],
)
def test_no_outbound_connection_and_no_pipeline_machinery(roots: tuple[str, ...]) -> None:
    assert importers(roots) == []


def test_no_model_is_called() -> None:
    assert importers(("anthropic", "openai")) == []


def test_no_clock_is_read() -> None:
    """Dates come from the record. A clock would let an answer depend on when it was asked."""
    clock = r"datetime\.now|date\.today|\btime\.time\b|time\.monotonic|perf_counter|utcnow"
    assert offenders(clock) == []
    assert importers(("time",)) == []


def test_only_the_app_listens() -> None:
    assert importers(("socket", "socketserver", "uvicorn", "hypercorn"), {LISTENER}) == []
    assert offenders(r"\.bind\(|start_server|\.listen\(", {LISTENER}) == []


def test_no_stdio_entry_point() -> None:
    """The server is reached over HTTP only, so a stdio mode would be code nobody runs."""
    assert offenders(r"stdio") == []


def test_only_the_cli_reads_the_environment() -> None:
    assert offenders(r"\benviron\b|getenv", {CONFIGURATION}) == []


def test_nothing_writes_a_file() -> None:
    """The volumes are read-only to the server; a write would be a bug the mount hides."""
    mode = r"""(?:mode\s*=\s*)?["'][rbt]*[wax+][rwxabt+]*["']"""
    write_mode = rf"\bopen\((?:[^)]*,\s*)?{mode}"
    pattern = rf"write_text|write_bytes|{write_mode}|mkdir|unlink|rmtree|os\.remove|\.rename\("
    assert offenders(pattern) == []


def test_every_module_stays_under_the_line_cap() -> None:
    long = {path: source.count("\n") for path, source in modules() if source.count("\n") > LINE_CAP}
    assert long == {}
