"""Scoring a judge against the one set of human labels this project has.

The faithfulness row rests on an LLM judge, and a hand review is the only thing that makes that
judge scoreable at all. `LABELLED_SIGNOFF_PATH` names the sign-off of 2026-08-08 as the label
set: `signoff.py` carries the reviewer's verdict on each of twenty sampled triples, keyed by
`sha256` of the judge prompt, and a judge's own verdicts on the same twenty prompts sit in a
committed cassette directory. Two artifacts, made independently, over identical strings. This
module joins them and counts the agreement.

**Two questions, kept apart.** Faithfulness asks whether the shipped sentences follow from the
texts; this asks whether a judge agrees with a person. A number from here never enters the
faithfulness row and never enters the README's metrics table, and the report it feeds says so in
its own first paragraph.

**The direction of a miss is the finding, not the count.** A judge that is wrong at random is a
noisy instrument; a judge that is *lenient*, calling an entry faithful where the reviewer did not,
inflates every faithfulness rate it ever produces, in one direction, silently. So both directions
are counted separately and printed separately.

**A partial score is refused rather than published.** Scoring a judge over the nineteen entries it
happens to have recorded is exactly the curated number this project publishes measured numbers to
avoid, and the missing one is never the easy one. A recorded judgement that maps to no entry is
the opposite case and is counted rather than dropped: it is a coverage gap, and the report prints
it.

Pure and offline: files in, counts out, no model client, no network and no clock.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.eval_.judgements import JudgeCassette, JudgeCassetteStore
from emendrix.eval_.signoff import SIGNOFF_DIR, ReviewSignoff

__all__ = [
    "BENCHMARK_CASSETTE_DIR",
    "LABELLED_JUDGE_MODEL",
    "LABELLED_SIGNOFF_PATH",
    "AmbiguousJudgement",
    "BenchmarkRow",
    "IncompleteBenchmark",
    "JudgeScore",
    "load_recorded",
    "score",
]

LABELLED_SIGNOFF_PATH: Final = SIGNOFF_DIR / "faithfulness-signoff-2026-08-08.json"
"""The one review whose entries the committed judge cassettes answer, named rather than derived.

Sign-offs accumulate, one per sheet, and the newest is what a run publishes. This benchmark is
pinned to a named one instead, for the same reason `LABELLED_JUDGE_MODEL` is written out: every
judgement either judge has of these entries answers the prompts of *this* sample, so reading "the
newest review" here would silently re-point the label set at prompts nothing in the tree has
answered, the next time a review lands.
"""

LABELLED_JUDGE_MODEL: Final = "openrouter:anthropic/claude-sonnet-5"
"""The judge whose verdicts a person read beside their own, on 2026-08-08.

Its twenty judgements are irreplaceable: they are the only verdicts that exist on prose a human
also worked through, so they stay in the tree whatever the current pin is, and the empty
`rubric_sha` branch in `judgements.judgement_key` stays with them. Written out rather than read
off the explainer's own pinned model, which would silently re-point this label set the next time
the explainer changes.
"""

BENCHMARK_CASSETTE_DIR: Final = (
    Path(__file__).resolve().parents[3] / "tests" / "cassettes-judge-benchmark"
)
"""Where a challenger judge's answers to those same twenty prompts are committed.

A separate directory from `tests/cassettes-judge/`, which holds exactly one judgement per triple
of the *current* faithfulness sample and is asserted to. These judgements are about the prose
recorded on 2026-08-08, which is not the prose that ships, so filing them together would make
"which of these does the published rate replay?" unanswerable.
"""


class IncompleteBenchmark(RuntimeError):
    """A judge has no recorded answer for every labelled entry. Loud, like a cassette miss.

    Not a first-class state: the labelled set is fixed at twenty entries and a judge that
    answered nineteen of them was mis-recorded, not partially measurable. Scoring it anyway
    would publish an agreement rate over a denominator the reader cannot see.
    """

    def __init__(self, judge_model: str, missing: Sequence[str]) -> None:
        super().__init__(
            f"{judge_model} has no recorded judgement for {len(missing)} of the labelled "
            f"entries: {', '.join(missing)}. Record the missing prompts before scoring; a "
            f"benchmark over a subset of the labels is not a benchmark."
        )
        self.judge_model = judge_model
        self.missing = tuple(missing)


class AmbiguousJudgement(RuntimeError):
    """One judge has two recorded answers to one prompt, and nothing here may pick between them.

    The cassette key is `(judge_model, schema_version, prompt, rubric_sha)`, so a rubric edit or
    a schema bump files a *second* answer to the same question beside the first rather than
    replacing it, and the stale file is deleted by hand. Joining on the prompt alone would then
    quietly score whichever of the two sorts first. Which rubric an answer was given under is the
    substance of this comparison, so the ambiguity is refused and named.
    """

    def __init__(self, judge_model: str, prompt_sha: str, rubric_shas: Sequence[str]) -> None:
        super().__init__(
            f"{judge_model} has more than one recorded judgement of the prompt {prompt_sha}, "
            f"under rubrics {', '.join(digest or '(unrecorded)' for digest in rubric_shas)}. "
            f"Delete the superseded recording; a judge cannot be scored on two answers to one "
            f"question."
        )
        self.judge_model = judge_model
        self.prompt_sha = prompt_sha
        self.rubric_shas = tuple(rubric_shas)


class BenchmarkRow(BaseModel):
    """One labelled entry, the reviewer's verdict on it and one judge's."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1, description="The entry's position in the review sheet.")
    slug: str = Field(min_length=1, description="`{case_id} {unit}`, the worksheet's identity.")
    human: bool = Field(description="The reviewer's verdict.")
    judge: bool = Field(description="The recorded verdict of the judge being scored.")
    issue: str = Field(default="", description="What the judge said was wrong, when it said so.")
    note: str = Field(default="", description="What the reviewer said was wrong, when they did.")

    @property
    def agrees(self) -> bool:
        return self.judge == self.human

    @property
    def lenient(self) -> bool:
        """The judge passed an entry the reviewer failed. The direction that inflates a rate."""
        return self.judge and not self.human

    @property
    def strict(self) -> bool:
        """The judge failed an entry the reviewer passed."""
        return self.human and not self.judge


