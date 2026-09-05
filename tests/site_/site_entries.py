"""Corroborated toy entries for the site suite: the attribution states, built, not asserted.

The site tests mostly render diff-only entries, whose `corroboration` is `None` and which
therefore never enter the no-amending-act class. The class needs entries that carry a
corroboration report, and this module builds them the way the loop does: `corroborate()` over
the toy delta, with the signals the case calls for, wrapped exactly as `ChangelogEntry.of`
wraps an emitted delta. Nothing here writes a report by hand.

A sibling of `tests/output/toy_entries.py` rather than an import of it: the test tree has one
conftest and no `__init__.py`, so a module here can import its own directory's neighbours and
the top-level fixtures, and a scoped `tests/site_` run would never put `tests/output` on the
path.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import Delta, ProvisionLocation, Signal, SignalClaim, SignalReport
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.explain import NOTHING_TO_EXPLAIN
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange, EmittedDelta
from emendrix.output import ChangelogEntry
from toy_corpus import AMENDMENT, HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED_ON = date(2026, 8, 9)
IN_FORCE = date(2026, 6, 1)

__all__ = [
    "IN_FORCE",
    "OBSERVED_ON",
    "attributed_entry",
    "disputed_entry",
    "some_textless_entry",
    "textless_entry",
    "unattributed_entry",
    "untouched_entry",
]


def _toy_delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert not isinstance(before, Exception) and not isinstance(after, Exception)
    return compute_delta(before, after)  # type: ignore[arg-type]


def _entry_of(delta: Delta, metadata: SignalReport | None, *, reason: str = "") -> ChangelogEntry:
    """The toy transition corroborated and wrapped the way `ChangelogEntry.of` wraps one.

    `reason` is the sentence the explain stage records against a change it was never able to
    ask about, and giving one means the stage ran: a diff-only entry has no per-change reason
    to give, so the two travel together.
    """
    merged = corroborate(delta, metadata=metadata, instructions=None)
    return ChangelogEntry.of(
        EmittedDelta(
            act=merged.delta.act,
            from_version=merged.delta.from_version,
            to_version=merged.delta.to_version,
            summary=merged.delta.summary,
            changes=tuple(
                EmittedChange(
                    change=change,
                    outcome=GateOutcome.UNEXPLAINED,
                    unexplained=reason if change.textless else "",
                )
                for change in merged.delta.changes
            ),
            corroboration=merged.report,
        ),
        detected_on=OBSERVED_ON,
        diff_only=not reason,
    )


def _named(*locations: str) -> SignalReport:
    """A metadata signal naming units and nothing else, the way an annotation window does."""
    return SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=tuple(
            SignalClaim(
                location=ProvisionLocation.parse(location),
                in_force=IN_FORCE,
                amending_act=AMENDMENT,
            )
            for location in locations
        ),
    )


def unattributed_entry() -> ChangelogEntry:
    """The toy transition with both non-diff signals unavailable: the class member.

    `metadata=None` and `instructions=None` are exactly what a window naming no amending act
    hands `corroborate()`, so this entry is the shape the committed class ships in.
    """
    return _entry_of(_toy_delta(), None)


def untouched_entry() -> ChangelogEntry:
    """The toy act compared against itself: corroborated, and the comparison matched every unit.

    The shape the committed zero-touched events ship in: a corroboration report is present,
    both non-diff signals are unavailable, and the change list is empty because nothing
    differed. Comparing one version with itself is the honest way to build that delta; the
    committed cases carry two distinct version identifiers, but nothing rendered from the
    entry reads the pair for sameness.
    """
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    assert not isinstance(before, Exception)
    return _entry_of(compute_delta(before, before), None)  # type: ignore[arg-type]


def attributed_entry() -> ChangelogEntry:
    """The same transition with an available metadata signal naming the amending act."""
    delta = _toy_delta()
    metadata = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=tuple(
            SignalClaim(
                location=change.unit,
                change_type=change.change_type,
                in_force=IN_FORCE,
                amending_act=AMENDMENT,
            )
            for change in delta.changes
        ),
    )
    return _entry_of(delta, metadata)


def disputed_entry() -> ChangelogEntry:
    """The same transition with metadata that lists every change but the first.

    An available signal that did not see one of the units is the disagreement `disputed`
    names, so the entry ships one. Handing `corroborate()` an empty claim list would not do
    it: a signal given no annotations at all is unavailable, not silent, which is the
    distinction corrected on 2026-08-12 and the reason the report here names three units.
    """
    delta = _toy_delta()
    metadata = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=tuple(
            SignalClaim(
                location=change.unit,
                change_type=change.change_type,
                in_force=IN_FORCE,
                amending_act=AMENDMENT,
            )
            for change in delta.changes[1:]
        ),
    )
    return _entry_of(delta, metadata)


def textless_entry() -> ChangelogEntry:
    """Every touched unit named by the metadata, and the text comparison saw none of them.

    The shape `corroborate.merge` appends: a location, a kind, `disputed=True` and no text on
    either side. It is built by comparing one version with itself, so the diff has nothing to
    contribute, and by naming two units the toy act does not contain, so both are appended.
    """
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    assert not isinstance(before, Exception)
    delta = compute_delta(before, before)  # type: ignore[arg-type]
    return _entry_of(delta, _named("AR 9", "AR 12"), reason=NOTHING_TO_EXPLAIN)


def some_textless_entry() -> ChangelogEntry:
    """The toy transition, with one unit the metadata named and the diff never saw.

    The mixed event: four units carrying text and one carrying none, which is what keeps the
    count line's three-way split honest rather than only its all-or-nothing branch.
    """
    delta = _toy_delta()
    named = [change.unit.canonical for change in delta.changes] + ["AR 9"]
    return _entry_of(delta, _named(*named), reason=NOTHING_TO_EXPLAIN)
