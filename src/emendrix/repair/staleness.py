"""Which committed changes describe evidence today's parse no longer produces.

Two extractor fixes, on 2026-08-12 and 2026-09-01, corrected stored verbatim text after most of
the published corpus had been written, and an explanation is the one thing this pipeline cannot
recompute. So a published change either still reads as the text its sentences were written
about or it does not, and that difference is what a corrective pass selects and is priced from.

**One notion of "differs", shared by the repair and by the validation script that measures the
reach of one.** The state machine is `output.provenance.checked`; what this module adds is the
two sides handed to it.

- **What a change states its evidence was**: the digest the entry itself recorded where it has
  one, and the digest of its own stored text where it has none. Those are two kinds of fact, a
  witnessed one and a payload's own claim, which is why `output.provenance` refuses to write the
  second onto an entry; reading them in that order is safe, and it is the only way to ask the
  question at all of a document published before the field existed.
- **What today's parse produces**: the digest of the change a re-derived delta holds at the same
  location, and nothing where that delta holds no such change any more.

`UNDERIVABLE` therefore reads differently depending on who supplied the right-hand side, and
both readings are the same honest "there is no evidence to compare against": for a caller that
looked up two provision trees, a version it could not produce; for a caller that re-derived the
delta from both of them, a change the delta no longer has, which is a withdrawal.

Core types and the committed document. No corpus, no clock, no model, no network.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change
from emendrix.output import ChangelogEntry, EvidenceCheck, EvidenceState, checked, digest_of
from emendrix.output.provenance import ChangeKey, keys_of, recorded_digests

__all__ = ["EvidencePlan", "compare", "derived_digests", "stated", "stored_digests"]


def stored_digests(entry: ChangelogEntry) -> dict[ChangeKey, str]:
    """The evidence each committed change holds today, whoever it was written about."""
    changes = [item.change for item in entry.changes]
    return {key: digest_of(change) for key, change in zip(keys_of(changes), changes, strict=True)}


def stated(entry: ChangelogEntry) -> dict[ChangeKey, str]:
    """The evidence each committed change states, recorded digest first, stored text second.

    A recorded digest is what a run watched itself show the model; a digest over the stored
    text is what the document says it holds today. Where an entry carries the first it wins,
    because it answers the question directly, and where it does not the second is the only
    reading available and is never written back onto the entry.
    """
    return stored_digests(entry) | recorded_digests(entry.evidence)


def derived_digests(changes: Iterable[Change]) -> dict[ChangeKey, str]:
    """The evidence a re-derived delta holds, keyed the way a committed entry keys its own."""
    listed = tuple(changes)
    return {key: digest_of(change) for key, change in zip(keys_of(listed), listed, strict=True)}


class EvidencePlan(BaseModel):
    """What re-deriving one transition implies for the entry that was published.

    `carried`, `reasked`, `added` and `restated` partition today's delta, so every change a
    rebuilt entry would hold is accounted for exactly once and none is quietly dropped.
    `withdrawn` is the other side of that: locations the published entry holds and today's
    delta does not.

    Two of the tuples are subsets rather than parts, and both are there so that `moves` says
    what actually moved. `restored` is the carried whose stored text drifted anyway, which a
    recorded digest settles without a call. `emptied` is the restated the entry did not already
    publish with no text: a unit that has always carried the same stated reason is restated
    identically every time, and counting that as a correction would put every entry holding one
    into a pass that has nothing to do to it.
    """

    model_config = ConfigDict(frozen=True)

    answers: tuple[EvidenceCheck, ...] = Field(
        default=(), description="One state per committed change, in the entry's own order."
    )
    carried: tuple[int, ...] = Field(
        default=(), description="Today's changes whose evidence is the evidence published."
    )
    reasked: tuple[int, ...] = Field(
        default=(), description="Today's changes whose evidence moved and that carry text."
    )
    added: tuple[int, ...] = Field(
        default=(), description="Today's changes the entry does not have, and that carry text."
    )
    restated: tuple[int, ...] = Field(
        default=(), description="Today's changes with no text at all: nothing to ask about."
    )
    emptied: tuple[int, ...] = Field(
        default=(),
        description="The restated the entry did not already publish with no text: a real move.",
    )
    restored: tuple[int, ...] = Field(
        default=(),
        description="Carried changes whose stored text moved anyway: corrected, never asked.",
    )
    withdrawn: tuple[str, ...] = Field(
        default=(), description="Locations the entry publishes that today's delta does not hold."
    )

    @property
    def asked(self) -> tuple[int, ...]:
        """Every change this pass would pay for, in the delta's own order."""
        return tuple(sorted((*self.reasked, *self.added)))

    @property
    def moves(self) -> bool:
        """Whether re-deriving found anything at all to say about this entry."""
        return bool(self.reasked or self.added or self.withdrawn or self.emptied or self.restored)


def compare(entry: ChangelogEntry, derived: Sequence[Change]) -> EvidencePlan:
    """Hold one published entry against today's delta for the same transition.

    A change with no text is never asked about, whether it is new or whether it is a unit the
    diff used to see text for and no longer does: nothing was ever asked about such a change,
    and there is nothing to ask now.

    A textless change digests to a value of its own, so a unit that was textless before and is
    textless now reads as matching and moves nothing; one whose text the diff has stopped
    producing reads as differing, which is what tells the two apart without reading either.

    **Two questions are asked of every change and they have different answers.** Whether the
    explanation is stale is asked of what the change *states* its evidence was, so a recorded
    digest settles it however the stored text has since been corrected. Whether the stored text
    itself moved is asked of the text, and where a digest proves the prose was written about
    today's parse the text is corrected and nothing is asked: the entry is out of date and the
    explanation is not.
    """
    committed = [item.change for item in entry.changes]
    today = derived_digests(derived)
    answers = checked(committed, recorded=stated(entry), derived=today)
    states = {(answer.location, answer.occurrence): answer.state for answer in answers}
    stored = stored_digests(entry)
    carried: list[int] = []
    reasked: list[int] = []
    added: list[int] = []
    restated: list[int] = []
    emptied: list[int] = []
    restored: list[int] = []
    for index, (key, change) in enumerate(zip(keys_of(derived), derived, strict=True)):
        if change.textless:
            restated.append(index)
            if states.get(key) is not EvidenceState.MATCHES:
                emptied.append(index)
        elif key not in states:
            added.append(index)
        elif states[key] is EvidenceState.MATCHES:
            carried.append(index)
            if stored[key] != today[key]:
                restored.append(index)
        else:
            reasked.append(index)
    held = set(keys_of(derived))
    return EvidencePlan(
        answers=answers,
        carried=tuple(carried),
        reasked=tuple(reasked),
        added=tuple(added),
        restated=tuple(restated),
        emptied=tuple(emptied),
        restored=tuple(restored),
        withdrawn=tuple(key[0] for key in keys_of(committed) if key not in held),
    )
