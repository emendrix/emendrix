"""What the text store holds, line by line, and the answers a read can give instead of a file.

A version file is gzipped JSON lines: one `StoredVersion` header, then one `StoredNode` per node
of the tree in pre-order. `states.json` beside it is one `StatesFile`. Every model is frozen and
serialised in declaration order, which is half of what makes a file the same bytes on a rerun.
Nothing here names a corpus: the store keeps whatever an adapter's trees hold.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MARKER_FILE",
    "STATES_FILE",
    "STORE_SCHEMA",
    "VERSION_SUFFIX",
    "StatesFile",
    "StoredNode",
    "StoredState",
    "StoredVersion",
    "StoredVersionFile",
    "UnreadableVersion",
]

STORE_SCHEMA: Final = "1.0"
MARKER_FILE: Final = ".emendrix-texts"
STATES_FILE: Final = "states.json"
VERSION_SUFFIX: Final = ".jsonl.gz"


class StoredVersion(BaseModel):
    """The first line of a version file: which version this is and how much follows."""

    model_config = ConfigDict(frozen=True)

    store_schema: Literal["1.0"] = Field(description="The layout this file was written in.")
    corpus: str = Field(description="The adapter namespace the act belongs to.")
    key: str = Field(description="The act's opaque key within its corpus.")
    version: str = Field(description="The version asked for, which also names the file.")
    served_version: str = Field(
        description="The version the adapter actually served; differs when it fell back."
    )
    language: str | None = Field(description="The language of the text, as the tree states it.")
    nodes: int = Field(ge=0, description="How many node lines follow this header.")
    units: int = Field(ge=0, description="How many of those nodes are top-level units.")


class StoredNode(BaseModel):
    """One node of the tree, its text verbatim, and where it hangs."""

    model_config = ConfigDict(frozen=True)

    location: str = Field(description="The node's canonical location string.")
    parent: str | None = Field(
        description="The canonical location of the parent node; `None` for a top-level unit."
    )
    heading: str | None = Field(description="The node's heading, verbatim.")
    text: str = Field(description="The node's text, verbatim: its whole subtree.")
    comparison_text: str = Field(description="The whitespace-normalised form the diff compares.")
    digest: str = Field(description="sha256 hex of `comparison_text` in UTF-8, for deduplication.")


class StoredState(BaseModel):
    """A version the adapter answered with a state rather than a tree."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(description="The version asked for.")
    state: str = Field(description="The state's tag, as the adapter's state carries it.")
    detail: str = Field(default="", description="What the adapter said about it, verbatim.")


class StatesFile(BaseModel):
    """`states.json`: every state recorded for one act, sorted by version."""

    model_config = ConfigDict(frozen=True)

    store_schema: Literal["1.0"] = Field(description="The layout this file was written in.")
    states: tuple[StoredState, ...] = Field(default=(), description="Sorted by version.")


class StoredVersionFile(BaseModel):
    """A version file read back whole: its header and its nodes in pre-order."""

    model_config = ConfigDict(frozen=True)

    header: StoredVersion = Field(description="The file's first line.")
    nodes: tuple[StoredNode, ...] = Field(description="Every node line, in file order.")


class UnreadableVersion(BaseModel):
    """A version file that exists but does not decompress, validate or rebuild into a tree.

    A counted, reported answer, never an exception: the file is rebuilt from the corpus with
    `texts build --rebuild`, because the store is never the source of truth.
    """

    model_config = ConfigDict(frozen=True)

    state: Literal["unreadable"] = "unreadable"
    version: str = Field(description="The version whose file could not be read.")
    detail: str = Field(description="Why, in one line.")
