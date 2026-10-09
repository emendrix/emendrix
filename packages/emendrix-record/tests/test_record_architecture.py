"""What the reader of the record must never do, checked over its source rather than promised.

Every reader beside the pipeline reads the published record through this member, so it carries
none of their side effects: it imports nothing of `emendrix` and nothing of a server, opens no
connection, reads no clock and no environment, calls no model and writes no file. Its one
third-party dependency is `pydantic`. Each test fails the moment one of these appears anywhere
in the member, including in modules not yet written.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "emendrix_record"

LINE_CAP = 330
"""The backstop above the house limit of about 300 lines, the same one the pipeline uses."""

ALLOWED_ROOTS = frozenset({"emendrix_record", "pydantic", *sys.stdlib_module_names})
"""The top-level modules an import may name: the member, its one dependency, the stdlib."""


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
    expected = {
        "__init__.py",
        "links.py",
        "locations.py",
        "models.py",
        "payload.py",
        "reads.py",
        "reasons.py",
        "record.py",
    }
    assert expected <= {path for path, _ in modules()}


def test_nothing_imports_the_pipeline() -> None:
    """The pipeline's wheel carries the model stage; no reader of the record may reach it."""
    assert importers(("emendrix",)) == []


def test_every_import_is_the_stdlib_pydantic_or_the_member() -> None:
    foreign = {
        path: sorted(name for name in imported(source) if name.split(".")[0] not in ALLOWED_ROOTS)
        for path, source in modules()
    }
    assert {path: names for path, names in foreign.items() if names} == {}


@pytest.mark.parametrize(
    "roots",
    [
        ("mcp", "starlette", "uvicorn", "fastapi"),
        ("httpx", "httpx2", "requests", "urllib.request", "aiohttp", "socket", "http.client"),
        ("pydantic_ai", "langgraph", "anthropic", "openai"),
    ],
    ids=["no-server", "no-network", "no-model"],
)
def test_no_server_no_network_and_no_model(roots: tuple[str, ...]) -> None:
    assert importers(roots) == []


def test_no_clock_is_read() -> None:
    """Dates come from the record. A clock would let a read depend on when it was made."""
    clock = r"datetime\.now|date\.today|\btime\.time\b|time\.monotonic|perf_counter|utcnow"
    assert offenders(clock) == []
    assert importers(("time",)) == []


def test_no_environment_is_read() -> None:
    """Every input is a path or a string a caller hands over."""
    assert offenders(r"\benviron\b|getenv|BaseSettings") == []


def test_nothing_writes_a_file() -> None:
    """The record is read-only to every reader; a write would be a bug a read-only mount hides."""
    mode = r"""(?:mode\s*=\s*)?["'][rbt]*[wax+][rwxabt+]*["']"""
    write_mode = rf"\bopen\((?:[^)]*,\s*)?{mode}"
    pattern = rf"write_text|write_bytes|{write_mode}|mkdir|unlink|rmtree|os\.remove|\.rename\("
    assert offenders(pattern) == []


def test_the_write_scan_sees_a_write() -> None:
    mode = r"""(?:mode\s*=\s*)?["'][rbt]*[wax+][rwxabt+]*["']"""
    assert re.search(rf"\bopen\((?:[^)]*,\s*)?{mode}", 'open(path, "w")')


def test_every_module_stays_under_the_line_cap() -> None:
    long = {path: source.count("\n") for path, source in modules() if source.count("\n") > LINE_CAP}
    assert long == {}
