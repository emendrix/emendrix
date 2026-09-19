"""The words a page says: "sources differ" and "version", never the stored words, and no arrow.

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

**"Event" is the pipeline's word too**, for one recorded transition between two consolidated
versions, and it stays in the Python names, the JSON and the feeds' own summaries. On a page
that transition is a version, decided on 2026-09-18, so no page's visible text or `<title>`
says "event". The one place a page prints it is the law's own text, where the Medical Devices
Regulation says "in the event that" and "adverse events": the verbatim blocks are taken out
before the check and what they say is counted per page, so a stored text that stopped saying
it, or a page that started, fails here rather than passing quietly.

**No link's words carry an arrow.** A drawn arrow beside a link is the sheet's, with empty
alternative text, so a screen reader names the link by its words alone. The `→` between two
version codes is meaning rather than decoration and sits outside any link.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from helpers import text_of
from test_act_page_at_scale import _entries, _pages

GOLDEN: Final = Path(__file__).resolve().parent / "golden"

_BANNED: Final = re.compile(r"disputed|contested|conflict", re.IGNORECASE)

_EXCEPTION: Final = (
    "methodology/index.html",
    '<tr role="row"><td role="cell" data-label="Measure">Disputed changes (signals disagree)</td>',
)
"""The measured table's row, rendered from the eval harness's metric rows, which the README's
published table shares; the site does not own its words, its label or its meaning."""

_EVENT: Final = re.compile(r"\bevents?\b", re.IGNORECASE)

_VERBATIM: Final = re.compile(
    r'<p class="diff">.*?</p>|<pre class="verbatim[^"]*">.*?</pre>', re.DOTALL
)
"""The stored legal text, as a diff or as one side whole: the law's words, not the site's."""

_LAW_SAYS: Final = {
    "acts/32017R0745/02017R0745-20200424/index.html": 2,
    "acts/32017R0745/ar-17/index.html": 1,
    "acts/32017R0745/ar-120/index.html": 1,
}
"""How often the verbatim text on a golden page says "event", read 2026-09-19: Article 17's "In
the event that" and Article 120's "serious adverse events", both on the version page and each
on its own article's history."""

_ARROWS: Final = re.compile("[\u2190\u2191\u2192\u2197]")
_LINK: Final = re.compile(r"<a\b[^>]*>(.*?)</a>", re.DOTALL)

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


def _event_words(page: str) -> tuple[list[str], int]:
    """ "Event" as the page says it, and how often the law's own text on it says it."""
    law = sum(len(_EVENT.findall(text_of(block))) for block in _VERBATIM.findall(page))
    page = _VERBATIM.sub("", page)
    title = " ".join(_TITLE.findall(page))
    body = text_of(_SCRIPT.sub("", _HEAD.sub("", page)))
    return _EVENT.findall(f"{title}\n{body}"), law


def _check_event(pages: dict[str, str], law_says: dict[str, int]) -> None:
    assert pages
    counted: dict[str, int] = {}
    for path, page in pages.items():
        said, law = _event_words(page)
        assert said == [], path
        if law:
            counted[path] = law
    assert counted == law_says


def test_no_golden_page_says_event_where_the_law_does_not() -> None:
    _check_event(_golden(), _LAW_SAYS)


def test_no_page_of_the_scale_tree_says_event_at_all() -> None:
    _check_event(_pages(_entries()), {})


def test_no_link_in_the_golden_tree_carries_an_arrow_in_its_words() -> None:
    pages = _golden()
    links = 0
    for path, page in pages.items():
        for words in _LINK.findall(_HEAD.sub("", page)):
            links += 1
            assert not _ARROWS.search(text_of(words)), (path, words)
    assert links > 500
