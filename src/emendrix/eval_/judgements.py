"""The judgement as it sits on disk: its key, its envelope, its store and the replay path.

Split from `judge.py` the way `explain/cassette.py` is split from `explain/schema.py`: one file
holds what a judgement *is* to the rest of the eval layer, this one holds what it is to the
filesystem. `emendrix eval run` replays committed judgements and must not import a model client
to do it, exactly as the explain stage does not in `CassetteMode.REPLAY`, so nothing here reaches
`faithfulness.py`.

**The rubric is part of the key.** `RUBRIC_SHA` enters the payload, so editing the rubric misses
every cassette recorded against the old one, loudly, which is the same contract the explain
stage's `(model_id, system, user)` key has. Without it a rubric edit would change nothing on disk
and every committed verdict would keep replaying under an instruction it had never seen, which is
exactly the drift `rubric.py` exists to make visible.

The rubric entered the key on 2026-08-08. An empty `rubric_sha` reproduces the payload of the
twenty judgements recorded before that date byte for byte, so they still load and verify against
their own file names; the branch exists only for them and goes when they do.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import Field

from emendrix.eval_.judge import (
    FaithfulnessReport,
    Judgement,
    Triple,
    Verdict,
    prompt_for,
)
from emendrix.eval_.rubric import JUDGE_RUBRIC
from emendrix.explain import JsonCassette, JsonCassetteStore

__all__ = [
    "JUDGE_CASSETTE_DIR",
    "JUDGE_SCHEMA_VERSION",
    "RUBRIC_SHA",
    "JudgeCassette",
    "JudgeCassetteStore",
    "judgement_key",
    "replay",
    "rubric_digest",
]

JUDGE_SCHEMA_VERSION: Final = 1
"""The `Verdict` shape's version, mixed into every cassette key like the explain stage's."""


def rubric_digest(rubric: str = JUDGE_RUBRIC) -> str:
    """`sha256` of one rubric, hex. One construction, so two callers cannot disagree.

    Takes the rubric rather than reading the constant because a run may be made under an older
    rubric on purpose: scoring a judge against verdicts taken under a different instruction
    measures the pair, and separating the two means handing this function the other text.
    """
    return hashlib.sha256(rubric.encode("utf-8")).hexdigest()


RUBRIC_SHA: Final = rubric_digest()
"""`sha256` of the rubric currently in git, hex. Derived rather than written down, so it cannot
disagree with the instruction the judge is actually given."""

JUDGE_CASSETTE_DIR: Final = Path(__file__).resolve().parents[3] / "tests" / "cassettes-judge"
"""Committed judge exchanges, kept apart from the explain stage's so neither can shadow the
other. Resolved from this file rather than the working directory, like `DEFAULT_CASSETTE_DIR`."""


def judgement_key(
    judge_model: str,
    prompt: str,
    schema_version: int = JUDGE_SCHEMA_VERSION,
    rubric_sha: str = "",
) -> str:
    """`sha256` over the canonical JSON of `(judge_model, schema_version, prompt, rubric)`.

    The same construction as `explain.cassette_key`, and separate from it on purpose: the two
    exchanges have different output schemas, so a shared key space would let a changed `Verdict`
    miss quietly against an `Explanation` cassette.

    An empty `rubric_sha` leaves the field out of the payload entirely rather than hashing an
    empty string, which is what makes the key of a judgement recorded before 2026-08-08 still
    derivable. Every judgement recorded since carries one.
    """
    payload: dict[str, object] = {
        "judge_model": judge_model,
        "prompt": prompt,
        "schema_version": schema_version,
    }
    if rubric_sha:
        payload["rubric_sha"] = rubric_sha
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


class JudgeCassette(JsonCassette):
    """One recorded judgement, exactly as it sits on disk."""

    schema_version: int = JUDGE_SCHEMA_VERSION
    judge_model: str = Field(min_length=1)
    synthetic: bool = Field(description="True when a stub produced it. Never evidence.")
    recorded_with: str = Field(min_length=1)
    prompt: str = Field(min_length=1, description="The whole prompt, verbatim and reviewable.")
    rubric_sha: str = Field(
        default="", description="`sha256` of the rubric this was judged under; see the module."
    )
    output: Verdict


class JudgeCassetteStore(JsonCassetteStore[JudgeCassette]):
    """A directory of judgements, one subdirectory per judge model.

    The store itself is the explain stage's: hash-named files, the name checked against the
    contents on every read, tmp-and-rename on every write. Only what a judgement *is* differs,
    which is the three hooks below.
    """

    def __init__(self, directory: Path = JUDGE_CASSETTE_DIR) -> None:
        super().__init__(directory)

    def _parse(self, text: str) -> JudgeCassette:
        return JudgeCassette.model_validate_json(text)

    def _model_of(self, cassette: JudgeCassette) -> str:
        return cassette.judge_model

    def _derived_key(self, cassette: JudgeCassette) -> str:
        return judgement_key(
            cassette.judge_model, cassette.prompt, cassette.schema_version, cassette.rubric_sha
        )

    def save(self, cassette: JudgeCassette) -> Path:
        """Write one judgement. No downgrade guard — the explain stage's is the interesting one.

        Its cassettes are recorded by the same command with or without an API key; these are
        recorded by a command that has no keyless mode at all.
        """
        return self.write(cassette)


def replay(
    triples: Sequence[Triple],
    *,
    judge_model: str,
    store: JudgeCassetteStore | None = None,
    worksheet: str = "",
) -> FaithfulnessReport:
    """The sampled triples' committed judgements. Reads disk; never calls anything.

    A triple with no committed judgement is reported as unjudged rather than raising: unlike a
    missing explain cassette — which would let CI go green having explained nothing — a missing
    judgement narrows a sample that is already labelled as weak, and `sampled` vs `judged` in the
    report says so in the open. `human_review` stays `pending` until somebody fills in the
    worksheet by hand and says otherwise; this function never claims a review happened.
    """
    cassettes = store if store is not None else JudgeCassetteStore()
    judgements: list[Judgement] = []
    for triple in triples:
        key = judgement_key(judge_model, prompt_for(triple), rubric_sha=RUBRIC_SHA)
        found = cassettes.load(judge_model, key)
        judgements.append(
            Judgement(
                case_id=triple.case_id,
                unit=triple.unit,
                outcome=triple.outcome,
                fallback=triple.fallback,
                verdict=None if found is None else found.output,
                synthetic=found is not None and found.synthetic,
                judge_model=judge_model,
            )
        )
    judged = tuple(item for item in judgements if item.verdict is not None)
    return FaithfulnessReport(
        judge_model=judge_model,
        sampled=len(triples),
        judged=len(judged),
        faithful=sum(1 for item in judged if item.verdict is not None and item.verdict.faithful),
        synthetic=sum(1 for item in judged if item.synthetic),
        fallback_triples=sum(1 for triple in triples if triple.fallback),
        worksheet=worksheet,
        judgements=tuple(judgements),
    )
