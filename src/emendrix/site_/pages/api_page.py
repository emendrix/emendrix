"""The page about the JSON API: where each file lives, what its fields mean, and a CI example.

What a reader of the site needs from the API's reference document, and nothing about any act.
The `curl` examples name the first act and provision this build holds a change to, so a command
copied off the page answers on the deployment it was copied from. Absolute addresses are the
deployment's `--site-url`; without one the page says so, as the feeds page does, and its
examples use the hosted instance's address, read from the package's own `Homepage` because it
is configuration a fork changes. The workflow is published here and in the API's reference
document, and a test holds the two to one constant. The page closes with the MCP server, whose
install line names this build's own `/mcp` when it knows its address. The words themselves live
in `api_prose.py`; this module lays them out.

Under the lede, the three ways in are an index into the page itself: `take_away`'s block, with
each door a fragment here, so the words are the ones the home and About pages print and a
reader reaches the layout table, the MCP server or the workflow in one jump.
"""

from __future__ import annotations

import json
from importlib.metadata import metadata
from textwrap import dedent, indent
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
from emendrix.site_.pages.api_prose import (
    AGENT,
    CI,
    CLIENTS,
    FIELDS,
    LEDE,
    MCP,
    NO_ENDPOINT,
    RECORD,
    SNIPPET_TEMPLATE,
    UNCONFIGURED,
)
from emendrix.site_.pages.take_away import take_away
from emendrix.site_.urls import depth_of, up

__all__ = ["SNIPPET_TEMPLATE", "render_api_page", "snippet"]

_PATH: Final = "api/"
_DEPTH: Final = depth_of(_PATH)


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


_REASONS: Final = "\n".join(f"- `{code}`: {REASON_SENTENCES[code]}" for code in DisputeReason)
"""Every reason in the order `SignalSet.reason` tries them, in the site's own sentences."""


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
    """Per blank-line group: `## <id> <heading>`, `- ` items, a block indented four spaces, or a
    paragraph run through `inline`. A line break in a paragraph is a space."""
    lines: list[Html] = []
    for group in text.strip().split("\n\n"):
        if group.startswith("    "):
            lines.append(Html(f'<div class="scroll"><pre>{escape(dedent(group))}</pre></div>'))
        elif group.startswith("## "):
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


def _mcp(site: SiteInputs) -> list[Html]:
    """The MCP section, with the lines a client needs when this build knows its address."""
    if not site.site_url:
        return [*_prose(MCP), Html(f'<p class="none">{escape(NO_ENDPOINT)}</p>')]
    endpoint = canonical_url(site.site_url, "mcp")
    config = json.dumps({"mcpServers": {"emendrix": {"type": "http", "url": endpoint}}}, indent=2)
    clients = CLIENTS.replace("{endpoint}", endpoint).replace("{config}", indent(config, "    "))
    return _prose(MCP + clients)


def render_api_page(site: SiteInputs) -> Html:
    """The page at `api/`. Same inputs, same bytes, no clock, no network."""
    root = up(_DEPTH)
    base = site.site_url or _hosted()
    lines = [
        *page_masthead("prose", "About this site", "The JSON API", _PATH),
        Html(f'<p class="lede">{escape(LEDE)}</p>'),
    ]
    if not site.site_url:
        lines.append(Html(f'<p class="none">{escape(UNCONFIGURED)}</p>'))
    lines.append(take_away(root, heading="Three ways in", here=True))
    lines.extend((Html('<h2 id="layout">Layout</h2>'), _layout(site), _schemas(site)))
    lines.extend((*_prose(FIELDS), *_prose(_REASONS), _methodology(root), *_prose(RECORD)))
    lines.extend(_licence(site.changelogs_url))
    lines.extend((*_examples(site, base), *_mcp(site)))
    lines.extend(
        (
            Html('<section id="watch-in-ci">'),
            Html("<h2>Watch a provision from CI</h2>"),
            *_prose(CI),
            Html(f'<div class="scroll"><pre>{escape(snippet(base))}</pre></div>'),
            *_prose(AGENT),
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
