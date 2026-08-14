"""The resume record: which transitions this installation has already run.

A backfill over a large watchlist is hundreds of transitions, each one several HTTP fetches and
one model call per change, so a run that dies two thirds of the way through must not begin again
at the start. Re-emitting an event into the output repository is already a no-op, because
identical bytes are not rewritten; re-computing one is not, and this file is the difference.

Written the way the poll state is written, and for the same reason: a sibling `.tmp` and an
`os.replace`, which is atomic on POSIX and on Windows, so a process killed mid-write leaves the
previous ledger intact. A file this build cannot read is moved aside rather than deleted and the
run starts from an empty ledger, saying so: losing the record costs money, and losing it silently
costs trust. A read-only caller (a dry run, which promises to write nothing) passes
`set_aside=False` and the unusable file is reported where it lies.

**A failed transition is retried on the next run, up to a limit.** A failure here is a fetch that
timed out or a provider that refused, not a verdict about the document, so the default is to try
again. But an act that will refuse forever would then be re-attempted, and re-paid for, on every
run until somebody noticed, so each row counts the tries it has cost and `exhausted` names the
ones a run should give up on. A transition that produced an answer, including the answer "there
is nothing here to diff", is settled and is skipped.

**The resume unit is one whole transition.** The row is written after a transition finishes, so a
run killed in the middle of one restarts that transition rather than continuing it: its fetches
come back from the disk cache and cost nothing, and its model calls are paid again. Resuming
inside a transition would mean a second, finer progress record for one saved call, and the loop
is not built to be entered halfway.

**One run at a time per ledger.** Two backfills sharing a ledger do not corrupt it, they lose
work: each holds its own in-memory `Ledger`, and `save_ledger` is last-write-wins, so one run's
finished transitions vanish from the record and get paid for twice. `ledger_lock` is the claim
that prevents it.

The default path is relative to the working directory, as `watchlist.toml` is, and deliberately
not in a user-data directory: `eu/cache.py` and `watch/state.py` are the only two modules allowed
to decide where files live outside the repository, and that is asserted.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

__all__ = [
    "DEFAULT_LEDGER",
    "DEFAULT_RETRY_LIMIT",
    "LEDGER_SCHEMA",
    "Attempt",
    "AttemptStatus",
    "Ledger",
    "LedgerBusy",
    "LedgerLoad",
    "ledger_lock",
    "load_ledger",
    "save_ledger",
]

LEDGER_SCHEMA: Final = 1
"""Bumped when the shape below changes. A ledger from another schema is set aside, not read."""

DEFAULT_LEDGER: Final = Path("backfill-ledger.json")
"""Working-directory relative, like `watchlist.toml`. Override it with `--ledger`."""

DEFAULT_RETRY_LIMIT: Final = 3
"""Tries a failing transition gets before a run gives up on it. `--retry-limit 0` never does."""

AttemptStatus = Literal["emitted", "skipped", "failed"]
"""`emitted`: a delta reached the output. `skipped`: the loop answered, with nothing to diff.
`failed`: the attempt did not complete, and the next run tries it again."""


class Attempt(BaseModel):
    """What became of one transition, and how many goes it has taken so far."""

    model_config = ConfigDict(frozen=True)

    key: str
    act: str
    from_version: str
    to_version: str
    status: AttemptStatus
    detail: str = ""
    tries: int = 1


class Ledger(BaseModel):
    """Every transition this installation has attempted."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = LEDGER_SCHEMA
    attempts: tuple[Attempt, ...] = ()

    @property
    def done(self) -> frozenset[str]:
        """Keys a later run skips: the ones that produced an answer. Failures are retried."""
        return frozenset(item.key for item in self.attempts if item.status != "failed")

    def exhausted(self, limit: int) -> frozenset[str]:
        """Keys a later run gives up on: still failing, and already tried `limit` times.

        Separate from `done` on purpose. These are not finished, they are abandoned, and the
        command says so on its own line rather than folding them into a count of successes.
        A limit of zero or less gives up on nothing, which is what `--retry-limit 0` asks for.
        """
        if limit <= 0:
            return frozenset()
        return frozenset(
            item.key for item in self.attempts if item.status == "failed" and item.tries >= limit
        )

    def record(self, attempt: Attempt) -> Ledger:
        """This ledger plus one attempt, replacing any earlier attempt at the same transition.

        `tries` accumulates across the replacement: it is the history of what this transition
        has cost, not a property of the latest go at it. A transition that succeeds on its
        fourth try keeps the four.

        Attempts are kept sorted by key, so a ledger somebody chooses to commit diffs cleanly
        instead of recording the order one particular run happened to visit them in.
        """
        previous = next((item for item in self.attempts if item.key == attempt.key), None)
        counted = (
            attempt
            if previous is None
            else attempt.model_copy(update={"tries": previous.tries + 1})
        )
        kept = [item for item in self.attempts if item.key != attempt.key]
        ordered = sorted((*kept, counted), key=lambda item: item.key)
        return self.model_copy(update={"attempts": tuple(ordered)})


