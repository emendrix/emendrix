"""Pin test documents from CELLAR — reproducibly, by identifier, never by hand.

```bash
uv run python -m emendrix.eu.fetch_fixtures            # populate tests/fixtures/eu/
uv run python -m emendrix.eu.fetch_fixtures --list     # what is pinned, and why
```

Two rules make this script the only honest way to get fixtures into the repo.

**Nothing is hand-edited.** Fixtures are real responses to real requests, and where a
document is too big to commit whole it is *trimmed by a rule that lives here* — pruning a
notice to the elements the parser reads, dropping the `.tif` page scans a Formex package
carries. Re-running reproduces the same bytes. The manifest records the digest of the
untrimmed response alongside the trimmed one, so a claim about a fixture is checkable.

**Nothing is guessed.** The pins name an act and a version, not a URL; the request that gets
recorded is whatever `CellarClient` decides to make. That way the fixture set is exactly the
set of requests the code under test makes — including the 404s the fallback chain is *driven*
by, which are cached like any other answer (`eu/cache.py`).

Re-runs are network no-ops: everything already in the user cache is served from there.

**What is pinned lives next door,** in `eu/fixture_pins.py`: the hand-written document set the
parser and diff tests need, and the notification-feed windows the watcher runs on. The eval
corpus chooses many more documents by a rule rather than by hand and writes them into
`<fixture dir>/eval_pins.json`; this module reads that file by default and pins the union. One
directory, one manifest, one owner — and the plain command above still rebuilds the *complete*
set, which is what keeps the two from drifting apart.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Final
from urllib.parse import parse_qs, urlparse

from emendrix.eu.cache import (
    CachedResponse,
    DiskResponseCache,
    ManifestEntry,
    ResponseCache,
    entry_for,
    write_manifest,
)
from emendrix.eu.cellar import CellarClient
from emendrix.eu.feed import fetch_notifications
from emendrix.eu.fixture_pins import (
    EXTRA_PINS_NAME,
    FEED_PINNED,
    ORIGINAL,
    PINNED,
    FeedPin,
    Pin,
    PinSet,
    merge_pins,
    read_extra_pins,
    write_extra_pins,
)
from emendrix.eu.http import ACCEPT_BRANCH_NOTICE, ACCEPT_TREE_NOTICE, CellarHttp
from emendrix.eu.identifiers import Celex, ConsolidatedId
from emendrix.eu.trims import BRANCH_SPEC, TREE_SPEC, trim_formex_zip, trim_notice

__all__ = [
    "EXTRA_PINS_NAME",
    "FEED_PINNED",
    "ORIGINAL",
    "PINNED",
    "FeedPin",
    "Pin",
    "PinSet",
    "build_fixtures",
    "main",
    "merge_pins",
    "read_extra_pins",
    "write_extra_pins",
]

DEFAULT_OUT: Final = Path("tests/fixtures/eu")
OBSERVED_ON: Final = date(2026, 8, 6)
"""The date the pinned set was assembled. Fixtures are a snapshot; this is its timestamp."""


def _trim(response: CachedResponse) -> tuple[bytes, str | None]:
    """Which trim rule applies to a response, if any — see `eu/trims.py`."""
    accept = response.entry.accept or ""
    if response.status_code != 200:
        return response.body, None
    if accept == ACCEPT_TREE_NOTICE:
        return trim_notice(response.body, TREE_SPEC), "notice-tree"
    if accept == ACCEPT_BRANCH_NOTICE:
        return trim_notice(response.body, BRANCH_SPEC), "notice-branch"
    if "zip" in accept:
        return trim_formex_zip(response.body), "formex-xml-only"
    return response.body, None


# ------------------------------------------------------------------------ recording


class _Recorder:
    """A cache that remembers every response the client touched, so it can be exported."""

    def __init__(self, inner: ResponseCache) -> None:
        self.inner = inner
        self.seen: dict[str, CachedResponse] = {}

    @property
    def offline(self) -> bool:
        return self.inner.offline

    def get(self, key: str) -> CachedResponse | None:
        found = self.inner.get(key)
        if found is not None:
            self.seen[key] = found
        return found

    def store(self, response: CachedResponse) -> None:
        self.inner.store(response)
        self.seen[response.entry.key] = response


def _feed_filename(url: str) -> str:
    """`notification_ingestion_20260805T1000_20260805T1005_p1.atom.xml` — window and page."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    bounds = "_".join(
        value[0].replace("-", "").replace(":", "")[:13]
        for value in (query.get("startDate", [""]), query.get("endDate", [""]))
    )
    page = query.get("page", ["1"])[0]
    return f"notification_{parsed.path.rsplit('/', 1)[-1]}_{bounds}_p{page}.atom.xml"


