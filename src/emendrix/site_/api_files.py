"""The half of the JSON API the site build writes: the catalogue and the schemas.

The record itself, the root index, the act indexes and the payloads, is served from the
changelogs repository as committed and never copied into the site tree. A copy would be
rewritten on every hourly build, and a host serving the repository's files under the same paths
would shadow it, so a deployment without that route would answer with a stale record. Nothing
here therefore writes `api/v1/index.json` or anything under `api/v1/<corpus>/`.

The catalogue carries what the record cannot know: the watchlist's labels, aliases and sectors,
and the address of every page and feed this build writes. Every address is minted by the same
function the builder writes the page under, so a link read out of the catalogue resolves to a
file this tree holds. Without a site URL the addresses are relative to the site root and no
feed is named, because none is written.

It also carries the poller's own record at build time, when the deployment handed the build
its state file: the window end the corpus was read through, and per act the consolidations
announced and still waiting for a text. A watched act with nothing to show is either quiet or
waiting, and only this tells the two apart. Both fields are additive in `1.1`; a build handed
no state file writes `checked_through: null` and every `waiting` empty.

The schemas are the ones `output.schemas` generates, plus the catalogue's own. Their `$id`s are
relative, so the bytes written here are the bytes committed under `docs/schema/`.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix import DISCLAIMER
from emendrix.output.schemas import SUFFIX, schema_document, schema_documents
from emendrix.site_.feeds import feed_path
from emendrix.site_.head import canonical_url
from emendrix.site_.history import histories
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.urls import act_href, event_href, provision_href

__all__ = [
    "API_ROOT",
    "CATALOGUE",
    "CATALOGUE_SCHEMA",
    "PROVENANCE",
    "Catalogue",
    "CatalogueAct",
    "CatalogueWaiting",
    "api_files",
    "catalogue",
]

API_ROOT: Final = "api/v1/"
"""Where every file of the API sits, relative to the site root."""

CATALOGUE: Final = f"{API_ROOT}catalogue.json"
CATALOGUE_SCHEMA: Final = "1.1"
"""Bumped whenever a consumer of the catalogue would have to change to keep reading it."""

PROVENANCE: Final = (
    "Derived by the site build from the watchlist and the committed changelogs; not part of "
    "the record."
)


class CatalogueWaiting(BaseModel):
    """One consolidation the poller was told about and could not read yet, at build time."""

    model_config = ConfigDict(frozen=True)

    version: str | None = Field(
        description="The consolidated version announced; null when it is not yet known."
    )
    state: str = Field(
        description="`consolidation_pending` while the text is not published yet, or "
        "`english_unavailable` when no English text is offered."
    )
    first_seen: date | None = Field(
        description="The day the poller first saw it; null when its record holds no date."
    )


class CatalogueAct(BaseModel):
    """One watched act: the watchlist's names for it, and where this site shows it."""

    model_config = ConfigDict(frozen=True)

    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    label: str = Field(description="The watchlist's short label.")
    long_name: str = Field(description="The watchlist's long form, or ''.")
    aliases: tuple[str, ...] = Field(description="Other names the watchlist gives the act.")
    domain: str = Field(description="The watchlist's sector for the act, or ''.")
    url: str = Field(description="The act's page: absolute with a site URL, else root-relative.")
    feed: str | None = Field(
        description="The act's Atom feed, by the same rule; null when the build wrote no feeds."
    )
    eurlex_url: str = Field(description="The act on EUR-Lex, or ''.")
    provisions: dict[str, str] = Field(
        description="Canonical top-level location to its provision page, for every location a "
        "committed change names."
    )
    events: dict[str, str] = Field(
        description="Entry key to its event page, for every committed entry."
    )
    waiting: tuple[CatalogueWaiting, ...] = Field(
        description="Consolidations announced for the act and still waiting for a text, as the "
        "poller's own record held them at build time, oldest first; empty when nothing waits or "
        "the build was handed no record.",
    )


class Catalogue(BaseModel):
    """Every watched act, quiet ones included, sorted by corpus and key."""

    model_config = ConfigDict(frozen=True)

    catalogue_schema: str = Field(
        default=CATALOGUE_SCHEMA, description="The catalogue format's version."
    )
    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    provenance: str = Field(default=PROVENANCE, description="Where this file comes from.")
    acts: tuple[CatalogueAct, ...] = Field(description="One row per watched act.")
    checked_through: date | None = Field(
        description="The end of the last window the poller read, from its own record at build "
        "time: changes published up to this day were looked for. Null when the build was handed "
        "no record or the poller has never closed a window.",
    )


def _address(site: SiteInputs, path: str) -> str:
    return canonical_url(site.site_url, path) if site.site_url else path


def _waiting(site: SiteInputs, act: ActSite) -> tuple[CatalogueWaiting, ...]:
    """The poller's waiting rows for this act. The record keys them by `corpus:key`, and a row
    for an act the watchlist does not hold joins no catalogue row, so it is left out."""
    if site.polled is None:
        return ()
    rows = site.polled.by_act.get(f"{act.act.corpus}:{act.act.key}", ())
    return tuple(
        CatalogueWaiting(version=row.version, state=row.state, first_seen=row.first_seen)
        for row in rows
    )


def _row(site: SiteInputs, act: ActSite) -> CatalogueAct:
    return CatalogueAct(
        corpus=act.act.corpus,
        key=act.act.key,
        label=act.label,
        long_name=act.long_name,
        aliases=act.aliases,
        domain=act.domain,
        url=_address(site, act_href(act.slug)),
        feed=_address(site, feed_path(act)) if site.site_url else None,
        eurlex_url=act.eurlex_url,
        provisions={
            history.location.canonical: _address(
                site, provision_href(act.slug, history.location.canonical)
            )
            for history in histories(act)
        },
        events={
            entry.key: _address(site, event_href(act.slug, entry.key)) for entry in act.entries
        },
        waiting=_waiting(site, act),
    )


def catalogue(site: SiteInputs) -> Catalogue:
    """The catalogue of this build. Pure: the same inputs give the same model."""
    acts = sorted(site.acts, key=lambda act: (act.act.corpus, act.act.key))
    return Catalogue(
        acts=tuple(_row(site, act) for act in acts),
        checked_through=None if site.polled is None else site.polled.checked_through,
    )


def api_files(site: SiteInputs) -> dict[str, str]:
    """Every API file the site writes, as `site-root-relative path -> text`."""
    document = catalogue(site).model_dump(mode="json")
    files = {CATALOGUE: json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"}
    schemas = {**schema_documents(), f"catalogue{SUFFIX}": schema_document("catalogue", Catalogue)}
    files.update({f"{API_ROOT}schema/{name}": text for name, text in schemas.items()})
    return files
