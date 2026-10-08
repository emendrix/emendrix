"""The reference deployment's routes for the API and for `/mcp`, and its compose file, as text.

nginx is not run here: CI has no web server and needs none to check what the location admits.
The pattern is compiled with Python's `re`, whose syntax agrees with nginx's PCRE for every
construct the pattern uses (anchors, alternation, character classes, `*`), so what it matches
here is what the server routes to the changelogs volume.
"""

from __future__ import annotations

import re

import pytest
from helpers import REPO

from emendrix.core import ActId
from emendrix.output.json_out import payload_for, slug

CONF = REPO / "deploy" / "default.conf"
COMPOSE = REPO / "deploy" / "compose.yaml"

_RECORDED = re.compile(r"location ~ (\^/api/v1/\S+\$) \{(.*?)\n    \}", re.DOTALL)
_DERIVED = re.compile(r"location /api/v1/ \{(.*?)\n    \}", re.DOTALL)


def _recorded() -> tuple[re.Pattern[str], str]:
    found = _RECORDED.search(CONF.read_text(encoding="utf-8"))
    assert found is not None
    return re.compile(found.group(1)), found.group(2)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/index.json",
        "/api/v1/eu/32017R0745/index.json",
        f"/api/v1/{payload_for(ActId(corpus='eu', key='32017R0745'), '02017R0745-20200424')}",
    ],
)
def test_every_recorded_kind_of_file_is_routed_to_the_changelogs_volume(path: str) -> None:
    pattern, _ = _recorded()
    assert pattern.fullmatch(path), path


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/.git/config",
        "/api/v1/.git/refs/index.json",
        "/api/v1/eu/32017R0745/CHANGELOG.md",
        "/api/v1/eu/",
        "/api/v1/eu/32017R0745/changes/",
        "/api/v1/catalogue.json",
        "/api/v1/schema/index.schema.json",
        "/api/v1/README.md",
    ],
)
def test_nothing_else_in_the_repository_is_routed(path: str) -> None:
    pattern, _ = _recorded()
    assert not pattern.fullmatch(path), path


def test_the_pattern_admits_every_name_the_slug_can_write() -> None:
    pattern, _ = _recorded()
    for name in ("a", "A.b-c_d", "02017R0745-20200424", slug("x/y z"), slug("")):
        assert pattern.fullmatch(f"/api/v1/{name}/{name}/changes/{name}.json"), name


def test_both_api_locations_repeat_the_headers_they_need() -> None:
    """A location that declares `add_header` inherits none, so each states its own."""
    _, recorded = _recorded()
    derived = _DERIVED.search(CONF.read_text(encoding="utf-8"))
    assert derived is not None
    for block in (recorded, derived.group(1)):
        assert 'add_header X-Content-Type-Options "nosniff" always;' in block
        assert 'add_header Access-Control-Allow-Origin "*" always;' in block
    assert "alias /srv/changelogs/$1;" in recorded


def test_the_web_service_mounts_the_record_read_only_and_owns_its_server_block() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "      - changelogs:/srv/changelogs:ro\n" in compose
    assert "      - ./default.conf:/etc/nginx/conf.d/default.conf:ro\n" in compose
    assert "error_page  404              /404.html;" in CONF.read_text(encoding="utf-8")


_MCP = re.compile(r"location = /mcp \{(.*?)\n    \}", re.DOTALL)


def _service(compose: str, name: str) -> str:
    """One service's block of `compose.yaml`, up to the next service or top-level key."""
    found = re.search(rf"\n  {name}:\n(.*?)(?=\n  [a-z]+:\n|\n[a-z]+:)", compose, re.DOTALL)
    assert found is not None, name
    return found.group(1)


def test_the_mcp_location_proxies_uncached_and_repeats_its_headers() -> None:
    found = _MCP.search(CONF.read_text(encoding="utf-8"))
    assert found is not None
    block = found.group(1)
    for directive in (
        "proxy_pass http://mcp:8000/mcp;",
        "proxy_buffering off;",
        "expires off;",
        "client_max_body_size 64k;",
        'add_header X-Content-Type-Options "nosniff" always;',
        "add_header Strict-Transport-Security",
    ):
        assert directive in block, directive


def test_the_mcp_service_reads_both_volumes_and_publishes_no_port() -> None:
    mcp = _service(COMPOSE.read_text(encoding="utf-8"), "mcp")
    assert "      - changelogs:/srv/changelogs:ro\n" in mcp
    assert "      - site:/srv/site:ro\n" in mcp
    assert "read_only: true" in mcp
    assert "ports:" not in mcp
    assert "EMENDRIX_MCP_CATALOGUE: /srv/site/api/v1/catalogue.json" in mcp


def test_one_variable_names_the_deployments_host() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "emendrix.eu" not in compose
    assert "github.com/emendrix/changelogs" not in compose
    page = _service(compose, "page")
    assert '      - "--site-url"\n      - "https://${EMENDRIX_PUBLIC_HOST:?' in page
    assert '      - "--changelogs-url"\n      - "${EMENDRIX_CHANGELOGS_URL:-}"\n' in page
    assert 'EMENDRIX_MCP_ALLOWED_HOSTS: "${EMENDRIX_PUBLIC_HOST:?' in _service(compose, "mcp")
    example = (REPO / "deploy" / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^EMENDRIX_PUBLIC_HOST=\S+$", example, re.MULTILINE)
