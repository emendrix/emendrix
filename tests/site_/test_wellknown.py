"""The documents under `/.well-known/` and the home page's pointers at them.

A build without a site URL writing no `.well-known/` file is asserted beside the other files that
need one, in `test_site_build.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from helpers import REPORTS, SITE_URL, build

from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.pages.home import render_home
from emendrix.site_.wellknown import (
    AI_CATALOG,
    API_CATALOG,
    CARD_PATH,
    CARD_TYPE,
    ai_catalog,
    api_catalog,
)
from eu_pins import OBSERVED_ON

_RELATION = (
    '<link rel="api-catalog" href=".well-known/api-catalog" type="application/linkset+json">'
)


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, changelog_repo: Path) -> Path:
    return build(tmp_path_factory.mktemp("wellknown") / "site", changelog_repo)


def _inputs(site_url: str) -> SiteInputs:
    return SiteInputs(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report="r.json",
        site_url=site_url,
    )


def _load(site: Path, path: str) -> Any:
    return json.loads((site / path).read_bytes().decode("ascii"))


def _addresses(document: Any) -> list[str]:
    """Every `href` and `anchor` and `url` in a JSON document, at any depth."""
    if isinstance(document, dict):
        own = [v for k, v in document.items() if k in {"href", "anchor", "url"}]
        return own + [a for value in document.values() for a in _addresses(value)]
    if isinstance(document, list):
        return [a for item in document for a in _addresses(item)]
    return []


def test_both_refuse_without_a_site_url() -> None:
    for render in (api_catalog, ai_catalog):
        with pytest.raises(ValueError, match="site URL"):
            render(_inputs(""))


def test_a_build_writes_both_at_their_exact_paths(site: Path) -> None:
    written = sorted(p.relative_to(site).as_posix() for p in (site / ".well-known").iterdir())
    assert written == sorted((API_CATALOG, AI_CATALOG))


@pytest.mark.parametrize("path", [API_CATALOG, AI_CATALOG])
def test_each_is_ascii_sorted_json_with_one_trailing_newline(site: Path, path: str) -> None:
    text = (site / path).read_bytes().decode("ascii")
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize("path", [API_CATALOG, AI_CATALOG])
def test_every_address_is_absolute_under_the_site_url(site: Path, path: str) -> None:
    addresses = _addresses(_load(site, path))
    assert addresses
    for address in addresses:
        if address == "https://www.rfc-editor.org/info/rfc9727":
            continue
        assert address.startswith(f"{SITE_URL}/"), address


def test_the_api_catalog_names_the_mcp_endpoint_and_the_json_api(site: Path) -> None:
    linkset = _load(site, API_CATALOG)["linkset"]
    by_anchor = {context["anchor"]: context for context in linkset}
    catalog = by_anchor[f"{SITE_URL}/{API_CATALOG}"]
    mcp, api = f"{SITE_URL}/mcp", f"{SITE_URL}/api/v1/"
    assert [item["href"] for item in catalog["item"]] == [mcp, api]
    assert catalog["profile"] == [{"href": "https://www.rfc-editor.org/info/rfc9727"}]
    assert by_anchor[mcp]["service-desc"] == [
        {"href": f"{SITE_URL}/{CARD_PATH}", "type": CARD_TYPE}
    ]
    assert by_anchor[mcp]["service-doc"][0]["href"] == f"{SITE_URL}/api/#mcp"
    assert by_anchor[api]["service-doc"][0]["href"] == f"{SITE_URL}/api/"
    assert set(by_anchor) == {catalog["anchor"], mcp, api}


def test_the_ai_catalog_lists_the_server_card_under_the_sites_host(site: Path) -> None:
    document = _load(site, AI_CATALOG)
    assert document["specVersion"] == "1.0"
    assert document["entries"] == [
        {
            "identifier": "urn:air:example.invalid:mcp:emendrix",
            "type": CARD_TYPE,
            "url": f"{SITE_URL}/{CARD_PATH}",
        }
    ]
    assert document["host"]["displayName"] == "emendrix"


def test_two_builds_of_one_input_write_identical_bytes(
    site: Path, tmp_path: Path, changelog_repo: Path
) -> None:
    again = build(tmp_path / "again", changelog_repo)
    for path in (API_CATALOG, AI_CATALOG):
        assert (again / path).read_bytes() == (site / path).read_bytes()


def test_the_home_page_points_at_both_with_a_site_url() -> None:
    home = render_home(_inputs(SITE_URL))
    assert home.count(_RELATION) == 1
    assert '<a href="llms.txt">llms.txt</a>' in home
    assert f"<code>{SITE_URL}/mcp</code>" in home


def test_the_home_page_names_neither_without_one() -> None:
    home = render_home(_inputs(""))
    assert 'rel="api-catalog"' not in home
    assert "llms.txt" not in home
    assert "/mcp</code>" not in home


def test_no_other_page_carries_the_relation(site: Path) -> None:
    carriers = [
        page.relative_to(site).as_posix()
        for page in site.rglob("*.html")
        if 'rel="api-catalog"' in page.read_text(encoding="utf-8")
    ]
    assert carriers == ["index.html"]