def _filename(response: CachedResponse) -> str:
    """A readable, collision-free name: the resource path, plus what was asked of it."""
    if "/webapi/notification/" in response.url:
        return _feed_filename(response.url)
    resource = response.url.partition("/resource/")[2] or response.url
    stem = resource.replace("%2F", "_").replace("/", "_")
    accept = response.entry.accept or ""
    if response.status_code != 200:
        return f"{stem}.{response.status_code}.txt"
    if "notice=tree" in accept:
        return f"{stem}.tree.xml"
    if "notice=branch" in accept:
        return f"{stem}.branch.xml"
    if "zip" in accept:
        return f"{stem}.zip"
    return stem


def _export(response: CachedResponse, out: Path) -> ManifestEntry:
    body, trim = _trim(response)
    name = _filename(response)
    (out / name).write_bytes(body)
    return entry_for(
        key=response.entry.key,
        url=response.url,
        accept=response.entry.accept,
        accept_language=response.entry.accept_language,
        status_code=response.status_code,
        content_type=response.entry.content_type,
        fetched_at=response.fetched_at,
        body=body,
        file=name,
        source_sha256=response.entry.sha256 if trim else None,
        trim=trim,
    )


def build_fixtures(
    out: Path,
    *,
    pins: tuple[Pin, ...] = PINNED,
    feed_pins: tuple[FeedPin, ...] = FEED_PINNED,
    quiet: bool = False,
) -> int:
    """Fetch every pin, trim, write, and rewrite the manifest. Returns the number of files."""
    out.mkdir(parents=True, exist_ok=True)
    recorder = _Recorder(DiskResponseCache())
    http = CellarHttp(cache=recorder)
    client = CellarClient(http, observed_on=OBSERVED_ON)
    with http:
        for window in feed_pins:
            feed = fetch_notifications(
                http, start=window.start, end=window.end, channel=window.channel
            )
            if not quiet:
                print(
                    f"  {window.label}: {len(feed.entries)} entries, {feed.pages} page(s)",
                    file=sys.stderr,
                )
        for pin in pins:
            celex = Celex.parse(pin.celex)
            if pin.version is None:
                client.tree_notice(celex)
                client.branch_notice(celex)
                continue
            version = (
                celex.version
                if pin.version == ORIGINAL
                else ConsolidatedId.parse(pin.version).version
            )
            result = client.fetch_formex(celex, version)
            if not quiet:
                print(f"  {pin.label}: {type(result).__name__}", file=sys.stderr)

    entries = tuple(_export(response, out) for response in recorder.seen.values())
    write_manifest(
        out / "manifest.json",
        entries,
        note=(
            f"Pinned from CELLAR by emendrix.eu.fetch_fixtures on {OBSERVED_ON.isoformat()}. "
            "Real responses, trimmed by the rules in that module; `trim` names the rule and "
            "`source_sha256` is the digest of the untrimmed response."
        ),
    )
    if not quiet:
        total = sum(entry.size for entry in entries)
        print(
            f"{len(entries)} fixtures, {total / 1024:.0f} KiB, {http.network_calls} network calls",
            file=sys.stderr,
        )
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="fixture directory")
    parser.add_argument("--list", action="store_true", help="print the pinned set and exit")
    parser.add_argument(
        "--base-only",
        action="store_true",
        help=f"ignore the generated {EXTRA_PINS_NAME}; pin only the hand-written set",
    )
    args = parser.parse_args(argv)
    extra = () if args.base_only else read_extra_pins(args.out / EXTRA_PINS_NAME)
    pins = merge_pins(PINNED, extra)
    if args.list:
        for pin in pins:
            print(f"{pin.label:32s} {pin.reason}")
        for window in FEED_PINNED:
            print(f"{window.label:32s} {window.reason}")
        return 0
    build_fixtures(args.out, pins=pins)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
