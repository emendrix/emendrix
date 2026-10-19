"""The twin map: which units of one act are textually similar to units of another.

One JSON document per pair of acts, committed into the changelog repository at
`twins/<corpus>-<keyA>--<corpus>-<keyB>.json` with the lower act first. "Twin" means textually
similar by the measure in `TwinMethod` and nothing more: a pair says nothing about what either
provision requires, or whether one should change because the other did.

Every model is frozen and serialised in declaration order, and every tuple is built in an order
stated where it is built, which is what makes a rebuild over the same texts the same bytes.
Nothing here names a corpus: a map is computed from any two adapter trees.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId
from emendrix.output.json_out import slug

__all__ = [
    "TWINS_DIR",
    "TWINS_SCHEMA",
    "AlignedChild",
    "Passage",
    "TwinMap",
    "TwinMethod",
    "TwinPair",
    "TwinSide",
    "Unpaired",
    "ordered",
    "twins_path",
]

TWINS_SCHEMA: Final = "1.0"
TWINS_DIR: Final = "twins"


class TwinMethod(BaseModel):
    """How the ratios were computed, and the floor a pair must reach to be a twin."""

    model_config = ConfigDict(frozen=True)

    measure: Literal["word-ratio"] = Field(
        description=(
            "difflib.SequenceMatcher(None, a_words, b_words, autojunk=False).ratio() over the "
            "whitespace-split comparison texts of the two provisions."
        )
    )
    floor: float = Field(ge=0.0, le=1.0, description="The least ratio a twin pair reaches.")
    verified_on: str = Field(description="The date the floor was read off the corpus, ISO.")


class TwinSide(BaseModel):
    """One of the two acts, and the version of it the map was computed on."""

    model_config = ConfigDict(frozen=True)

    corpus: str = Field(description="The adapter namespace the act belongs to.")
    key: str = Field(description="The act's opaque key within its corpus.")
    version: str = Field(description="The version whose texts were compared.")


class AlignedChild(BaseModel):
    """Two provisions below a twin pair, aligned by the same measure and floor."""

    model_config = ConfigDict(frozen=True)

    a: str = Field(description="Canonical location in act A.")
    b: str = Field(description="Canonical location in act B.")
    ratio: float = Field(description="The word ratio, rounded to 3 places.")


class Passage(BaseModel):
    """One differing span, with a few equal words of context either side.

    An excerpt of the comparison texts (whitespace collapsed), for reading the difference;
    it is not the verbatim text, which the two acts' own publications carry.
    """

    model_config = ConfigDict(frozen=True)

    a: str = Field(description="The span in A with its context; context alone where B adds words.")
    b: str = Field(description="The span in B with its context; context alone where B drops words.")
    cut: bool = Field(description="True when either side was cut short, marked with `[…]`.")


class TwinPair(BaseModel):
    """Two units, each the other's best match at or above the floor."""

    model_config = ConfigDict(frozen=True)

    a: str = Field(description="Canonical unit location in act A.")
    b: str = Field(description="Canonical unit location in act B.")
    ratio: float = Field(description="The word ratio, rounded to 3 places.")
    identical: bool = Field(description="True when the two comparison texts are equal.")
    children: tuple[AlignedChild, ...] = Field(
        description="Descendants aligned level by level, below aligned parents only, in A's order."
    )
    passages: tuple[Passage, ...] = Field(
        description="The first differing spans, up to the cap; empty when identical or withheld."
    )
    passages_omitted: int = Field(
        ge=0, description="Differing spans beyond the cap, counted and not shown; 0 when withheld."
    )
    passages_withheld: bool = Field(
        description="True when the spans would show too large a share of either text to excerpt."
    )
    headings_equal: bool = Field(
        description="Whether the normalised headings are equal: published, no part of the pairing."
    )


class Unpaired(BaseModel):
    """A unit with no twin, and the unit it matched best if that reached the floor."""

    model_config = ConfigDict(frozen=True)

    unit: str = Field(description="Canonical unit location in this act.")
    best: str | None = Field(
        description="Its best match at or above the floor, which preferred another unit; null "
        "when no unit of the other act reaches the floor."
    )
    ratio: float | None = Field(description="The ratio to `best`, rounded to 3 places.")


class TwinMap(BaseModel):
    """Every twin pair of two acts' units, with the units left unpaired on either side."""

    model_config = ConfigDict(frozen=True)

    twins_schema: Literal["1.0"] = Field(description="The layout this document was written in.")
    disclaimer: str = Field(description="The not-legal-advice disclaimer, verbatim.")
    method: TwinMethod = Field(description="How the pairs were computed.")
    a: TwinSide = Field(description="The act with the lower key.")
    b: TwinSide = Field(description="The act with the higher key.")
    pairs: tuple[TwinPair, ...] = Field(description="In A's document order.")
    unpaired_a: tuple[Unpaired, ...] = Field(description="A's units with no twin, location order.")
    unpaired_b: tuple[Unpaired, ...] = Field(description="B's units with no twin, location order.")


def ordered(first: ActId, second: ActId) -> tuple[ActId, ActId]:
    """The two acts lower first, by `(corpus, key)`: the order every map is written in."""
    return (
        (first, second)
        if (first.corpus, first.key) <= (second.corpus, second.key)
        else (
            second,
            first,
        )
    )


def twins_path(a: ActId, b: ActId) -> str:
    """`twins/eu-32017R0745--eu-32017R0746.json`, relative to the repository root."""
    low, high = ordered(a, b)
    left = f"{slug(low.corpus)}-{slug(low.key)}"
    right = f"{slug(high.corpus)}-{slug(high.key)}"
    return f"{TWINS_DIR}/{left}--{right}.json"
