"""The substance half of the JSON API: one list of every number, and one file per number.

```
api/v1/substances.json                    every CAS and EC number with a page, and every other
                                          identifier (an Index No) that lands on one
api/v1/substances/<scheme>-<value>.json   one number's page as data: its entries and changes
```

Both are derived by the site build, like the catalogue, from the committed registers and
payloads; neither is part of the record. A file says what its page says and nothing more: the
entries of the newest version each act's register holds that print the number, with their rows
and their table's header, and every recorded change to an entry printing it, newest first, each
with the event page's permalink to the change block and the payload it was read from. Every
address is minted by the function the builder writes the page under, absolute with a site URL
and root-relative without, so an address read out of a file resolves to a file this tree holds.

The list keeps a row for an Index No whose entry carries a CAS or EC number, pointing at the
same page and file the search box lands on, so a reader of the API resolves one without the
site's search file. A number the list does not hold is printed by no entry the record holds,
which says nothing about the law.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix import DISCLAIMER
from emendrix.core import EntryKind, Identifier, TableEntry
from emendrix.output.json_out import payload_for
from emendrix.output.schemas import SUFFIX, schema_document
from emendrix.site_.amending import amending_keys
from emendrix.site_.api_files import API_ROOT
from emendrix.site_.head import canonical_url
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.substance_inputs import Holding, Moved, Substance
from emendrix.site_.urls import act_href, event_href, provision_href, substance_href

__all__ = [
    "SUBSTANCES",
    "SUBSTANCE_SCHEMA",
    "SubstanceFile",
    "SubstanceIndex",
    "substance_document",
    "substance_file_path",
    "substance_files",
    "substance_index",
]

SUBSTANCES: Final = f"{API_ROOT}substances.json"
SUBSTANCE_SCHEMA: Final = "1.0"
"""Bumped whenever a reader of either file would have to change to keep reading it."""

PROVENANCE: Final = (
    "Derived by the site build from the committed registers and changelogs; not part of the record."
)


def substance_file_path(scheme: str, value: str) -> str:
    """`api/v1/substances/cas-50-00-0.json`, relative to the site root."""
    return f"{API_ROOT}substances/{scheme}-{value}.json"


class SubstanceRow(BaseModel):
    """One identifier, and where its page and its file are."""

    model_config = ConfigDict(frozen=True)

    scheme: str = Field(description="`cas`, `ec`, or a row key's scheme such as `index`.")
    value: str = Field(description="The canonical value.")
    page: str = Field(description="The page it lands on.")
    file: str = Field(description="The file holding that page's facts.")
    canonical: str = Field(description="The page a search engine is pointed at for it.")


class SubstanceIndex(BaseModel):
    """Every number with a page, then every other identifier that lands on one, sorted."""

    model_config = ConfigDict(frozen=True)

    substance_schema: str = Field(default=SUBSTANCE_SCHEMA, description="This format's version.")
    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    provenance: str = Field(default=PROVENANCE, description="Where this file comes from.")
    substances: tuple[SubstanceRow, ...] = Field(description="One row per identifier.")


class SubstanceEntry(BaseModel):
    """One entry of an act's newest version that prints the number, as its register holds it."""

    model_config = ConfigDict(frozen=True)

    corpus: str = Field(description="The act's corpus namespace.")
    act: str = Field(description="The act's key within its corpus.")
    label: str = Field(description="The act's short label on this site.")
    version: str = Field(description="The version the register was read from.")
    key_label: str | None = Field(description="How the act names the key; null for a name key.")
    header: tuple[tuple[str | None, ...], ...] = Field(description="The table's header rows.")
    entry: TableEntry = Field(description="The entry, its rows verbatim.")
    act_page: str = Field(description="The act's page.")
    provision_page: str | None = Field(
        description="The unit's page, where a recorded change touched it; else null."
    )
    last_changed: str | None = Field(
        description="The permalink of the newest recorded change to this entry; null for none."
    )


class SubstanceChange(BaseModel):
    """One recorded change to an entry printing the number."""

    model_config = ConfigDict(frozen=True)

    corpus: str = Field(description="The act's corpus namespace.")
    act: str = Field(description="The act's key within its corpus.")
    label: str = Field(description="The act's short label on this site.")
    version: str = Field(description="The version the change was recorded in.")
    dated: date = Field(description="The version's in-force date, else the day it was seen.")
    in_force: bool = Field(description="True when `dated` is the in-force date.")
    kind: EntryKind = Field(description="`added`, `amended` or `removed`.")
    typography_only: bool = Field(description="Amended only in spacing, dash forms or accents.")
    key_label: str | None = Field(description="How the act names the key; null for a name key.")
    header: tuple[tuple[str | None, ...], ...] = Field(description="The table's header rows.")
    before: TableEntry | None = Field(description="The entry before; null when added.")
    after: TableEntry | None = Field(description="The entry after; null when removed.")
    amending_acts: tuple[str, ...] = Field(
        description="The amending acts the change names, which may be fewer than made it."
    )
    event: str = Field(description="The permalink of the change block on its version page.")
    file: str = Field(description="The payload the change was read from.")


