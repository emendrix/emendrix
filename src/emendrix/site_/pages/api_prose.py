"""The words of the `/api/` page, kept apart from the code that lays them out.

The page is mostly prose: what the fields mean, how corrections show and how to poll, the CI
example and the MCP section are sentences a reviewer reads as text, while `api_page.py` turns
them into markup, links the files a build writes and fills in the deployment's own address.
Splitting along that line keeps a change of wording out of the layout code and a change of
layout out of the wording. Prose is written in the small format `api_page._prose` reads:
`## <id> <heading>`, `- ` items, a block indented four spaces, or a paragraph.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "AGENT",
    "CI",
    "CLIENTS",
    "FIELDS",
    "LEDE",
    "MCP",
    "NO_ENDPOINT",
    "RECORD",
    "SNIPPET_TEMPLATE",
    "UNCONFIGURED",
]

SNIPPET_TEMPLATE: Final = """\
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
          curl -fsSL -A "emendrix-snippet/1" "{base}/api/v1/eu/$act/index.json" -o idx.json
          new=$(jq -r --arg l "$loc" '.provisions[$l][0].version // empty' idx.json)
          if [ -z "$new" ] || [ "$new" = "$SEEN" ]; then exit 0; fi
          title="$act $loc changed: $new"
          gh issue list --state all --search "\\"$title\\" in:title" --json title -q '.[].title' \\
            | grep -qxF "$title" && exit 0
          row=$(jq -c --arg l "$loc" '.provisions[$l][0]' idx.json)
          gh issue create --title "$title" --body "$(printf '%s\\n\\n%s\\n\\n%s' \\
            "Newest index row: $row" \\
            "History, verbatim text and citations: {base}/acts/$act/$slug/" \\
            "Not legal advice: computed by emendrix from published texts, \
with no lawyer's review.")"
"""
"""`{base}` is filled by `.replace`: the YAML's own braces would trip `str.format`."""

LEDE: Final = (
    "The record this site renders, as files a program can fetch. There is no query endpoint, "
    "no account and no key: every answer is a file, and the record's files are the committed "
    "bytes of the changelogs repository, at the same relative paths as in a clone of it."
)

UNCONFIGURED: Final = (
    "The API's absolute addresses are not known for this build, because no site URL was "
    "configured. The paths below are relative to wherever the site is served, and the examples "
    "use the hosted instance's address as an example."
)

FIELDS: Final = """
## dates The three dates

- `detected_on` is the date the watcher saw the consolidated version: when this record learnt
of the change, not when the law moved. A repair never changes it.
- `in_force` is the start of validity the publisher states for the consolidated version: on a
version's row the dates its changes report, on a change one date or null.
- `applies_from` is a date only when one is deterministically readable from a date change in the
act's own application provision; otherwise `unknown`, the common and honest answer, or
`unchanged`. It is never a deadline and never says whether a provision applies to you.

`updated_on` on a version's row is the latest of `detected_on` and every repair's date, the
field to sort by to see what moved since you last looked.

## disputed Where the sources differ: signals and reasons

Three signals look at every transition: `structural_diff`, `corpus_metadata` and
`instruction_parse`. Each reports one status per change:

- `observed`: the signal names this unit.
- `absent`: the signal could speak about this window and does not name this unit.
- `unavailable`: the signal could not speak about this window at all. It is not dissent and
never makes a dispute.

A change is `disputed` when one signal observed it and another is absent, or when the signals
that observed it name kinds of change that share nothing. Each such change carries a
`dispute_reason`, every other change carries null, and every row of an act index carries the
field whether or not an older payload stored it. Filter on the reason or on the signal triple,
never on `disputed` alone. The seven reasons, in the order they are tried:
"""

RECORD: Final = """
## units Units no change carries

- `metadata_only_units`, on each row of `events`: units the corpus metadata names that no
change of that version carries.
- `instruction_only_units`, on each row of `events`: units only the instruction parse names.

## corrections Corrections

The record is corrected forward and its history is never rewritten. A repaired version gets a new
`sha256`, a later `updated_on` and one more `repairs` row; a change a repair withdraws disappears
from `provisions`. Key cached rows on `(act, version, location, occurrence)` and re-read a version
whenever its `sha256` moves.

## polling Polling, CORS and keys

Poll the root index, never the whole tree. An act's `index_sha256` moves exactly when its act
index's bytes move, and a version's `sha256` exactly when its payload's do, so a consumer holding
a file whose hash still matches has nothing to fetch.

Any origin may `GET` any file. There are no credentials, no keys and no cookies, and no rate
promise: a client that polls more often than the record is written gets the same bytes and gains
nothing.
"""

CI: Final = """
A GitHub Actions workflow that opens an issue when a provision you pin has a newer change. It is
an example to adapt rather than a maintained action: set `PIN` to the act and the canonical
location, and `SEEN` to the version you have already reviewed. It needs no secret beyond the
job's own token and dedupes by issue title. It uses `jq` and `gh`, which GitHub-hosted runners
have preinstalled.
"""

MCP: Final = """
## mcp The MCP server

The same record, for a model: a read-only MCP server at `/mcp`, answering streamable HTTP with one
JSON response per request, with no session, no key and no account. Its seven tools are
`list_acts`, `find_provisions`, `changes_since`, `provision_history`, `get_change`, `get_event`
and `list_disputed`, and its four resources `emendrix://acts`, `emendrix://acts/{act}`,
`emendrix://changes/{act}/{version}/{location}` and `emendrix://methodology`. Every result carries
the disclaimer and the file each fact was read from, with that file's `sha256`.

It decides nothing: it does not read or interpret law, cannot search law text and cannot resolve
a free reference such as `Art. 50(2)`. Name an act by its key and a provision by its canonical
location, as `list_acts` and `find_provisions` give them.
"""

CLIENTS: Final = """
A client that takes a URL needs only `{endpoint}`. In Claude Code:

    claude mcp add --transport http emendrix {endpoint}

In a client configured by a JSON file:

{config}
"""

NO_ENDPOINT: Final = (
    "The MCP endpoint's address is not known for this build, because no site URL was "
    "configured. Where a deployment runs the server, it answers at /mcp under wherever the "
    "site is served."
)

AGENT: Final = """
The `emendrix-snippet/1` user agent lets the example's use be counted from the server's own
request lines, with no cookies and no tracking; change it if you would rather not be counted.
"""
