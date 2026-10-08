"""The `/api/` page: what it links, what it says without a base, and the one CI example.

The example workflow is published twice, on this page and in `docs/api.md`, and the two must be
the same bytes. The hosted address the reference document uses is read from `pyproject.toml`'s
`Homepage`, never written here, because it is configuration a fork changes.
"""

from __future__ import annotations

import html
import re
import tomllib
from pathlib import Path

import pytest
from helpers import REPO, REPORTS, SITE_URL, WATCHLIST, build, runner, text_of

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.site_.markup import escape
from emendrix.site_.pages.api_page import SNIPPET_TEMPLATE, snippet
from eu_pins import OBSERVED_ON

API_DOC = REPO / "docs" / "api.md"
PAGE = "api/index.html"

_TABLE = re.compile(r'<table role="table">(.*?)</table>', re.DOTALL)
_PRE = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)
_CI = re.compile(r'<section id="watch-in-ci">(.*?)</section>', re.DOTALL)


def _hosted() -> str:
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    homepage: str = project["urls"]["Homepage"]
    return homepage.rstrip("/")


def _documented() -> str:
    """The first `yaml` block under `## Watch a provision from CI` in the API's document."""
    text = API_DOC.read_text(encoding="utf-8")
    section = text.split("\n## Watch a provision from CI\n", 1)[1]
    return section.split("```yaml\n", 1)[1].split("```\n", 1)[0]


def _unconfigured(out: Path, changelog_repo: Path, *extra: str) -> Path:
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
        "--changelogs",
        str(changelog_repo),
        *extra,
    ]
    result = runner.invoke(app, arguments, env={"EMENDRIX_OUTPUT_REPO": ""})
    assert result.exit_code == 0, result.output
    return out


@pytest.fixture(scope="module")
def page(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> str:
    out = build(tmp_path_factory.mktemp("api-page") / "site", changelog_repo)
    return (out / PAGE).read_text(encoding="utf-8")


def test_the_page_carries_the_disclaimer_and_the_ci_anchor(page: str) -> None:
    assert escape(DISCLAIMER) in text_of(page)
    assert page.count('id="watch-in-ci"') == 1


def test_every_address_in_the_layout_table_is_under_the_site_url(page: str) -> None:
    table = _TABLE.search(page)
    assert table is not None
    links = re.findall(r'href="([^"]+)"', table.group(1))
    assert len(links) == 3
    assert all(link.startswith(f"{SITE_URL}/api/") for link in links), links


def test_the_page_links_the_methodology_page(page: str) -> None:
    assert 'href="../methodology/"' in page


def test_the_page_names_no_endpoint_it_does_not_serve(page: str) -> None:
    assert "mcp" not in page.lower()


def test_the_snippet_on_the_page_is_pointed_at_the_site_it_is_on(page: str) -> None:
    section = _CI.search(page)
    assert section is not None
    blocks = _PRE.findall(section.group(1))
    assert [html.unescape(block) for block in blocks] == [snippet(SITE_URL)]
    assert "jq" in section.group(1) and "gh" in section.group(1)


def test_the_documented_snippet_is_the_one_the_page_publishes() -> None:
    assert _documented() == SNIPPET_TEMPLATE.replace("{base}", _hosted())
    assert SNIPPET_TEMPLATE.count("{base}") == 2


def test_without_a_site_url_the_page_says_so_and_shows_the_hosted_example(
    tmp_path: Path, changelog_repo: Path
) -> None:
    out = _unconfigured(tmp_path / "site", changelog_repo)
    text = (out / PAGE).read_text(encoding="utf-8")
    assert "absolute addresses are not known for this build" in text
    table = _TABLE.search(text)
    assert table is not None
    assert "href=" not in table.group(1)
    section = _CI.search(text)
    assert section is not None
    assert [html.unescape(block) for block in _PRE.findall(section.group(1))] == [
        snippet(_hosted())
    ]
    for link in re.findall(r'href="(v1/[^"]+)"', text):
        assert (out / "api" / link).is_file(), link


def test_the_licence_is_named_only_with_a_changelogs_url(
    tmp_path: Path, changelog_repo: Path, page: str
) -> None:
    assert 'id="licence"' not in page
    home = "https://data.example.invalid/changelogs"
    out = _unconfigured(tmp_path / "site", changelog_repo, "--changelogs-url", home)
    text = (out / PAGE).read_text(encoding="utf-8")
    assert 'id="licence"' in text
    assert f'<a href="{home}">changelogs repository</a>' in text
