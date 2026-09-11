"""The one place in the package that constructs an HTTP client.

Everything else — the diff, the classification, the corroboration, the gate, the renderer —
reads the disk cache or a fixture. That is not a style preference: it is what makes CI
offline by construction and the pipeline deterministic. `tests/test_architecture.py` greps
for violations.

What this module knows about the Publications Office, all verified 2026-08-06:

- **HTTPS works** on `publications.europa.eu/resource/…` and is used here; it returns the
  same bytes and the same `ETag` as plain HTTP.
- **A 404 is an answer.** Asking for a manifestation that does not exist in a language,
  `consolidation/2024R1689%2F20240712.ENG.fmx4`, returns `404` with the body
  `Resource [system 'consolidation' - id '…'] not found.`, not a 406.
- **A 406 is also an answer,** and a different one: it comes from *notice* requests carrying
  `Accept-Language: eng` for a work with no English expression
  (`celex/02024R1689-20240712` → `406 … Not found work … + language(s) [eng]`).
- Neither is retried. Retrying is for `5xx` and transport failures only, three attempts,
  exponential backoff; anything else would hammer a public endpoint to be told the same
  thing again.

Every non-`5xx` response is handed back as it came, including the ones nobody expects: a
`403`, a `429`, a challenge page. This module deliberately does not interpret them.
`eu/cellar.py` does, and it reads *only* `404` and `406` as statements about the document.
Anything else is the server refusing the client, and must never become a claim about an act.

`robots.txt` on `publications.europa.eu` is `Allow: /` (checked 2026-08-05); a polite delay
between *network* calls is still applied, and cache hits never sleep.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from types import TracebackType
from typing import Final, Self

import httpx

from emendrix import __version__
from emendrix.eu.cache import (
    CachedResponse,
    DiskResponseCache,
    FixtureMissing,
    ResponseCache,
    cache_key,
    entry_for,
)
from emendrix.eu.identifiers import ResourceRef

__all__ = [
    "BASE_URL",
    "NOTICE_MAX_AGE_ENV",
    "NOTICE_MAX_AGE_S",
    "POLITE_DELAY_ENV",
    "POLITE_DELAY_S",
    "USER_AGENT",
    "CellarHttp",
    "OfflineFetch",
    "notice_max_age",
    "polite_delay",
    "today_utc",
]

BASE_URL: Final = "https://publications.europa.eu"

# The Publications Office asks for an identifying agent, and the contact URL it carries has to
# resolve for a server operator who follows it. This one is the public repository, registered
# 2026-08-12.
USER_AGENT: Final = f"emendrix/{__version__} (+https://github.com/emendrix/emendrix)"

DEFAULT_TIMEOUT: Final = 120.0
"""Consolidated Formex zips of a big act take tens of seconds to build server-side."""

MAX_ATTEMPTS: Final = 3
RETRY_BACKOFF_S: Final = 2.0
POLITE_DELAY_S: Final = 1.0

POLITE_DELAY_ENV: Final = "EMENDRIX_POLITE_DELAY_S"
"""How an operator turns the delay up without editing code. `polite_delay` reads it."""

NOTICE_MAX_AGE_S: Final = 21600.0
"""Seconds a notice may be served from cache before it is asked for again.

