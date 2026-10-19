"""The reference deployment's routes and its compose file, as text.

The routes are the API (the recorded and derived halves, and the bare `/api/v1/` rewritten to
the root index), `/mcp` and its server card at `/mcp/server-card`, the two well-known catalogs
(`/.well-known/api-catalog` and `/.well-known/ai-catalog.json`) and the home page's
`api-catalog` `Link` header.

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
        "/api/v1/eu/32008R1272/register.json",
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


def _exact(path: str) -> str:
    """The body of the exact-match location for `path`."""
    found = re.search(
        rf"location = {re.escape(path)} \{{(.*?)\n    \}}",
        CONF.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert found is not None, path
    return found.group(1)


def test_the_server_card_is_proxied_and_left_its_own_caching_and_cors() -> None:
    """`expires off` would override the server's caching; a second CORS header breaks browsers."""
    block = _exact("/mcp/server-card")
    for directive in (
        "proxy_pass http://mcp:8000/mcp/server-card;",
        "proxy_set_header Host $http_host;",
        'add_header X-Content-Type-Options "nosniff" always;',
        "add_header Strict-Transport-Security",
    ):
        assert directive in block, directive
    assert "expires" not in block
    assert "Access-Control-Allow-Origin" not in block


@pytest.mark.parametrize(
    ("path", "media_type"),
    [
        ("/.well-known/api-catalog", "application/linkset+json"),
        ("/.well-known/ai-catalog.json", "application/ai-catalog+json"),
    ],
)
def test_each_well_known_catalog_is_served_under_its_media_type(path: str, media_type: str) -> None:
    block = _exact(path)
    assert f"default_type {media_type};" in block
    assert f"charset_types {media_type};" in block
    assert 'add_header Access-Control-Allow-Origin "*" always;' in block
    assert 'add_header X-Content-Type-Options "nosniff" always;' in block


def test_the_ai_catalog_extension_does_not_override_its_media_type() -> None:
    """`default_type` applies only when no extension maps, and `.json` maps to plain JSON."""
    assert "types { }" in _exact("/.well-known/ai-catalog.json")


def test_the_bare_api_directory_answers_with_the_root_index_from_the_volume() -> None:
    assert _exact("/api/v1/").strip() == "rewrite ^ /api/v1/index.json last;"
    pattern, _ = _recorded()
    assert pattern.fullmatch("/api/v1/index.json")


def test_the_home_page_names_the_api_catalog() -> None:
    block = _exact("/index.html")
    assert "add_header Link '</.well-known/api-catalog>; rel=\"api-catalog\"' always;" in block
    assert 'add_header X-Content-Type-Options "nosniff" always;' in block
    every_page = re.search(
        r"location / \{(.*?)\n    \}", CONF.read_text(encoding="utf-8"), re.DOTALL
    )
    assert every_page is not None
    assert "add_header" not in every_page.group(1)
