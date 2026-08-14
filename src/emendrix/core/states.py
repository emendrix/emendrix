"""First-class states: the answers that are not text.

"There is no consolidated version yet", "there is no English text", "there is no
machine-readable text at all" are *answers*, not failures. They are values: they flow to
the output, they are rendered, and they are counted in the metrics. Raising an exception
where one of these applies is a bug.

Every state carries the date it was observed, passed in from the caller, because nothing in the
core reads a clock. `Unavailable` is the tagged union `fetch_version` and `parse_amending_act`
may return instead of a document.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core.identifiers import ActId, VersionId

__all__ = [
    "ConsolidationPending",
    "EnglishUnavailable",
    "StructuredTextUnavailable",
    "Unavailable",
]


class ConsolidationPending(BaseModel):
    """The act was amended, but no consolidated version exists yet.

    Measured lag between publication and a consolidated text: ≈10 days for the AI Act and
    17 days and counting for the MDR, both on 2026-08-05. This is a persisted state that resolves
    exactly once, not a retry-until-it-works error.
    """

    model_config = ConfigDict(frozen=True)

    state: Literal["consolidation_pending"] = "consolidation_pending"
    act: ActId
    amending_act: ActId | None = None
    in_force: date | None = Field(
        default=None, description="When the amendment took effect, if the corpus says."
    )
    observed_on: date = Field(description="Date of the observation; passed in, never clock-read.")
    detail: str = ""


class EnglishUnavailable(BaseModel):
    """The version exists, but not in the requested language.

    Named for the case this project ships (English) and generalised by `requested_language`. A
    consolidated act can exist in eleven languages and not that one, as `02024R1689-20240712`
    did, verified 2026-08-05. A refusal from the source is an answer here, not an error.
    """

    model_config = ConfigDict(frozen=True)

    state: Literal["english_unavailable"] = "english_unavailable"
    act: ActId
    version: VersionId | None = None
    requested_language: str = "ENG"
    available_languages: tuple[str, ...] = ()
    observed_on: date
    detail: str = ""


class StructuredTextUnavailable(BaseModel):
    """The version exists in the language asked for, but no structured text can be read for it.

    Two ways that happens.

    *The corpus offers no structured manifestation.* 5 of REACH's 68 consolidated versions
    offer only PDF and XHTML (measured 2026-08-05; both numbers asserted by
    `tests/eu/test_cellar.py`). A version existing does not imply a parseable text exists.

    *A package arrives and holds no act document the parser can read.* REACH's
    `02006R1907-20150513` and `02006R1907-20150601` parse without raising and yield no
    provisions at all (measured 2026-08-11). Answering that with an empty tree is what this
    state exists to prevent: the diff cannot tell an empty tree from a repeal, and would report
    all 158 units of REACH deleted and then re-inserted. `eu/adapter.py::fetch_version` names
    the state instead.
    """

    model_config = ConfigDict(frozen=True)

    state: Literal["structured_text_unavailable"] = "structured_text_unavailable"
    act: ActId
    version: VersionId | None = None
    formats_offered: tuple[str, ...] = ()
    observed_on: date
    detail: str = ""


Unavailable = Annotated[
    ConsolidationPending | EnglishUnavailable | StructuredTextUnavailable,
    Field(discriminator="state"),
]
"""Why a document could not be produced: a value the pipeline carries, not an exception."""
