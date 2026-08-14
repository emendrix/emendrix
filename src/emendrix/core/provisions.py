"""The provision tree: the text of one version of an act, keyed by location.

Every node carries **two** text forms. `text` is verbatim: the characters the source produced,
in the source's own spacing, never normalised and never collapsed, because output quotes must be
verbatim. `comparison_text` is the form the diff compares, built by the parser *at extraction
time* with a separator at every element boundary and whitespace collapsed afterwards. The second
cannot be derived from the first: on the 2008→2009 REACH pair, extraction that loses those
boundaries reports all 143 units as modified against 40 real ones (measured 2026-08-05).

A parser reading a *tree* has no character stream to transcribe and must decide how to
serialise one; where the markup opens a block and the source supplies no text, `text` may
carry a line break, so that a title does not run into its subtitle. That is a serialisation
choice made once at extraction and it is the only thing ever inserted. What the rule forbids
is editing a stored text afterwards, and nothing downstream of extraction does.

This module knows nothing about markup, files or corpora: it is the shape the parsers produce
and the diff consumes.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from typing import Final, NewType, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from emendrix.core.identifiers import ActId, VersionId
from emendrix.core.location import ProvisionLocation

__all__ = [
    "ComparisonText",
    "DateMention",
    "ProvisionNode",
    "ProvisionText",
    "ProvisionTree",
    "normalize_for_comparison",
]

ProvisionText = NewType("ProvisionText", str)
"""Verbatim provision text. Never normalised, never truncated without a visible marker."""

ComparisonText = NewType("ComparisonText", str)
"""The whitespace-collapsed form used *only* for comparison. Never quoted in output."""

_WHITESPACE: Final = re.compile(r"\s+")


def normalize_for_comparison(text: str) -> ComparisonText:
    """Collapse whitespace for comparison.

    Call this on text whose element boundaries are already separated: collapsing runs of
    whitespace cannot put back a boundary that extraction never emitted. It is a pure
    function and it never touches stored text.

    **Whitespace and nothing else, deliberately.** A no-break space collapses like any other
    space, so a run of them moving is not a difference. Every character that is not whitespace
    is a difference, a typographic one included. The AI Act's Article 1 heading is the worked
    case: it acquired a different apostrophe between the OJ publication and the consolidation,
    and its unit reports `MODIFIED`. Verified 2026-08-12 that the character is a literal byte
    in the Publications Office's own document and that the pinned fixture and the cached blob
    are byte-identical, so there is nothing upstream to fix and nothing here to route around.

    That is the answer rather than an open gap. Ruling some character swaps not to count would
    take a table of characters declared equivalent, and such a table normalises the source
    itself rather than its layout, which is a judgement about legal text that no deterministic
    stage of this loop is allowed to make. Whitespace earns its exemption because the
    serialisation chose it and the drafter did not. The two errors are also not symmetric:
    over-reporting costs a reader the moment it takes to read a word-level diff showing that
    one character moved, while under-reporting tells them a provision is unchanged when it is
    not, and only the first of those is recoverable by the reader.
    """
    return ComparisonText(_WHITESPACE.sub(" ", text).strip())


def _as_location(location: ProvisionLocation | str) -> ProvisionLocation:
    if isinstance(location, ProvisionLocation):
        return location
    return ProvisionLocation.parse(location)


class DateMention(BaseModel):
    """A machine-readable date found in provision text, with the slice around it.

    Feeds the second clock: a date is only ever *quoted*, never interpreted into an
    applicability rule by the model.
    """

    model_config = ConfigDict(frozen=True)

    value: date
    context: str = Field(default="", description="Verbatim slice surrounding the date.")


class ProvisionNode(BaseModel):
    """One provision and everything under it, in document order."""

    model_config = ConfigDict(frozen=True)

    location: ProvisionLocation
    heading: str | None = None
    text: ProvisionText
    comparison_text: ComparisonText
    dates: tuple[DateMention, ...] = ()
    children: tuple[ProvisionNode, ...] = ()

    @model_validator(mode="after")
    def _children_are_within(self) -> Self:
        for child in self.children:
            if not self.location.contains(child.location):
                raise ValueError(
                    f"child location {child.location.canonical!r} is not within "
                    f"{self.location.canonical!r}"
                )
        return self

    @classmethod
    def from_plain_text(
        cls,
        location: ProvisionLocation | str,
        text: str,
        *,
        heading: str | None = None,
        dates: tuple[DateMention, ...] = (),
        children: tuple[ProvisionNode, ...] = (),
    ) -> Self:
        """Build a node whose comparison form is just its whitespace-collapsed text.

        Only correct for sources with no markup to lose (a plain-text corpus, a fixture).
        A markup parser must build `comparison_text` during extraction instead — see the
        module docstring.
        """
        return cls(
            location=_as_location(location),
            heading=heading,
            text=ProvisionText(text),
            comparison_text=normalize_for_comparison(text),
            dates=dates,
            children=children,
        )

    def walk(self) -> Iterator[ProvisionNode]:
        """This node and its descendants, in document order (pre-order)."""
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, location: ProvisionLocation) -> ProvisionNode | None:
        """The node at `location` within this subtree, or `None`."""
        if location == self.location:
            return self
        if not self.location.contains(location):
            return None
        for child in self.children:
            found = child.find(location)
            if found is not None:
                return found
        return None


class ProvisionTree(BaseModel):
    """One version of one act, as a forest of top-level provisions in document order."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    version: VersionId
    language: str | None = None
    roots: tuple[ProvisionNode, ...] = ()

    def walk(self) -> Iterator[ProvisionNode]:
        """Every node, in document order."""
        for root in self.roots:
            yield from root.walk()

    def find(self, location: ProvisionLocation | str) -> ProvisionNode | None:
        """The node at `location`, or `None` if this version has no such provision."""
        target = _as_location(location)
        for root in self.roots:
            found = root.find(target)
            if found is not None:
                return found
        return None

    def locations(self) -> tuple[ProvisionLocation, ...]:
        """Every location in the tree, in document order."""
        return tuple(node.location for node in self.walk())

    def unit_locations(self) -> tuple[ProvisionLocation, ...]:
        """The top-level units (the unit of change), in document order."""
        return tuple(root.location for root in self.roots)
