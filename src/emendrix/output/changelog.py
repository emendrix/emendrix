"""The `CHANGELOG.md` file itself: its header, its entry markers, and newest version first.

One file per act, newest entry first, rewritten in place. The awkward part is that the file is
mostly *quoted legal text*, and legal text can contain anything, including anything this module
might use as a marker. Three rules follow, and together they make a collision structurally
impossible rather than unlikely:

1. **Markers are HTML comments carrying a fixed random token** (`MARKER`), not prose.
2. **They are matched anchored to the start of a line.** Every line of quoted text in a
   rendered entry is inside a Markdown blockquote and therefore begins with `> `
   (`markdown.py::_quote`), and every generated sentence is folded onto one line, so no line
   of content can begin where a marker begins.
3. **The header is regenerated, never parsed.** It is a pure function of the act, so there is
   nothing to recover from the old file and no regex is ever run over the part of the file a
   human might have edited.

An entry is delimited at both ends and keyed by the event's identity
(`ChangelogEntry.key`), which buys the property that matters for a tool that runs on a cron:
re-emitting an event **replaces its entry in place** and keeps every other entry byte-identical,
rather than appending a near-duplicate at the top.

The same key decides where a new entry goes. "Newest first" has to mean the newest *version*,
not the newest *emission*: the poller runs forward and a backfill fills history in underneath it
weeks later, so a prepend would leave the genuinely newest entry at the bottom of the file. The
key is the version tag the transition produced and ends in that version's date, so an act's
entries sort lexicographically and the insertion point is the first entry the new one is newer
than. Emission order then stops mattering, which is the only way two writers on one file can
agree about it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from emendrix.core import ActId
from emendrix.output.disclaimer import MARKDOWN_DISCLAIMER
from emendrix.output.json_out import ChangelogEntry
from emendrix.output.markdown import render_entry

__all__ = [
    "MARKER",
    "changelog_text",
    "entry_marker",
    "header_for",
    "repo_readme",
    "split_entries",
]

MARKER: Final = "b7f4a1c2-9e3d"
"""A fixed token that no legal text will contain. Not generated per run: the markers are part of
the committed file format, so they may not wobble between runs (`uuid` is banned in the gate for
the same reason and would be just as wrong here)."""

_ENTRY = re.compile(rf"^<!-- emendrix:entry {MARKER} (\S+) -->$", re.MULTILINE)


def entry_marker(key: str) -> str:
    return f"<!-- emendrix:entry {MARKER} {key} -->"


def _entry_end(key: str) -> str:
    return f"<!-- emendrix:entry-end {MARKER} {key} -->"


def header_for(act: ActId) -> str:
    """The top of one act's `CHANGELOG.md`. A pure function of the act, so it is regenerated.

    The heading is the act's identifier and the *full* official title goes on its own line
    beneath, uncut: official titles run to hundreds of characters (the MDR's names the four
    directives it amends), a heading is not the place for one, and nor is a changelog the place
    to be coy about which act it is about.
    """
    title = act.display_name
    return "\n".join(
        (
            f"<!-- emendrix:changelog {MARKER} {act} -->",
            f"# {act} — changelog",
            "",
            *(() if title is None else (f"**{title}**", "")),
            f"Amendments to `{act}`, newest first, computed by emendrix from the corpus's own "
            "published versions.",
            "",
            "Generated — do not edit by hand. Entries are delimited by "
            "`<!-- emendrix:entry … -->` markers and are rewritten in place when an event is "
            "re-emitted.",
            "",
            MARKDOWN_DISCLAIMER,
            "",
            "",
        )
    )


def split_entries(text: str) -> list[tuple[str, str]]:
    """The file's entries as `(key, block)`, in file order. Anything before the first is header.

    Each block runs from its own opening marker up to the next one (or the end of the file), so
    reassembling `"".join(blocks)` after the header reproduces the file exactly.
    """
    matches = list(_ENTRY.finditer(text))
    return [
        (
            match[1],
            text[
                match.start() : (matches[index + 1].start() if index + 1 < len(matches) else None)
            ],
        )
        for index, match in enumerate(matches)
    ]


def changelog_text(existing: str | None, entry: ChangelogEntry) -> str:
    """The new contents of one act's `CHANGELOG.md` with this entry in it.

    Inserted at its place in the order when the event is new and replaced where it lies when it
    is not, so a re-run neither duplicates an entry nor reorders the ones already committed.
    """
    block = f"{entry_marker(entry.key)}\n{render_entry(entry)}{_entry_end(entry.key)}\n\n"
    blocks = split_entries(existing or "")
    if any(key == entry.key for key, _ in blocks):
        blocks = [(key, block if key == entry.key else body) for key, body in blocks]
    else:
        blocks.insert(_position_for(entry.key, blocks), (entry.key, block))
    return header_for(entry.act) + "".join(body for _, body in blocks)


def _position_for(key: str, blocks: Sequence[tuple[str, str]]) -> int:
    """Above the first entry this one is newer than, or at the end of the file.

    The comparison is on the entry key, which is the version tag the transition produced and
    ends in that version's date, so entries of one act sort lexicographically into date order.
    Only the new entry moves: every block already in the file keeps its bytes and its
    neighbours, which is what keeps a re-emit a no-op in the git diff.
    """
    return next(
        (index for index, (existing, _) in enumerate(blocks) if existing < key), len(blocks)
    )


def repo_readme() -> str:
    """The output repository's own `README.md`, written once when the repo is initialised.

    The repository is the user's: emendrix commits into it and never pushes it. So it says what
    it is, who wrote it and what it is not, for whoever opens it without context.
    """
    return "\n".join(
        (
            f"<!-- emendrix:output-repo {MARKER} -->",
            "# Regulatory changelogs",
            "",
            "Written by emendrix, a regulatory change engine: it watches published "
            "legislation, computes a provision-level structural diff when an act is amended, "
            "and commits the result here.",
            "",
            "Layout — one directory per act, namespaced by the corpus it came from:",
            "",
            "```",
            "<corpus>/<act>/CHANGELOG.md          the human-readable changelog, newest first",
            "<corpus>/<act>/changes/<version>.json  the same events as structured JSON",
            "```",
            "",
            "The JSON schema is versioned and documented in the emendrix repository. "
            "This repository belongs to you: emendrix commits into it and "
            "never pushes it anywhere.",
            "",
            MARKDOWN_DISCLAIMER,
            "",
        )
    )
