"""What a change's explanation was written about, as a digest, and how to check it later.

Every stage of this loop is deterministic and free to recompute except one. The diff, the
classification, the corroboration, the gate and the pages are pure functions of stored inputs.
An explanation is not: it is the output of a paid, non-repeatable call, and it was written
about a particular pair of verbatim texts. Correct those texts, as the extractor fixes of
2026-08-12 and 2026-09-01 both did, and the stored prose describes evidence the page no longer
shows, and nothing recomputes the sentence that would have been written instead.

Without a record of what the writer was shown, that question has no cheap answer. It has to be
asked by re-parsing the whole corpus and diffing it against every committed payload, which is
why the only reading available on 2026-09-05 was the coarse "64 of 276 events re-parse to a
different unit set" rather than a list of the entries that moved. A digest on the entry turns
it into arithmetic.

**The evidence is digested, never the prompt.** A reworded instruction, a moved date in the
header or a renamed citation key does not make a shipped sentence describe text that is no
longer there; a changed verbatim text does. So exactly three things go in, in this order: the
change's canonical location, its `before` text and its `after` text, NUL-separated and UTF-8
encoded. A side that does not exist is a different value from a side that is the empty string,
so each is tagged before it is joined. A textless change therefore digests to something stable
and distinguishable from every other change and from no digest at all.

**A digest is never derived for an entry that does not carry one.** It records what one call
was shown, so it is written by the run that made the call and carried over untouched by any
repair that does not re-ask, exactly as `detected_on` is. Deriving one for a published entry
would assert that a call nobody witnessed was shown the text the payload happens to hold today.
That is why `provenance_unknown` is a counted state in the register of `ApplicabilityUnknown`
rather than a gap to be filled in: the 5,336 changes published before 2026-09-05 carry no
digest and never will.

Split off `json_out.py` rather than added to it: that module crossed its size cap on
2026-09-05 and was split at the counts seam, and this is a second self-contained question,
asked of one change and answering with one string.

No clock, no network, no corpus, no model.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change

__all__ = [
    "DIGEST_PREFIX",
    "ChangeKey",
    "EvidenceCheck",
    "EvidenceDigest",
    "EvidenceState",
    "checked",
    "digest_of",
    "digest_of_texts",
    "evidence_for",
    "keys_of",
    "merged",
    "recorded_digests",
]

DIGEST_PREFIX: Final = "sha256:"
"""The algorithm, named in the value, so a later one can be told apart rather than guessed."""

_ABSENT: Final = "-"
_PRESENT: Final = "+"
"""A side that does not exist against one that is the empty string. Verbatim means verbatim,
and an empty provision text is a text."""

_SEPARATOR: Final = "\0"
"""No parsed provision text in this project carries a NUL, so the three fields cannot run
together and `("ab", "c")` cannot digest as `("a", "bc")`."""

ChangeKey = tuple[str, int]
"""One change's identity inside an entry: its canonical location, and which occurrence there.

Position would be cheaper and is wrong: a repair may append a unit another signal named or drop
one it withdrew, so the third change of a rebuilt entry need not be the third change of the one
it came from. The location is what corroboration and the payload already key on, and the index
disambiguates a location carrying more than one change without reading any text.
"""


def digest_of_texts(location: str, before: str | None, after: str | None) -> str:
    """The digest of one change's evidence, from its parts. Pure and stable across runs."""
    parts = (
        location,
        _ABSENT if before is None else _PRESENT + before,
        _ABSENT if after is None else _PRESENT + after,
    )
    body = _SEPARATOR.join(parts).encode("utf-8")
    return DIGEST_PREFIX + hashlib.sha256(body).hexdigest()


def digest_of(change: Change) -> str:
    """What the explain stage was shown for one change, as one value.

    The uncapped texts, not the capped ones the prompt printed: the cap is a setting of the
    run and the question this answers is whether the *evidence* moved. A text whose visible
    prefix is unchanged and whose tail was corrected is still a text the explanation may now
    misdescribe, since a later run with a wider cap shows the tail.
    """
    return digest_of_texts(change.location.canonical, change.before, change.after)