class JudgeScore(BaseModel):
    """One judge against the labelled set. Counts are stored; every rate is derived."""

    model_config = ConfigDict(frozen=True)

    judge_model: str = Field(min_length=1)
    rubric_shas: tuple[str, ...] = Field(
        default=(),
        description="Digests of the rubrics these judgements ran under; `''` means unrecorded.",
    )
    rows: tuple[BenchmarkRow, ...] = ()
    unmapped: tuple[str, ...] = Field(
        default=(), description="Recorded judgements no labelled entry claims, by prompt digest."
    )

    @property
    def entries(self) -> int:
        return len(self.rows)

    @property
    def agreements(self) -> int:
        return sum(1 for row in self.rows if row.agrees)

    @property
    def misses(self) -> int:
        return sum(1 for row in self.rows if not row.agrees)

    @property
    def lenient(self) -> int:
        return sum(1 for row in self.rows if row.lenient)

    @property
    def strict(self) -> int:
        return sum(1 for row in self.rows if row.strict)

    @property
    def agreement_rate(self) -> float | None:
        """The raw fraction, or `None` when there is nothing to divide by."""
        return None if self.entries == 0 else self.agreements / self.entries


def load_recorded(directory: Path, judge_model: str) -> tuple[JudgeCassette, ...]:
    """Every committed judgement one judge has in a directory, sorted by file name.

    Read through `JudgeCassetteStore`, so each file is checked against its own name on the way
    in: a hand-edited prompt would otherwise be scored as the question it claims to answer.
    """
    store = JudgeCassetteStore(directory)
    found = (store.load(judge_model, key) for key in store.keys(judge_model))
    return tuple(cassette for cassette in found if cassette is not None)


def score(
    signoff: ReviewSignoff, recorded: Sequence[JudgeCassette], *, judge_model: str
) -> JudgeScore:
    """Join a judge's recorded verdicts onto the reviewer's, by `sha256` of the prompt.

    The digest is the join key rather than the slug because a slug names a *change* and a
    judgement is about one exact prompt: the same article, re-explained by a different model,
    keeps its slug and becomes a different question entirely. Raises `IncompleteBenchmark` when
    any labelled entry has no recorded answer, and `AmbiguousJudgement` when one has two.
    """
    by_prompt: dict[str, JudgeCassette] = {}
    for cassette in recorded:
        digest = hashlib.sha256(cassette.prompt.encode("utf-8")).hexdigest()
        clash = by_prompt.get(digest)
        if clash is not None:
            raise AmbiguousJudgement(
                judge_model, digest, sorted({clash.rubric_sha, cassette.rubric_sha})
            )
        by_prompt[digest] = cassette
    rows: list[BenchmarkRow] = []
    missing: list[str] = []
    for number, entry in enumerate(signoff.entries, start=1):
        answer = by_prompt.get(entry.prompt_sha)
        if answer is None:
            missing.append(f"{number}. {entry.slug}")
            continue
        rows.append(
            BenchmarkRow(
                number=number,
                slug=entry.slug,
                human=entry.faithful,
                judge=answer.output.faithful,
                issue=answer.output.issue or "",
                note=entry.note,
            )
        )
    if missing:
        raise IncompleteBenchmark(judge_model, missing)
    claimed = {entry.prompt_sha for entry in signoff.entries}
    return JudgeScore(
        judge_model=judge_model,
        rubric_shas=tuple(sorted({cassette.rubric_sha for cassette in recorded})),
        rows=tuple(rows),
        unmapped=tuple(sorted(sha for sha in by_prompt if sha not in claimed)),
    )
