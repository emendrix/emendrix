"""The committed twin maps, read and indexed by act and unit for the pages that mention a twin.

A twin map sits at the changelog repository's root under `twins/`, one file per pair of acts,
and says which units of one act are textually similar to units of the other, at the versions
it names. The site reads those files and nothing else about twins: it never computes a pair,
and a pair it shows is one the committed file holds.

Each map's committed bytes are kept beside the parsed map, keyed by its file stem, because the
site serves the file as committed and a re-serialisation would be a second document under the
record's name.

Missing inputs are stated, not raised: a file that does not validate is named in `unreadable`,
and a map naming an act the site does not show is named in `ignored`, so the build can say
both and still write every page.

The index is built once, from sorted inputs, and every mapping in it keeps the insertion order
it was built in, so two builds of one repository state iterate it alike. `events` answers the
note's one question about the record, whether the instrument that made an event also made an
event of the sister act and which units that event touched, through `amending_keys`, the same
attribution every other page reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, Change
from emendrix.site_.act_site import ActSite
from emendrix.site_.amending import amending_keys
from emendrix.site_.urls import twin_page_href
from emendrix.twins.model import TWINS_DIR, TwinMap, TwinPair, TwinSide, twins_path

__all__ = [
    "NO_TWIN_MAPS",
    "TwinIndex",
    "TwinMaps",
    "TwinSpot",
    "TwinUnit",
    "pair_slug",
    "read_twin_maps",
    "twin_index",
]


class TwinMaps(BaseModel):
    """Every committed twin map, with what the CLI boundary resolved about the versions in it."""

    model_config = ConfigDict(frozen=True)

    maps: tuple[TwinMap, ...] = Field(default=(), description="In sorted path order.")
    unreadable: tuple[str, ...] = Field(
        default=(), description="Repository-relative paths of map files that did not validate."
    )
    dates: Mapping[str, date] = Field(
        default_factory=dict, description="The date each paired version speaks as of, by version."
    )
    urls: Mapping[str, Mapping[str, str]] = Field(
        default_factory=dict,
        description="The public address of each paired coordinate, by version then canonical.",
    )
    raw: Mapping[str, bytes] = Field(
        default_factory=dict,
        description="Each map's committed bytes, by `pair_slug`, so a copy is never re-serialised.",
    )


NO_TWIN_MAPS = TwinMaps()


def pair_slug(document: TwinMap) -> str:
    """The map's file stem, `eu-32017R0745--eu-32017R0746`: the pair's name in every address."""
    path = twins_path(_act(document.a), _act(document.b))
    return path.removeprefix(f"{TWINS_DIR}/").removesuffix(".json")


def read_twin_maps(root: Path) -> TwinMaps:
    """Every `twins/*.json` under one changelog repository, in sorted path order."""
    maps: list[TwinMap] = []
    unreadable: list[str] = []
    raw: dict[str, bytes] = {}
    for path in sorted(root.glob(f"{TWINS_DIR}/*.json")):
        try:
            committed = path.read_bytes()
            document = TwinMap.model_validate_json(committed)
        except (OSError, ValueError):
            unreadable.append(path.relative_to(root).as_posix())
            continue
        maps.append(document)
        raw.setdefault(pair_slug(document), committed)
    return TwinMaps(maps=tuple(maps), unreadable=tuple(unreadable), raw=raw)


class TwinSpot(BaseModel):
    """One coordinate of the sister act, and how textually similar it is to its partner here."""

    model_config = ConfigDict(frozen=True)

    location: str = Field(description="Canonical location in the sister act.")
    ratio: float = Field(description="The map's word ratio, as committed.")
    identical: bool = Field(description="True when the two units' comparison texts are equal.")
    url: str = Field(default="", description="Its public address in the paired version, or ''.")


class TwinUnit(BaseModel):
    """One unit's twin in one sister act, with the children aligned below the pair."""

    model_config = ConfigDict(frozen=True)

    sister: ActSite = Field(description="The act the twin belongs to, as the site shows it.")
    twin: TwinSpot = Field(description="The sister act's unit.")
    children: Mapping[str, TwinSpot] = Field(
        description="This act's aligned descendants, by canonical, to the sister's partner."
    )
    page: bool = Field(description="Whether the sister act has a provision page for the twin.")
    here: str = Field(description="The version of this act the pair was computed on.")
    there: str = Field(description="The version of the sister act the pair was computed on.")
    compare: str = Field(
        default="", description="The pair's own page, site-root-relative; '' when identical."
    )


