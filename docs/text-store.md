# The text store

`emendrix texts` keeps the verbatim text of every provision of every stored version of every
watched act, one file per version, in a directory **beside** the changelogs repository. It is
there for computation: anything that needs the whole text of a version, not just the provisions
an event touched, reads it from here instead of fetching and parsing the package again.

What it is **not**:

- **Not published.** No page, feed, sitemap, API file or bulk download carries this text, and
  the reference deployment mounts the store into no web-facing service. EU legislative text is
  reusable under Commission Decision 2011/833/EU; keeping it unpublished is a product choice,
  not a legal constraint. The changelogs quote the provisions an event changed, under the caps
  [`output-format.md`](./output-format.md) states, and that is the only text emendrix publishes.
- **Not a source of truth.** CELLAR is. Every file is rebuilt from the corpus by
  `emendrix texts build --rebuild`, so losing the store costs a rebuild and nothing else.
- **Not part of the loop.** No stage of `WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE →
  EMIT` reads it, and `emendrix run` behaves the same with or without it.

## Layout

```
<store>/.emendrix-texts                           the marker: a directory emendrix created
<store>/<corpus>/<slug(key)>/<slug(version)>.jsonl.gz
<store>/<corpus>/<slug(key)>/states.json          versions the corpus answered with a state
```

`slug` is the same path-segment rule the changelogs repository uses; an EU act key and version
are already in its alphabet, so `eu/32017R0745/02017R0745-20250110.jsonl.gz` is what lands.

A version file is gzipped JSON lines. The first line is the header; every following line is
one node of the provision tree, in document pre-order (a parent always comes before its
children).

| Header field | Meaning |
|---|---|
| `store_schema` | `"1.0"`, the layout this file was written in |
| `corpus`, `key` | the act, as the adapter identifies it: `"eu"`, `"32017R0745"` |
| `version` | the version asked for, which also names the file |
| `served_version` | the version the adapter actually served; differs when it fell back to the Official Journal text for a consolidation with no English text of its own |
| `language` | the language of the text, as the tree states it |
| `nodes`, `units` | how many node lines follow, and how many of them are top-level units |

| Node field | Meaning |
|---|---|
| `location` | the canonical location code, `"AR 10 PA 9"` |
| `parent` | the canonical location of the parent node; `null` for a top-level unit |
| `heading` | the provision's heading, verbatim, or `null` |
| `text` | the provision's text, verbatim, and its **whole subtree**: a paragraph's text repeats inside its article's |
| `comparison_text` | the whitespace-normalised form the structural diff compares |
| `digest` | sha256 hex of `comparison_text` in UTF-8 |

Each version file is self-contained: identical texts are not pooled across versions, so one
file can be read, checked and replaced alone. `digest` is what lets a reader deduplicate.
Dates found in the text and table rows are not stored; a reader gets a tree with neither, and
the store is rebuildable when something needs them.

## What the bytes promise

- **Byte-stable.** Each line is the model's JSON in field declaration order plus `\n`, and the
  file is gzip at level 9 with a zero `mtime` and no file name in its header. Writing one
  version twice gives the same bytes.
- **Immutable.** A consolidated package is the same bytes forever, so a file that exists is
  never rewritten, except by `texts build --rebuild`.
- **Never half-written.** Every file is written to a temporary file in the same directory and
  moved into place.
- **Never a crash on read.** A file that does not decompress, does not validate, disagrees with
  its own header or does not rebuild into a tree reads as the state `unreadable`, with the
  reason. Rebuild it with `--rebuild`.

## `states.json`

A version the corpus answers with a first-class state instead of a text
(`consolidation_pending`, `english_unavailable`, `structured_text_unavailable`) is recorded here
and counted in the build summary:

```json
{
  "store_schema": "1.0",
  "states": [
    {"version": "02006R1907-20150513", "state": "structured_text_unavailable", "detail": "..."}
  ]
}
```

Sorted by version and rewritten only when its bytes change. A recorded version is asked again
on every build, because a pending consolidation resolves and a missing language can appear;
once its text is stored, its state is dropped. A fetch that **raises** (an unexpected HTTP
status, a fixture set lacking the document, a source that never answered) is not an answer the
corpus gave: it is counted as `fetch_failed` in the summary, written nowhere, and retried by
the next run.

## Where the store lives

Three sources, one order, the same as the output repository's:

| Source | Form | Wins over |
|---|---|---|
| Flag | `--text-store ~/emendrix-texts` | everything |
| Environment | `EMENDRIX_TEXT_STORE=~/emendrix-texts` | the file |
| File | `[output] text_store_path = "~/emendrix-texts"` in `watchlist.toml` | — |

There is no default. With none of the three, `texts build` exits with status 2 and says so. A
path inside any git working tree is refused with status 2, and so is a non-empty directory that
does not carry the `.emendrix-texts` marker: the store is never inside the changelogs
repository, so no commit there can ever publish it.

## Commands

```bash
# Every watched act, offline, over the pinned fixtures (what the tests do)
uv run emendrix texts build --fixture-dir tests/fixtures/eu --text-store ~/emendrix-texts

# One act, from the disk cache and the network, a few files at a time
uv run emendrix texts build --act 32017R0745 --limit 3 --text-store ~/emendrix-texts

# What a build would fetch, without fetching any text or writing anything
uv run emendrix texts build --dry-run --text-store ~/emendrix-texts

# A stored version's header and unit list, then one node's text, verbatim
uv run emendrix texts show 32017R0745 02017R0745-20250110 --text-store ~/emendrix-texts
uv run emendrix texts show 32017R0745 02017R0745-20250110 "AR 10 PA 9" --text-store ~/emendrix-texts
```

`build` lists each act's versions through the adapter, oldest first, and for each one the store
lacks fetches and parses it and writes its file, or records the state. A second run over an
unchanged listing writes nothing and says so. `--limit N` stops after N files written;
`--rebuild` fetches and writes stored versions again; `--observed-on` is the date the states
are stamped with (today, UTC, by default); `--summary json` puts the summary on stderr as one
JSON line for a log collector. The exit status is 0 whenever the run completes: states and
failures are in the summary, not in the status.

The summary's first line says what was read. **Offline means `--fixture-dir`.** Without it the
build reads the disk cache, which re-fetches any tree notice older than its six-hour life
(`EMENDRIX_NOTICE_MAX_AGE_S`): correct in production, where a notice is the listing that says a
new version exists, and slow on a laptop whose cache is days old. A version package is never
re-fetched once cached.

`show` is an operator's inspection tool and no published surface reads it. Its unit list and the
node text go to stdout, the not-legal-advice line to stderr, so the text form prints exactly
the stored text.

## Self-hosting

`deploy/compose.yaml` gives the store its own named volume, `texts`, mounted at `/work/texts` on
a one-shot `texts` service that runs `texts build --summary json` after the poller, reading the
poller's response cache. The volume is mounted on no other service, and in particular never on
the web server.

**Not legal advice.** emendrix produces engineering assistance: a machine-computed description of
textual differences between published versions of legal acts. Nothing in the store, and nothing
the tool emits, is a substitute for reading the official consolidated text on
[EUR-Lex](https://eur-lex.europa.eu/) or for professional legal counsel.
