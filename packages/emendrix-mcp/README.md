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
so the server cannot import the pipeline's model stage. Two tests in the `emendrix` suite
import both: `tests/output/test_mcp_contract.py` holds this package's models, disclaimer and
dispute-reason sentences to the originals, and `tests/output/test_mcp_fixture.py` holds the
committed fixture under `tests/fixtures/` to what the emendrix writers produce.

## What it reads

Two locations it is given, both read-only, both read again on every call:

- the directory of a changelogs repository: `index.json` at the root, `<corpus>/<act>/index.json`
  per act, and the payloads under `<corpus>/<act>/changes/`, every path taken from the index and
  resolved under the root (one that leaves it is refused);
- optionally, the `api/v1/catalogue.json` a site build wrote, for labels, aliases, domains and
  page addresses. Without it every permalink is reported unavailable.

A payload whose bytes differ from the `sha256` its index row states is still returned, marked
as a mismatch: it means the repository is being rewritten while it is read.

There is no HTTP client, no cache and no clock: the server reads files, so it needs none. It is
served over streamable HTTP only; there is no stdio mode.

## Layout

| Module | Holds |
|---|---|
| `emendrix_mcp/__init__.py` | `DISCLAIMER`, the same sentence as the pipeline's |
| `emendrix_mcp/models.py` | the root index, an act index and the catalogue |
| `emendrix_mcp/payload.py` | one payload: the event, its changes, its corroboration |
| `emendrix_mcp/reasons.py` | `REASON_SENTENCES`, one sentence per `dispute_reason` code |
| `emendrix_mcp/reads.py` | what a read returns: `PayloadRead`, `ChangeRead`, `Unavailable` |
| `emendrix_mcp/record.py` | `Record`, which reads all of the above off disk |

`tests/test_mcp_architecture.py` checks over the source that no module imports `emendrix`, an
HTTP client or a model SDK, reads a clock, writes a file or mentions stdio; that only `app.py`
may listen and only `cli.py` may read the environment; and that every module stays under the
line cap.

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
  missing `Origin` is accepted. It cannot express "any `https` origin", so a policy of that shape
  needs a check of its own in front of the app.
