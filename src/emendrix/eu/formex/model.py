"""What the parser returns besides the tree: how much of the document it understood.

A parser that silently drops what it does not recognise is a parser whose quality is a
rumour. Every element the walk cannot place is counted here and the count travels with the
tree, so degradation on a 2006-generation document is a number in a test rather than a
surprise in an eval report.

The numbers measured on the five pinned documents on 2026-08-06 are asserted in
`tests/eu/test_formex_parse.py`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import AmendingActDoc, ProvisionTree

__all__ = ["CoverageCounter", "ParsedAct", "ParsedAmendingAct", "ParserCoverage"]


class ParserCoverage(BaseModel):
    """How much of one Formex package became structure, and what did not.

    `unknown_elements` is the `UNKNOWN(str)` escape hatch in its parser form: an element tag
    outside the documented vocabulary is descended through, counted here, and its text still
    reaches the enclosing node. Coverage gaps are counted, never crashed on and never silently
    dropped.
    """

    model_config = ConfigDict(frozen=True)

    documents: int = Field(default=0, ge=0, description="XML members read as act or annex.")
    documents_unreadable: int = Field(
        default=0, ge=0, description="XML members that would not parse at all."
    )
    units: int = Field(default=0, ge=0, description="Top-level provisions found.")
    nodes: int = Field(default=0, ge=0, description="Located provision nodes, units included.")
    containers_flattened: int = Field(
        default=0,
        ge=0,
        description="Elements that could carry a location but published no usable number.",
    )
    unmapped_identifiers: int = Field(
        default=0, ge=0, description="`IDENTIFIER` values no decoding rule accepted."
    )
    heading_mismatches: int = Field(
        default=0, ge=0, description="`TI.ART` and `IDENTIFIER` naming different articles."
    )
    unreadable_dates: int = Field(
        default=0, ge=0, description="`<DATE>` elements whose `ISO` attribute would not parse."
    )
    unknown_elements: tuple[tuple[str, int], ...] = Field(
        default=(), description="Tag → count, sorted by tag; empty when the vocabulary held."
    )

    @property
    def unknown_total(self) -> int:
        return sum(count for _, count in self.unknown_elements)

    @property
    def clean(self) -> bool:
        """True when nothing at all fell outside the parser's vocabulary."""
        return (
            not self.unknown_elements
            and not self.unmapped_identifiers
            and not self.documents_unreadable
        )


@dataclass
class CoverageCounter:
    """The mutable tally the walk keeps; frozen into a `ParserCoverage` at the end."""

    documents: int = 0
    documents_unreadable: int = 0
    units: int = 0
    nodes: int = 0
    containers_flattened: int = 0
    unmapped_identifiers: int = 0
    heading_mismatches: int = 0
    unreadable_dates: int = 0
    unknown: Counter[str] = field(default_factory=Counter)

    def freeze(self) -> ParserCoverage:
        return ParserCoverage(
            documents=self.documents,
            documents_unreadable=self.documents_unreadable,
            units=self.units,
            nodes=self.nodes,
            containers_flattened=self.containers_flattened,
            unmapped_identifiers=self.unmapped_identifiers,
            heading_mismatches=self.heading_mismatches,
            unreadable_dates=self.unreadable_dates,
            unknown_elements=tuple(sorted(self.unknown.items())),
        )


class ParsedAct(BaseModel):
    """One version of an act, plus what the parse could not account for."""

    model_config = ConfigDict(frozen=True)

    tree: ProvisionTree
    coverage: ParserCoverage = ParserCoverage()


class ParsedAmendingAct(BaseModel):
    """An amending document, plus what the parse could not account for."""

    model_config = ConfigDict(frozen=True)

    document: AmendingActDoc
    coverage: ParserCoverage = ParserCoverage()