class SubstanceFile(BaseModel):
    """One CAS or EC number: every entry that prints it now, and every change to such entries."""

    model_config = ConfigDict(frozen=True)

    substance_schema: str = Field(default=SUBSTANCE_SCHEMA, description="This format's version.")
    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    provenance: str = Field(default=PROVENANCE, description="Where this file comes from.")
    scheme: str = Field(description="`cas` or `ec`.")
    value: str = Field(description="The canonical value.")
    page: str = Field(description="This number's page.")
    canonical: str = Field(description="The page a search engine is pointed at for it.")
    identifiers: tuple[Identifier, ...] = Field(
        description="Every identifier the entries' rows carry, this one included."
    )
    entries: tuple[SubstanceEntry, ...] = Field(description="Act order, then document order.")
    history: tuple[SubstanceChange, ...] = Field(description="Newest first.")


def _address(site: SiteInputs, path: str) -> str:
    return canonical_url(site.site_url, path) if site.site_url else path


def _permalink(site: SiteInputs, moved: Moved) -> str:
    return _address(site, f"{event_href(moved.act.slug, moved.event.key)}#{moved.anchor}")


def _entry(site: SiteInputs, substance: Substance, holding: Holding) -> SubstanceEntry:
    act, entry = holding.act, holding.entry
    touched = site.substances.touched.get(act.slug, frozenset())
    last = next(
        (
            moved
            for moved in substance.history
            if moved.act.act == act.act
            and entry.key is not None
            and moved.change.after is not None
            and (moved.change.container, moved.change.table, moved.change.key)
            == (entry.container, entry.table, entry.key)
            and moved.change.occurrence == entry.occurrence
        ),
        None,
    )
    unit = entry.unit.canonical
    return SubstanceEntry(
        corpus=act.act.corpus,
        act=act.act.key,
        label=act.label,
        version=holding.version,
        key_label=holding.table.key_label if holding.table else None,
        header=holding.table.header if holding.table else (),
        entry=entry,
        act_page=_address(site, act_href(act.slug)),
        provision_page=(
            _address(site, provision_href(act.slug, unit)) if unit in touched else None
        ),
        last_changed=None if last is None else _permalink(site, last),
    )


def _change(site: SiteInputs, moved: Moved) -> SubstanceChange:
    dated = moved.dated
    change = moved.change
    return SubstanceChange(
        corpus=moved.act.act.corpus,
        act=moved.act.act.key,
        label=moved.act.label,
        version=str(moved.event.to_version),
        dated=dated.on,
        in_force=dated.in_force,
        kind=change.kind,
        typography_only=change.typography_only,
        key_label=moved.table.key_label if moved.table else None,
        header=moved.table.header if moved.table else (),
        before=change.before,
        after=change.after,
        amending_acts=amending_keys(moved.event),
        event=_permalink(site, moved),
        file=_address(site, f"{API_ROOT}{payload_for(moved.event.act, moved.event.to_version)}"),
    )


def _canonical(site: SiteInputs, substance: Substance) -> str:
    target = substance.canonical or Identifier(scheme=substance.scheme, value=substance.value)
    return _address(site, substance_href(target.scheme, target.value))


def substance_document(site: SiteInputs, substance: Substance) -> SubstanceFile:
    """One number's file. Pure: the same inputs give the same model."""
    return SubstanceFile(
        scheme=substance.scheme,
        value=substance.value,
        page=_address(site, substance_href(substance.scheme, substance.value)),
        canonical=_canonical(site, substance),
        identifiers=substance.identifiers,
        entries=tuple(_entry(site, substance, holding) for holding in substance.holdings),
        history=tuple(_change(site, moved) for moved in substance.history),
    )


def substance_index(site: SiteInputs) -> SubstanceIndex:
    """The list of every number. Pure: the same inputs give the same model."""
    found = {(one.scheme, one.value): one for one in site.substances.substances}
    rows = [
        SubstanceRow(
            scheme=one.scheme,
            value=one.value,
            page=_address(site, substance_href(one.scheme, one.value)),
            file=_address(site, substance_file_path(one.scheme, one.value)),
            canonical=_canonical(site, one),
        )
        for one in site.substances.substances
    ]
    for label in site.substances.labels:
        target = found[(label.target.scheme, label.target.value)]
        rows.append(
            SubstanceRow(
                scheme=label.scheme,
                value=label.value,
                page=_address(site, substance_href(target.scheme, target.value)),
                file=_address(site, substance_file_path(target.scheme, target.value)),
                canonical=_canonical(site, target),
            )
        )
    return SubstanceIndex(substances=tuple(rows))


def _dumped(model: BaseModel) -> str:
    """Indented and newline-terminated, keys in the model's own order, as the register is."""
    return model.model_dump_json(indent=2) + "\n"


def substance_files(site: SiteInputs) -> dict[str, str]:
    """Both kinds of file and the schema of the second, as `site-root-relative path -> text`."""
    files = {
        SUBSTANCES: _dumped(substance_index(site)),
        f"{API_ROOT}schema/substance{SUFFIX}": schema_document("substance", SubstanceFile),
    }
    for substance in site.substances.substances:
        path = substance_file_path(substance.scheme, substance.value)
        files[path] = _dumped(substance_document(site, substance))
    return files
