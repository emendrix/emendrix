"""The two documents under `/.well-known/` that say where the machine-readable doors are.

`.well-known/api-catalog` is an RFC 9727 API catalog, verified 2026-10-19 against
https://www.rfc-editor.org/rfc/rfc9727 (section 4 and Appendix A). It is a Linkset (RFC 9264,
`application/linkset+json`): a top-level `{"linkset": [...]}` of context objects, each an
`anchor` and its relations as arrays of target objects. Three context objects are written, in a
fixed order. The first is the catalog itself, anchored at its own well-known address, with an
`item` link to each API, as Appendix A.2 does, and a `profile` link to the RFC 9727 profile URI,
which section 4.2 asks for and which a static file can carry only as a link. The other two
describe one API each, as Appendix A.1 does: the MCP endpoint, whose `service-desc` is its server
card and whose `service-doc` is the `/api/` page's MCP section; and the JSON API at `api/v1/`,
whose `service-doc` is `/api/`. The JSON API has no `service-desc`, because the build writes one
schema per document under `api/v1/schema/` and no single document describing the whole API, and
a catalog that pointed at one schema as the API's description would claim more than it holds.

`.well-known/ai-catalog.json` is an AI Catalog, verified 2026-10-19 against
`specification/ai-catalog.md` of https://github.com/Agent-Card/ai-catalog at commit `9316f00`.
It is a Level 2 catalog in that specification's terms: the required `specVersion` (`"1.0"`, the
version every example in it carries) and `entries`, plus the optional `host` with its required
`displayName`. Its one entry is the server card, with the required `identifier`, `type` and
`url`. The identifier follows the `urn:air:{publisher}:{namespace}:{name}` form with the
publisher read off the site URL's host, so it names whoever serves this build. Entry
`displayName`, `description` and `version` are left out because the specification says to omit
them when the referenced card carries its own.

The card path is written here as a literal because the pipeline does not import the MCP
server's package; a test beside the server holds the two to one string. Both documents are
pure functions of `SiteInputs`: absolute addresses through `canonical_url`, sorted keys, ASCII,
two-space indent, one trailing newline, and no clock. Like `llms_txt`, each refuses without a
site URL, and the builder writes them only with one.
"""

from __future__ import annotations

import json
from typing import Final
from urllib.parse import urlsplit

from emendrix.site_.head import SITE_NAME, canonical_url
from emendrix.site_.inputs import SiteInputs

__all__ = ["AI_CATALOG", "API_CATALOG", "ai_catalog", "api_catalog", "well_known_files"]

API_CATALOG: Final = ".well-known/api-catalog"
"""RFC 9727's well-known address, with no extension: the web server names its media type."""

AI_CATALOG: Final = ".well-known/ai-catalog.json"
"""The AI Catalog specification's well-known address."""

CARD_PATH: Final = "mcp/server-card"
"""Where the MCP server describes itself: the endpoint's address plus `/server-card`."""

CARD_TYPE: Final = "application/mcp-server-card+json"

_PROFILE: Final = "https://www.rfc-editor.org/info/rfc9727"
_AI_CATALOG_VERSION: Final = "1.0"

_UNCONFIGURED: Final = (
    "the well-known documents' links are absolute, so writing them needs a site URL; "
    "check `site.site_url` before asking for them"
)


def _json(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _site_url(site: SiteInputs) -> str:
    if not site.site_url:
        raise ValueError(_UNCONFIGURED)
    return site.site_url


def api_catalog(site: SiteInputs) -> str:
    """The RFC 9727 Linkset naming the MCP endpoint and the JSON API. Refuses without a URL."""
    url = _site_url(site)
    mcp = canonical_url(url, "mcp")
    api = canonical_url(url, "api/v1/")
    linkset = (
        {
            "anchor": canonical_url(url, API_CATALOG),
            "item": [{"href": mcp}, {"href": api}],
            "profile": [{"href": _PROFILE}],
        },
        {
            "anchor": mcp,
            "service-desc": [{"href": canonical_url(url, CARD_PATH), "type": CARD_TYPE}],
            "service-doc": [{"href": canonical_url(url, "api/#mcp"), "type": "text/html"}],
        },
        {
            "anchor": api,
            "service-doc": [{"href": canonical_url(url, "api/"), "type": "text/html"}],
        },
    )
    return _json({"linkset": list(linkset)})


def ai_catalog(site: SiteInputs) -> str | None:
    """The AI Catalog with the server card as its one entry. Refuses without a URL.

    `None` when the site URL names no host, because the identifier's publisher is that host and
    an entry with an invented one would be worse than no catalog.
    """
    url = _site_url(site)
    host = urlsplit(url).hostname or ""
    if not host:
        return None
    entry = {
        "identifier": f"urn:air:{host}:mcp:{SITE_NAME}",
        "type": CARD_TYPE,
        "url": canonical_url(url, CARD_PATH),
    }
    return _json(
        {
            "entries": [entry],
            "host": {"displayName": SITE_NAME, "documentationUrl": canonical_url(url, "api/")},
            "specVersion": _AI_CATALOG_VERSION,
        }
    )


def well_known_files(site: SiteInputs) -> dict[str, str]:
    """Both documents as `relative path -> contents`, the AI Catalog only when it is written."""
    files = {API_CATALOG: api_catalog(site)}
    if (catalog := ai_catalog(site)) is not None:
        files[AI_CATALOG] = catalog
    return files
