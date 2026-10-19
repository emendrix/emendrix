# How a machine finds the MCP server and the record

Not legal advice: this output is machine-computed from published texts, carries no lawyer's review, and is engineering assistance only.

The MCP server and the JSON API are described to programs in several places at once: the server
itself, the files a site build writes, the reference web server's routes and a registry entry.
Each states a few of the same facts (the endpoint, the card's address, the version, the server's
name, the tool list), and nothing makes them agree except the tests named below. This document
lists every such surface, says who writes it and which test holds it, and says what to amend when
the server changes. **Read it before adding or renaming a tool**, and add the next surface here
when one is created.

## What an agent finds, and in what order

The route as it stands, for a site built with `--site-url https://emendrix.eu` and served by the
reference web server in [`../deploy/default.conf`](../deploy/default.conf):

1. **The home page.** Under the ways to take the record away, one sentence names `/llms.txt` and
   the MCP endpoint, and the head carries
   `<link rel="api-catalog" href=".well-known/api-catalog" type="application/linkset+json">`.
   Served as `text/html`.
2. **The `Link` header on the home response**, `</.well-known/api-catalog>; rel="api-catalog"`, on
   `/` and `/index.html` only.
3. **`/llms.txt`**, Markdown for a model: the JSON API's files, the `/api/` page's MCP section
   whole, and links to the server card and both catalogs. Served as `text/plain`, ASCII.
4. **`/.well-known/api-catalog`**, an RFC 9727 linkset naming the MCP endpoint (its
   `service-desc` is the server card) and the JSON API at `/api/v1/`. Served as
   `application/linkset+json; charset=utf-8`, with `Access-Control-Allow-Origin: *`.
5. **`/.well-known/ai-catalog.json`**, an AI Catalog whose one entry is the server card. Served as
   `application/ai-catalog+json`, with `Access-Control-Allow-Origin: *`.
6. **`/mcp/server-card`**, the server card: name, version, description and the one
   streamable-HTTP remote. Served by the MCP server itself as `application/mcp-server-card+json`,
   with a strong `ETag`, `Cache-Control: public, max-age=3600`, `Vary: Host` and CORS `*`.
7. **`/mcp`**, the endpoint: MCP over streamable HTTP, `POST` only. A `GET` answers `405` with
   `Allow: POST` and a `text/plain` body naming the card and `/llms.txt`.
8. **The MCP Registry entry** `eu.emendrix/emendrix`, published from
   [`../packages/emendrix-mcp/server.json`](../packages/emendrix-mcp/server.json) by a person, not
   by any build. It names the same endpoint and version as the card.

`/api/v1/` answers with the root index rather than a directory listing, so an agent that follows
the catalog's `item` link gets data in one request.

## The surfaces

Generated surfaces are written by code and change only when that code does. Surfaces kept by hand
are marked; they are the ones that rot.

| Surface | Written by | Held by |
|---|---|---|
| the tool and resource registrations, and `TOOLS` | `packages/emendrix-mcp/src/emendrix_mcp/server.py`, `packages/emendrix-mcp/src/emendrix_mcp/resources.py` | `packages/emendrix-mcp/tests/test_mcp_server.py`, `packages/emendrix-mcp/tests/test_mcp_http.py` |
| the server's `INSTRUCTIONS`, read by a calling model on `initialize` | `packages/emendrix-mcp/src/emendrix_mcp/server.py` (by hand) | `packages/emendrix-mcp/tests/test_mcp_server.py` |
| the server card at `/mcp/server-card` | `packages/emendrix-mcp/src/emendrix_mcp/card.py` (generated per request) | `packages/emendrix-mcp/tests/test_mcp_card.py`, `tests/output/test_discovery_surfaces.py` |
| the `405` pointer on `GET /mcp` | `packages/emendrix-mcp/src/emendrix_mcp/app.py` | `packages/emendrix-mcp/tests/test_mcp_http.py` |
| the version | `packages/emendrix-mcp/src/emendrix_mcp/__init__.py`, `packages/emendrix-mcp/pyproject.toml` (both by hand) | `tests/output/test_discovery_surfaces.py` |
| the MCP Registry descriptor | `packages/emendrix-mcp/server.json` (by hand) | `packages/emendrix-mcp/tests/test_mcp_registry.py`, `tests/output/test_discovery_surfaces.py` |
| the MCP section of `/api/` and of `/llms.txt` | `src/emendrix/site_/pages/api_prose.py` (`MCP`, `CLIENTS`, by hand), `src/emendrix/site_/llms.py` | `tests/site_/test_llms.py`, `tests/output/test_record_contract.py`, `tests/output/test_discovery_surfaces.py` |
| the home page's sentence and `api-catalog` link | `src/emendrix/site_/pages/home.py` | `tests/site_/test_wellknown.py` |
| `/.well-known/api-catalog` and `/.well-known/ai-catalog.json` | `src/emendrix/site_/wellknown.py` | `tests/site_/test_wellknown.py`, `tests/output/test_discovery_surfaces.py` |
| the web server's routes and headers | `deploy/default.conf` (by hand; the hosted instance serves its own copy, kept in the deployment's repository) | `tests/site_/test_api_deploy.py`, `tests/output/test_discovery_surfaces.py` |
| the "MCP server" section of the API reference and its tool table | `docs/api.md` (by hand) | `tests/output/test_record_contract.py` |
| the member's README | `packages/emendrix-mcp/README.md` (by hand) | nothing |
| this document | `docs/mcp-discovery.md` (by hand) | `tests/output/test_discovery_surfaces.py`, which checks every path in this table's middle and right columns exists |

