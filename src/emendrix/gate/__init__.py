"""`emendrix.gate` — the GATE stage: a claim without a resolvable citation does not ship.

The loop is WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → **GATE** → EMIT, and this package
is the second half of the sentence the project is built on: the model may phrase a difference,
but nothing it phrases reaches a reader until a deterministic check has confirmed that every
citation it carries points at a provision that was actually in front of it.

The check is three questions and no judgement (`check.py`): is the key one this side offered,
does the provision it names exist in that version's tree, and, since a key is an opaque token
rather than a syntax, nothing else. Failure policy is fixed and implemented in `run.py`: one
revision with the specific complaint attached, then a verbatim quotation, which is correct by
construction. **A change is never dropped and an ungrounded sentence is never let through**, and
both are tested as properties.

Nothing here imports a model, a corpus or a clock; the package runs unchanged on the toy
corpus, and `tests/test_architecture.py` greps for all three.

Layout:

- `results.py` — the verdict types, the outcomes and the counts.
- `check.py` — the check itself, `TreeResolver`, which answers from trees already fetched, the
  one string test the gate does make (an applicability note has to quote the AFTER text the
  model was shown, or it is dropped and counted rather than published), and the counted-only
  check that every coordinate a sentence names is somewhere in the model's evidence.
- `fallback.py` — the verbatim quotation, capped visibly, and the substitution policy.
- `run.py` — the two rounds of the one retry, over a whole delta.
"""

from emendrix.gate.check import (
    ProvisionResolver,
    TreeResolver,
    check_explanation,
    note_is_verbatim,
    unsupported_coordinates,
)
from emendrix.gate.fallback import (
    QUOTE_CHAR_CAP,
    apply_fallback,
    fallback_key,
    fallback_sentence,
    verbatim_quote,
)
from emendrix.gate.results import (
    APPLICABILITY_NOTE,
    CitationFailure,
    FailureReason,
    GatedChange,
    GatedDelta,
    GatedExplanation,
    GatedSentence,
    GateOutcome,
    GateResult,
    GateStats,
    Resolution,
    SentenceFailure,
)
from emendrix.gate.run import first_round, second_round

__all__ = [
    "APPLICABILITY_NOTE",
    "QUOTE_CHAR_CAP",
    "CitationFailure",
    "FailureReason",
    "GateOutcome",
    "GateResult",
    "GateStats",
    "GatedChange",
    "GatedDelta",
    "GatedExplanation",
    "GatedSentence",
    "ProvisionResolver",
    "Resolution",
    "SentenceFailure",
    "TreeResolver",
    "apply_fallback",
    "check_explanation",
    "fallback_key",
    "fallback_sentence",
    "first_round",
    "note_is_verbatim",
    "second_round",
    "unsupported_coordinates",
    "verbatim_quote",
]
