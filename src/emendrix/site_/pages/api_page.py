"""The page about the JSON API: where each file lives, what its fields mean, and a CI example.

What a reader of the site needs from the API's reference document, and nothing about any act.
The `curl` examples name the first act and provision this build holds a change to, so a command
copied off the page answers on the deployment it was copied from. Absolute addresses are the
deployment's `--site-url`; without one the page says so, as the feeds page does, and its
examples use the hosted instance's address, read from the package's own `Homepage` because it
is configuration a fork changes. The workflow is published here and in the API's reference
document, and a test holds the two to one constant.
"""

from __future__ import annotations

from importlib.metadata import metadata
from typing import Final

from emendrix.core.changes import DisputeReason
from emendrix.output.json_out import act_dir_for
from emendrix.output.schemas import SCHEMAS
from emendrix.site_.api_files import API_ROOT
from emendrix.site_.chrome import page
from emendrix.site_.dispute import REASON_SENTENCES
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.head import canonical_url
from emendrix.site_.history import histories
from emendrix.site_.identity import page_masthead
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, escape, inline, join
from emendrix.site_.urls import depth_of, up

__all__ = ["SNIPPET_TEMPLATE", "render_api_page", "snippet"]

_PATH: Final = "api/"
_DEPTH: Final = depth_of(_PATH)

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

_LEDE: Final = (
    "The record this site renders, as files a program can fetch. There is no query endpoint, "
    "no account and no key: every answer is a file, and the record's files are the committed "
    "bytes of the changelogs repository, at the same relative paths as in a clone of it."
)
_UNCONFIGURED: Final = (
    "The API's absolute addresses are not known for this build, because no site URL was "
    "configured. The paths below are relative to wherever the site is served, and the examples "
    "use the hosted instance's address as an example."
)

_LAYOUT: Final = (
    ("", "this page, with the CI example at its end", "the site build"),
    ("v1/index.json", "the root index: one row per act", "the record, served as committed"),
    ("v1/<act_dir>/index.json", "one act's versions, and every change per provision", "the record"),
    ("v1/<act_dir>/changes/<version>.json", "one version's payload, with the texts", "the record"),
    ("v1/catalogue.json", "labels, aliases, sectors, page and feed addresses", "the site build"),
    ("v1/schema/<name>.schema.json", "the JSON Schema of each document", "the site build"),
)
"""Every path the API serves, relative to this page, with what it is and who writes it."""

_TABLE: Final = (
    '<div class="scroll"><table role="table">\n<thead role="rowgroup"><tr role="row">'
    '<th role="columnheader">Path</th><th role="columnheader">What it is</th>'
    '<th role="columnheader">From</th></tr></thead><tbody role="rowgroup">\n{rows}\n'
    "</tbody></table></div>"
)

_FIELDS: Final = """
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

_REASONS: Final = "\n".join(f"- `{code}`: {REASON_SENTENCES[code]}" for code in DisputeReason)
"""Every reason in the order `SignalSet.reason` tries them, in the site's own sentences."""

