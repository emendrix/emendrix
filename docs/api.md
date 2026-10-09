# The JSON API

Not legal advice: this output is machine-computed from published texts, carries no lawyer's review, and is engineering assistance only.

The record emendrix publishes, as files a program can fetch: what the API is, where each file
lives, what every date, signal and dispute reason means, how a correction shows, how often to
poll, what the API is not, how to watch one provision from CI, and the MCP server that hands the
same record to a model. A model can start at `/llms.txt`, which names these files and the MCP
server in plain Markdown. The documents themselves are
described in [`./output-format.md`](./output-format.md); this page is about reading them over
HTTP. Every address below is the hosted instance's, `https://emendrix.eu/api/v1/`; a
self-hosted site serves the same layout under its own address.

## What it is

A static tree of JSON files and nothing else. There is no query endpoint, no account and no key:
every answer is a file, and the same files are in a clone of the changelogs repository
(`https://github.com/emendrix/changelogs`) at the same relative paths. A program can therefore be
written against either and moved between them by changing one base address.

Reading starts at the root index, which names every act with at least one event and the path of
its act index. An act index lists every event of that act and, per provision, every change it
went through, without any text. A change's verbatim text, its explanation and its citations are
in the event's payload, which the act index names by `path`.

## Layout

| Path | What it is | Where it comes from |
|---|---|---|
| `/api/` | this page as part of the site, with the CI snippet at `#watch-in-ci` | the site build |
| `/api/v1/index.json` | the root index: one row per act | the record, served as committed |
| `/api/v1/<act_dir>/index.json` | one act's index: its events, and every change per provision | the record, served as committed |
| `/api/v1/<act_dir>/changes/<version>.json` | one event's payload, with the verbatim texts and the explanations | the record, served as committed |
| `/api/v1/catalogue.json` | what the record cannot know: watchlist labels, aliases, sectors, page and feed addresses, and what the poller is waiting for | the site build |
| `/api/v1/schema/<name>.schema.json` | the JSON Schema of each document: `index`, `act-index`, `entry`, `change`, `catalogue` | the site build |

`<act_dir>` is the act's corpus and key, `eu/32017R0745` for the Medical Devices Regulation, and
`<version>` is the version the event produced, `02017R0745-20260101` for one of its events. Every
`path` and `index` field in an index is relative to the root, so it resolves against
`https://emendrix.eu/api/v1/` and against a clone alike. The three files the record holds are the
committed bytes, unaltered, which is why an index's `sha256` of a payload can be checked against
the file a consumer downloads. Nothing else is served under `/api/v1/`: there is no file per
change, and a path not in this table is not part of the API.

The schemas are generated from the models that write the documents, and the ones for the record
are committed in this repository under [`./schema/`](./schema/). Each declares JSON Schema
2020-12 and carries its own file name as a relative `$id`, so the same bytes resolve correctly
wherever they are served. A schema describes a document as the current model writes it. A
payload committed earlier can lack a field added since with a default, which a schema treats as
optional, and one field the schemas mark as always present, the read-only `dispute_reason` (see
below); a validator run over an older payload's raw bytes refuses it on that field alone.

## The three dates

- **`detected_on`** is the date the watcher saw the consolidated version, which is the date of
  the run that wrote the event. It says when this record learnt of the change, not when the law
  moved, and a repair never changes it.
- **`in_force`** is the start of validity CELLAR publishes for the consolidated version. On an
  event it is the tuple of the dates the changes report, usually exactly one; on a change it is
  one date or null.
- **`applies_from`** is a date only when one is deterministically readable from a date change in
  the act's own application provision. Otherwise it is `unknown`, which is the common and honest
  answer, or `unchanged`, when the change does not move the date. It is never a deadline and it
  never says whether a provision applies to you. In a payload the two non-dates are objects with
  a `kind` (`{"kind": "unknown", ...}`); in an index row they are flattened to the strings.

