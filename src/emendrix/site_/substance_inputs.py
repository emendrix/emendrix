"""Where each CAS and EC number appears: the registers read off disk, and every entry change.

A payload holds only what changed, so an entry nobody amended since the first version the record
holds is in no payload at all. The register beside each act's changelog holds the newest
version's whole reading, and this module reads it through the same changelogs directory the
payloads come from:

```
<output-repo>/<corpus>/<act>/register.json   every table entry of the act's newest version
```

Both are inverted here into one row per identifier: the register entries that print it now
(`Holding`) and every recorded `EntryChange` whose before or after side carries it (`Moved`),
so an entry that was removed keeps its history and its page. Only `cas` and `ec` are addressed;
a row key such as an Index No is shown and searched, never given a page of its own.

An EC page defers to a CAS page when the two say the same thing: it holds exactly the entries
and the changes of one CAS page it links, and no other. Its own page is still written, and is
canonical to that CAS page and kept out of the sitemap. Everything else is its own canonical.

Only the acts this build shows are read, because a substance page links an act page, and an
act the watchlist leaves out has none. Nothing here reads a clock, a socket or a model; every
list is sorted explicitly so two builds of one repository state produce one tree.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from emendrix.core import Identifier, TableEntry
from emendrix.output import REGISTER_FILE, Register
from emendrix.site_.act_site import ActSite
from emendrix.site_.substance_model import (
    NO_LINKS,
    PAGED,
    Holding,
    IndexLabel,
    Moved,
    Substance,
    SubstanceInputs,
    SubstanceLinks,
    identifier_order,
)
from emendrix.site_.urls import entry_anchors

__all__ = [
    "NO_LINKS",
    "PAGED",
    "Holding",
    "IndexLabel",
    "Moved",
    "Substance",
    "SubstanceInputs",
    "SubstanceLinks",
    "collect_substances",
    "identifier_order",
    "read_registers",
]


def read_registers(root: Path) -> tuple[Register, ...]:
    """Every register in one output repository, in sorted path order.

    A file that does not validate is refused by name, as `read_entries` refuses a payload: the
    register is written by the same writer, and a broken one is not something to skip quietly.
    """
    registers: list[Register] = []
    for path in sorted(root.glob(f"*/*/{REGISTER_FILE}")):
        try:
            registers.append(Register.model_validate_json(path.read_bytes()))
        except ValueError as error:
            raise ValueError(f"{path} is not a register emendrix wrote: {error}") from error
    return tuple(registers)


def _moves(acts: Iterable[ActSite]) -> list[Moved]:
    """Every recorded entry change of the shown acts, newest first, stably."""
    moves: list[Moved] = []
    for act in acts:
        for event in act.entries:
            anchors = entry_anchors(event.key, [e.change.location.canonical for e in event.changes])
            for index, emitted in enumerate(event.changes):
                delta = emitted.change.table_entries
                if delta is None:
                    continue
                tables = {(t.container, t.table): t for t in delta.tables}
                moves.extend(
                    Moved(
                        act=act,
                        event=event,
                        index=index,
                        position=position,
                        anchor=anchors[index],
                        table=tables.get((change.container, change.table)),
                        change=change,
                    )
                    for position, change in enumerate(delta.changes)
                )
    moves.sort(key=lambda moved: moved.dated.on, reverse=True)
    return moves


def _holdings(registered: Iterable[tuple[ActSite, Register]]) -> list[Holding]:
    holdings: list[Holding] = []
    for act, register in registered:
        tables = {(t.container, t.table): t for t in register.tables}
        holdings.extend(
            Holding(
                act=act,
                version=register.version,
                position=position,
                table=tables.get((entry.container, entry.table)),
                entry=entry,
            )
            for position, entry in enumerate(register.entries)
        )
    return holdings


def _same(one: Substance, other: Substance) -> bool:
    """Whether two pages hold exactly the same entries and the same changes."""
    return {(h.act.act, h.position) for h in one.holdings} == {
        (h.act.act, h.position) for h in other.holdings
    } and {(m.act.act, m.event.key, m.index, m.position) for m in one.history} == {
        (m.act.act, m.event.key, m.index, m.position) for m in other.history
    }


def _canonical(found: dict[tuple[str, str], Substance]) -> dict[tuple[str, str], Substance]:
    """Each EC page that repeats exactly one CAS page it links, pointed at that page."""
    resolved = dict(found)
    for key, substance in found.items():
        if substance.scheme != "ec":
            continue
        linked = [
            found[(one.scheme, one.value)]
            for one in substance.identifiers
            if one.scheme == "cas" and (one.scheme, one.value) in found
        ]
        equal = [other for other in linked if _same(substance, other)]
        if len(equal) == 1:
            target = Identifier(scheme="cas", value=equal[0].value)
            resolved[key] = substance.model_copy(update={"canonical": target})
    return resolved


def _labels(
    entries: Iterable[TableEntry], found: dict[tuple[str, str], Substance]
) -> tuple[tuple[IndexLabel, ...], tuple[Identifier, ...]]:
    """Each unpaged identifier, labelled with the first entry carrying it that names a page."""
    labelled: dict[tuple[str, str], IndexLabel] = {}
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        targets = [one for scheme in PAGED for one in entry.identifiers if one.scheme == scheme]
        targets = [one for one in targets if (one.scheme, one.value) in found]
        for one in entry.identifiers:
            key = (one.scheme, one.value)
            if one.scheme in PAGED:
                continue
            seen.add(key)
            if key not in labelled and targets:
                labelled[key] = IndexLabel(scheme=one.scheme, value=one.value, target=targets[0])
    order = sorted(seen, key=lambda pair: identifier_order(*pair))
    return (
        tuple(labelled[key] for key in order if key in labelled),
        tuple(Identifier(scheme=s, value=v) for s, v in order if (s, v) not in labelled),
    )


def collect_substances(
    acts: tuple[ActSite, ...], registers: tuple[Register, ...]
) -> SubstanceInputs:
    """The inverted index over the shown acts' registers and recorded entry changes. Pure."""
    shown = {(act.act.corpus, act.act.key): act for act in acts}
    by_act = {(register.corpus, register.key): register for register in registers}
    registered = tuple((act, by_act[key]) for key, act in shown.items() if key in by_act)
    holdings = _holdings(registered)
    moves = _moves(acts)
    places: dict[tuple[str, str], tuple[list[Holding], list[Moved]]] = {}
    for holding in holdings:
        for one in holding.entry.identifiers:
            if one.scheme in PAGED:
                places.setdefault((one.scheme, one.value), ([], []))[0].append(holding)
    for moved in moves:
        sides = [side for side in (moved.change.before, moved.change.after) if side is not None]
        carried = {(one.scheme, one.value) for side in sides for one in side.identifiers}
        for key in sorted(carried):
            if key[0] in PAGED:
                places.setdefault(key, ([], []))[1].append(moved)
    found = {
        key: Substance(scheme=key[0], value=key[1], holdings=tuple(held), history=tuple(moved))
        for key, (held, moved) in places.items()
    }
    found = _canonical(found)
    sides = [side for m in moves for side in (m.change.after, m.change.before) if side]
    labels, unlabelled = _labels([h.entry for h in holdings] + sides, found)
    return SubstanceInputs(
        registered=registered,
        substances=tuple(found[key] for key in sorted(found, key=lambda k: identifier_order(*k))),
        labels=labels,
        unlabelled=unlabelled,
        pages=frozenset(substance.slug for substance in found.values()),
        touched={
            act.slug: frozenset(
                emitted.change.location.canonical
                for entry in act.entries
                for emitted in entry.changes
            )
            for act in acts
        },
    )
