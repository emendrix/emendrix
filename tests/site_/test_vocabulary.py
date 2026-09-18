"""The words a page says about the sources: "sources differ", and never the stored word.

`disputed` is the project's own vocabulary and it stays where it is correct: in `core`, in the
JSON, in the metrics and in the committed changelog's Markdown. On a page a newcomer reads it
as a claim about the law, when it is a claim about three detectors, so no page says it, nor
`contested` or `conflict`, which read the same way. This is asserted over every page of the two
trees the suite builds: the golden tree, which is the fixture site byte for byte, and the scale
tree, two hundred generated versions of one act.

**One stated exception.** The methodology page's measured table prints the row label the eval
harness publishes, which is shared with the README's own table and generated outside the site.
It is found here by its label's exact text and taken out whole, label and meaning, exactly
once, so a second occurrence anywhere fails.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from helpers import text_of
from test_act_page_at_scale import _entries, _pages

GOLDEN: Final = Path(__file__).resolve().parent / "golden"

_BANNED: Final = re.compile(r"disputed|contested|conflict", re.IGNORECASE)

_EXCEPTION: Final = ("methodology/index.html", "<tr><td>Disputed changes (signals disagree)</td>")
"""The measured table's row, rendered from the eval harness's metric rows, which the README's
published table shares; the site does not own its words, its label or its meaning."""

_SCRIPT: Final = re.compile(r"<script\b.*?</script>", re.DOTALL)
_HEAD: Final = re.compile(r"<head>.*?</head>", re.DOTALL)
_TITLE: Final = re.compile(r"<title>(.*?)</title>", re.DOTALL)
_CLASS: Final = re.compile(r'class="([^"]*)"')


def _golden() -> dict[str, str]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(GOLDEN.rglob("*.html"))
    }


def _said(path: str, page: str) -> list[str]:
    """Every banned word a reader can see or a result list shows, the exception taken out."""
    exception_path, exception = _EXCEPTION
    if path == exception_path:
        assert page.count(exception) == 1, path
        start = page.index(exception)
        page = page[:start] + page[page.index("</tr>", start) :]
    title = " ".join(_TITLE.findall(page))
    body = text_of(_SCRIPT.sub("", _HEAD.sub("", page)))
    return _BANNED.findall(f"{title}\n{body}")


def _check(pages: dict[str, str]) -> None:
    assert pages
    for path, page in pages.items():
        assert _said(path, page) == [], path
        for classes in _CLASS.findall(page):
            assert not any(
                name.startswith("disp-") or name == "disp" for name in classes.split()
            ), path


def test_no_golden_page_says_the_stored_word_but_the_one_measured_row() -> None:
    pages = _golden()
    assert _EXCEPTION[0] in pages
    _check(pages)


def test_no_page_of_the_scale_tree_says_it_either() -> None:
    _check(_pages(_entries()))
