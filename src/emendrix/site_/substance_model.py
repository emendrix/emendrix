"""The substance surface's vocabulary: an entry held now, a change recorded, a number's page.

Split out of `substance_inputs` on 2026-10-17, when that module passed the size cap. The seam is
the one between what the surface is made of and how it is gathered: these are the frozen values
every renderer of the surface reads, and `substance_inputs` reads the registers off disk and
inverts them into these values. `substance_inputs` re-exports every name, so a caller may import
from either module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import EntryChange, EntryTable, Identifier, TableEntry
from emendrix.output import ChangelogEntry, Register
from emendrix.site_.act_site import ActSite
from emendrix.site_.clocks import EventDate, event_date
from emendrix.site_.urls import substance_href

__all__ = [
    "NO_LINKS",
    "PAGED",
    "Holding",
    "IndexLabel",
    "Moved",
    "Substance",
    "SubstanceInputs",
    "SubstanceLinks",
    "identifier_order",
]

PAGED: Final = ("cas", "ec")
"""The schemes that get a page. Anything else an entry carries is shown, never addressed."""

_DIGITS: Final = re.compile(r"(\d+)")


def identifier_order(scheme: str, value: str) -> tuple[str, tuple[tuple[int, str], ...]]:
    """`cas 50-00-0` before `cas 100-00-5`: digit runs compared as numbers, the rest as text."""
    parts = _DIGITS.split(value)
    return scheme, tuple((int(part), "") if part.isdigit() else (0, part) for part in parts)


@dataclass(frozen=True)
class SubstanceLinks:
    """Which identifiers have a page, and the climb back to the root a page links them from.

    A dataclass rather than a model because one is made per rendered page over a set of every
    page's slug, and validating that set thousands of times would be the slowest line of a build.
    """

    root: str
    pages: frozenset[str]

    def href(self, scheme: str, value: str) -> str | None:
        """The identifier's page under `root`, or None where no page exists to link."""
        if f"{scheme}-{value}" not in self.pages:
            return None
        return f"{self.root}{substance_href(scheme, value)}"


NO_LINKS: Final = SubstanceLinks(root="", pages=frozenset())
"""What a renderer with no substance pages to point at is handed: nothing links."""


class Holding(BaseModel):
    """One entry of an act's newest version, as its register holds it."""

    model_config = ConfigDict(frozen=True)

    act: ActSite = Field(description="The act whose register holds the entry.")
    version: str = Field(description="The version the register was read from.")
    position: int = Field(ge=0, description="The entry's place in the register, document order.")
    table: EntryTable | None = Field(
        description="The entry's table; None if the register omits it."
    )
    entry: TableEntry = Field(description="The entry, its rows verbatim.")


class Moved(BaseModel):
    """One recorded change to one entry, with the event and the change block that carry it."""

    model_config = ConfigDict(frozen=True)

    act: ActSite = Field(description="The act the change was recorded for.")
    event: ChangelogEntry = Field(description="The committed event holding the change.")
    index: int = Field(ge=0, description="Position of the change in `event.changes`.")
    position: int = Field(ge=0, description="Position of the entry change in its delta.")
    anchor: str = Field(description="The change block's fragment on the event page.")
    table: EntryTable | None = Field(description="The entry's table, from the delta.")
    change: EntryChange = Field(description="The entry change itself.")

    @property
    def dated(self) -> EventDate:
        """The event's date with its clock, the one every dated line on the site prints."""
        return event_date(self.event)

    @property
    def side(self) -> TableEntry:
        """The newer side where there is one, else the side that was removed."""
        found = self.change.after or self.change.before
        assert found is not None
        return found


class Substance(BaseModel):
    """One CAS or EC number: every entry that prints it now, and every change that named it."""

    model_config = ConfigDict(frozen=True)

    scheme: str = Field(description="`cas` or `ec`.")
    value: str = Field(description="The canonical value.")
    holdings: tuple[Holding, ...] = Field(default=(), description="Act order, then document.")
    history: tuple[Moved, ...] = Field(default=(), description="Newest first.")
    canonical: Identifier | None = Field(
        default=None, description="The CAS number whose page this one defers to; None for self."
    )

    @property
    def slug(self) -> str:
        """`cas-50-00-0`: the page's directory and the API file's name."""
        return f"{self.scheme}-{self.value}"

    @cached_property
    def identifiers(self) -> tuple[Identifier, ...]:
        """Every identifier the rows carry, this one included, sorted for display. Computed once
        per number, since the page, its file and the canonical rule all read it."""
        found: set[tuple[str, str]] = set()
        for holding in self.holdings:
            found.update((one.scheme, one.value) for one in holding.entry.identifiers)
        for moved in self.history:
            for side in (moved.change.before, moved.change.after):
                if side is not None:
                    found.update((one.scheme, one.value) for one in side.identifiers)
        found.add((self.scheme, self.value))
        ordered = sorted(found, key=lambda pair: identifier_order(*pair))
        return tuple(Identifier(scheme=scheme, value=value) for scheme, value in ordered)


class IndexLabel(BaseModel):
    """A row key carried as an identifier (an Index No), and the page a search for it lands on."""

    model_config = ConfigDict(frozen=True)

    scheme: str = Field(description="The key's scheme, `index`.")
    value: str = Field(description="The canonical value.")
    target: Identifier = Field(description="The first CAS, else EC, number its entry carries.")


class SubstanceInputs(BaseModel):
    """What the substance surface renders, resolved once per build."""

    model_config = ConfigDict(frozen=True)

    registered: tuple[tuple[ActSite, Register], ...] = Field(
        default=(), description="The registers of the acts this build shows, in roster order."
    )
    substances: tuple[Substance, ...] = Field(
        default=(), description="Every paged identifier, sorted by scheme then value."
    )
    labels: tuple[IndexLabel, ...] = Field(
        default=(), description="Every other identifier with a page to land on, sorted."
    )
    unlabelled: tuple[Identifier, ...] = Field(
        default=(), description="Other identifiers whose entries carry no CAS or EC number."
    )
    pages: frozenset[str] = Field(
        default=frozenset(), description="Every substance page's slug, `cas-50-00-0`."
    )
    touched: dict[str, frozenset[str]] = Field(
        default_factory=dict,
        description="Per act slug, the units a recorded change touched: those with a page.",
    )

    def has_register(self, act: ActSite) -> bool:
        """Whether the act's tables are read as entries at all: what an act page's door asks."""
        return any(held.act == act.act for held, _ in self.registered)

    def links(self, root: str) -> SubstanceLinks:
        """The links a page at the climb `root` gives the numbers it prints."""
        return SubstanceLinks(root=root, pages=self.pages)
