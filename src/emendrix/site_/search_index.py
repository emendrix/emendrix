"""The prebuilt index the one script searches: names, identifiers and touched provisions.

A static site cannot query anything, so the whole searchable surface is computed here and
written once. What is in it is deliberately narrow:

- **names, not text.** An act by its label, by every alias the watchlist gives it and by its
  own identifier; a provision by its human coordinate. Full text is not indexed, because a
  substring index over the whole corpus is a different artifact with a different size and this
  one has to stay a file a browser downloads without noticing.
- **touched provisions only.** The site has a page fragment for a provision an amendment
  moved and nothing at all for one it did not, so indexing an untouched coordinate would
  promise a destination that does not exist.

The anchors are not recomputed here. A provision's url is the fragment the event page publishes
for the newest change at that coordinate, on that event's own page, and it comes from
`urls.entry_anchors`, the one place the occurrence counter lives. An index running its own
counter would drift from the page the moment one entry touched one coordinate twice, and the
symptom would be a search result landing at the top of a page instead of at the change: the
sort of defect nobody reports. Newest first is the entry order `collect_site` guarantees, so
the first anchor seen for a coordinate is the newest one and later events do not overwrite it.

Deterministic bytes: entries are sorted by label, kind and url before serialisation, object
keys are sorted by the serialiser, and the separators are pinned, so two builds of one
repository state produce one file.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.urls import act_href, entry_anchors, event_href

__all__ = ["IndexEntry", "IndexKind", "search_index_json"]

IndexKind = Literal["act", "alias", "celex", "provision"]
"""What a hit is, shown beside it so a reader can tell a name from a coordinate."""


class IndexEntry(BaseModel):
    """One searchable thing: what to match on, what it is, and where it lives."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1, description="The text the script matches against.")
    kind: IndexKind
    url: str = Field(min_length=1, description="Relative to the site root, like every href.")


def _names(act: ActSite) -> list[IndexEntry]:
    """The act under every name it answers to: its label, its long form, its aliases, its key.

    The long form is indexed as an alias, since to a search it is one more name the act
    answers to, and is skipped when the watchlist already lists it among the aliases. The key
    is skipped when it is already the label, which is what an act with no configured name
    looks like. Either way, one row saying the same string twice is noise in a result list.
    """
    href = act_href(act.slug)
    entries = [IndexEntry(label=act.label, kind="act", url=href)]
    if act.long_name and act.long_name not in act.aliases:
        entries.append(IndexEntry(label=act.long_name, kind="alias", url=href))
    entries.extend(
        IndexEntry(label=alias, kind="alias", url=href) for alias in act.aliases if alias
    )
    if act.act.key != act.label:
        entries.append(IndexEntry(label=act.act.key, kind="celex", url=href))
    return entries


def _provisions(act: ActSite) -> list[IndexEntry]:
    """Every coordinate this act's watched history touched, at its newest change."""
    entries: list[IndexEntry] = []
    seen: set[str] = set()
    for entry in act.entries:
        href = event_href(act.slug, entry.key)
        anchors = entry_anchors(
            entry.key, [emitted.change.location.canonical for emitted in entry.changes]
        )
        for emitted, anchor in zip(entry.changes, anchors, strict=True):
            location = emitted.change.location
            if location.canonical in seen:
                continue
            seen.add(location.canonical)
            entries.append(
                IndexEntry(
                    label=f"{location.human} — {act.label}",
                    kind="provision",
                    url=f"{href}#{anchor}",
                )
            )
    return entries


def search_index_json(site: SiteInputs) -> str:
    """The whole index as committed bytes, newline-terminated. No clock, no network."""
    entries = [item for act in site.acts for item in (*_names(act), *_provisions(act))]
    entries.sort(key=lambda item: (item.label.casefold(), item.kind, item.url))
    payload = {"entries": [item.model_dump() for item in entries]}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
