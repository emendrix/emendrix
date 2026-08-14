"""`compute_delta`: the DELTA stage of the loop, in one function.

Pure, offline, and free of any clock: two runs over the same pair of trees produce the same
`Delta`, byte for byte, which is what lets the output stage commit changelogs into git and diff
them. Nothing here knows about any corpus; it runs on whatever a `CorpusAdapter` returned,
including the toy corpus that has no law in it at all.

`in_force` (clock 1) is not something the diff can see. It comes from the corpus's own amendment
metadata, which corroboration reads, so it is a parameter, passed in from the boundary and
stamped on every change exactly like the observation dates the fetch path takes.

The signal set is filled with `structural_diff = OBSERVED` and nothing else: the diff has seen
these changes and cannot speak for the other two signals, which stay `UNAVAILABLE` until
`corroborate/merge.py` merges them. `UNAVAILABLE` is not dissent, so no change leaves this stage
`disputed`.

A deletion is referenced in the version that still contains it, the old one. Everything else is
referenced in the new version, at the location it now occupies.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import (
    ActId,
    ApplicabilityUnknown,
    Change,
    ChangeType,
    Delta,
    ProvisionNode,
    ProvisionRef,
    ProvisionTree,
    Signal,
    SignalObservation,
    SignalSet,
    SignalStatus,
    VersionId,
)
from emendrix.diff.deferred import read_dates
from emendrix.diff.sub_localise import changed_sublocations
from emendrix.diff.tree_diff import UnitMatch, diff_units

__all__ = ["STRUCTURAL_ONLY", "compute_delta"]

STRUCTURAL_ONLY = SignalSet(
    structural_diff=SignalObservation(
        status=SignalStatus.OBSERVED, detail=Signal.STRUCTURAL_DIFF.value
    )
)
"""What the diff alone can claim: it saw the change, and it does not speak for the others."""

_INSERTED_REASON = "an inserted provision states its own application date only in prose"
_DELETED_REASON = "a deleted provision has no application date to move"


def compute_delta(
    before: ProvisionTree, after: ProvisionTree, *, in_force: date | None = None
) -> Delta:
    """Everything that changed between two versions of one act, deterministically ordered.

    `before` and `after` must be two versions of the same act; being handed two different acts
    is a programming error, not a first-class state, and raises.
    """
    if before.act != after.act:
        raise ValueError(f"cannot diff {before.act} against {after.act}: different acts")
    diff = diff_units(before, after)
    builder = _Builder(after.act, before.version, after.version, in_force)
    return Delta(
        act=after.act,
        from_version=before.version,
        to_version=after.version,
        changes=tuple(builder.change(match) for match in diff.matches),
        unchanged_units=diff.unchanged_units,
    )


class _Builder:
    """The per-delta constants a `Change` needs beyond the two nodes it is built from."""

    def __init__(
        self, act: ActId, from_version: VersionId, to_version: VersionId, in_force: date | None
    ) -> None:
        self.act = act
        self.from_version = from_version
        self.to_version = to_version
        self.in_force = in_force

    def change(self, match: UnitMatch) -> Change:
        if match.change_type is ChangeType.INSERTED and match.after is not None:
            return self._one_sided(match.after, self.to_version, inserted=True)
        if match.change_type is ChangeType.DELETED and match.before is not None:
            return self._one_sided(match.before, self.from_version, inserted=False)
        if match.before is None or match.after is None:
            raise ValueError(f"a {match.change_type} match must carry both sides")
        return self._two_sided(match.before, match.after, match.change_type)

    def _ref(self, node: ProvisionNode, version: VersionId) -> ProvisionRef:
        return ProvisionRef(act=self.act, version=version, location=node.location)

    def _one_sided(self, node: ProvisionNode, version: VersionId, *, inserted: bool) -> Change:
        return Change(
            change_type=ChangeType.INSERTED if inserted else ChangeType.DELETED,
            provision=self._ref(node, version),
            heading=node.heading,
            before=None if inserted else node.text,
            after=node.text if inserted else None,
            applies_from=ApplicabilityUnknown(
                reason=_INSERTED_REASON if inserted else _DELETED_REASON
            ),
            in_force=self.in_force,
            signals=STRUCTURAL_ONLY,
        )

    def _two_sided(
        self, before: ProvisionNode, after: ProvisionNode, change_type: ChangeType
    ) -> Change:
        """A modification or a renumbering: the two cases that carry both texts.

        `DEFERRED` refines `MODIFIED` and only that: a renumbered provision keeps its type
        even if its dates moved, because "it moved" is the more surprising fact about it.
        """
        verdict = read_dates(before, after)
        renumbered = change_type is ChangeType.RENUMBERED
        if not renumbered and verdict.deferred:
            change_type = ChangeType.DEFERRED
        return Change(
            change_type=change_type,
            provision=self._ref(after, self.to_version),
            heading=after.heading,
            before=before.text,
            after=after.text,
            previous_location=before.location if renumbered else None,
            changed_within=changed_sublocations(before, after),
            dates_removed=verdict.removed,
            dates_added=verdict.added,
            applies_from=verdict.applies_from,
            in_force=self.in_force,
            signals=STRUCTURAL_ONLY,
        )
