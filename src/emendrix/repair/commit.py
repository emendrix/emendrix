"""Opening the repository a repair writes into, committing what moved, and naming the commit.

Split from `cli.py` on 2026-09-04, when a third verb took that module past the line cap. The
seam is the one the commands themselves draw: `cli.py` is the composition root, the place that
reads the clock, builds the adapter for the one verb that needs it and wires the flags; this is
what every verb does with a result once it has one, which is the same thing in every case.

**One commit per entry, and only for entries that actually moved.** Batching would make a single
revert impossible to scope and would hide which act was corrected. A git failure ends the pass,
because the next entry's commit would fail the same way.

**Every subject says the entry was repaired rather than emitted.** They differ only in the
phrase naming what moved, which is why they live together: a reader of `git log` who sees an
emit subject on the day a correction ran is told an amendment was detected that was not.

Nothing here reads a clock, a network or a model. It is handed the date to stamp.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

import typer

from emendrix.backfill.inputs import repository_at
from emendrix.output import GitError, OutputRepo
from emendrix.output.json_out import ChangelogEntry, RepairRecord
from emendrix.repair import corroborate as corroboration_repair
from emendrix.repair import explanations as explain_repair
from emendrix.repair import unexplained as unexplained_repair
from emendrix.repair.entry import RepairResult, with_record

__all__ = [
    "NO_COORDINATES",
    "Subject",
    "corroborated_subject",
    "explained_subject",
    "repository",
    "restated_subject",
    "write_all",
]

NO_COORDINATES = (
    "no coordinate check ran: this repair holds neither provision tree, so the gate counted "
    "nothing rather than counting every coordinate a sentence names as unsupported."
)
"""Said on every pass and recorded on every entry, so an unrun check never reads as a passed one."""

Subject = Callable[[ChangelogEntry, RepairResult], str]
"""How one repair kind names its commit. The count phrase is the only part that differs."""


def repository(path: Path | None) -> OutputRepo:
    """The repository to repair, opened before anything is read, or a message and exit 2."""
    if path is None:
        typer.echo(
            "a repair addresses entries that are already committed: give --output-repo, set "
            "EMENDRIX_OUTPUT_REPO or [output] repo_path.",
            err=True,
        )
        raise typer.Exit(code=2)
    opened = repository_at(path)
    if opened is None:  # pragma: no cover - `repository_at` returns None only for None
        raise typer.Exit(code=2)
    return opened


def write_all(
    repo: OutputRepo,
    results: Sequence[RepairResult],
    kind: str,
    repaired_on: date,
    subject: Subject,
) -> int:
    """Commit each repaired entry on its own, with what the pass did recorded on it.

    `coordinates_checked` is False for every repair mounted here, and it is passed rather than
    left to a default: none of them holds the two provision trees the coordinate-support sets
    are computed from, so the check did not run and an unrun check may not read on a published
    entry as one that passed.
    """
    written = 0
    try:
        for result in results:
            rebuilt = result.entry
            if rebuilt is None:
                continue
            stamped = with_record(
                rebuilt,
                RepairRecord(
                    kind=kind,
                    repaired_on=repaired_on,
                    addressed=result.addressed,
                    repaired=result.repaired,
                    remaining=result.remaining,
                    usage=result.usage,
                    coordinates_checked=False,
                ),
            )
            outcome = repo.write(stamped, message=subject(stamped, result))
            if not outcome.unchanged:
                written += 1
                typer.echo(f"  {outcome.changelog}: committed {outcome.revision[:7]}")
    except GitError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    return written


def corroborated_subject(entry: ChangelogEntry, result: RepairResult) -> str:
    """`32019R2088: 02019R2088-20260702 corroboration repaired (2 changes)`."""
    return _message(entry, f"{corroboration_repair.KIND} repaired ({result.repaired} changes)")


def explained_subject(entry: ChangelogEntry, result: RepairResult) -> str:
    """`32013R0575: 02013R0575-20140101 explanations repaired (3 of 4 changes)`.

    Both counts, because a change that failed again is part of what the pass did and a subject
    naming only the successes would read as though every gap had been closed.
    """
    phrase = f"{explain_repair.KIND} repaired ({result.repaired} of {result.addressed} changes)"
    return _message(entry, phrase)


def restated_subject(entry: ChangelogEntry, result: RepairResult) -> str:
    """`32016R1011: 02016R1011-20210213 unexplained notes restated (1 of 2 changes)`.

    Both counts for the same reason, and here the difference between them is a note the pass
    read and declined to touch rather than one it failed on.
    """
    phrase = (
        f"{unexplained_repair.KIND} notes restated "
        f"({result.repaired} of {result.addressed} changes)"
    )
    return _message(entry, phrase)


def _message(entry: ChangelogEntry, phrase: str) -> str:
    """The subject and the one line saying what did not move.

    The subject says what was repaired rather than what was emitted, because a reader of
    `git log` would otherwise be told an amendment was detected on the day a correction ran.
    """
    return (
        f"{entry.act.key}: {entry.to_version} {phrase}\n"
        "\n"
        "The verbatim texts, the sibling explanations and the detection date did not move."
    )
