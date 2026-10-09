"""The account shell: split on its three markers, stripped of its script, read again on change."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest
from markupsafe import Markup

from emendrix_service.web.shell import (
    CONTENT_MARKER,
    FOOTER_NOTE,
    FOOTER_NOTE_MARKER,
    TITLE_MARKER,
    Shell,
    ShellSource,
)
from tests.conftest import SHELL_HTML


def parsed(text: str = SHELL_HTML) -> Shell:
    shell = Shell.parse(text)
    assert isinstance(shell, Shell), shell
    return shell


def test_svc_web_shell_splits_on_its_markers() -> None:
    shell = parsed()
    assert shell.head.endswith("<title>")
    assert shell.middle.startswith("</title>")
    assert shell.middle.endswith('<main id="content">')
    assert shell.lower.startswith("</main>")
    assert shell.tail.startswith("</footer>")
    for piece in (shell.head, shell.middle, shell.lower, shell.tail):
        assert "<!--emendrix:" not in piece


@pytest.mark.parametrize("marker", [TITLE_MARKER, CONTENT_MARKER, FOOTER_NOTE_MARKER])
def test_svc_web_shell_names_a_missing_or_repeated_marker(marker: str) -> None:
    missing = Shell.parse(SHELL_HTML.replace(marker, ""))
    assert isinstance(missing, str)
    assert marker in missing
    repeated = Shell.parse(SHELL_HTML.replace(marker, marker * 2))
    assert isinstance(repeated, str)
    assert marker in repeated


def test_svc_web_shell_drops_the_script_line() -> None:
    shell = parsed()
    page = shell.render(title="t", content=Markup(""))
    assert "<script" not in page
    assert '<link rel="stylesheet" href="/style.test.css">\n</head>' in page


def test_svc_web_shell_render_escapes_the_title_only() -> None:
    page = parsed().render(title="<b>A & B</b>", content=Markup("<p>kept</p>"))
    assert "<title>&lt;b&gt;A &amp; B&lt;/b&gt;</title>" in page
    assert '<main id="content"><p>kept</p></main>' in page
    assert str(FOOTER_NOTE) in page
    assert 'href="/account/privacy"' in page


def test_svc_web_shell_load_reports_an_unreadable_file(tmp_path: Path) -> None:
    reason = Shell.load(tmp_path / "absent.html")
    assert reason == "the account shell cannot be read (FileNotFoundError)"


def test_svc_web_shell_is_read_again_when_the_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "account-shell.html"
    path.write_text(SHELL_HTML, encoding="utf-8")
    source = ShellSource(path)
    first = source.get()
    assert isinstance(first, Shell)
    assert source.get() is first, "an unchanged file is not read again"
    path.write_text(SHELL_HTML.replace("style.test.css", "style.0123abcd.css"), encoding="utf-8")
    second = source.get()
    assert isinstance(second, Shell)
    assert "style.0123abcd.css" in second.middle


def test_svc_web_shell_keeps_the_last_good_one_through_a_broken_rewrite(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "account-shell.html"
    path.write_text(SHELL_HTML, encoding="utf-8")
    source = ShellSource(path)
    good = source.get()
    assert isinstance(good, Shell)
    path.write_text(SHELL_HTML.replace(CONTENT_MARKER, ""), encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    with caplog.at_level(logging.WARNING, logger="emendrix_service.web.shell"):
        assert source.get() is good
        assert source.get() is good
    warnings = [r for r in caplog.records if r.name == "emendrix_service.web.shell"]
    assert len(warnings) == 1
    assert CONTENT_MARKER in warnings[0].getMessage()


def test_svc_web_shell_source_without_a_good_read_gives_the_reason(tmp_path: Path) -> None:
    source = ShellSource(tmp_path / "absent.html")
    assert source.get() == "the account shell cannot be read (FileNotFoundError)"