class LedgerLoad(BaseModel):
    """The ledger, and what reading it cost. `detail` is printed; it is never silent."""

    model_config = ConfigDict(frozen=True)

    ledger: Ledger
    existed: bool = False
    recovered: bool = False
    detail: str = ""


def load_ledger(path: Path, *, set_aside: bool = True) -> LedgerLoad:
    """Read the ledger. Never raises: an unusable file is set aside, not obeyed.

    `set_aside=False` is for a caller that has promised to write nothing at all: the unusable
    file stays exactly where it is and the detail says so, so a dry run can report the problem
    without being the thing that changed the disk.
    """
    if not path.is_file():
        return LedgerLoad(ledger=Ledger(), detail=f"no ledger at {path}; starting from nothing")
    try:
        ledger = Ledger.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError) as error:
        return _unusable(path, f"{type(error).__name__}: {error}", set_aside=set_aside)
    if ledger.schema_version != LEDGER_SCHEMA:
        return _unusable(
            path,
            f"ledger schema {ledger.schema_version}, this build reads {LEDGER_SCHEMA}",
            set_aside=set_aside,
        )
    return LedgerLoad(ledger=ledger, existed=True)


def _unusable(path: Path, reason: str, *, set_aside: bool) -> LedgerLoad:
    """Start over from an empty ledger, saying which file was unusable and what happened to it."""
    if not set_aside:
        detail = f"{path} is unusable ({reason}); left in place"
        return LedgerLoad(ledger=Ledger(), existed=True, recovered=True, detail=detail)
    spoiled = path.with_name(path.name + ".corrupt")
    try:
        os.replace(path, spoiled)
        detail = f"{path} was unusable ({reason}); moved to {spoiled}"
    except OSError as error:  # unwritable directory, permissions: say so and carry on
        detail = f"{path} was unusable ({reason}) and could not be moved aside ({error})"
    return LedgerLoad(ledger=Ledger(), existed=True, recovered=True, detail=detail)


def save_ledger(path: Path, ledger: Ledger) -> None:
    """Write the ledger atomically: temp file, then rename. Never a half-written ledger."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class LedgerBusy(RuntimeError):
    """Another run holds this ledger. Carries the lock path, so it can be cleared by hand.

    An error rather than a first-class state, on the same terms as `output.GitError`: the
    first-class states are things the *corpus* reported and the output has to carry. This is an
    operator's environment being wrong before any work starts, and the command turns it into a
    message and a non-zero exit the way it does a missing watchlist.
    """


@contextmanager
def ledger_lock(path: Path) -> Iterator[Path]:
    """Hold an exclusive claim on one ledger for the length of a run.

    `O_CREAT | O_EXCL` is atomic on POSIX and on Windows, which is all this needs: the race it
    prevents is two long-running backfills, not two threads. The claim is released on the way
    out however the run ends, including `KeyboardInterrupt`, so Ctrl-C never poisons the next
    run.

    **A lock left behind by a killed process is not cleared automatically**, and deliberately.
    Deciding a lock is stale means either reading a clock, which this project does in exactly
    one place, or trusting a recorded pid, which is meaningless across a container boundary.
    The pid is written for a human to look at, and the message says which file to delete.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise LedgerBusy(
            f"{lock} exists, so another backfill is using {path}. If no run is in progress, "
            f"delete {lock} and start again."
        ) from error
    try:
        os.write(handle, f"{os.getpid()}\n".encode())
    finally:
        os.close(handle)
    try:
        yield lock
    finally:
        lock.unlink(missing_ok=True)
