"""`emendrix watch` — the composition root of the WATCH stage, and its only clock read.

```bash
uv run emendrix watch --once                                  # since the last successful poll
uv run emendrix watch --once --since 2026-08-05               # or from an explicit date
uv run emendrix watch --loop --interval 86400                 # a while/sleep, deliberately dumb
uv run emendrix watch --once --since 2026-08-05T10:00:00 --until 2026-08-05T10:05:00 \
    --fixture-dir tests/fixtures/eu --state-file /tmp/state.json     # offline, no network
```

The window is `[since, until)`. `--since` defaults to the end of the last successful poll,
backed off by an hour so a run that died mid-write repeats work instead of losing it; with no
state at all it defaults to fourteen days, which covers the ≈10-day consolidation lag.
`--until` defaults to **midnight this morning**, not to now: a window is only closed once the
day it covers is over, so nothing is skipped by the cursor advancing past entries that had not
been published when the poll ran.

Both bounds accept `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`. The endpoint reads them in its own
timezone rather than UTC; the hour of overlap and the dedupe absorb the difference, which is
cheaper and more honest than pretending to know the server's zone.

`--loop` is a `while True: poll; sleep` and stays that way on purpose — a deployment's cron or
systemd timer is a better scheduler than anything this file could grow into.
"""

from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix import DISCLAIMER
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import FixtureResponseCache, ResponseCache
from emendrix.eu.feed import DEFAULT_CHANNEL
from emendrix.eu.http import today_utc
from emendrix.watch.config import Watchlist, load_watchlist
from emendrix.watch.events import AmendmentEvent, PollResult
from emendrix.watch.source import FeedWatchSource
from emendrix.watch.state import default_state_path

__all__ = ["DATE_FORMATS", "render_events", "watch"]

DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]

_WATCHLIST = Path("watchlist.toml")


def watch(
    once: Annotated[
        bool, typer.Option("--once/--loop", help="Poll a single window, or keep polling.")
    ] = True,
    since: Annotated[
        datetime | None,
        typer.Option(
            "--since",
            formats=DATE_FORMATS,
            help="Window start. Defaults to the end of the last successful poll.",
        ),
    ] = None,
    until: Annotated[
        datetime | None,
        typer.Option("--until", formats=DATE_FORMATS, help="Window end. Defaults to midnight."),
    ] = None,
    watchlist_path: Annotated[
        Path, typer.Option("--watchlist", help="The acts to watch.")
    ] = _WATCHLIST,
    state_file: Annotated[
        Path | None,
        typer.Option("--state-file", help="Where the seen-state lives. Defaults to user data."),
    ] = None,
    channel: Annotated[
        str, typer.Option("--channel", help="Notification channel segment.")
    ] = DEFAULT_CHANNEL,
    interval: Annotated[
        int, typer.Option("--interval", help="Seconds between polls under --loop.")
    ] = 86400,
    fixture_dir: Annotated[
        Path | None,
        typer.Option("--fixture-dir", help="Read from a pinned fixture set, never the network."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the events as JSON.")] = False,
) -> None:
    """Poll the notification feed for amendments to the watched acts."""
    path = state_file if state_file is not None else default_state_path()
    while True:
        # Re-read the watchlist each poll, so a long-running `--loop` picks up an edited file.
        try:
            watchlist = load_watchlist(watchlist_path)
        except (FileNotFoundError, ValueError) as error:
            # The one hand-written input in the system: say what is wrong with it and stop.
            typer.echo(str(error), err=True)
            raise typer.Exit(code=2) from error
        result = _poll(
            watchlist=watchlist,
            state_path=path,
            channel=channel,
            since=since,
            until=until,
            fixture_dir=fixture_dir,
            observed_on=today_utc(),
        )
        typer.echo(
            result.model_dump_json(indent=2)
            if as_json
            else render_events(result, len(watchlist.acts))
        )
        if once:
            return
        since = None  # subsequent windows resume from the state this poll just wrote
        time.sleep(interval)


def _poll(
    *,
    watchlist: Watchlist,
    state_path: Path,
    channel: str,
    since: datetime | None,
    until: datetime | None,
    fixture_dir: Path | None,
    observed_on: date,
) -> PollResult:
    """One window, end to end: read, fetch, poll, persist. The clock is already a value here.

    The sequence itself is `watch/source.py`, shared with `emendrix run --once` so the two
    commands cannot end up with two cursors over one feed.
    """
    end = until if until is not None else datetime.combine(observed_on, datetime.min.time())
    cache: ResponseCache | None = None if fixture_dir is None else FixtureResponseCache(fixture_dir)
    with EuCorpusAdapter.build(observed_on=observed_on, cache=cache) as adapter:
        source = FeedWatchSource(
            adapter,
            watchlist=watchlist,
            state_path=state_path,
            channel=channel,
            notice=lambda message: typer.echo(message, err=True),
        )
        return source.poll(source.window(since=since, until=end, observed_on=observed_on))


def render_events(result: PollResult, watched: int) -> str:
    """The plain report: the window's numbers, then one block per event. Byte-stable."""
    stats = result.stats
    lines = [
        f"{stats.entries} notifications · {stats.matched} naming a watched act "
        f"({watched} watched) · {stats.duplicates} already seen",
        f"{len(result.events)} events · {stats.suppressed} suppressed as already reported · "
        f"{stats.pending_checked} pending re-checked, {stats.pending_resolved} resolved",
    ]
    # Per-row waiting lines are printed below, and a reader of ninety watched acts scrolls past
    # them; the headline is what says the oldest has been waiting longer than the lag allows.
    if stats.pending_waiting:
        lines.append(
            f"{stats.pending_waiting} still waiting for text · oldest first seen "
            f"{stats.pending_oldest_days} day(s) ago"
        )
    lines.append("")
    for event in result.events:
        lines.extend(_event_lines(event))
    if not result.events:
        lines.append("nothing new.")
    if stats.truncated:
        lines.append(
            "! this window was not read to its end; the cursor stopped where the feed did "
            f"({result.state.last_window_end}) and the next poll resumes from there"
        )
    for waiting in result.state.pending:
        lines.append(
            f"? still waiting  {waiting.act_key} {waiting.version or '(latest)'} — "
            f"{waiting.state}, first seen {waiting.first_seen.isoformat()}, "
            f"{waiting.checks} check(s)"
        )
    lines.extend(("", DISCLAIMER))
    return "\n".join(lines)


def _event_lines(event: AmendmentEvent) -> list[str]:
    if event.ready:
        previous = event.previous_version or "(none)"
        return [
            f"+ new version   {event.act} {previous} -> {event.new_version}",
            f"    announced by: {event.trigger}",
        ]
    unavailable = event.unavailable
    state = unavailable.state if unavailable is not None else "unknown"
    detail = unavailable.detail if unavailable is not None else ""
    return [
        f"~ {state:<13} {event.act} {event.target_version or '(latest)'}",
        f"    {detail}",
        f"    announced by: {event.trigger}",
    ]
