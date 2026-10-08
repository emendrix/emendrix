"""`/llms.txt`: what the site offers a model, and how to fetch the record instead of the pages.

The file follows the llms.txt convention's shape: one `#` heading, a blockquote summary, then
`##` sections of `- [name](url): note` lines, the last of them `## Optional`. It is Markdown
read by a program, not a page: no shell, no navigation, and the disclaimer stated in its own
paragraph because there is no footer to carry it.

It adds no description of its own. The summary is `pitch.PITCH`, the section headings and the
one-line purposes are `take_away.DOORS`, the API's lede and the MCP section are the constants
`/api/` renders, and the install line is filled by the same three expressions `api_page._mcp`
uses, so a test can hold the two to one string. The words written here are the headings of the
link lists and their short notes, which name files and pages and claim nothing measured. The
MCP section reaches here whole, so the contract test that holds its tool sentence to the
server's registered tools holds this file too.

Every link is absolute, built with `head.canonical_url`, because the file is read off the site
by an agent with no page to resolve a relative address against. So, like the sitemap,
`llms_txt` refuses without a site URL rather than inventing a base, and the builder writes the
file only with one. It is assembled as a string for byte-stability, with a fixed order and no
clock. Its bytes are ASCII because a static host serves `.txt` as `text/plain` with no charset,
and a reader left to guess one decodes ASCII the same way under every guess.
"""

from __future__ import annotations

import json
from textwrap import indent
from typing import Final

from emendrix import DISCLAIMER
from emendrix.site_.api_files import API_ROOT, CATALOGUE
from emendrix.site_.head import canonical_url
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.pages.api_prose import CLIENTS, LEDE, MCP
from emendrix.site_.pages.take_away import DOORS
from emendrix.site_.pitch import PITCH

__all__ = ["LLMS", "llms_txt"]

LLMS: Final = "llms.txt"
"""Where the builder writes the file: the site root, which is where an agent looks for it."""

_MCP_HEADING: Final = "## mcp The MCP server"
"""The anchor-carrying first line of `MCP`, which only `api_page._prose` reads; the file gives
the section a heading of its own."""

_UNCONFIGURED: Final = (
    "llms.txt links are absolute, so writing it needs a site URL; "
    "check `site.site_url` before asking for it"
)


def _link(site_url: str, name: str, path: str, note: str) -> str:
    return f"- [{name}]({canonical_url(site_url, path)}): {note}"


def _mcp(site_url: str) -> str:
    """The MCP section of `/api/`, its install lines filled exactly as that page fills them."""
    endpoint = canonical_url(site_url, "mcp")
    config = json.dumps({"mcpServers": {"emendrix": {"type": "http", "url": endpoint}}}, indent=2)
    clients = CLIENTS.replace("{endpoint}", endpoint).replace("{config}", indent(config, "    "))
    body = MCP.strip()
    if not body.startswith(_MCP_HEADING):
        raise ValueError(f"the MCP section no longer opens with {_MCP_HEADING!r}")
    return f"{body.removeprefix(_MCP_HEADING).strip()}\n\n{clients.strip()}"


def llms_txt(site: SiteInputs) -> str:
    """The file, newline-terminated and ASCII. Refuses without a site URL, like the sitemap."""
    if not site.site_url:
        raise ValueError(_UNCONFIGURED)
    url = site.site_url
    files, mcp, ci = DOORS
    sections = (
        "# emendrix",
        f"> {PITCH}",
        DISCLAIMER,
        "The record is published three ways besides these pages: as JSON files, to model "
        "clients over MCP, and as feeds. Prefer them to reading the HTML.",
        f"## {files.name}",
        LEDE,
        "\n".join(
            (
                _link(url, files.name, files.href, files.purpose),
                _link(
                    url,
                    "Root index",
                    f"{API_ROOT}index.json",
                    "one row per act, naming its act index",
                ),
                _link(url, "Catalogue", CATALOGUE, "every watched act's names and page addresses"),
                _link(url, "JSON Schemas", "api/#layout", "one per document the API serves"),
            )
        ),
        f"## {mcp.name}",
        _mcp(url),
        _link(url, mcp.name, mcp.href, mcp.purpose),
        f"## {ci.name}",
        "\n".join(
            (
                _link(url, "Example GitHub Actions workflow", ci.href, ci.purpose),
                _link(
                    url,
                    "Feeds",
                    "feeds/",
                    "Atom, one per act and one per touched provision, and OPML per act",
                ),
            )
        ),
        "## Optional",
        "\n".join(
            (
                _link(
                    url, "Methodology", "methodology/", "what every figure means and does not mean"
                ),
                _link(url, "About", "about/", "who runs this instance and what it is not"),
            )
        ),
    )
    return "\n\n".join(sections) + "\n"