A notice is a listing about an act and grows whenever the publisher consolidates, so an entry
for one held without a life is a standing claim that the act has no new versions. Six hours
rather than an hour because a poll's window ends at midnight this morning and the cursor
advances by whole days, so a refresh more often than daily buys no detection at all.
"""

NOTICE_MAX_AGE_ENV: Final = "EMENDRIX_NOTICE_MAX_AGE_S"
"""How an operator changes it without editing code. `notice_max_age` reads it."""


ACCEPT_ZIP: Final = "application/zip"
ACCEPT_TREE_NOTICE: Final = "application/xml;notice=tree"
ACCEPT_BRANCH_NOTICE: Final = "application/xml;notice=branch"


class OfflineFetch(RuntimeError):
    """A cache-miss happened where the network is not allowed (CI, fixture-backed tests)."""


def _utc_now() -> datetime:
    """The only clock read in the fetch path, and it is provenance, not logic."""
    return datetime.now(UTC)


def today_utc() -> date:
    """Today, for a CLI that has to default an observation date to something.

    It lives here because this is the one module allowed to read a clock at all
    (`tests/test_architecture.py`). Callers take a value and pass it down; nothing inside the
    diff, the classification, the gate or the rendering ever asks what time it is.
    """
    return _utc_now().date()


def polite_delay(
    flag: float | None = None, *, environment: Mapping[str, str] | None = None
) -> float:
    """Seconds to wait between network calls: flag > environment > `POLITE_DELAY_S`.

    The delay exists because this project fetches a lot of documents from one public endpoint,
    and a backfill over an act's whole history is the workload that most wants to be gentler
    than the default.

    A value that is not a non-negative number is refused by name rather than falling back to
    the default: "the delay you configured is not the delay you got" is precisely the sort of
    quiet decision that ends in a public server being hammered by a job left running overnight.
    """
    if flag is not None:
        return flag
    raw = (environment if environment is not None else os.environ).get(POLITE_DELAY_ENV)
    if raw is None:
        return POLITE_DELAY_S
    try:
        seconds = float(raw)
    except ValueError as error:
        raise ValueError(f"{POLITE_DELAY_ENV}={raw!r} is not a number of seconds") from error
    if seconds < 0:
        raise ValueError(f"{POLITE_DELAY_ENV}={raw!r} is negative; a delay cannot be")
    return seconds


def notice_max_age(
    flag: float | None = None, *, environment: Mapping[str, str] | None = None
) -> timedelta:
    """How long a notice stays fresh: flag > environment > `NOTICE_MAX_AGE_S`.

    Refused by name where it is not a number of seconds, as `polite_delay` refuses one: a value
    silently not the one configured is how a poller ends up reading a year-old inventory.
    """
    if flag is not None:
        return timedelta(seconds=flag)
    raw = (environment if environment is not None else os.environ).get(NOTICE_MAX_AGE_ENV)
    if raw is None:
        return timedelta(seconds=NOTICE_MAX_AGE_S)
    try:
        seconds = float(raw)
    except ValueError as error:
        raise ValueError(f"{NOTICE_MAX_AGE_ENV}={raw!r} is not a number of seconds") from error
    if seconds < 0:
        raise ValueError(f"{NOTICE_MAX_AGE_ENV}={raw!r} is negative; an age cannot be")
    return timedelta(seconds=seconds)


class CellarHttp:
    """Content-negotiated, cached, retrying GETs against CELLAR.

    Construct one and share it: the cache is per-instance-cheap but the connection pool is
    not. `close()` (or the context manager) releases the pool; a client is only opened when
    a request actually misses the cache, so a fixture-backed run opens no socket at all.
    """

    def __init__(
        self,
        *,
        cache: ResponseCache | None = None,
        base_url: str = BASE_URL,
        user_agent: str = USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        max_attempts: int = MAX_ATTEMPTS,
        backoff_s: float = RETRY_BACKOFF_S,
        polite_delay_s: float = POLITE_DELAY_S,
        notice_max_age_s: float | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.cache: ResponseCache = cache if cache is not None else DiskResponseCache()
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.polite_delay_s = polite_delay_s
        # Resolved here rather than at the composition root, unlike `polite_delay_s`: the eval
        # and fixture commands construct a client directly and none should have to know of this.
        self.notice_max_age = notice_max_age(notice_max_age_s)
        self._transport = transport
        self._sleep = sleep
        self._now = now
        self._client: httpx.Client | None = None
        self._network_calls = 0

    # ----------------------------------------------------------------- lifecycle

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @property
    def network_calls(self) -> int:
        """How many requests actually left the machine. Tests assert this is zero."""
        return self._network_calls

    # -------------------------------------------------------------------- fetch

    def url_for(self, target: ResourceRef | str) -> str:
        if isinstance(target, ResourceRef):
            return f"{self.base_url}{target.path}"
        if target.startswith(("http://", "https://")):
            return target
        return f"{self.base_url}/{target.lstrip('/')}"

    def get(
        self,
        target: ResourceRef | str,
        *,
        accept: str,
        accept_language: str | None = "eng",
        volatile: bool = False,
    ) -> CachedResponse:
        """Fetch a resource, from the cache if it is there and still counts.

        Returns the response whatever its status: a `404` and a `406` are answers about the
        document, and the caller (`eu/cellar.py`) turns them into first-class states.

        `volatile` marks a resource whose purpose is to change: a hit for one older than
        `notice_max_age` is a miss, and everything else is served from any hit as before.
        """
        url = self.url_for(target)
        key = cache_key("GET", url, accept, accept_language)
        cached = self.cache.get(key)
        if cached is not None and not self._expired(cached, volatile=volatile):
            return cached
        if self.cache.offline:
            raise FixtureMissing(
                f"no fixture for GET {url} (accept={accept!r}, "
                f"accept-language={accept_language!r}, key={key}). "
                "Pin it with `uv run python -m emendrix.eu.fetch_fixtures`."
            )
        response = self._fetch(url, key=key, accept=accept, accept_language=accept_language)
        self.cache.store(response)
        return response

    def _expired(self, cached: CachedResponse, *, volatile: bool) -> bool:
        """Whether a hit is too old to answer with. Offline is exempt before the age is read."""
        if not volatile or self.cache.offline:
            return False
        fetched = cached.entry.fetched_at
        if fetched.tzinfo is None:
            return True  # not comparable with a zoned stamp, and asking again is the safe answer
        return fetched < self._now() - self.notice_max_age

    def _fetch(
        self, url: str, *, key: str, accept: str, accept_language: str | None
    ) -> CachedResponse:
        headers = {"User-Agent": self.user_agent, "Accept": accept}
        if accept_language is not None:
            headers["Accept-Language"] = accept_language

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            if attempt > 1:
                self._sleep(self.backoff_s * 2 ** (attempt - 2))
            elif self._network_calls:
                self._sleep(self.polite_delay_s)
            self._network_calls += 1
            try:
                response = self._http().get(url, headers=headers)
            except httpx.TransportError as error:  # timeouts, connection resets, DNS
                last_error = error
                continue
            if response.status_code < 500:
                return CachedResponse(
                    entry=entry_for(
                        key=key,
                        url=url,
                        accept=accept,
                        accept_language=accept_language,
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type"),
                        fetched_at=self._now(),
                        body=response.content,
                        file=f"{key}.body",
                    ),
                    body=response.content,
                )
            last_error = httpx.HTTPStatusError(
                f"{response.status_code} from {url}", request=response.request, response=response
            )
        message = f"CELLAR unreachable after {self.max_attempts} attempts: {url}"
        raise ConnectionError(message) from last_error

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True, timeout=self.timeout, transport=self._transport
            )
        return self._client
