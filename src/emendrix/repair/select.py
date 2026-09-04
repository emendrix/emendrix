"""Walking an output repository: every committed entry, and how to narrow the set.

The layout and the documents are the output repository writer's own, so a file that does not
validate means the repository was edited by hand or written by a different version of the
schema: loud, named, and not something to skip quietly. A repair that silently skipped a file
it could not read would report a clean pass over a repository it had not seen all of.

Which entries a repair kind would actually touch is that kind's own question and lives beside
it. This module walks the tree and knows nothing about what any repair does.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from emendrix.output import ChangelogEntry
from emendrix.repair.entry import RepairTarget

__all__ = ["for_act", "read_targets"]


def read_targets(root: Path) -> tuple[RepairTarget, ...]:
    """Every committed event in one output repository, in sorted path order."""
    targets: list[RepairTarget] = []
    for path in sorted(root.glob("*/*/changes/*.json")):
        try:
            entry = ChangelogEntry.model_validate_json(path.read_bytes())
        except ValueError as error:
            raise ValueError(f"{path} is not a changelog document emendrix wrote: {error}") from (
                error
            )
        targets.append(RepairTarget(path=path.relative_to(root), entry=entry))
    return tuple(targets)


def for_act(targets: Iterable[RepairTarget], key: str) -> tuple[RepairTarget, ...]:
    """Only the entries of one act, by the key the corpus gave it.

    The key is opaque here, as it is everywhere below the composition root: this compares the
    string the entry carries and never parses it.
    """
    return tuple(target for target in targets if target.entry.act.key == key)
