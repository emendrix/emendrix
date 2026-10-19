"""The surfaces that describe the MCP server to a machine agree about the facts they share.

The server card is computed by the MCP server's package; the catalogs and `llms.txt` by the site
build, which cannot import that package; the registry descriptor, the version and the web
server's routes are kept by hand. Each states some of the same facts: the card's path, the
version, the registry name, the endpoint. `docs/mcp-discovery.md` lists every surface and what
to amend when the server changes, and this module holds the surfaces to one another and that
document to the tree. Like `test_record_contract.py`, it imports both `emendrix` and
`emendrix_mcp`, which nothing outside the tests may do.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.site_ import wellknown
from emendrix.site_.head import canonical_url
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.llms import llms_txt
from emendrix.site_.pages.api_prose import CLIENTS
from emendrix_mcp import __version__
from emendrix_mcp.card import CARD_PATH, MEDIA_TYPE, build_card, endpoint, registry_name
from eu_pins import OBSERVED_ON

REPO = Path(__file__).resolve().parents[2]
MEMBER = REPO / "packages" / "emendrix-mcp"
DISCOVERY = REPO / "docs" / "mcp-discovery.md"
HOSTED = "emendrix.eu"
SITE_URL = f"https://{HOSTED}"


def _card(host: str = HOSTED) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(build_card(host).body)
    return loaded


def _descriptor() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((MEMBER / "server.json").read_text(encoding="utf-8"))
    return loaded


def _inputs() -> SiteInputs:
    """The inputs `tests/site_/test_llms.py` builds a bare `llms.txt` from, at the hosted URL."""
    return SiteInputs(
        generated_on=OBSERVED_ON,
        run=EvalRun.model_validate_json(latest_report(REPO / "reports" / "eval").read_bytes()),
        report="r.json",
        site_url=SITE_URL,
    )


def test_every_surface_names_the_card_path_the_server_answers() -> None:
    """Catches the card path moving in the server while the site or the routes keep the old one."""
    assert f"/{wellknown.CARD_PATH}" == CARD_PATH
    assert wellknown.CARD_TYPE == MEDIA_TYPE
    nginx = (REPO / "deploy" / "default.conf").read_text(encoding="utf-8")
    assert f"location = {CARD_PATH} {{" in nginx
    assert f"proxy_pass http://mcp:8000{CARD_PATH};" in nginx
    assert f"]({SITE_URL}{CARD_PATH})" in llms_txt(_inputs())


def test_the_card_the_package_and_the_descriptor_state_one_version() -> None:
    """Catches a release that bumps one of the three version strings and not the others."""
    pyproject = tomllib.loads((MEMBER / "pyproject.toml").read_text(encoding="utf-8"))
    versions = {
        "card": _card()["version"],
        "__init__": __version__,
        "pyproject.toml": pyproject["project"]["version"],
        "server.json": _descriptor()["version"],
    }
    assert len(set(versions.values())) == 1, versions


def test_the_descriptor_is_the_hosted_card_by_name_and_endpoint() -> None:
    """Catches the registry entry naming a server or an address the hosted card does not."""
    descriptor = _descriptor()
    assert descriptor["name"] == registry_name(HOSTED) == _card()["name"]
    assert [remote["url"] for remote in descriptor["remotes"]] == [
        remote["url"] for remote in _card()["remotes"]
    ]


def test_the_site_documents_name_the_endpoint_the_server_reports() -> None:
    """Catches `llms.txt`, the catalogs and the `/api/` install line naming different endpoints."""
    hosted = endpoint(HOSTED)
    assert canonical_url(SITE_URL, "mcp") == hosted
    text = llms_txt(_inputs())
    assert CLIENTS.replace("{endpoint}", hosted).split("\n\n", 1)[0].strip() in text
    assert f"]({SITE_URL}/{wellknown.API_CATALOG})" in text
    linkset = json.loads(wellknown.api_catalog(_inputs()))["linkset"]
    described = [entry for entry in linkset if "service-desc" in entry]
    assert [entry["anchor"] for entry in described] == [hosted]
    assert described[0]["service-desc"][0]["href"] == f"{SITE_URL}{CARD_PATH}"
    catalog = json.loads(wellknown.ai_catalog(_inputs()) or "{}")
    assert [entry["url"] for entry in catalog["entries"]] == [f"{SITE_URL}{CARD_PATH}"]


def _surfaces_table() -> list[list[str]]:
    section = DISCOVERY.read_text(encoding="utf-8").split("\n## The surfaces\n", 1)[1]
    section = section.split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| ")]
    cells = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]
    return [row for row in cells[1:] if not set(row[0]) <= set("-")]


def test_every_path_in_the_surfaces_table_exists() -> None:
    """Catches a file renamed or moved while the discovery document still points at the old name."""
    rows = _surfaces_table()
    assert len(rows) >= 10
    for surface, written_by, held_by in rows:
        paths = [
            path
            for cell in (written_by, held_by)
            for path in re.findall(r"`([^`\s]+)`", cell)
            if "/" in path
        ]
        assert paths or held_by == "nothing", surface
        for path in paths:
            assert (REPO / path).exists(), f"{surface}: {path}"


def test_the_discovery_document_is_written_by_the_repository_rules() -> None:
    """Catches an em-dash or a reference to a working note, which no clone can follow."""
    text = DISCOVERY.read_text(encoding="utf-8")
    assert chr(0x2014) not in text
    assert not re.search(r"\btemp[/]|\bplans?\b|\bstep \d", text, re.IGNORECASE)