The card states no tool list, and nothing else that is generated restates one: the tool list
lives in `server.py` and is repeated only in the two hand-kept places the contract tests read,
the table in `docs/api.md` and the tool sentence in `api_prose.py`.

## When you change the MCP server, amend these

**Adding, renaming or removing a tool or resource.**

- the registration in `server.py` and its entry in `TOOLS` (resources in `resources.py`);
- the tool table under "MCP server" in [`./api.md`](./api.md), in registration order;
- `MCP` in `src/emendrix/site_/pages/api_prose.py`: the sentence running from "eight tools are"
  to "four resources" is split on by tests, so keep both phrases and fix the counts in words;
- `INSTRUCTIONS` in `server.py`, if it names the tool;
- the member's README, if it names the tool;
- not the card: it lists no tools, on purpose;
- the version (below).

**Changing the endpoint path.** `MCP_PATH` in `packages/emendrix-mcp/src/emendrix_mcp/settings.py`
moves the card path with it. Then: `deploy/default.conf` (both exact locations) and the hosted
copy of it; `CARD_PATH` and the `mcp` address in `src/emendrix/site_/wellknown.py`; the endpoint
`_mcp` builds in `src/emendrix/site_/llms.py` and the one the `/api/` page fills `CLIENTS` with;
the `/mcp` and `/mcp/server-card` the `MCP` prose names; `server.json`'s remote URL; and every
address in [`./api.md`](./api.md).

**Releasing a new version.** `__version__` in `packages/emendrix-mcp/src/emendrix_mcp/__init__.py`,
`version` in `packages/emendrix-mcp/pyproject.toml` and `version` in
`packages/emendrix-mcp/server.json`, together. Then publish the registry entry again, which is a
person's step (`mcp-publisher publish` from the member's directory, after `mcp-publisher login`).

**Changing the host or the namespace.** The card derives its `name` from the `Host` the request
named (`emendrix.eu` gives `eu.emendrix/emendrix`), so a new host changes the card by itself.
`server.json`'s `name` and remote URL do not change by themselves, and the registry verifies the
namespace against the domain, so a new domain needs a new verification (a DNS TXT record on the
apex, or a file at `/.well-known/mcp-registry-auth`) before it can be published under.

**Removing a `.well-known` document.** The build stops writing it, but `site build --prune` never
deletes a dot-directory, so the old file stays served until it is deleted on the host by hand.
Remove its route from `deploy/default.conf` and the hosted copy in the same change.

**Changing a route's headers.** Each of the five exact locations in `deploy/default.conf` that
declares `add_header` inherits none from the `server` or `http` level, so a header added there must
be added to each of them too. The hosted copy repeats an `http`-level set, and is mounted so that
an edit does not restart the web server: read the headers back from the edge after every change.

## Conventions relied on, with dates

Each was read on the date given; none is vendored, and no test fetches any of them.