`updated_on` on an event is the latest of `detected_on` and every repair's date, so it is the
field to sort by when the question is "what moved since I last looked".

## Disputed changes, signals and reasons

Three signals look at every transition: the structural diff of the two consolidated texts
(`structural_diff`), CELLAR's modification metadata (`corpus_metadata`) and the parse of the
amending act's instructions (`instruction_parse`). Each reports one status per change:

- `observed`: the signal names this unit;
- `absent`: the signal could speak about this window and does not name this unit;
- `unavailable`: the signal could not speak about this window at all, for example no metadata was
  published for it or no instruction was parsed. It is not dissent and never makes a dispute.

A change is `disputed` when one signal observed it and another is absent, or when the signals
that observed it name kinds of change that share nothing. Every disputed change
carries a `dispute_reason` saying which signal disagreed and how, and every undisputed change
carries `null`. The codes are evaluated in this order and the first that applies wins:

| Code | When |
|---|---|
| `kind_mismatch` | no applicable signal is absent, and the kinds the observing signals name share nothing |
| `textless_both_others` | the structural diff is absent; the metadata and the instruction parse both observed the unit |
| `textless_metadata_only` | the structural diff is absent; the metadata observed it; the instruction parse is absent or unavailable |
| `textless_instruction_only` | the structural diff is absent; only the instruction parse observed it |
| `both_others_silent` | the structural diff observed it; the metadata and the instruction parse are both absent |
| `metadata_silent` | the metadata is absent; the instruction parse observed it or is unavailable |
| `instruction_silent` | the instruction parse is absent; the metadata observed it or is unavailable |