_RECORD: Final = """
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

_CI: Final = """
A GitHub Actions workflow that opens an issue when a provision you pin has a newer change. It is
an example to adapt rather than a maintained action: set `PIN` to the act and the canonical
location, and `SEEN` to the version you have already reviewed. It needs no secret beyond the
job's own token and dedupes by issue title. It uses `jq` and `gh`, which GitHub-hosted runners
have preinstalled.
"""

_AGENT: Final = """
The `emendrix-snippet/1` user agent lets the example's use be counted from the server's own
request lines, with no cookies and no tracking; change it if you would rather not be counted.
"""


def _hosted() -> str:
    """The hosted instance's address, from the package's own `Homepage`, or '' if none."""
    entries: list[str] = metadata("emendrix").get_all("Project-URL") or []
    for entry in entries:
        name, _, url = entry.partition(", ")
        if name == "Homepage":
            return url.rstrip("/")
    return ""


def snippet(base: str) -> str:
    """The example workflow, pointed at the site served from `base`."""
    return SNIPPET_TEMPLATE.replace("{base}", base)


def _layout(site: SiteInputs) -> Html:
    """The layout table. A concrete path links its file, absolutely, when there is a base."""
    rows = []
    for tail, what, source in _LAYOUT:
        cell = escape(f"/{_PATH}{tail}")
        if site.site_url and "<" not in tail:
            cell = Html(
                f'<a href="{escape(canonical_url(site.site_url, _PATH + tail))}">{cell}</a>'
            )
        rows.append(
            f'<tr role="row"><td role="cell"><code>{cell}</code></td><td role="cell" data-label='
            f'"What it is">{escape(what)}</td><td role="cell" data-label="From">{escape(source)}'
            "</td></tr>"
        )
    return Html(_TABLE.format(rows="\n".join(rows)))


def _schemas(site: SiteInputs) -> Html:
    """One link per published schema, each a file this build writes beside the page."""
    links = []
    for name in (*sorted(SCHEMAS), "catalogue"):
        path = f"{API_ROOT}schema/{name}.schema.json"
        href = canonical_url(site.site_url, path) if site.site_url else up(_DEPTH) + path
        links.append(f'<a href="{escape(href)}"><code>{escape(name)}</code></a>')
    return Html(
        "<p><code>&lt;act_dir&gt;</code> is the act's corpus and key, and "
        "<code>&lt;version&gt;</code> the version it is the payload of. Every path an index names "
        f"is relative to <code>/{API_ROOT}</code>. The schemas: {', '.join(links)}. Each "
        "carries its own file name as a relative <code>$id</code>.</p>"
    )


def _examples(site: SiteInputs, base: str) -> list[Html]:
    """Two `curl` commands against this site, naming the first act it holds a change to."""
    held = sorted(site.acts, key=lambda act: (act.act.corpus, act.act.key))
    found = next(((act, histories(act)) for act in held if act.entries), None)
    act_dir, key, location = (
        (act_dir_for(found[0].act), found[0].act.key, found[1][0].location.canonical)
        if found
        else ("<act_dir>", "<act>", "<location>")
    )
    commands = (
        f"curl -fsSL {base}/{API_ROOT}index.json \\\n"
        "  | jq -r '.acts[] | [.key, .newest_version, .changes, .disputed, .title] | @tsv'",
        f"curl -fsSL {base}/{API_ROOT}{act_dir}/index.json \\\n"
        f"  | jq '.provisions[\"{location}\"][0]'",
    )
    return [
        Html('<h2 id="examples">Examples</h2>'),
        Html("<p>Every act, with its newest version, its counts and its title:</p>"),
        Html(f'<div class="scroll"><pre>{escape(commands[0])}</pre></div>'),
        Html(f"<p>The newest change to {inline(f'`{location}` of `{key}`')}:</p>"),
        Html(f'<div class="scroll"><pre>{escape(commands[1])}</pre></div>'),
    ]


def _prose(text: str) -> list[Html]:
    """Per blank-line group: `## <id> <heading>`, `- ` items, or a paragraph, run through
    `inline`. These are the page's own wrapped sentences, so a line break in one is a space."""
    lines: list[Html] = []
    for group in text.strip().split("\n\n"):
        if group.startswith("## "):
            anchor, heading = group[3:].split(" ", 1)
            lines.append(Html(f'<h2 id="{anchor}">{escape(heading)}</h2>'))
        elif group.startswith("- "):
            items = (" ".join(item.split()) for item in group[2:].split("\n- "))
            lines.append(Html("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>"))
        else:
            lines.append(Html(f"<p>{inline(' '.join(group.split()))}</p>"))
    return lines


def _methodology(root: str) -> Html:
    return Html(
        "<p>A reason is a reading of stored verdicts and says nothing about the law. The "
        f'<a href="{root}methodology/">methodology page</a> explains each signal and how often '
        "the sources differ.</p>"
    )


def _licence(changelogs_url: str) -> list[Html]:
    """Named only where the deployment says where its record is published, which states it."""
    if not changelogs_url:
        return []
    link = f'<a href="{escape(changelogs_url)}">changelogs repository</a>'
    return [
        Html(
            f'<h2 id="licence">Licence</h2>\n<p>The record is licensed as its {link} states, '
            "which also says on what terms the legislative text it quotes is reused.</p>"
        )
    ]


def render_api_page(site: SiteInputs) -> Html:
    """The page at `api/`. Same inputs, same bytes, no clock, no network."""
    root = up(_DEPTH)
    base = site.site_url or _hosted()
    lines = [
        *page_masthead("prose", "About this site", "The JSON API", _PATH),
        Html(f'<p class="lede">{escape(_LEDE)}</p>'),
    ]
    if not site.site_url:
        lines.append(Html(f'<p class="none">{escape(_UNCONFIGURED)}</p>'))
    lines.extend((Html('<h2 id="layout">Layout</h2>'), _layout(site), _schemas(site)))
    lines.extend((*_prose(_FIELDS), *_prose(_REASONS), _methodology(root), *_prose(_RECORD)))
    lines.extend(_licence(site.changelogs_url))
    lines.extend(_examples(site, base))
    lines.extend(
        (
            Html('<section id="watch-in-ci">'),
            Html("<h2>Watch a provision from CI</h2>"),
            *_prose(_CI),
            Html(f'<div class="scroll"><pre>{escape(snippet(base))}</pre></div>'),
            *_prose(_AGENT),
            Html("</section>"),
        )
    )
    return page(
        title="The JSON API — emendrix",
        description="The record emendrix publishes, as JSON files a program can fetch, and an "
        "example that watches one provision from CI.",
        body=join(lines, "\n"),
        path=_PATH,
        chrome=site.chrome,
        section=_PATH,
        feeds=((feed_path(None), feed_title(None)),),
    )
