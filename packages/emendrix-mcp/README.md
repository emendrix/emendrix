# emendrix-mcp

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server over a published
emendrix changelogs repository. It hands a calling model the verified record of what changed in
which provision, with the source of every fact, and it decides nothing.

> Not legal advice: this output is machine-computed from published texts, carries no lawyer's
> review, and is engineering assistance only.

## What it is, and what it is not

It is a reader. Every fact it returns was computed by the deterministic emendrix loop and is
returned as stored: change type, location, `disputed` and its reason, the three signals'
statuses, dates and citation URLs are copied off the committed files, never paraphrased, and
every result carries the file it came from and that file's `sha256`.

It is not a second pipeline. It has no model, no diff and no classifier, it never reads law
text other than the verbatim sides a payload already stores, and it never works out a date,
a kind of change or a permalink. A page address is one the site catalogue states, or it is
reported unavailable.

It is a separate distribution in the emendrix uv workspace and does not depend on `emendrix`,
so the server cannot import the pipeline's model stage. It reads the record through
[`../emendrix-record`](../emendrix-record/README.md), the workspace member that holds the models
of every published file and the reader of them, and declares no such model of its own. Two
tests in the `emendrix` suite import both: `tests/output/test_record_contract.py` holds that
member's models, disclaimer and dispute-reason sentences to the originals, and the tools this
server registers to the ones `docs/api.md` lists, and `tests/output/test_record_fixture.py`
holds the committed fixture under `packages/emendrix-record/tests/fixtures/`, which this
server's tests read too, to what the emendrix writers produce.

## What it reads

Two locations it is given, both read-only, both read again on every call:

- the directory of a changelogs repository: `index.json` at the root, `<corpus>/<act>/index.json`
  per act, and the payloads under `<corpus>/<act>/changes/`, every path taken from the index and
  resolved under the root (one that leaves it is refused);
- optionally, the `api/v1/catalogue.json` a site build wrote, for labels, aliases, domains and
  page addresses. Without it every permalink is reported unavailable.

A payload whose bytes differ from the `sha256` its index row states is still returned, marked
as a mismatch: it means the repository is being rewritten while it is read.

There is no HTTP client, no cache and no clock: the server reads files, so it needs none.

## Where it answers

At `<site URL>/mcp`: MCP over streamable HTTP, stateless, one JSON response per request, with no
session and no stream held open, so any replica can answer any request. There is no other mode.
The path `/mcp` is fixed in the code and nothing else of the address is: the host is the
deployment's, and every page address the server returns is read from the catalogue the site
build wrote under its own `--site-url`. The hosted instance's address, the line that adds it to a
client and what each tool answers are in [`../../docs/api.md`](../../docs/api.md) §"MCP server".

A request is answered only when its `Host` is one of the configured hosts and its `Origin` is
absent or `https`; anything else is refused before the SDK sees it, and so is any method but
`POST` on `/mcp`. `GET /healthz` answers `ok` when the root index can be read, whatever the
`Host`, for a container's probes.

## Settings

Each comes from its environment variable, and a flag of the same name wins over it. A required
one that is missing stops the process with one line naming the variable and the flag, before
anything is read or bound. `--help` lists them all.

| Variable | Flag | Required | Meaning |
|---|---|---|---|
| `EMENDRIX_MCP_CHANGELOGS` | `--changelogs` | yes | the directory of a changelogs repository, read-only |
| `EMENDRIX_MCP_CATALOGUE` | `--catalogue` | no | a site build's `api/v1/catalogue.json`; without it every permalink is reported unavailable |
| `EMENDRIX_MCP_ALLOWED_HOSTS` | `--allowed-hosts` | yes | comma-separated `Host` values to answer, spaces trimmed; there is no default |
| `EMENDRIX_MCP_BIND` | `--bind` | no | the address to listen on, default `0.0.0.0` |
| `EMENDRIX_MCP_PORT` | `--port` | no | the port to listen on, default `8000` |

From a clone, over a changelogs repository and a site build of your own:

```bash
uv run python -m emendrix_mcp --changelogs <repo> --catalogue <site>/api/v1/catalogue.json \
  --allowed-hosts localhost:8000
```

The image is built from the repository root with
`docker build -f packages/emendrix-mcp/Dockerfile .`; it installs this member and its
dependencies only, runs as a non-root user and is entered as `python -m emendrix_mcp`. The
reference deployment's `mcp` service in [`../../deploy/compose.yaml`](../../deploy/compose.yaml)
runs it behind the site's nginx, with both volumes read-only.

## Layout

| Module | Holds |
|---|---|
| `emendrix_mcp/__init__.py` | `DISCLAIMER`, re-exported from `emendrix_record` |
| `emendrix_mcp/tools.py` | what every tool result shares: the sentences a caller is told, the row view |
| `emendrix_mcp/tools_read.py` | `list_acts`, `find_provisions`, `changes_since` |
| `emendrix_mcp/tools_event.py` | `provision_history`, `get_event`, `list_disputed` |
| `emendrix_mcp/tools_text.py` | `get_change`, with each verbatim side paged behind a visible marker |
| `emendrix_mcp/resources.py` | the four resources |
| `emendrix_mcp/server.py` | `build_server(record)`: the seven tools and four resources, no transport |
| `emendrix_mcp/settings.py` | `Settings`, and the fixed path `/mcp` |
| `emendrix_mcp/app.py` | `create_app` and `serve`: the HTTP app, its Host and Origin check, `/healthz` |
| `emendrix_mcp/cli.py` | the settings from the environment and the command line |
| `emendrix_mcp/__main__.py` | `python -m emendrix_mcp`, the image's entry point |

The models, `Record` and the dispute-reason sentences are in `emendrix_record`.

`tests/test_mcp_architecture.py` checks over the source that no module imports `emendrix`, an
HTTP client or a model SDK, or declares a model of a published file, reads a clock, writes a file or mentions stdio; that only `app.py`
may listen and only `cli.py` may read the environment; that no string in the source is an
address; and that every module stays under the line cap.

## The SDK it is built on

Resolved by `uv` on 2026-10-08 and read from the installed sources, not from documentation:

- `mcp` 2.2.0 (with `mcp-types` 2.2.0), capped below 2.3 because 2.3.0 requires `httpx2>=2.10`
  and would move a package the pipeline's model stage resolves; `pydantic` 2.13.4;
  `starlette` 1.7.0; `uvicorn` 0.54.0.
- Server: `mcp.server.MCPServer(name, instructions=...)`, tools registered with
  `@server.tool(description=...)` (a function returning a pydantic model publishes its schema as
  the tool's output schema), resources with `@server.resource("emendrix://...")`.
- In-process testing: `async with mcp.Client(server) as client:` then `client.list_tools()`,
  `client.call_tool(name, arguments)`, `client.list_resources()`. Result types use snake_case
  attributes (`tool.output_schema`, `result.structured_content`).
- HTTP: `server.streamable_http_app(streamable_http_path="/mcp", json_response=True,
  stateless_http=True, transport_security=TransportSecuritySettings(...))` returns a Starlette
  app for uvicorn. `mcp.server.transport_security.TransportSecuritySettings` takes
  `allowed_hosts` and `allowed_origins`, each matched exactly or by a `host:*` port wildcard; a
  missing `Origin` is accepted. It cannot express "any `https` origin", so `app.py` switches it
  off and puts a check of its own in front of the app.
- Stateless JSON mode answers a JSON-RPC POST with no `initialize` before it and no session
  header. A `GET` on the path would open an event stream, which this server never uses, so
  `app.py` answers it `405` before it reaches the SDK.
