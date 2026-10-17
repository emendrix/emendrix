"""The prebuilt index the one script searches: names, identifiers and touched provisions.

A static site cannot query anything, so the whole searchable surface is computed here and
written once. What is in it is deliberately narrow:

- **names, not text.** An act by its label, by every alias the watchlist gives it and by its
  own identifier; an amending instrument by the name and number it is shown under and by its
  own identifier; a provision by its human coordinate and its title. Full text is not indexed,
  because a substring index over the whole corpus is a different artifact with a different size
  and this one has to stay a file a browser downloads without noticing.
- **a title is a name too.** A reader who knows Annex II as the allergens annex knows it by its
  title, not its number, so a provision's row carries the title its page prints: the law's own
  words, decided by `provision_title`, the rule every page uses, from the newest change. A row
  with nothing to add has no `title` key at all, so the other rows' bytes do not grow. An act's
  official title is not indexed: it is long, and the act is already found by its names.
- **touched provisions only.** The site has a page for a provision an amendment moved and
  nothing at all for one it did not, so indexing an untouched coordinate would promise a
  destination that does not exist.

A provision's url is its own page, one row per coordinate per act. It pointed at the newest
change's fragment on an event page until those pages existed, which meant a search for a
provision landed in one arbitrary version transition with nothing to say which; the row now
lands on the coordinate's whole history, which is the question the row was always answering.
The dedupe by canonical string is unchanged and is what that means: one coordinate, one page,
one row.

A second file, `substance-index.json`, holds every CAS, EC and Index number an entry prints, in
the same row shape. It is apart because a single table can print thousands of numbers, and the
script fetches it only when a query can use it, so the first file stays the size it was.

Deterministic bytes: entries are sorted by label, kind and url before serialisation, object
keys are sorted by the serialiser, and the separators are pinned, so two builds of one
repository state produce one file.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix.site_.amending import resolve
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.instruments import amended_by
from emendrix.site_.subject import provision_title
from emendrix.site_.substance_inputs import Substance
from emendrix.site_.substance_words import page_name
from emendrix.site_.urls import act_href, amendment_href, provision_href, substance_href

__all__ = [
    "SUBSTANCE_INDEX",
    "IndexEntry",
    "IndexKind",
    "search_index_json",
    "substance_index_json",
]

SUBSTANCE_INDEX = "substance-index.json"
"""The second file the script fetches, beside the first: only for a query that opens with a
digit, or on the first keystroke on a page whose search mount asks for it."""

IndexKind = Literal["act", "alias", "amending", "celex", "provision", "substance"]
"""What a hit is, shown beside it so a reader can tell a name from a coordinate."""


class IndexEntry(BaseModel):
    """One searchable thing: what to match on, what it is, and where it lives."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1, description="The text the script matches against.")
    kind: IndexKind
    url: str = Field(min_length=1, description="Relative to the site root, like every href.")
    title: str = Field(
        default="",
        description="A provision's title where the page can say more than its coordinate, else ''.",
    )


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
    """Every coordinate this act's watched history touched, each pointing at its own page.

    `act.entries` runs newest first, so the change kept for a coordinate is its newest, and the
    row's title is the one the provision page's heading prints.
    """
    entries: list[IndexEntry] = []
    seen: set[str] = set()
    for entry in act.entries:
        for emitted in entry.changes:
            location = emitted.change.location
            if location.canonical in seen:
                continue
            seen.add(location.canonical)
            entries.append(
                IndexEntry(
                    label=f"{location.human} — {act.label}",
                    kind="provision",
                    url=provision_href(act.slug, location.canonical),
                    title=provision_title(emitted.change) or "",
                )
            )
    return entries


def _instruments(site: SiteInputs) -> list[IndexEntry]:
    """Every amending instrument with a page, under the name it is shown under and its key.

    The row's label carries the number beside the short name where the two differ, so a
    reader who types `2020/561` and a reader who types the declared short name both land on
    the same page from one row. The key gets a row of its own on the same rule `_names` uses
    for an act's: only when it is not already the label, one row saying one string twice
    being noise in a result list.
    """
    entries: list[IndexEntry] = []
    for key in amended_by(site):
        instrument = resolve(site.amending, key)
        short = instrument.short
        number = instrument.number
        label = f"{short} — {number}" if number and number != short else short
        href = amendment_href(key)
        entries.append(IndexEntry(label=label, kind="amending", url=href))
        if key != label:
            entries.append(IndexEntry(label=key, kind="celex", url=href))
    return entries


def search_index_json(site: SiteInputs) -> str:
    """The whole index as committed bytes, newline-terminated. No clock, no network."""
    entries = [item for act in site.acts for item in (*_names(act), *_provisions(act))]
    entries.extend(_instruments(site))
    return _serialised(entries)


def _serialised(entries: list[IndexEntry]) -> str:
    entries.sort(key=lambda item: (item.label.casefold(), item.kind, item.url))
    payload = {"entries": [item.model_dump(exclude_defaults=True) for item in entries]}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def _titled(substance: Substance) -> str:
    """The name the page's heading prints, then the acts whose entries print the number."""
    labels: dict[str, None] = {}
    for act in [h.act for h in substance.holdings] + [m.act for m in substance.history]:
        labels.setdefault(act.label, None)
    name = page_name(substance)
    acts = ", ".join(labels)
    return f"{name} · {acts}" if name else acts


def substance_index_json(site: SiteInputs) -> str:
    """The second file: every CAS, EC and Index number, each landing on a substance page.

    Labels are canonical values and nothing else, so a typed number matches a row exactly or by
    its leading digits, and the script reads a hyphenless number into these forms itself. An
    Index No lands on the page of the first CAS, else EC, number its entry carries; one whose
    entry carries neither has no page to land on and no row. Same row shape and the same bytes
    rule as the first file.
    """
    pages = {(one.scheme, one.value): one for one in site.substances.substances}
    entries = [
        IndexEntry(
            label=one.value,
            kind="substance",
            url=substance_href(one.scheme, one.value),
            title=_titled(one),
        )
        for one in site.substances.substances
    ]
    for label in site.substances.labels:
        target = pages[(label.target.scheme, label.target.value)]
        entries.append(
            IndexEntry(
                label=label.value,
                kind="substance",
                url=substance_href(target.scheme, target.value),
                title=_titled(target),
            )
        )
    return _serialised(entries)
