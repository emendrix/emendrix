"""`/llms.txt`: written only with a site URL, ASCII, and pointing only at what the build wrote.

A build without a site URL writing no `llms.txt` is asserted beside the other files that need
one, in `test_site_build.py`.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from helpers import REPORTS, SITE_URL, build

from emendrix import DISCLAIMER
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.llms import LLMS, llms_txt
from emendrix.site_.pages.api_prose import MCP
from eu_pins import OBSERVED_ON

_LINK = re.compile(r"\]\(([^)\s]+)\)")
_INSTALL = re.compile(r"claude mcp add [^\n<]+")
_RECORD_ROOT = "api/v1/index.json"
"""The one target the site build does not write: the record's root index, which a deployment
serves from the changelogs repository as committed, as the API page's layout table says."""


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("llms") / "site", changelog_repo)


def _text(site: Path) -> str:
    return (site / LLMS).read_bytes().decode("ascii")


def test_llms_txt_refuses_without_a_site_url() -> None:
    bare = SiteInputs(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report="r.json",
        site_url="",
    )
    with pytest.raises(ValueError, match="site URL"):
        llms_txt(bare)


def test_a_build_with_a_site_url_writes_one_at_the_root(site: Path) -> None:
    assert [path.relative_to(site).as_posix() for path in site.rglob(LLMS)] == [LLMS]


def test_the_file_is_ascii_and_ends_in_one_newline(site: Path) -> None:
    text = _text(site)
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_it_opens_with_the_name_and_carries_the_disclaimer_once(site: Path) -> None:
    text = _text(site)
    assert text.startswith("# emendrix\n\n> ")
    assert text.count(DISCLAIMER) == 1
    assert "## Optional\n" in text


def test_every_link_is_absolute_and_resolves_in_the_built_tree(site: Path) -> None:
    targets = _LINK.findall(_text(site))
    assert targets
    for target in targets:
        assert target.startswith(f"{SITE_URL}/"), target
        path, _, fragment = target.removeprefix(f"{SITE_URL}/").partition("#")
        if path == _RECORD_ROOT:
            assert "v1/index.json" in (site / "api" / "index.html").read_text(encoding="utf-8")
            continue
        file = site / (f"{path}index.html" if not path or path.endswith("/") else path)
        assert file.is_file(), target
        if fragment:
            assert f'id="{fragment}"' in file.read_text(encoding="utf-8"), target


def test_the_install_line_and_the_tools_are_the_api_pages_own(site: Path) -> None:
    text = _text(site)
    page = html.unescape((site / "api" / "index.html").read_text(encoding="utf-8"))
    (line,) = _INSTALL.findall(text)
    assert _INSTALL.findall(page) == [line]
    assert line.endswith(f"{SITE_URL}/mcp")
    tools = MCP.split("Its seven tools are", 1)[1].split("four resources", 1)[0]
    assert tools in text
    assert "## mcp " not in text


def test_two_builds_of_one_input_write_identical_bytes(
    site: Path, tmp_path: Path, changelog_repo: Path
) -> None:
    again = build(tmp_path / "again", changelog_repo)
    assert (again / LLMS).read_bytes() == (site / LLMS).read_bytes()
