"""What the poller remembers between runs, and how it survives being killed mid-write.

One JSON file, four things in it:

- **`last_window_end`** — the cursor. The next poll starts here (minus a deliberate overlap),
  and it advances even when the window held nothing, or the next run re-scans forever.
- **`seen`** — entry identities, so an overlapping window emits nothing twice. Bounded to a
  rolling 60 days: the feed's own window is what makes an older identity unreachable, and an
  unbounded set would grow by ~3,000 records a day forever.
- **`emitted`** — what those entries *resolved to* (`eu:32024R1689@02024R1689-20260727`). This
  is the dedupe that matters: CELLAR re-notifies the same consolidation every few minutes for
  hours, under fresh entry ids each time. Kept for a year, because a pending consolidation
  that resolves months later must still not re-announce a version already reported.
- **`pending`** — acts amended but not yet consolidated. Re-checked on every poll, resolving
  exactly once.

## Durability

`save_state` writes a sibling `.tmp` and `os.replace`s it, which is atomic on POSIX and on
Windows: a reader either sees the whole old file or the whole new one, never a half-written
one. If anything fails before the rename, the temporary file is removed and the previous
state survives untouched.

`load_state` never raises on the contents of the file. Missing → empty state. Unreadable,
malformed, or written by a future schema → the file is moved aside to `.corrupt` and an empty
state is returned, so the poll starts from `--since` instead of dying. The caller is told
which happened (`StateLoad.recovered`) and says so, because silently forgetting everything
that has been seen is exactly the bug this module exists to prevent.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import platformdirs
from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "EMITTED_RETENTION_DAYS",
    "SEEN_RETENTION_DAYS",
    "STATE_SCHEMA",
    "EmittedEvent",
    "PendingConsolidation",
    "SeenEntry",
    "StateLoad",
    "WatchState",
    "default_state_path",
    "load_state",
    "prune",
    "save_state",
]

STATE_SCHEMA: Final = 1
"""Bumped when the shape below changes. An older or newer file is set aside, never guessed at."""

SEEN_RETENTION_DAYS: Final = 60
"""Rolling window for entry identities — comfortably longer than any window worth polling."""

EMITTED_RETENTION_DAYS: Final = 365
"""Rolling window for resolved `act@version` keys. Long, because pending states resolve late."""

STATE_NAME: Final = "watch-state.json"


def default_state_path() -> Path:
    """The user-data directory, not the cache: losing this file loses work, not just bytes.

    (`eu/cache.py` owns the *cache* location and this module owns this one — the two are the
    only modules allowed to name a platform directory, and `tests/test_architecture.py` says
    so.)
    """
    return Path(platformdirs.user_data_dir("emendrix")) / STATE_NAME


class SeenEntry(BaseModel):
    """One feed entry already processed, and the window date it was processed in."""

    model_config = ConfigDict(frozen=True)

    entry_id: str
    on: date


class EmittedEvent(BaseModel):
    """One `act@version` already reported, so no later poll reports it again."""

    model_config = ConfigDict(frozen=True)

    key: str
    on: date


class PendingConsolidation(BaseModel):
    """An act the feed says changed, whose new text is not fetchable yet.

    `version` is the consolidated id the feed announced, when it announced one; `state` names
    which first-class state the last check produced (`consolidation_pending` or
    `english_unavailable`), so the record says what it is waiting for rather than merely that
    it is waiting.
    """

    model_config = ConfigDict(frozen=True)

    act_key: str = Field(description="`str(ActId)` — e.g. `eu:32024R1689`.")
    celex: str
    version: str | None = None
    state: str = "consolidation_pending"
    first_seen: date
    last_checked: date
    checks: int = 1
    detail: str = ""

    @property
    def key(self) -> str:
        return f"{self.act_key}@{self.version or 'latest'}"


class WatchState(BaseModel):
    """Everything the poller carries between runs. Frozen: a poll returns a new one."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = STATE_SCHEMA
    last_window_end: datetime | None = None
    seen: tuple[SeenEntry, ...] = ()
    emitted: tuple[EmittedEvent, ...] = ()
    pending: tuple[PendingConsolidation, ...] = ()

    @property
    def seen_ids(self) -> frozenset[str]:
        return frozenset(entry.entry_id for entry in self.seen)

    @property
    def emitted_keys(self) -> frozenset[str]:
        return frozenset(entry.key for entry in self.emitted)


class StateLoad(BaseModel):
    """A state, and the honest account of where it came from."""

    model_config = ConfigDict(frozen=True)

    state: WatchState
    existed: bool = False
    recovered: bool = Field(
        default=False, description="True if an unusable file was set aside and forgotten."
    )
    detail: str = ""


def prune(state: WatchState, *, on: date) -> WatchState:
    """Drop entries and emitted keys older than their retention window, relative to `on`.

    Takes the horizon date as an argument rather than reading a clock — the poller's window
    end is what "now" means here, which is also what makes the pruning testable.
    """
    seen_floor = on - timedelta(days=SEEN_RETENTION_DAYS)
    emitted_floor = on - timedelta(days=EMITTED_RETENTION_DAYS)
    return state.model_copy(
        update={
            "seen": tuple(entry for entry in state.seen if entry.on >= seen_floor),
            "emitted": tuple(entry for entry in state.emitted if entry.on >= emitted_floor),
        }
    )


def load_state(path: Path) -> StateLoad:
    """Read the state file. Never raises: an unusable file is set aside, not obeyed."""
    if not path.is_file():
        return StateLoad(state=WatchState(), detail=f"no state file at {path}")
    try:
        state = WatchState.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError) as error:
        return _set_aside(path, f"{type(error).__name__}: {error}")
    if state.schema_version != STATE_SCHEMA:
        return _set_aside(
            path, f"state schema {state.schema_version}, this build reads {STATE_SCHEMA}"
        )
    return StateLoad(state=state, existed=True)


def _set_aside(path: Path, reason: str) -> StateLoad:
    """Move an unusable state file out of the way and start over, saying so."""
    spoiled = path.with_name(path.name + ".corrupt")
    try:
        os.replace(path, spoiled)
        detail = f"{path} was unusable ({reason}); moved to {spoiled}"
    except OSError as error:  # unreadable directory, permissions — say so and continue
        detail = f"{path} was unusable ({reason}) and could not be moved aside ({error})"
    return StateLoad(state=WatchState(), existed=True, recovered=True, detail=detail)


def save_state(path: Path, state: WatchState) -> None:
    """Write the state atomically: temp file, flush, rename. Never a half-written state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
