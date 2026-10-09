"""Log records are JSON lines on stdout, and a marker is exactly its own object."""

from __future__ import annotations

import json
import logging

import pytest

from emendrix_service.log import configure_logging, marker


def test_svc_a_marker_renders_as_the_alert_reads_it(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    marker("tick", status="complete", loaded=3, announced=0)
    assert capsys.readouterr().out == (
        '{"emendrix_service":"tick","status":"complete","loaded":3,"announced":0}\n'
    )


def test_svc_a_record_is_one_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    configure_logging()
    logging.getLogger("emendrix_service.test").warning("hello %s", "there")
    lines = capsys.readouterr().out.splitlines()
    assert [json.loads(line) for line in lines] == [
        {"level": "warning", "logger": "emendrix_service.test", "message": "hello there"}
    ]


def test_svc_an_exception_travels_in_the_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logging.getLogger("emendrix_service.test").exception("failed")
    line = json.loads(capsys.readouterr().out)
    assert line["message"] == "failed"
    assert "RuntimeError: boom" in line["error"]
