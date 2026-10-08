"""The three ways to take the record away: worded once, resolving in the built tree, constant.

The doors are read off the committed golden rather than a fresh build, because the golden is the
fixture site byte for byte and `test_golden.py` already holds the two equal; every page that
prints the block is checked for every door it prints.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from posixpath import dirname, join, normpath
from typing import Final

from helpers import REPORTS
from test_vocabulary import _ARROWS, _BANNED, _EVENT

from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.inputs import collect_site
from emendrix.site_.pages.home import render_home
from emendrix.site_.pages.take_away import DOORS, take_away

GOLDEN: Final = Path(__file__).resolve().parent / "golden"

_PRINTED_ON: Final = ("index.html", "about/index.html", "api/index.html")
"""The pages that render the block: home, About, and the index at the top of `/api/`."""

_BLOCK: Final = re.compile(r'<section class="doors".*?</section>', re.DOTALL)
_HREF: Final = re.compile(r'<a href="([^"]*)"')


def _block(page: str) -> str:
    found = _BLOCK.findall(page)
    assert len(found) == 1, "the block is printed once a page"
    return str(found[0])


def test_the_doors_are_the_three_addresses_in_order() -> None:
    assert [door.href for door in DOORS] == ["api/", "api/#mcp", "api/#watch-in-ci"]
    assert [door.anchor for door in DOORS] == ["layout", "mcp", "watch-in-ci"]
    assert [door.name for door in DOORS] == ["The JSON API", "The MCP server", "Watch from CI"]


def test_every_door_resolves_to_a_file_and_an_id_in_the_built_tree() -> None:
    """A door whose page or id went away would be a link into nothing on three pages at once."""
    for page in _PRINTED_ON:
        hrefs = _HREF.findall(_block((GOLDEN / page).read_text(encoding="utf-8")))
        assert len(hrefs) == len(DOORS), page
        for href in hrefs:
            path, _, anchor = href.partition("#")
            file = GOLDEN / normpath(join(dirname(page), path)) / "index.html" if path else None
            target = GOLDEN / page if file is None else file
            assert target.is_file(), (page, href)
            if anchor:
                text = target.read_text(encoding="utf-8")
                assert text.count(f'id="{anchor}"') == 1, (page, href)


def test_the_block_is_the_same_bytes_whatever_the_build_was_given() -> None:
    run = EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())
    one = collect_site(generated_on=date(2026, 8, 9), run=run, report=Path("r.json"))
    other = collect_site(
        generated_on=date(2027, 1, 1),
        run=run,
        report=Path("other.json"),
        configured=True,
        site_url="https://example.invalid/site",
    )
    assert _block(render_home(one)) == _block(render_home(other))


def test_the_words_say_no_banned_word_and_carry_no_arrow() -> None:
    block = take_away("", heading="Take the record with you", note="A sentence.")
    words = re.sub(r"<[^>]*>", "", block)
    assert not _BANNED.search(words)
    assert not _EVENT.search(words)
    assert not _ARROWS.search(words)


def test_on_the_api_page_every_door_is_a_jump_down_the_same_page() -> None:
    block = take_away("../", heading="Three ways in", here=True)
    assert _HREF.findall(block) == ["#layout", "#mcp", "#watch-in-ci"]
