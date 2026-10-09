"""The dependency between the pipeline and the members beside it points one way only.

The members (the record reader, the MCP server, the account service) read what the pipeline
published; the pipeline never reads them, and never imports the web, database or mail stack they
run on. If it did, a user's data or a server's framework would sit one import away from the
loop that decides what changed. This scans `src/emendrix` only: the members' own architecture
tests hold the other direction.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "emendrix"

FORBIDDEN = (
    "emendrix_record",
    "emendrix_service",
    "emendrix_mcp",
    "fastapi",
    "sqlalchemy",
    "alembic",
    "psycopg",
    "aiosmtplib",
    "jinja2",
    "uvicorn",
)


def imported(source: str) -> Iterator[str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_the_pipeline_imports_no_member_and_no_server_stack() -> None:
    offenders = sorted(
        (path.relative_to(SRC).as_posix(), name)
        for path in SRC.rglob("*.py")
        for name in imported(path.read_text(encoding="utf-8"))
        if any(name == root or name.startswith(f"{root}.") for root in FORBIDDEN)
    )
    assert offenders == []


def test_the_scan_reads_the_pipeline() -> None:
    names = {name for path in SRC.rglob("*.py") for name in imported(path.read_text("utf-8"))}
    assert any(name.startswith("emendrix.core") for name in names)
    assert "fastapi" in set(imported("from fastapi import FastAPI"))
