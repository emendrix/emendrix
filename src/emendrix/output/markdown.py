"""Rendering one amendment event as Markdown, the primary artifact of the whole project.

What the format *forces* is the reason for every decision below:

- **Every sentence carries a citation**, and the citation is a link. They were rendered to
  `Citation` objects by the adapter at emit time (`graph/report.py`); nothing here invents a
  URL, and nothing here re-derives one. Labels are compacted against the two version tags of
  this entry (`Art. 4, v2`) with the mapping stated once in the header, because a full
  consolidated identifier in every bracket costs more readability than it buys precision.
- **`before`/`after` are verbatim.** They come from the stored `ProvisionText` untouched. The
  only things done to them are a `> ` prefix per line, which is Markdown framing rather than a
  change to the text, and a character cap whose every use is *visibly marked*: a silently
  truncated "verbatim" quote is worse than a long one (`QUOTE_CHAR_CAP`).
- **Applicability is separate and first-class**, on the change's own headline, because "in
  force" and "applies to you" are different questions and `unknown` is an answer.
- **The change type comes from the diff**, never from a model, so it is printed as fact.
- **A disputed change is rendered and marked, never dropped**, and the marker says *what*
  disagreed, its `dispute_reason` in words and then the verdicts ("seen by the structural
  diff, not by corpus metadata"), because that transparency is the product's honesty made
  visible.
- **A sentence the gate wrote is visually distinct from one the model wrote.** The gate's
  verbatim fallback is correct by construction and the model's prose is not; a reader who
  cannot tell them apart has lost the more useful half of that distinction.

This module frames an entry: its header, its title and the standalone form with the
disclaimer. How one change is written down lives in `markdown_change.py`, whose names are
re-exported here so the site and the tests keep importing them from this module.

No clock, no corpus, no model: `detected_on` arrives on the entry, and two runs of one event
produce identical bytes.
"""

from __future__ import annotations

from typing import Final

from emendrix.output.disclaimer import MARKDOWN_DISCLAIMER
from emendrix.output.json_out import ChangelogEntry
from emendrix.output.markdown_change import (
    FALLBACK_PREFIX,
    QUOTE_CHAR_CAP,
    REASON_PHRASES,
    TRUNCATION_MARKER,
    applies_text,
    change_block,
    dispute_text,
    short_label,
)

__all__ = [
    "FALLBACK_PREFIX",
    "QUOTE_CHAR_CAP",
    "REASON_PHRASES",
    "TITLE_CAP",
    "TRUNCATION_MARKER",
    "applies_text",
    "dispute_text",
    "render_entry",
    "render_standalone",
    "short_label",
    "short_title",
]

TITLE_CAP: Final = 120
"""Where an act's official title is cut in the heading, visibly, with `[…]`.

Official EU titles are one long sentence (the MDR's is 266 characters, naming the four
directives it amends) and an H2 that wide is not a heading. The cut is marked and the full title
is in the JSON document's `act.display_name`, uncut.
"""


def short_title(title: str) -> str:
    """An act's name for a heading, cut at `TITLE_CAP` and marked when it is cut."""
    if len(title) <= TITLE_CAP:
        return title
    return f"{title[:TITLE_CAP].rsplit(' ', 1)[0].rstrip(' ,;')} […]"


def _header(entry: ChangelogEntry) -> list[str]:
    counts, summary = entry.counts, entry.summary
    in_force = ", ".join(value.isoformat() for value in entry.in_force) or "not stated"
    lines = [
        f"## {short_title(entry.title)}",
        f"### `{entry.from_version}` → `{entry.to_version}`",
        "",
        f"- **Act** `{entry.act}` · **In force** {in_force} · "
        f"**Detected** {entry.detected_on.isoformat()}",
        f"- **Touched** {counts.touched} provisions — {counts.substantive} substantive · "
        f"{counts.date_only} date-only · {counts.textless} with no text · "
        f"**{counts.disputed} disputed**",
        f"- **Diff** {summary.inserted} inserted · {summary.modified} modified · "
        f"{summary.deleted} deleted · {summary.renumbered} renumbered · "
        f"{summary.deferred} deferred · {summary.unchanged_units} unchanged",
    ]
    if entry.diff_only:
        lines.append(
            "- **Diff only** — the explain stage did not run, so this entry carries the "
            "structural facts and the verbatim texts and no prose"
        )
    else:
        lines.append(
            f"- **Gate** {counts.quoted} sentences quoted verbatim · "
            f"{counts.unexplained} changes shipped without an explanation"
        )
    lines.extend(
        (
            f"- **Citations** `v1` = `{entry.from_version}` · `v2` = `{entry.to_version}`",
            "",
            "---",
        )
    )
    return lines


def render_entry(entry: ChangelogEntry) -> str:
    """One amendment event as Markdown, newline-terminated. Deterministic and byte-stable."""
    lines = list(_header(entry))
    for emitted in entry.changes:
        lines.extend(change_block(emitted, entry))
    return "\n".join(lines).rstrip() + "\n"


def render_standalone(entry: ChangelogEntry) -> str:
    """The same entry printed on its own, for `emendrix diff --markdown`, with the disclaimer.

    Inside a `CHANGELOG.md` the disclaimer sits once at the top of the file (`changelog.py`).
    """
    return f"{render_entry(entry)}\n{MARKDOWN_DISCLAIMER}\n"
