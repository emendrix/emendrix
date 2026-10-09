"""Per-client-address limits, kept in memory and measured on the injected monotonic clock.

Nothing here is stored: a restart forgets every window, which is acceptable for a limit whose
only job is to slow a flood. The per-address limit on login links is not here, because it must
survive a restart; it is a count of the `login_tokens` rows the address already has.

Each app holds its own windows on `app.state`, so two apps (two tests) never share a count.
"""

from __future__ import annotations

from collections import deque
from typing import Final

from fastapi import HTTPException, Request

from emendrix_service.clock import Clock
from emendrix_service.web.client import client_ip

__all__ = [
    "IP_LINKS_PER_HOUR",
    "IP_POSTS_PER_HOUR",
    "SlidingWindow",
    "link_window",
    "post_limit",
]

HOUR: Final = 3600.0
IP_LINKS_PER_HOUR: Final = 20
IP_POSTS_PER_HOUR: Final = 300
"""Form posts other than a link request, per client address: far above what a person editing
watchlists sends, and low enough to make a scripted flood visible."""

SWEEP_AT: Final = 10_000
"""Keys held before stale ones are dropped, so a scan from many addresses cannot grow memory."""


class SlidingWindow:
    """At most `limit` hits per key in any `window_seconds`, on `clock.monotonic()`."""

    def __init__(self, limit: int, window_seconds: float, clock: Clock) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def _recent(self, key: str, now: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        return hits

    def hit(self, key: str) -> bool:
        """Count one hit for `key` and say whether it is within the limit.

        A refused hit is not counted, so a client that keeps trying is let in again as soon as
        its earlier hits age out.
        """
        now = self._clock.monotonic()
        if len(self._hits) >= SWEEP_AT:
            for stale in [k for k in self._hits if not self._recent(k, now)]:
                del self._hits[stale]
        hits = self._recent(key, now)
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


def _window(request: Request, name: str, limit: int) -> SlidingWindow:
    state = request.app.state
    window: SlidingWindow | None = getattr(state, name, None)
    if window is None:
        window = SlidingWindow(limit, HOUR, state.clock)
        setattr(state, name, window)
    return window


def link_window(request: Request) -> SlidingWindow:
    """The app's window on login-link requests per client address."""
    return _window(request, "link_window", IP_LINKS_PER_HOUR)


async def post_limit(request: Request) -> None:
    """A dependency answering 429 once a client address has posted too many forms.

    Not for a link request: that one answers the same page whatever happens, and has its own
    window inside `request_link`.
    """
    if not _window(request, "post_window", IP_POSTS_PER_HOUR).hit(
        client_ip(request, request.app.state.settings)
    ):
        raise HTTPException(status_code=429)