The three `textless_` codes are changes with no text on either side, since the structural diff is
the only signal that carries any. `textless_instruction_only` is not produced by a current run and
is kept so an older document read again still gets a code. A reason is a reading of stored
verdicts and says nothing about the law. The site's
[methodology page](https://emendrix.eu/methodology/) explains each signal and what the disputed
rate does and does not measure.

**`dispute_reason` is present on every row of an act index and on every change read through the
`change` schema, whether or not an older payload stored the key.** It is computed from the
change's own `signals` and was not written into payloads before 2026-10-08, so a reader of an
older payload's raw bytes finds no key; the index is built by reading every payload through the
model and always carries it. The disputed flag alone mixes very different situations, a change
with no text at all and a change the diff saw that the metadata did not annotate, so **filter on
the reason or on the signal triple, never on `disputed` alone**.

## Units no change carries

An event row carries two lists, both canonical location strings and both empty when the event has
none:

- `metadata_only_units`: units the corpus metadata names that no change of the event carries;
- `instruction_only_units`: units only the instruction parse names.

They are published by name so that no signal's claim is silently dropped, and they are never
appended as changes: a unit with no text and one signal behind it is a claim to look at, not a
change to act on. Both are copied from the payload's `corroboration` report, never recomputed.

## The catalogue

`catalogue.json` is written by the site build, not by the record, and says what the record
cannot know: each watched act's labels, aliases and sector, and the address of every page and
feed the build wrote for it. Watched acts nothing has happened to are listed too, with no events
and no provisions. Since `catalogue_schema` `1.1` it also carries the poller's own record as it
stood when the site was built, when the deployment handed the build that record:

- `checked_through`, at the root: the end of the last window the poller read, as a date. Changes
  published up to that day were looked for. It is a cursor, not the moment the poller ran, and
  it is `null` when the build was handed no record or the poller has never closed a window.
- `waiting`, on each act: the consolidations announced for that act whose text cannot be read
  yet, oldest first. Each has a `version` (`null` when the announcement named none yet), a
  `state` (`consolidation_pending` while the text is not published, `english_unavailable` when
  no English text is offered) and a `first_seen` date. It is empty when nothing waits.

Together they tell a quiet act from one that is waiting: an act with no new event and an empty
`waiting` was read through `checked_through` and nothing was announced for it. `1.1` is additive:
a reader of `1.0` that ignores unknown keys reads it unchanged, and a `1.0` file has neither
field.

## Corrections

The record is corrected forward and its history is never rewritten. What a consumer sees, and the
rule for caching rows, is stated once in [`./output-format.md`](./output-format.md) §"The index".
In short: a repaired event gets a new `sha256`, a later `updated_on` and one more `repairs` row,
whose `kind` is free text (for example `corroboration`, `signals` or `evidence`); a change a
repair withdraws disappears from `provisions`, and the git history of the changelogs repository
is the record of what was there. A consumer that caches rows keys them on
`(act, version, location, occurrence)` and re-reads an event whenever its `sha256` moves.

## Versioning

`v1` stays frozen as long as the index and the payloads stay compatible, by the rule the payloads
already follow: a field added with a default is not a bump; a field removed, renamed or re-meant
is. A breaking change ships beside `v1`, not over it, and `v1` keeps being written for an
announced period stated here with its end date.

Every file carries its own version, so a reader can refuse what it does not know. Both index
levels carry `index_schema`, `1.0` today, and the catalogue carries `catalogue_schema`, `1.1`
since 2026-10-09, when the two poller fields above were added beside every `1.0` field. Each payload carries `schema_version`, and each event
row repeats it: the hosted record holds payloads at `1.0` and at `1.2`, and a reader meets both.
What each version means is in [`./output-format.md`](./output-format.md) §"The JSON".

## Caching and polling

Every file is served with a ten-minute lifetime, at the origin and at the edge. Poll the root
index at most every ten minutes; the record moves at most about once an hour. Decide what to
re-fetch from the hashes rather than by downloading everything:

- an act's `index_sha256` in the root index moves exactly when its act index's bytes move;
- an event's `sha256` in the act index moves exactly when its payload's bytes move.

A payload's bytes do not change unless the event is repaired, so a consumer holding one whose
`sha256` still matches has nothing to fetch.

## CORS, keys and limits

Any origin may `GET` any file. There are no credentials, no keys and no cookies, and there is no
rate promise: a client that polls more often than above gets the same bytes and gains
nothing.

## Licence

On the hosted instance the licence is the changelogs repository's: its `LICENSE` puts the
computed data under CC BY 4.0, and the legislative text it quotes is reused under the EU reuse
decision its `LICENCE-NOTICE.md` states. A self-hosted installation publishes its own record and
sets its own licence.

## What it is not

It is not legal advice and not a legal database: the record covers only the acts its watchlist
names. It is not a search service, a notification service or a
source of law: the authoritative text is the one EUR-Lex publishes, and every citation in a
payload links there. It decides nothing about whether a change applies to you.

## Serving it yourself

The reference deployment in [`../deploy/`](../deploy/) serves the API from two places and copies
neither. `emendrix site build` writes `/api/`, `catalogue.json` and the schemas into the site tree.
The root index, the act indexes and the payloads are served by nginx straight from the changelogs
volume, mounted read-only into the web container, through one `location` in
[`../deploy/default.conf`](../deploy/default.conf) whose pattern admits those three kinds of file
and nothing else in the repository: no `.git`, no `CHANGELOG.md`, no directory listing. The hourly
site build therefore rewrites nothing of the record, and a payload is served as soon as the poller
has committed it. A site served without that location still has its catalogue and schemas and
answers the record's paths with a 404, never with a stale copy, because the build writes none of
the record into the site.

Both API locations set `Access-Control-Allow-Origin: *` and `X-Content-Type-Options: nosniff`.
An `add_header` in an nginx `location` replaces every header inherited from the `server` and
`http` blocks rather than adding to them, so a deployment that sets security or caching headers at
those levels must repeat them inside both locations, or the API answers without them. A plain
`GET` is a CORS simple request, so there is no preflight to handle. The file is the pinned image's
own `default.conf` with those locations added; when the image digest moves, read the new image's
file and carry the additions onto it.

## Examples

`curl` and `jq` are all three need.

Every act, with its newest version, its counts and its title:

```bash
curl -fsSL https://emendrix.eu/api/v1/index.json \
  | jq -r '.acts[] | [.key, .newest_version, .changes, .disputed, .title] | @tsv'
```

The newest change to Annex I of the Medical Devices Regulation:

```bash
curl -fsSL https://emendrix.eu/api/v1/eu/32017R0745/index.json \
  | jq '.provisions["AN I"][0]'
```

Every disputed change of one act, grouped by its reason:

```bash
curl -fsSL https://emendrix.eu/api/v1/eu/32017R0745/index.json \
  | jq '[.provisions | to_entries[] | .key as $loc | .value[] | select(.disputed)
         | {location: $loc, version, dispute_reason, signals}]
        | group_by(.dispute_reason)
        | map({dispute_reason: .[0].dispute_reason, count: length, changes: .})'
```

## Watch a provision from CI

A GitHub Actions workflow that opens an issue when a provision you pin has a newer change. It is
an example to adapt rather than a maintained action: set `PIN` to the act and the canonical
location, and `SEEN` to the version you have already reviewed. It needs no secret beyond the job's
own token, it dedupes by issue title so `SEEN` is only the starting point, and it uses `jq` and
`gh`, which GitHub-hosted runners have preinstalled.

```yaml
# .github/workflows/regulations.yml: opens an issue when a provision you pin changes.
on:
  schedule: [{ cron: "17 6 * * 1" }]
  workflow_dispatch: {}
permissions: { issues: write }
jobs:
  check:
    runs-on: ubuntu-latest
    env:
      PIN: "32017R0745 AN I"
      SEEN: "02017R0745-20260101"
      GH_TOKEN: ${{ github.token }}
      GH_REPO: ${{ github.repository }}
    steps:
      - run: |
          act=${PIN%% *}; loc=${PIN#* }
          slug=$(printf '%s' "$loc" | tr 'A-Z ' 'a-z-' | tr -d '()')
          curl -fsSL -A "emendrix-snippet/1" "https://emendrix.eu/api/v1/eu/$act/index.json" -o idx.json
          new=$(jq -r --arg l "$loc" '.provisions[$l][0].version // empty' idx.json)
          if [ -z "$new" ] || [ "$new" = "$SEEN" ]; then exit 0; fi
          title="$act $loc changed: $new"
          gh issue list --state all --search "\"$title\" in:title" --json title -q '.[].title' \
            | grep -qxF "$title" && exit 0
          row=$(jq -c --arg l "$loc" '.provisions[$l][0]' idx.json)
          gh issue create --title "$title" --body "$(printf '%s\n\n%s\n\n%s' \
            "Newest index row: $row" \
            "History, verbatim text and citations: https://emendrix.eu/acts/$act/$slug/" \
            "Not legal advice: computed by emendrix from published texts, with no lawyer's review.")"
```

The `-A "emendrix-snippet/1"` user agent is there so the snippet's use can be counted from the
server's own request lines, without cookies or any tracking; change it if you would rather not be
counted.

## MCP server

The same record, for a model: a read-only [Model Context Protocol](https://modelcontextprotocol.io)
server at `https://emendrix.eu/mcp`. It answers MCP over streamable HTTP, stateless, with one
JSON response per request: no session, no stream held open, no `initialize` it needs first. There
is no key and no account; any rate limit is applied at the edge, in front of the server. Its
source is the workspace member [`../packages/emendrix-mcp/`](../packages/emendrix-mcp/). It reads
the record through [`../packages/emendrix-record/`](../packages/emendrix-record/), the same reader
any Python consumer can use: the models of the files above and a reader that reads them fresh on
every call.

In Claude Code:

```bash
claude mcp add --transport http emendrix https://emendrix.eu/mcp
```

A client configured by a JSON file takes the same address, in the shape most of them read:

```json
{
  "mcpServers": {
    "emendrix": {
      "type": "http",
      "url": "https://emendrix.eu/mcp"
    }
  }
}
```

A connector form that asks only for a URL, with no key and no header, needs nothing else: give it
`https://emendrix.eu/mcp`.

Seven tools, every one read-only:

| Tool | Answers |
|---|---|
| `list_acts` | the acts the record holds, with their labels, aliases, sector, newest version and counts |
| `find_provisions` | the touched provisions of one act whose location or stored heading contains a string |
| `changes_since` | recorded changes on or after a date, by `updated_on`, `detected_on` or `in_force` |
| `provision_history` | every recorded change to one top-level provision, newest first |
| `get_change` | one change in full: the verbatim texts, paged behind a visible marker, its citations, signals and dates |
| `get_event` | one event of one act: its counts, repairs, stored corroboration and every row |
| `list_disputed` | disputed changes grouped by `dispute_reason`, with the sentence the site prints for each |

Four resources, each the JSON of the tool result that answers the same question:
`emendrix://acts`, `emendrix://acts/{act}`, `emendrix://changes/{act}/{version}/{location}` and
`emendrix://methodology`.

Every result carries the disclaimer and the file each fact was read from, with that file's
`sha256`, so an answer can be checked against the files above. Every fact is returned as stored.
A page address is one the site's `catalogue.json` states, or the result says it is unavailable.

**What it will not do.** It gives no legal advice and decides nothing: it never works out whether,
where or how something changed, never infers a date, and has no model, no diff and no classifier.
It does not read or interpret law, cannot search law text, and cannot resolve a free reference
such as "Art. 50(2)": an act is named by its key and a provision by its canonical location string,
as `list_acts` and `find_provisions` give them. It covers only the acts the record holds, and an
empty answer means nothing was recorded in the window the record covers, not that nothing happened.

### Running it yourself

The server reads two things, both read-only: the directory of a changelogs repository and,
optionally, the `api/v1/catalogue.json` a site build wrote. It is configured only through its
environment, and each variable has a flag of the same name that wins over it:

| Variable | Flag | Required | Meaning |
|---|---|---|---|
| `EMENDRIX_MCP_CHANGELOGS` | `--changelogs` | yes | the directory of a changelogs repository |
| `EMENDRIX_MCP_CATALOGUE` | `--catalogue` | no | a site build's `api/v1/catalogue.json`; without it every permalink is reported unavailable |
| `EMENDRIX_MCP_ALLOWED_HOSTS` | `--allowed-hosts` | yes | comma-separated `Host` values to answer, such as `mcp.example.org,localhost:8080`; there is no default |
| `EMENDRIX_MCP_BIND` | `--bind` | no | the address to listen on, default `0.0.0.0` |
| `EMENDRIX_MCP_PORT` | `--port` | no | the port to listen on, default `8000` |

A request whose `Host` is not one of the allowed hosts is refused, and so is one whose `Origin` is
anything but absent or `https`: the endpoint has nothing a cross-origin page could act on, and the
check refuses the shapes DNS rebinding takes. `GET /healthz` answers `ok` when the root index can
be read, for a container's probes.

The reference deployment runs it as the `mcp` service of
[`../deploy/compose.yaml`](../deploy/compose.yaml), behind the `location = /mcp` block of
[`../deploy/default.conf`](../deploy/default.conf), with the changelogs and site volumes mounted
read-only and no port of its own. Copy
`deploy/.env.example` to `deploy/.env` and set `EMENDRIX_PUBLIC_HOST`, the one variable that names
the deployment's host for the site's links and for the hosts the server answers, then
`docker compose up -d web mcp`. The endpoint is then `<your site URL>/mcp`. Its image is built
from [`../packages/emendrix-mcp/Dockerfile`](../packages/emendrix-mcp/Dockerfile) and carries the
server and its dependencies only, not the pipeline.

Not legal advice: this output is machine-computed from published texts, carries no lawyer's review, and is engineering assistance only.
