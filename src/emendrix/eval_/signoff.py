"""The committed record of a hand review, and the digest that keeps it honest.

`FaithfulnessReport.human_review` defaults to `pending` and `judge.replay` never sets it, so no
code path can claim a review happened. This module is the one thing that may move the field, and
only while a person's committed verdicts still describe the sample the run just built.

The guard is a digest over the exact triples the reviewer read: case id, unit, both texts and the
sentences that shipped, in sample order. Change a prompt, re-record a cassette or re-pin the
subset and the digest stops matching, so the published string reverts to `pending` by mechanism
rather than by somebody remembering to. There is no override and no third answer: a partial claim
("mostly reviewed") reads as a review to everyone not reading the code. Per-entry verdicts ride
along with the summary; they cost one field and turn the review into a labelled benchmark a judge
can be scored against.

**One file per review, named for the sheet it transcribes.** A sign-off is a dated artifact like
the sheet and the report beside it, not a slot that the next review overwrites. Re-recording the
cassettes moves the sample and the sample then needs reading again, but each reading is the only
set of human labels that will ever exist for its own sample, and a judge is scored against those
labels; keeping a reading only in git history would leave that benchmark resting on a commit
nobody reruns. So the dated `reports/faithfulness-signoff-<date>.json` files accumulate,
`latest_signoff` reads the newest of them for publication, and anything that needs one specific
review names its file.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.eval_.judge import Triple, prompt_for

__all__ = [
    "PENDING",
    "SIGNOFF_DIR",
    "SIGNOFF_GLOB",
    "ReviewSignoff",
    "ReviewedEntry",
    "latest_signoff",
    "load_signoff",
    "prompt_sha",
    "review_status",
    "sample_digest",
    "signoff_paths",
]

PENDING: Final = "pending"
"""What a report says when no committed review describes the sample it just measured."""

SIGNOFF_DIR: Final = Path(__file__).resolve().parents[3] / "reports"
"""Where the committed sign-offs live, resolved from this file rather than the working directory
(like `JUDGE_CASSETTE_DIR`): the directory a command ran from may not decide whether a review is
found."""

SIGNOFF_GLOB: Final = "faithfulness-signoff-*.json"
"""One file per review, named for the sheet it transcribes, so the names sort by date."""


class ReviewedEntry(BaseModel):
    """One triple a person read, and what they concluded about it."""

    model_config = ConfigDict(frozen=True)

    slug: str = Field(description="`{case_id} {unit}`, the worksheet's own identity.")
    prompt_sha: str = Field(description="`sha256` of the judge prompt, so a judge can be scored.")
    faithful: bool = Field(description="The reviewer's verdict, never the judge's.")
    note: str = Field(default="", description="One sentence naming the problem, when there is one.")


class ReviewSignoff(BaseModel):
    """One faithfulness sample, reviewed by hand. Nothing in this package ever writes one."""

    model_config = ConfigDict(frozen=True)

    reviewed_on: date
    reviewer: str = Field(min_length=1)
    worksheet: str = Field(min_length=1, description="The ticked sheet this reviews, by path.")
    sample_digest: str = Field(min_length=1, description="Identity of what was read; see below.")
    summary: str = Field(min_length=1, description="The one line published as `human_review`.")
    entries: tuple[ReviewedEntry, ...] = ()


def prompt_sha(triple: Triple) -> str:
    """`sha256` of the judge prompt one triple becomes, hex. The map from a sheet to a judgement."""
    return hashlib.sha256(prompt_for(triple).encode("utf-8")).hexdigest()


def sample_digest(triples: Sequence[Triple]) -> str:
    """`sha256` over the canonical JSON of the sample, in its own order.

    Every field the reviewer read, because a changed BEFORE text changes what "faithful" means as
    surely as a changed sentence does. Whatever the worksheet quotes is evidence the reviewer is
    shown and is therefore part of what the sign-off describes, which is why `context` entered the
    digest on 2026-08-08 and `header` on 2026-08-09, as each started reaching the sheet. Same
    construction as `judgements.judgement_key`, so both hashes are re-derivable by hand the same
    way."""
    payload = json.dumps(
        [
            {
                "case_id": item.case_id,
                "unit": item.unit,
                "before": item.before,
                "after": item.after,
                "context": item.context,
                "header": item.header,
                "sentences": list(item.sentences),
            }
            for item in triples
        ],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_signoff(path: Path) -> ReviewSignoff | None:
    """The sign-off at one path, or `None` when there is no file there.

    A malformed file raises rather than degrading to `None`: a missing review is a normal state
    of this project and an unreadable one is a build fault, and reporting the second as the first
    hides the fault behind a word that looks like an answer.
    """
    if not path.is_file():
        return None
    return ReviewSignoff.model_validate_json(path.read_bytes())


def signoff_paths(directory: Path = SIGNOFF_DIR) -> tuple[Path, ...]:
    """Every committed sign-off, oldest first.

    Sorted by file name, which carries an ISO date and therefore sorts chronologically. The name
    is the sheet's date rather than the reviewer's: two sheets are two samples, while one person
    can read two of them on one afternoon, as happened on 2026-08-08."""
    return tuple(sorted(directory.glob(SIGNOFF_GLOB)))


def latest_signoff(directory: Path = SIGNOFF_DIR) -> ReviewSignoff | None:
    """The most recent committed sign-off, or `None` when there is none.

    The newest is the only candidate for publication: it is the one reading of the sample a run
    is most likely to have just built, and the digest refuses it when it is not. Picking whichever
    of the accumulated sign-offs happened to match would resurrect an older review whenever a
    recording was reverted, and publish it as if it described today.
    """
    found = signoff_paths(directory)
    return load_signoff(found[-1]) if found else None


def review_status(signoff: ReviewSignoff | None, triples: Sequence[Triple]) -> str:
    """The `summary` when the sign-off describes this exact sample, `pending` otherwise.

    An empty sample is `pending`: there is nothing for a review to have been of."""
    if signoff is None or not triples or signoff.sample_digest != sample_digest(triples):
        return PENDING
    return signoff.summary
