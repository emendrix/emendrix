"""One committed payload as a reader reads it: the event, its changes, its corroboration.

A reader's own models of the document `emendrix` commits per event, for the same reason as
`models.py`: a reader must not import `emendrix`. They carry only what a reader hands over, and
default every field a document written before the field existed lacks, exactly as the writer's
own models default it. `dispute_reason` is the one a reader must not trust here: older payloads
do not store it, so a reader takes the reason from the index row, which always carries it.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ActRef",
    "Agreement",
    "ApplicabilityUnchanged",
    "ApplicabilityUnknown",
    "ChangeRecord",
    "CitationRecord",
    "Corroboration",
    "Disagreement",
    "Observation",
    "Observations",
    "Payload",
    "ProvisionRef",
    "Sentence",
    "SignalUnits",
    "StoredChange",
]

_FROZEN = ConfigDict(frozen=True)


class ActRef(BaseModel):
    """An act as a payload names it."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    display_name: str | None = Field(default=None, description="The watchlist's name, if any.")


class ProvisionRef(BaseModel):
    """One provision of one version of one act."""

    model_config = _FROZEN

    act: ActRef = Field(description="The act the provision belongs to.")
    version: str = Field(description="The version the reference points into.")
    location: str = Field(description="The provision's canonical location string.")


class Observation(BaseModel):
    """What one signal said about one change."""

    model_config = _FROZEN

    status: str = Field(default="unavailable", description="`observed`, `absent`, `unavailable`.")
    detail: str | None = Field(default=None, description="The signal's own note, as stored.")
    change_types: tuple[str, ...] = Field(default=(), description="Kinds the signal named.")


class Observations(BaseModel):
    """The three signals on one change, with their stored detail."""

    model_config = _FROZEN

    structural_diff: Observation = Field(default=Observation(), description="The text diff.")
    corpus_metadata: Observation = Field(default=Observation(), description="Corpus metadata.")
    instruction_parse: Observation = Field(
        default=Observation(), description="The amending act's instructions."
    )


class ApplicabilityUnknown(BaseModel):
    """No application date could be read deterministically, which is never "no date applies"."""

    model_config = _FROZEN

    kind: Literal["unknown"] = Field(default="unknown", description="Always `unknown`.")
    reason: str | None = Field(default=None, description="Why no date was read, when given.")


class ApplicabilityUnchanged(BaseModel):
    """The change moved no application date."""

    model_config = _FROZEN

    kind: Literal["unchanged"] = Field(default="unchanged", description="Always `unchanged`.")


class CitationRecord(BaseModel):
    """A resolvable reference a sentence cites."""

    model_config = _FROZEN

    ref: ProvisionRef = Field(description="The provision cited.")
    url: str = Field(description="Where a reader sees the provision, as the payload stores it.")
    label: str = Field(description="The display form the payload stores.")


class Sentence(BaseModel):
    """One sentence of a change's explanation, with what it cites."""

    model_config = _FROZEN

    text: str = Field(description="The sentence as stored.")
    fallback: bool = Field(default=False, description="Written by the gate as a quotation.")
    citations: tuple[CitationRecord, ...] = Field(default=(), description="What it cites.")


class StoredChange(BaseModel):
    """The deterministic facts of one change, as the payload stores them."""

    model_config = _FROZEN

    change_type: str = Field(description="The change's type as the structural diff named it.")
    provision: ProvisionRef = Field(description="The changed provision and its version.")
    heading: str | None = Field(default=None, description="The provision's heading, if any.")
    before: str | None = Field(default=None, description="Verbatim text before; null if none.")
    after: str | None = Field(default=None, description="Verbatim text after; null if none.")
    previous_location: str | None = Field(default=None, description="Location before renumbering.")
    changed_within: tuple[str, ...] = Field(default=(), description="Sub-provisions that differ.")
    amending_acts: tuple[ActRef, ...] = Field(default=(), description="Acts named as amending it.")
    dates_removed: tuple[date, ...] = Field(default=(), description="Dates carried before only.")
    dates_added: tuple[date, ...] = Field(default=(), description="Dates carried after only.")
    in_force: date | None = Field(default=None, description="The change's in-force date.")
    applies_from: date | ApplicabilityUnknown | ApplicabilityUnchanged = Field(
        default=ApplicabilityUnknown(), description="A date, or why there is none."
    )
    signals: Observations = Field(default=Observations(), description="The three signals.")
    disputed: bool = Field(
        default=False,
        description="Whether the signals disagree, as stored; a tool takes it from the index "
        "row, which the writer derived from the signals.",
    )
    dispute_reason: str | None = Field(
        default=None,
        description="Stored only by documents written after the field existed; read the index "
        "row's instead, which always carries it.",
    )