class EvidenceDigest(BaseModel):
    """One change's evidence digest, as it rides on the payload."""

    model_config = ConfigDict(frozen=True)

    location: str = Field(
        min_length=1, description="Canonical location of the change this digest is about."
    )
    occurrence: int = Field(
        default=0, ge=0, description="Which change at that location, in the entry's own order."
    )
    digest: str = Field(min_length=1, description="`sha256:` and the hex digest of the evidence.")

    @property
    def key(self) -> ChangeKey:
        return (self.location, self.occurrence)


def keys_of(changes: Iterable[Change]) -> tuple[ChangeKey, ...]:
    """One key per change, in the given order, numbering repeats at a location as they come."""
    seen: Counter[str] = Counter()
    keys: list[ChangeKey] = []
    for change in changes:
        location = change.location.canonical
        keys.append((location, seen[location]))
        seen[location] += 1
    return tuple(keys)


def evidence_for(changes: Iterable[Change]) -> tuple[EvidenceDigest, ...]:
    """A digest per change, for the run that has just been shown these very texts.

    Called with the `Change` objects the explain stage was handed, in the process that handed
    them over. Never with changes read back off a published document: see the module docstring.
    """
    listed = tuple(changes)
    return tuple(
        EvidenceDigest(location=location, occurrence=occurrence, digest=digest_of(change))
        for (location, occurrence), change in zip(keys_of(listed), listed, strict=True)
    )


def recorded_digests(evidence: Iterable[EvidenceDigest]) -> dict[ChangeKey, str]:
    """The digests an entry carries, keyed for lookup. A later record wins over an earlier."""
    return {item.key: item.digest for item in evidence}


def merged(
    carried: Iterable[EvidenceDigest], written: Iterable[EvidenceDigest]
) -> tuple[EvidenceDigest, ...]:
    """What an entry carries after a pass that witnessed some of its calls and not others.

    The written digests replace the carried ones at the same key and nothing else moves, so a
    repair that re-asks about one change records that one and leaves every sibling's provenance
    exactly as it found it, unknown ones included.
    """
    keyed = recorded_digests(carried) | recorded_digests(written)
    return tuple(
        EvidenceDigest(location=location, occurrence=occurrence, digest=digest)
        for (location, occurrence), digest in sorted(keyed.items())
    )


class EvidenceState(StrEnum):
    """What can be said about one change's evidence, checked against a digest derived today.

    `UNRECORDED` is the first-class counted state this file exists to make sayable, and it is
    not a failure: it is the honest reading of every change published before the digest
    existed. `UNDERIVABLE` is the other end, where today's text could not be produced at all,
    which is a coverage gap and not an answer about the explanation.
    """

    MATCHES = "matches"
    DIFFERS = "differs"
    UNRECORDED = "unrecorded"
    UNDERIVABLE = "underivable"


def _state(recorded: str | None, derived: str | None) -> EvidenceState:
    if recorded is None:
        return EvidenceState.UNRECORDED
    if derived is None:
        return EvidenceState.UNDERIVABLE
    return EvidenceState.MATCHES if recorded == derived else EvidenceState.DIFFERS


class EvidenceCheck(BaseModel):
    """One change's evidence, as a question asked of a digest derived today.

    `chars` is the size of the evidence behind the answer, so a caller pricing a corrective
    re-explanation adds a column rather than reading every payload again. It is the stored
    text's own length on both sides, uncapped: how much of it a prompt would carry is the
    explain stage's character cap to decide, and that is a setting rather than a property of
    the change.
    """

    model_config = ConfigDict(frozen=True)

    location: str = Field(min_length=1)
    occurrence: int = Field(default=0, ge=0)
    state: EvidenceState
    chars: int = Field(default=0, ge=0, description="Characters of evidence this change carries.")


def checked(
    changes: Iterable[Change],
    *,
    recorded: Mapping[ChangeKey, str],
    derived: Mapping[ChangeKey, str | None],
) -> tuple[EvidenceCheck, ...]:
    """One answer per change: does its evidence still read as the evidence it was written about.

    `recorded` is what the entry itself carries, empty for every document published before the
    field existed. `derived` is today's digest per change, with `None` where today's text could
    not be produced; a key absent from it is `None` too, so a caller need only supply what it
    managed to derive.
    """
    listed = tuple(changes)
    return tuple(
        EvidenceCheck(
            location=key[0],
            occurrence=key[1],
            state=_state(recorded.get(key), derived.get(key)),
            chars=len(change.before or "") + len(change.after or ""),
        )
        for key, change in zip(keys_of(listed), listed, strict=True)
    )
