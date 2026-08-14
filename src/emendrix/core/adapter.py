"""The seam: everything a corpus must supply, and nothing more.

Four methods. Discover the versions of an act, fetch one as a provision tree, parse an
amending document, render a citation. That is the entire core-facing contract: anything
corpus-specific (modification metadata, a notification feed) is a capability of that
adapter, consumed directly by the modules that need it, and never widens this Protocol.

The core therefore knows nothing about EU law, and an adapter for a corpus that is not law
at all satisfies the same interface (see `tests/toy_corpus.py`, the second implementor).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from emendrix.core.changes import ChangeType
from emendrix.core.citations import Citation
from emendrix.core.identifiers import ActId, ProvisionRef, VersionDescriptor, VersionId
from emendrix.core.location import ProvisionLocation
from emendrix.core.provisions import ComparisonText, ProvisionText, ProvisionTree
from emendrix.core.states import Unavailable

__all__ = ["AmendingActDoc", "CorpusAdapter", "QuotedProvision"]


class QuotedProvision(BaseModel):
    """Replacement or inserted text quoted inside an amending document.

    Amending prose states its target but routinely omits the identifier of what it inserts
    ("the following Article is inserted:"); the identifier is recoverable from the quoted
    provision itself (verified 2026-08-05). So `location`, `amended_act` and
    `stated_change_type` are all optional: what the document did not say is represented as
    absent, not guessed.

    `amended_act` exists because one amending document routinely amends several acts in
    parallel instruction articles, so a quotation's location means nothing without knowing
    which act it lands in (measured 2026-08-06 on `32026R1744`, which amends three).
    """

    model_config = ConfigDict(frozen=True)

    location: ProvisionLocation | None = None
    amended_act: ActId | None = None
    stated_change_type: ChangeType | None = None
    text: ProvisionText
    comparison_text: ComparisonText


class AmendingActDoc(BaseModel):
    """A document that amends another one: its own provision tree plus what it quotes."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    tree: ProvisionTree
    amends: tuple[ActId, ...] = ()
    quoted: tuple[QuotedProvision, ...] = ()


@runtime_checkable
class CorpusAdapter(Protocol):
    """The whole contract between the generic engine and one corpus.

    Implementations may hit the network *behind a disk cache* inside `discover_versions`,
    `fetch_version` and `parse_amending_act`. Everything downstream of them is pure: diff,
    classification, corroboration, gating, rendering.
    """

    def discover_versions(self, act: ActId) -> list[VersionDescriptor]:
        """Every version of `act` this corpus knows about, oldest first."""
        ...

    def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
        """The text of one version, or a first-class state saying why there is none."""
        ...

    def parse_amending_act(self, act: ActId) -> AmendingActDoc | Unavailable:
        """The amending document `act`, or a first-class state saying why there is none."""
        ...

    def render_citation(self, ref: ProvisionRef) -> Citation:
        """A clickable, human-labelled citation for one provision."""
        ...
