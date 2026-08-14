"""The substitution of last resort: a verbatim quotation, which is correct by construction.

When the one revision fails the gate too, the generated sentence is replaced by the provision's
own text. That is not a graceful-degradation trick: it is the only sentence about a provision
that cannot be wrong about it, because it *is* the provision. The substitution is counted and it
is flagged, so a reader and a metric can both tell which sentences the model wrote and which the
gate did.

Three policies decided here, each stated so the next reader does not have to guess:

1. **One quotation, not one per failed sentence.** Three rejected sentences would otherwise
   become three identical quotations. The passing sentences keep their places and a single
   fallback sentence takes the position of the first failure.
2. **A failing applicability note is dropped, not quoted.** The note is optional by design and
   exists only to quote the act's own application prose; quoting the whole provision in
   its place would answer a question nobody asked. Its rejection is still counted.
3. **The quotation is capped and the cap is visible.** Verbatim means verbatim, so the text is
   never normalised — but a 12,000-character annex is not a changelog entry, and a silent cut
   would be a quiet lie about what was quoted.
"""

from __future__ import annotations

from typing import Final

from emendrix.core import Change
from emendrix.explain import CitedSentence, ExplainContext, Explanation
from emendrix.gate.results import (
    APPLICABILITY_NOTE,
    GatedExplanation,
    GatedSentence,
    GateResult,
)

__all__ = ["QUOTE_CHAR_CAP", "apply_fallback", "fallback_key", "verbatim_quote"]

QUOTE_CHAR_CAP: Final = 600
"""How much of a provision a fallback sentence quotes before the marker takes over."""

_TRUNCATION: Final = " […truncated by emendrix: {dropped} characters omitted…]"

_QUOTED: Final = '{side} text of {label}: "{quote}"'


def verbatim_quote(change: Change, *, limit: int = QUOTE_CHAR_CAP) -> str:
    """The change's own text, quoted, with any cut marked in the sentence itself.

    The later side is preferred — what the provision says *now* is the more useful sentence —
    and a deletion falls back to what it said before, which is all there is.
    """
    side, text = ("after", change.after) if change.after is not None else ("before", change.before)
    if text is None:  # pragma: no cover - `explainable()` filters these long before the gate
        raise ValueError(
            f"{change.location.canonical} carries no text on either side, so it has no "
            f"verbatim fallback; such changes never reach the gate with an explanation"
        )
    quote = " ".join(text.split())
    if len(quote) > limit:
        quote = quote[:limit].rstrip() + _TRUNCATION.format(dropped=len(quote) - limit)
    return _QUOTED.format(
        side="The new" if side == "after" else "The removed",
        label=change.provision.human,
        quote=quote,
    )


def fallback_key(change: Change, context: ExplainContext) -> str:
    """The key the fallback sentence cites: the change's own provision, from the offered set.

    Taken from the context rather than minted here, so the sentence the gate writes passes the
    gate for the same reason every other sentence does. The first offered key is the fallback's
    fallback, for a caller whose minted keys this side cannot match by reference.
    """
    return context.key_for(change.provision) or context.offered[0].key


def fallback_sentence(change: Change, context: ExplainContext) -> GatedSentence:
    """The one sentence that replaces whatever the model could not ground."""
    return GatedSentence(
        sentence=CitedSentence(
            text=verbatim_quote(change), citations=(fallback_key(change, context),)
        ),
        fallback=True,
    )


def apply_fallback(
    change: Change, explanation: Explanation, result: GateResult, context: ExplainContext
) -> GatedExplanation:
    """Keep what passed, replace what did not with the quotation. Never drops the change.

    Called only after the single revision has failed; `result` is that second verdict, so the
    sentences it does not name are the ones that survived both rounds.
    """
    rejected = {failure.index for failure in result.failures}
    kept: list[GatedSentence] = []
    substituted = False
    for index, sentence in enumerate(explanation.sentences):
        if index not in rejected:
            kept.append(GatedSentence(sentence=sentence))
            continue
        if not substituted:  # policy 1: one quotation, at the first failure's place
            kept.append(fallback_sentence(change, context))
            substituted = True
    if not substituted and APPLICABILITY_NOTE not in rejected:
        raise ValueError("apply_fallback was called on a result that carries no failures")
    # `kept` cannot be empty: the schema guarantees at least one sentence, and every rejected
    # one either keeps its place or is replaced by the quotation.
    note = explanation.applicability_note
    return GatedExplanation(
        sentences=tuple(kept),
        # policy 2: an ungrounded note is dropped rather than replaced.
        applicability_note=(
            None if note is None or APPLICABILITY_NOTE in rejected else GatedSentence(sentence=note)
        ),
    )
