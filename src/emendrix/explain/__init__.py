"""`emendrix.explain` — the EXPLAIN stage, and the only place a model appears.

The loop is WATCH → FETCH → DELTA → CORROBORATE → **EXPLAIN** → GATE → EMIT. Every other
stage is deterministic Python. Here, and nowhere else, a model is handed two verbatim texts
that are already known to differ and asked to write a sentence about the difference. It does
not decide whether something changed, which provisions are involved, or how to classify the
change: those arrive as typed inputs.

`pydantic_ai` may be imported under this package and nowhere else in `src/emendrix` —
grep-enforced by `tests/test_architecture.py`, which is the point of writing it down.

Layout:

- `schema.py` — what the model may return. Types are the interface to the model.
- `context.py` — the opaque citation keys it may cite, minted on this side of the call, and
  the coordinate-support sets the gate tests membership against.
- `coordinates.py` — the recogniser that reads named coordinates off model prose, and only
  model prose.
- `rules.py` — the twelve rules it is given, as literal reviewable text.
- `prompt.py` — one change assembled into a message, and the per-prompt fence around the texts.
- `capping.py` — how much of a long text it is shown, and when that leaves it no evidence.
- `settings.py` — the pinned model (confirmed 2026-08-08) and every knob, env-overridable.
- `cassette.py` — replay: JSON on disk keyed by `(model_id, sha256(prompt))`.
- `results.py` — per-call and per-run accounting, including what a run cost.
- `engine.py` — the call itself, its single revision, and the bounded-concurrency batch.
"""

from emendrix.explain.capping import (
    NO_EVIDENCE_PAST_CAP,
    cap_text,
    shows_no_difference,
)
from emendrix.explain.cassette import (
    Cassette,
    CassetteCorrupt,
    CassetteMiss,
    CassetteStore,
    JsonCassette,
    JsonCassetteStore,
    cassette_key,
    model_slug,
)
from emendrix.explain.context import (
    NOTHING_TO_EXPLAIN,
    ExplainContext,
    OfferedCitation,
    build_context,
    contexts_for_delta,
    explainable,
)
from emendrix.explain.coordinates import mentioned_locations
from emendrix.explain.engine import MODEL_FAILED, ExplainEngine
from emendrix.explain.prompt import (
    FENCE_TOKEN_CHARS,
    PromptParts,
    build_prompt,
    fence_for,
    header_block,
    revision_note,
)
from emendrix.explain.results import CallUsage, ExplainedChange, ExplainRun, RunStats
from emendrix.explain.rules import SYSTEM_PROMPT
from emendrix.explain.schema import (
    MAX_SENTENCES,
    SCHEMA_VERSION,
    CitedSentence,
    Explanation,
    ExplanationUnavailable,
)
from emendrix.explain.settings import (
    DEFAULT_CASSETTE_DIR,
    DEFAULT_MODEL,
    PUBLISHED_RATES,
    CassetteMode,
    ExplainSettings,
    ModelRate,
    api_key_env,
    rate_for,
)

__all__ = [
    "DEFAULT_CASSETTE_DIR",
    "DEFAULT_MODEL",
    "FENCE_TOKEN_CHARS",
    "MAX_SENTENCES",
    "MODEL_FAILED",
    "NOTHING_TO_EXPLAIN",
    "NO_EVIDENCE_PAST_CAP",
    "PUBLISHED_RATES",
    "SCHEMA_VERSION",
    "SYSTEM_PROMPT",
    "CallUsage",
    "Cassette",
    "CassetteCorrupt",
    "CassetteMiss",
    "CassetteMode",
    "CassetteStore",
    "CitedSentence",
    "ExplainContext",
    "ExplainEngine",
    "ExplainRun",
    "ExplainSettings",
    "ExplainedChange",
    "Explanation",
    "ExplanationUnavailable",
    "JsonCassette",
    "JsonCassetteStore",
    "ModelRate",
    "OfferedCitation",
    "PromptParts",
    "RunStats",
    "api_key_env",
    "build_context",
    "build_prompt",
    "cap_text",
    "cassette_key",
    "contexts_for_delta",
    "explainable",
    "fence_for",
    "header_block",
    "mentioned_locations",
    "model_slug",
    "rate_for",
    "revision_note",
    "shows_no_difference",
]