class ChangeRecord(BaseModel):
    """One change as a reader receives it: the facts, then whatever prose survived the gate."""

    model_config = _FROZEN

    change: StoredChange = Field(description="The deterministic facts.")
    outcome: str = Field(description="How the change left the citation gate.")
    sentences: tuple[Sentence, ...] = Field(default=(), description="The gated explanation.")
    applicability_note: Sentence | None = Field(default=None, description="Applicability prose.")
    unexplained: str = Field(default="", description="Why there are no sentences, when none.")
    unexplained_kind: str = Field(default="", description="The counted kind of that reason.")


class SignalUnits(BaseModel):
    """One signal's verdict over the event: the top-level units it named."""

    model_config = _FROZEN

    signal: str = Field(description="Which signal.")
    available: bool = Field(default=True, description="Whether the signal could be read.")
    units: tuple[str, ...] = Field(default=(), description="Top-level units it named.")
    note: str | None = Field(default=None, description="Its stored note, if any.")


class Agreement(BaseModel):
    """How far two signals agree over one event, as the payload stores it."""

    model_config = _FROZEN

    left: str = Field(description="One signal.")
    right: str = Field(description="The signal it is compared against.")
    left_units: int = Field(ge=0, description="Units `left` names.")
    right_units: int = Field(ge=0, description="Units `right` names.")
    shared: int = Field(ge=0, description="Units both name.")
    precision: float = Field(ge=0.0, le=1.0, description="Share of `left`'s units `right` names.")
    recall: float = Field(ge=0.0, le=1.0, description="Share of `right`'s units `left` names.")
    kind_mismatches: int = Field(default=0, ge=0, description="Shared units of differing kind.")


class Disagreement(BaseModel):
    """One unit the signals do not agree about, as the payload states it."""

    model_config = _FROZEN

    unit: str = Field(description="The top-level unit.")
    reason: str = Field(description="The stored reason.")
    observed_by: tuple[str, ...] = Field(default=(), description="Signals that named it.")
    absent_from: tuple[str, ...] = Field(default=(), description="Signals that did not.")


class Corroboration(BaseModel):
    """What the three signals said over the whole event."""

    model_config = _FROZEN

    signals: tuple[SignalUnits, ...] = Field(default=(), description="Each signal's units.")
    agreements: tuple[Agreement, ...] = Field(default=(), description="Pairwise agreement.")
    disagreements: tuple[Disagreement, ...] = Field(default=(), description="Units in dispute.")
    metadata_only_units: tuple[str, ...] = Field(default=(), description="Metadata-only units.")
    instruction_only_units: tuple[str, ...] = Field(
        default=(), description="Instruction-only units."
    )


class Payload(BaseModel):
    """One committed payload, reduced to what a tool hands over."""

    model_config = _FROZEN

    schema_version: str = Field(description="The payload's own schema version.")
    disclaimer: str = Field(description="Not legal advice.")
    act: ActRef = Field(description="The act this event belongs to.")
    from_version: str = Field(description="The version the event was computed from.")
    to_version: str = Field(description="The version the event produced.")
    detected_on: date = Field(description="The date the run observed the event.")
    changes: tuple[ChangeRecord, ...] = Field(default=(), description="Every change, in order.")
    corroboration: Corroboration | None = Field(
        default=None, description="The signals over the event; null when none was recorded."
    )
