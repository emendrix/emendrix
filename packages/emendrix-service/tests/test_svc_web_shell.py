"""The account shell: split on its markers, stripped of its script, read again on change."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest
from markupsafe import Markup

from emendrix_service.web.shell import (
    ACCOUNT_MARKER,
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
    assert shell.has_account_slot
    assert shell.before_title.endswith("<title>")
    assert shell.before_account.startswith("</title>")
    assert shell.before_account.endswith('<div id="search" data-root="/"></div>')
    assert shell.before_content.startswith("</header>")
    assert shell.before_content.endswith('<main id="content">')
    assert shell.before_footer_note.startswith("</main>")
    assert shell.after.startswith("</footer>")
    pieces = (
        shell.before_title,
        shell.before_account,
        shell.before_content,
        shell.before_footer_note,
        shell.after,
    )
    for piece in pieces:
        assert "<!--emendrix:" not in piece


@pytest.mark.parametrize("marker", [TITLE_MARKER, CONTENT_MARKER, FOOTER_NOTE_MARKER])
def test_svc_web_shell_names_a_missing_or_repeated_marker(marker: str) -> None:
    missing = Shell.parse(SHELL_HTML.replace(marker, ""))
    assert isinstance(missing, str)
    assert marker in missing
    repeated = Shell.parse(SHELL_HTML.replace(marker, marker * 2))
    assert isinstance(repeated, str)
    assert marker in repeated


def test_svc_web_shell_without_an_account_slot_still_serves() -> None:
    text = SHELL_HTML.replace(ACCOUNT_MARKER, '<a class="account" href="/account/">Account</a>')
    shell = parsed(text)
    assert shell.has_account_slot is False
    page = shell.render(
        title="t",
        content=Markup("<p>c</p>"),
        account=Markup("<b>ignored</b>"),
        footer_note=Markup("n"),
    )
    expected = (
        text.replace('<script defer src="/search.test.js"></script>\n', "")
        .replace(TITLE_MARKER, "t")
        .replace(CONTENT_MARKER, "<p>c</p>")
        .replace(FOOTER_NOTE_MARKER, "n")
    )
    assert page == expected


def test_svc_web_shell_refuses_two_account_slots() -> None:
    reason = Shell.parse(SHELL_HTML.replace(ACCOUNT_MARKER, ACCOUNT_MARKER * 2))
    assert reason == (
        "the account shell has 2 <!--emendrix:account--> markers where it needs at most one"
    )


def test_svc_web_shell_wants_the_account_slot_between_title_and_content() -> None:
    after_content = SHELL_HTML.replace(ACCOUNT_MARKER, "").replace(
        CONTENT_MARKER, CONTENT_MARKER + ACCOUNT_MARKER
    )
    assert Shell.parse(after_content) == "the account shell's markers are out of order"


def test_svc_web_shell_render_places_the_account_slot() -> None:
    slot = Markup('<a class="account" href="/account/">Account</a>')
    page = parsed().render(title="t", content=Markup(""), account=slot)
    assert f'<div id="search" data-root="/"></div>{slot}</header>' in page


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
    assert "style.0123abcd.css" in second.before_account


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