class TwinIndex(BaseModel):
    """Every twin the committed maps name, by act and unit, and what the build could not read."""

    model_config = ConfigDict(frozen=True)

    units: Mapping[str, Mapping[str, tuple[TwinUnit, ...]]] = Field(
        default_factory=dict, description="By `str(ActId)`, then by the unit's canonical."
    )
    events: Mapping[str, Mapping[str, tuple[Change, ...]]] = Field(
        default_factory=dict,
        description="By `str(ActId)` of a sister act, then by instrument key: every change of "
        "every event of that act the instrument is attributed, newest event first.",
    )
    maps: tuple[TwinMap, ...] = Field(
        default=(), description="The maps whose two acts are both shown, in sorted path order."
    )
    dates: Mapping[str, date] = Field(default_factory=dict, description="As `TwinMaps.dates`.")
    urls: Mapping[str, Mapping[str, str]] = Field(
        default_factory=dict, description="As `TwinMaps.urls`."
    )
    raw: Mapping[str, bytes] = Field(default_factory=dict, description="As `TwinMaps.raw`.")
    unreadable: tuple[str, ...] = Field(default=(), description="As `TwinMaps.unreadable`.")
    ignored: tuple[str, ...] = Field(
        default=(), description="Pairs of acts a map names where the site does not show both."
    )

    def twins(self, act: ActId, canonical: str) -> tuple[TwinUnit, ...]:
        """The unit's twins, one per sister act, in the maps' path order; empty for none."""
        return self.units.get(str(act), {}).get(canonical, ())


def _act(side: TwinSide) -> ActId:
    return ActId(corpus=side.corpus, key=side.key)


def _spot(location: str, ratio: float, identical: bool, version: str, maps: TwinMaps) -> TwinSpot:
    url = maps.urls.get(version, {}).get(location, "")
    return TwinSpot(location=location, ratio=ratio, identical=identical, url=url)


def _unit(
    pair: TwinPair,
    *,
    slug: str,
    flip: bool,
    sister: ActSite,
    pages: set[str],
    here: str,
    there: str,
    maps: TwinMaps,
) -> tuple[str, TwinUnit]:
    """The pair seen from side A, or from side B when `flip`, keyed by this side's unit."""
    mine, theirs = (pair.b, pair.a) if flip else (pair.a, pair.b)
    children = {
        (child.b if flip else child.a): _spot(
            child.a if flip else child.b, child.ratio, pair.identical, there, maps
        )
        for child in pair.children
    }
    return mine, TwinUnit(
        sister=sister,
        twin=_spot(theirs, pair.ratio, pair.identical, there, maps),
        children=children,
        page=theirs in pages,
        here=here,
        there=there,
        compare="" if pair.identical else twin_page_href(slug, pair.a),
    )


def _events(act: ActSite) -> dict[str, tuple[Change, ...]]:
    found: dict[str, tuple[Change, ...]] = {}
    for entry in act.entries:
        changes = tuple(emitted.change for emitted in entry.changes)
        for key in amending_keys(entry):
            found[key] = (*found.get(key, ()), *changes)
    return found


def twin_index(maps: TwinMaps, acts: tuple[ActSite, ...]) -> TwinIndex:
    """Index every map whose two acts are both shown; name the rest in `ignored`."""
    shown = {str(item.act): item for item in acts}
    units: dict[str, dict[str, tuple[TwinUnit, ...]]] = {}
    events: dict[str, Mapping[str, tuple[Change, ...]]] = {}
    ignored: list[str] = []
    shown_maps: list[TwinMap] = []
    for document in maps.maps:
        a, b = shown.get(str(_act(document.a))), shown.get(str(_act(document.b)))
        if a is None or b is None:
            ignored.append(f"{_act(document.a)} and {_act(document.b)}")
            continue
        shown_maps.append(document)
        slug = pair_slug(document)
        sides = (
            (a, b, document.a.version, document.b.version, False),
            (b, a, document.b.version, document.a.version, True),
        )
        for here, sister, mine, theirs, flip in sides:
            pages = {e.change.location.canonical for entry in sister.entries for e in entry.changes}
            into = units.setdefault(str(here.act), {})
            for pair in document.pairs:
                unit, found = _unit(
                    pair,
                    slug=slug,
                    flip=flip,
                    sister=sister,
                    pages=pages,
                    here=mine,
                    there=theirs,
                    maps=maps,
                )
                into[unit] = (*into.get(unit, ()), found)
            if str(sister.act) not in events:
                events[str(sister.act)] = _events(sister)
    return TwinIndex(
        units=units,
        events=events,
        maps=tuple(shown_maps),
        dates=maps.dates,
        urls=maps.urls,
        raw=maps.raw,
        unreadable=maps.unreadable,
        ignored=tuple(ignored),
    )
