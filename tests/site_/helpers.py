"""Driving the shipped command from a test, and reading back what it wrote.

Imported by name rather than injected as fixtures: `build` and `_tree` are plain functions
over a temporary directory, and a fixture would only hide which arguments a test ran under.
`tests/` has one conftest and no `__init__.py`, so pytest's prepend import mode puts this
directory on `sys.path` and sibling modules import from here the way they import `eu_pins`.

Every invocation pins the generated-on date and the report directory, because a site built
against the clock or against whatever report happened to be newest on the machine would make
the assertions below untestable rather than lenient.
"""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from emendrix.cli import app
from eu_pins import OBSERVED_ON

runner = CliRunner()

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
WATCHLIST = REPO / "watchlist.example.toml"

SITE_URL = "https://example.invalid/site"
"""A reserved-by-RFC domain: absolute enough to render feeds, never resolvable."""


def build(out: Path, repo: Path | None, *extra: str) -> Path:
    """`emendrix site build` through the shipped command line, offline. Returns `out`."""
    arguments = [
        "site",
        "build",
        "--out",
        str(out),
        "--report-dir",
        str(REPORTS),
        "--watchlist",
        str(WATCHLIST),
        "--generated-on",
        OBSERVED_ON.isoformat(),
        "--site-url",
        SITE_URL,
        *extra,
    ]
    if repo is not None:
        arguments.extend(("--changelogs", str(repo)))
    result = runner.invoke(app, arguments, env={"EMENDRIX_OUTPUT_REPO": ""})
    assert result.exit_code == 0, result.output
    return out


_TAG = re.compile(r"<[^>]+>")


def text_of(rendered: str) -> str:
    """A page's words with its tags removed, and its character references left alone.

    For assertions about a sentence the markup emphasises part of. The disclaimer's lead is
    bold, so the constant it is built from is no longer one substring of the HTML while still
    being one substring of what a reader sees. Escaping is deliberately not undone: the escaped
    form is what the page must carry, and `escape(DISCLAIMER)` is what the assertions compare
    against.
    """
    return _TAG.sub("", rendered)


def _tree(out: Path) -> dict[str, bytes]:
    """Every file under a directory, keyed by its relative path. Bytes, so nothing is normalised."""
    return {
        str(path.relative_to(out)): path.read_bytes()
        for path in sorted(out.rglob("*"))
        if path.is_file()
    }
