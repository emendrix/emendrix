"""What a failed call becomes: the two reader-facing reasons, and which one applies.

Split from `engine.py` on 2026-09-04, when adding the second reason took that module past the
line cap. The seam is real rather than convenient: `engine.py` is *the call* — the agent, the
semaphore, the replay layer — and this is the one question asked about a call that did not
return, which the batch then carries as a value.

**The distinction is about the entry, not the reader.** A reader shown either sentence is in
the same position: the change ships with the verbatim texts it always carries and no prose.
What differs is whether anything was learned. A malformed answer is a fact about this change
and settles it. A refused or unreachable provider says nothing about it, so the entry is
unfinished and a later run must be free to ask again — which is what `OutputRepo.holds_finished`
reads, and why this is a counted `kind` rather than only a sentence.

Neither reason is ever an exception's own text. What a library called its failure belongs in
the operator's log, not in a published document.
"""

from __future__ import annotations

from typing import Final

from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError

__all__ = ["MODEL_FAILED", "PROVIDER_UNAVAILABLE", "provider_failed"]

MODEL_FAILED: Final = (
    "the model did not return a well-formed explanation for this change, so none is shipped; "
    "the verbatim before and after texts are unaffected"
)
"""The reader-facing reason when the model answered and the answer was unusable.

One sentence for every shape of that — a refusal, an exhausted repair budget, output the schema
rejects — because the distinctions are about the provider and the reader's situation is the same
in each."""

PROVIDER_UNAVAILABLE: Final = (
    "the explainer could not be reached when this entry was written, so no explanation is "
    "shipped yet; the verbatim before and after texts are unaffected"
)
"""The reader-facing reason when the provider never answered at all.

"Yet" is load-bearing: an entry carrying this is one a later backfill will complete, and the
module docstring says why that follows from the kind rather than from the sentence."""

_PROVIDER_STATUS: Final = frozenset({401, 402, 403, 408, 429})
"""Statuses about the account or the moment and never about the change: unauthorised, out of
credit, forbidden, timed out, rate limited. Anything from 500 up joins them."""


def provider_failed(error: Exception) -> bool:
    """Whether the provider never answered, as opposed to answering badly.

    An unrecognised `ModelHTTPError` status falls through to a settled change deliberately.
    Settling one wrongly costs a thinner entry once; marking one unfinished wrongly costs a
    re-run on every backfill for ever, and the second is the worse failure to have to notice.
    """
    if isinstance(error, ModelHTTPError):
        return error.status_code in _PROVIDER_STATUS or error.status_code >= 500
    return isinstance(error, ModelAPIError)
