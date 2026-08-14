"""`emendrix.watch` — the WATCH stage: what to look at, what has been seen, what is new.

```
config   watchlist.toml → the acts to watch, and the cheap index that filters the firehose
state    the persisted seen-set, window cursor and pending consolidations; atomic on disk
events   the typed vocabulary: PollWindow in, AmendmentEvent + PollResult out
poll     poll_once: feed entries + watchlist + state → those events and a new state
source   FeedWatchSource: one whole poll (fetch, resolve, persist) as a callable seam
cli      `emendrix watch --once`, the one place here that reads a clock
```

Two commands poll: `emendrix watch --once`, which prints what it found, and `emendrix run
--once`, whose graph diffs it. One cursor over one feed means one implementation, which is why
`source` exists and why the graph's `WatchSource` seam is satisfied by the same object the watch
command uses.

Three properties this package exists to have, in the order they cause production bugs:

- **Idempotent.** Windows overlap on purpose and the same work is re-notified dozens of times
  a day, so nothing is emitted twice: entries dedupe by `cellarId@updated`, and what they
  resolve to dedupes by `act@version`.
- **Resumable.** The window cursor and the seen-set are written before the next poll runs, by
  write-tmp-and-rename, so a process killed mid-run repeats work instead of losing it. A
  corrupt or unreadable state file is set aside and the poll starts from `--since`.
- **Clock-free below the boundary.** `poll_once` takes an explicit window and an explicit
  observation date. `watch/cli.py` is the only module here that asks what day it is.

"Amended, but not consolidated yet" is a value, not a retry loop: it is emitted once, written
into the state, re-checked on every later poll, and emitted once more, as an ordinary version
event, when the text finally appears roughly ten days later.
"""

from emendrix.watch.config import WatchedAct, WatchIndex, Watchlist, load_watchlist
from emendrix.watch.events import (
    AmendmentEvent,
    PollResult,
    PollStats,
    PollWindow,
    VersionSource,
)
from emendrix.watch.poll import poll_once
from emendrix.watch.source import (
    DEFAULT_LOOKBACK_DAYS,
    OVERLAP,
    FeedWatchSource,
    covered_to,
    window_start,
)
from emendrix.watch.state import (
    PendingConsolidation,
    SeenEntry,
    StateLoad,
    WatchState,
    default_state_path,
    load_state,
    save_state,
)

__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "OVERLAP",
    "AmendmentEvent",
    "FeedWatchSource",
    "PendingConsolidation",
    "PollResult",
    "PollStats",
    "PollWindow",
    "SeenEntry",
    "StateLoad",
    "VersionSource",
    "WatchIndex",
    "WatchState",
    "WatchedAct",
    "Watchlist",
    "covered_to",
    "default_state_path",
    "load_state",
    "load_watchlist",
    "poll_once",
    "save_state",
    "window_start",
]
