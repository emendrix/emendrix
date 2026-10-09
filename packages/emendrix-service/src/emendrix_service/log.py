"""JSON lines on stdout, and the one marker line every command ends with.

Each record is one JSON object: its level, its logger and its message. The collector in front of
the process stamps the time, so no timestamp is added here and no clock is read. What a line may
carry is narrow on purpose: never a request body, an email address, a token or the query string
of a token-addressed path; a user appears as their uuid.

A marker is the line an alert keys on. `marker("tick", status="complete", loaded=3)` writes
exactly `{"emendrix_service":"tick","status":"complete","loaded":3}`, with nothing around it, so
a log query can match it as a fixed string. A command writes exactly one, as its last line.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Final, Literal

__all__ = ["MARKER_LOGGER", "JsonFormatter", "configure_logging", "marker"]

MARKER_LOGGER: Final = "emendrix_service.marker"

_MARKER: Final = "emendrix_marker"
"""The record attribute a marker's object travels in, from `marker` to the formatter."""


def _dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)


class JsonFormatter(logging.Formatter):
    """One compact JSON object per record; a marker record renders as the marker alone."""

    def format(self, record: logging.LogRecord) -> str:
        carried = getattr(record, _MARKER, None)
        if isinstance(carried, dict):
            return _dumps(carried)
        line: dict[str, object] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            line["error"] = self.formatException(record.exc_info)
        return _dumps(line)


class _Handler(logging.StreamHandler):  # type: ignore[type-arg]
    """Ours, so a second `configure_logging` replaces it rather than adding a twin."""


def configure_logging(level: int = logging.INFO) -> None:
    """Send every logger's records to stdout as JSON. Calling it again changes nothing."""
    root = logging.getLogger()
    for handler in [handler for handler in root.handlers if isinstance(handler, _Handler)]:
        root.removeHandler(handler)
    handler = _Handler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def marker(
    command: str, *, status: Literal["complete", "failed"], **counts: int | float | str | None
) -> None:
    """Write the one line that says how `command` ended, with its counts in the order given."""
    line: dict[str, object] = {"emendrix_service": command, "status": status, **counts}
    logging.getLogger(MARKER_LOGGER).info(command, extra={_MARKER: line})