| Convention | Status | What is relied on | Verified |
|---|---|---|---|
| MCP Server Cards, SEP-2127, https://modelcontextprotocol.io/seps/2127-mcp-server-cards | Final as a SEP; the schema lives in an experimental extension repository, not in the core specification | a card may live at any unreserved URI and `<endpoint>/server-card` is the recommended one; media type `application/mcp-server-card+json`; CORS `*` for `GET`; `Cache-Control: public, max-age=3600` and an `ETag` | 2026-10-19 |
| the server-card schema, `schema.json` and `docs/discovery.md` at https://github.com/modelcontextprotocol/experimental-ext-server-card (branch `main`) | experimental | required `$schema` (`https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json`), `description` (1 to 100 characters), `name` (`^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$`) and `version`; each remote requires `type` and `url`; tools, resources, prompts and capabilities left out on purpose | 2026-10-19 |
| RFC 9727, `api-catalog`, https://www.rfc-editor.org/rfc/rfc9727 | IETF standard (Proposed Standard) | `/.well-known/api-catalog` as an RFC 9264 linkset, `application/linkset+json`; the `api-catalog` link relation; `item`, `service-desc` and `service-doc`; the profile URI `https://www.rfc-editor.org/info/rfc9727` | 2026-10-19 |
| AI Catalog 1.0, `specification/ai-catalog.md` at https://github.com/Agent-Card/ai-catalog, commit `9316f00` | draft, from a community project | `/.well-known/ai-catalog.json`, `application/ai-catalog+json`; `specVersion` `"1.0"`, `entries` of `identifier`, `type` and `url`, optional `host` with `displayName`; entry name, description and version left out because the card carries its own | 2026-10-19 |
| llms.txt, https://llmstxt.org | informal proposal | one `#` heading, a blockquote summary, `##` sections of link lines, the last `## Optional` | undated: no reading of the proposal was recorded; the file has followed this shape since it shipped on 2026-10-08 |
| the MCP Registry's `server.json`, schema `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json` | the registry's own format, versioned by date | the newest released schema version on that date; `name`, `version`, `remotes[]` of `type` and `url` | 2026-10-19 |
| the MCP Registry's namespace verification, `docs/modelcontextprotocol-io/authentication.mdx` and `remote-servers.mdx` at https://github.com/modelcontextprotocol/registry | the registry's own rule | a reverse-DNS name is proven by a DNS TXT record on the apex, `v=MCPv1; k=ed25519; p=<base64 public key>`, with `mcp-publisher login dns`, or by the same line at `/.well-known/mcp-registry-auth` with `login http`; an Ed25519 key needs OpenSSL 3; the remote URL is not checked against the domain, and each remote URL may belong to one server name | 2026-10-19 |

**Rejected, and why.**

- `/.well-known/mcp/server-card.json` was SEP-1649's proposal, closed on 2026-01-26 and replaced
  by SEP-2127, which moved the card next to the endpoint and domain-level discovery to the AI
  Catalog. `/.well-known/mcp.json` never got past a draft. Neither is served.
- Header-based discovery of the MCP server: SEP-2127 rejects it, because a client would have to
  send a request to the endpoint before it knew what the endpoint was. The `Link` header on the
  home page points at the RFC 9727 catalog, which is defined for APIs, and not at the MCP server.
- Tools in the card: the extension leaves out tools, resources, prompts and capabilities because
  they vary at run time and are listed over the protocol itself. A card that repeated the tool
  list would be one more place for it to drift.
- A `profile` media-type parameter on `/.well-known/api-catalog`: RFC 9727 §4.2 says the response
  SHOULD carry `profile="https://www.rfc-editor.org/info/rfc9727"`. The reference web server does
  not add it; the document carries the profile as a link in its body instead. That is a deviation
  from a SHOULD, recorded here rather than hidden.

## How to re-check them

Re-read the URLs in the table above. These conventions moved twice in the nine months before
2026-10-19 (the well-known card path was proposed and withdrawn, and the card's discovery moved to
the AI Catalog) and are expected to move again. When one does, the files to adjust are the card
(`card.py`), the two catalogs (`wellknown.py`) and the routes (`deploy/default.conf`), not the
server's tools; then re-date the row here.

The live state, read from outside:

```bash
curl -sI https://emendrix.eu/ | grep -i '^link'
curl -sI https://emendrix.eu/.well-known/api-catalog | grep -iE '^(HTTP|content-type|access-control)'
curl -s  https://emendrix.eu/.well-known/api-catalog | python3 -m json.tool | head -40
curl -sI https://emendrix.eu/.well-known/ai-catalog.json | grep -iE '^(HTTP|content-type)'
curl -si -H 'Accept: application/mcp-server-card+json' https://emendrix.eu/mcp/server-card
curl -si -H 'If-None-Match: <the ETag from the line above>' https://emendrix.eu/mcp/server-card | head -5
curl -si -X OPTIONS -H 'Origin: https://example.org' -H 'Access-Control-Request-Method: GET' https://emendrix.eu/mcp/server-card | head -12
curl -s  https://emendrix.eu/api/v1/ | head -c 300
curl -si https://emendrix.eu/mcp | head -12
curl -s  -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' https://emendrix.eu/mcp | python3 -m json.tool | grep '"name"' | wc -l
```

The last line counts the registered tools; it should print the length of `TOOLS`.

## Not done on purpose

- **A head link or footer line on every page.** Only the home page and `/api/` carry a new element.
  One on every page would move every file of the site's golden tree for no route an agent does not
  already have from the home page.
- **A `Link` header on every response.** It would sit in `location /`, where nginx would then need
  the whole replicated header set repeated beside it, and it reaches no agent the home page's
  header does not.
- **A Markdown twin of each page.** The JSON API and `/llms.txt` already serve the record as data,
  so a second rendering of every page would only be a third copy to keep in step.

## Adding a surface

A new place that describes the server or the record to a machine belongs in the surfaces table
above, with the file that writes it and the test that holds it, and, if it repeats a fact another
surface states, an assertion in `tests/output/test_discovery_surfaces.py`.
