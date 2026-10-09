"""The site's account shell: read from disk, split on its markers, filled once per page.

The site writes `account-shell.html` with three markers (the title, the body of `<main>`, and a
note in the footer). Every account page is the shell with those three filled, so it carries the
site's header, stylesheet and disclaimer without the service holding a copy of any of them.

The site rewrites the file on every build, and a release renames the fingerprinted stylesheet,
so `ShellSource` checks the file's size and modification time on each render and reads it again
when either moved. A rewrite that breaks it keeps the last good shell in service.

The shell's one script tag is dropped when it is read: account pages run no script, and the
service's policy allows none. The search box it would fill stays empty, which the site's
stylesheet already lays out.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from markupsafe import Markup

__all__ = [
    "CONTENT_MARKER",
    "FOOTER_NOTE",
    "FOOTER_NOTE_MARKER",
    "MARKERS",
    "TITLE_MARKER",
    "Shell",
    "ShellSource",
]

TITLE_MARKER: Final = "<!--emendrix:title-->"
CONTENT_MARKER: Final = "<!--emendrix:content-->"
FOOTER_NOTE_MARKER: Final = "<!--emendrix:footer-note-->"
MARKERS: Final = (TITLE_MARKER, CONTENT_MARKER, FOOTER_NOTE_MARKER)
"""In the order they stand in the file."""

FOOTER_NOTE: Final = Markup(
    "This page belongs to the account service, which sets one cookie, needed to keep you "
    'signed in. <a href="/account/privacy">Privacy notice</a>.'
)

_SCRIPT_LINE: Final = re.compile(r"(?m)^[ \t]*<script\b[^>]*>\s*</script>[ \t]*\r?\n?")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Shell:
    """The shell cut into the four pieces around its markers."""

    head: str
    middle: str
    lower: str
    tail: str

    @classmethod
    def parse(cls, text: str) -> Shell | str:
        """The shell `text` holds, or the reason it is not one."""
        for marker in MARKERS:
            count = text.count(marker)
            if count != 1:
                return f"the account shell has {count} {marker} markers where it needs one"
        text = _SCRIPT_LINE.sub("", text)
        if "<script" in text:
            return "the account shell carries a script the service cannot drop"
        head, rest = text.split(TITLE_MARKER)
        middle, rest = rest.split(CONTENT_MARKER)
        if FOOTER_NOTE_MARKER not in rest:
            return "the account shell's markers are out of order"
        lower, tail = rest.split(FOOTER_NOTE_MARKER)
        return cls(head=head, middle=middle, lower=lower, tail=tail)

    @classmethod
    def load(cls, path: Path) -> Shell | str:
        """The shell at `path`, or the reason it cannot be used."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            return f"the account shell cannot be read ({type(error).__name__})"
        return cls.parse(text)

    def render(self, *, title: str, content: Markup, footer_note: Markup = FOOTER_NOTE) -> str:
        """One page: the title escaped here, the content and note already rendered safe."""
        return "".join(
            (
                self.head,
                html.escape(title),
                self.middle,
                str(content),
                self.lower,
                str(footer_note),
                self.tail,
            )
        )


class ShellSource:
    """The shell at one path, read again whenever the file changes, never lost once read."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._shell: Shell | None = None
        self._seen: tuple[int, int] | None = None
        self._problem = "the account shell has not been read"

    def get(self) -> Shell | str:
        """The current shell, or the reason none has ever been read."""
        signature: tuple[int, int] | None
        loaded: Shell | str
        try:
            stat = self.path.stat()
        except OSError as error:
            signature, loaded = None, f"the account shell cannot be read ({type(error).__name__})"
        else:
            signature = (stat.st_mtime_ns, stat.st_size)
            if signature == self._seen:
                return self._current()
            loaded = Shell.load(self.path)
        self._seen = signature
        if isinstance(loaded, Shell):
            self._shell, self._problem = loaded, ""
        elif loaded != self._problem:
            if self._shell is not None:
                logger.warning("keeping the last good account shell: %s", loaded)
            self._problem = loaded
        return self._current()

    def _current(self) -> Shell | str:
        return self._shell if self._shell is not None else self._problem
