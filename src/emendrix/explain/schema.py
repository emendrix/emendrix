"""What the model is allowed to say, as a type. Nothing it produces escapes this shape.

The model's one job is to phrase the difference between two verbatim texts it is handed. It
does not decide *whether* something changed, *which* provisions are involved or *how* to
classify the change: those arrive as typed inputs and leave untouched. So the output type
carries no change type, no location, no date and no quote — only sentences, and the citation
keys each sentence stands on.

**Citations are keys, not URLs.** A sentence cites opaque strings drawn from the set the
caller offered (`context.py`). The model therefore *cannot* invent a URL — there is no field
to put one in — and the gate's containment check is a set operation on strings
rather than a judgement about content. Making that check structural is the whole
anti-hallucination invariant, and it is bought here, in the schema.

`ExplanationUnavailable` is the first-class state for "no explanation was produced": a model
error, a schema-repair budget exhausted, a provider refusal. It flows to the output and gets
counted, because raising where a state applies is a bug.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MAX_SENTENCES",
    "SCHEMA_VERSION",
    "CitedSentence",
    "Explanation",
    "ExplanationUnavailable",
]

SCHEMA_VERSION: Final = 1
"""Bumped whenever `Explanation` changes shape.

It is mixed into every cassette key (`cassette.py`), so a schema change misses every existing
cassette loudly instead of replaying a stale shape into a new validator.
"""

MAX_SENTENCES: Final = 3
"""A changelog entry is one or two sentences. Three is the
ceiling, enforced by the schema rather than asked for in prose."""


class CitedSentence(BaseModel):
    """One plain-English sentence and the citation keys it stands on. At least one.

    `citations` are keys from the offered set — validated here only for *shape* (non-empty,
    non-blank). Whether each key was actually offered is the gate's containment check, which
    is deliberately not performed by the schema: a model that cites outside its context must
    produce a well-formed answer that then *fails*, so the failure is counted rather than
    hidden behind a validation retry.
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(
        min_length=1,
        description=(
            "One sentence of plain English describing the difference. No legal advice, no "
            "speculation about intent, and no re-quoting of the before/after texts."
        ),
    )
    citations: tuple[str, ...] = Field(
        min_length=1,
        description=(
            "One or more citation keys, copied exactly from the offered set. Every sentence "
            "must carry at least one."
        ),
    )


class Explanation(BaseModel):
    """Everything the model returns for one change.

    `applicability_note` exists because the second clock lets the explanation *quote* the act's own
    application prose verbatim, with a citation — and never infer an applicability date from
    it. The note is optional and the honest answer is usually to omit it.
    """

    model_config = ConfigDict(frozen=True)

    sentences: tuple[CitedSentence, ...] = Field(
        min_length=1,
        max_length=MAX_SENTENCES,
        description="One to three sentences explaining the difference. Each carries citations.",
    )
    applicability_note: CitedSentence | None = Field(
        default=None,
        description=(
            "Optional. Only when the provision's own text states when it applies, and only as "
            "a verbatim quote of that text. Never an inferred date. Omit it otherwise."
        ),
    )

    @property
    def cited_keys(self) -> frozenset[str]:
        """Every key this explanation cites — the gate's input, in one call."""
        keys = {key for sentence in self.sentences for key in sentence.citations}
        if self.applicability_note is not None:
            keys.update(self.applicability_note.citations)
        return frozenset(keys)

    @property
    def sentence_count(self) -> int:
        return len(self.sentences) + (1 if self.applicability_note is not None else 0)


class ExplanationUnavailable(BaseModel):
    """No explanation was produced for this change — a value, not an exception.

    It reaches the changelog and the metrics exactly like `ConsolidationPending` and
    `EnglishUnavailable` do: a change is never dropped because the model failed on it.

    `kind` is what happened, closed and countable; `reason` is the sentence a reader is shown,
    always one of the curated constants beside the mechanism that mints it (`NOTHING_TO_EXPLAIN`
    in `context.py`, `NO_EVIDENCE_PAST_CAP` in `capping.py`, `MODEL_FAILED` in `engine.py`).
    `reason` is never an exception's text: what a library called its failure is a fact for the
    operator's log, not for a document intended for publication.
    """

    model_config = ConfigDict(frozen=True)

    state: Literal["explanation_unavailable"] = "explanation_unavailable"
    kind: Literal["nothing_to_explain", "no_evidence_past_cap", "model_failed"] = Field(
        description="Which of the three ways a change ends up with no explanation this was."
    )
    reason: str = Field(min_length=1, description="What went wrong, for the reader and the eval.")
