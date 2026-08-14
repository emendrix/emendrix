"""The disk cache every CELLAR response passes through — and the fixture cache CI uses.

Two backends behind one Protocol:

- `DiskResponseCache` writes under `platformdirs.user_cache_dir("emendrix")`, outside the
  working tree so nothing fetched is committed. Body and metadata are separate files: the body
  stays byte for byte what the server sent (a zip is a zip), the sidecar JSON carries status,
  headers worth keeping, and the fetch timestamp that becomes provenance downstream. Both go
  down tmp-and-rename and come back digest-checked, so a mid-write kill costs a re-fetch.
- `FixtureResponseCache` is read-only and manifest-driven, so a test run resolves from
  `tests/fixtures/eu/` and **cannot** reach the network: with it installed there is no
  code path from a cache miss to a socket, only `FixtureMissing`.

A missing fixture is a *programming* error, not a first-class state: it means a test asked
for a document nobody pinned. `EnglishUnavailable` and friends describe what the corpus
answered, and a fixture that does not exist is not an answer from the corpus.

So is a fixture that is not the document it was pinned as. Every manifest entry carries the
digest of the body it names, and `FixtureResponseCache.get` checks it on every read rather
than trusting it — for the same reason `explain/cassette.py` checks a cassette hashes to its
own file name: a body edited, re-trimmed, or swapped by a bad merge would otherwise be scored
silently under the pin of the document it replaced, and every published number is computed
from this fixture set. The check is a `sha256` of bytes already in memory, and the whole
committed set is 30 MB.

Non-200 answers are cached too. `404` (no such manifestation) and `406` (no such language)
are answers this system depends on, because the fallback chain in `eu/cellar.py` is driven by
them, so re-asking the network for them would be waste, not caution. `5xx` is never cached.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Final, Protocol, Self

import platformdirs
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CACHEABLE_STATUSES",
    "CachedResponse",
    "DiskResponseCache",
    "FixtureCorrupt",
    "FixtureMissing",
    "FixtureResponseCache",
    "Manifest",
    "ManifestEntry",
    "ResponseCache",
    "cache_key",
    "default_cache_dir",
    "entry_for",
    "read_manifest",
    "write_manifest",
]

CACHEABLE_STATUSES: Final = frozenset({200, 404, 406})
"""Statuses that are answers about the document, and so worth keeping."""

MANIFEST_NAME: Final = "manifest.json"


def default_cache_dir() -> Path:
    """The XDG-ish user cache directory. Never inside the working tree."""
    return Path(platformdirs.user_cache_dir("emendrix"))


def cache_key(method: str, url: str, accept: str | None, accept_language: str | None) -> str:
    """The cache key: a hash of everything that content-negotiates the response.

    Accept and Accept-Language are part of the key because on CELLAR they are part of the
    *request*: the same URL returns a tree notice, a branch notice or a zip depending on
    them. Stable across runs and machines — it is a plain sha256 of a canonical string, no
    dict ordering, no hostname, no locale.
    """
    canonical = "\n".join([method.upper(), url, accept or "", accept_language or ""])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ManifestEntry(BaseModel):
    """What is known about a cached response apart from its body.

    Serialised beside the body in the disk cache, and collected into `manifest.json` in a
    fixture directory, where it doubles as the human-readable record of what was pinned,
    when, and how it was trimmed.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    method: str = "GET"
    url: str
    accept: str | None = None
    accept_language: str | None = None
    status_code: int
    content_type: str | None = None
    fetched_at: datetime
    file: str = Field(description="Body filename, relative to the cache or fixture directory.")
    sha256: str = Field(description="Digest of the stored body — trimmed, if it was trimmed.")
    size: int
    source_sha256: str | None = Field(
        default=None, description="Digest of the untrimmed response, when the body was trimmed."
    )
    trim: str | None = Field(
        default=None, description="Which reproducible trim produced this body, if any."
    )


class CachedResponse(BaseModel):
    """A response, from the network or from disk. The body is verbatim in both cases."""

    model_config = ConfigDict(frozen=True)

    entry: ManifestEntry
    body: bytes
    from_cache: bool = False

    @property
    def status_code(self) -> int:
        return self.entry.status_code

    @property
    def url(self) -> str:
        return self.entry.url

    @property
    def fetched_at(self) -> datetime:
        return self.entry.fetched_at

    @property
    def ok(self) -> bool:
        return self.entry.status_code == 200

    def text(self, limit: int | None = None) -> str:
        """The body as text, for logging and for reading a server's error prose."""
        return self.body[:limit].decode("utf-8", "replace")


class FixtureMissing(LookupError):
    """A fixture-backed cache was asked for a document nobody pinned."""


class FixtureCorrupt(RuntimeError):
    """A committed fixture body is not the one its manifest entry pins. Loud, like a miss.

    The manifest records the digest of the trimmed bytes it names, so the claim is checkable —
    and checking it is what makes `CaseInput`'s promise ("a case whose inputs hash differently
    is not the case that was measured") true rather than merely written down. Not a first-class
    state: a fixture that disagrees with its own manifest is a repository fault, and scoring it
    would publish a number about a document nobody pinned.
    """

    def __init__(self, path: Path, expected: str, derived: str) -> None:
        super().__init__(
            f"{path} does not match its manifest entry: pinned {expected}, its bytes derive "
            f"{derived}. Re-pin it with `uv run python -m emendrix.eu.fetch_fixtures` rather "
            f"than editing either side."
        )
        self.path = path
        self.expected = expected
        self.derived = derived


class ResponseCache(Protocol):
    """Where `eu.http` looks before the network, and what it writes back to."""

    def get(self, key: str) -> CachedResponse | None: ...

    def store(self, response: CachedResponse) -> None: ...

    @property
    def offline(self) -> bool:
        """True if a miss must never become a network call."""
        ...


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _write_atomically(path: Path, payload: bytes) -> None:
    """Write via a sibling `.tmp` and a rename, as `watch/state.py` and `explain/cassette.py` do.

    Here for a sharper reason than either, because this cache is *re-written*: a first write
    that dies half way leaves a body with no sidecar, which `get` reads as a miss, but a
    re-store that dies half way would leave a truncated body under a sidecar that is still
    there and still confident, and that document would be served forever.
    """
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class DiskResponseCache:
    """The real cache: one body file and one JSON sidecar per key, under the user cache dir."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else default_cache_dir() / "cellar"

    @property
    def offline(self) -> bool:
        return False

    def _paths(self, key: str) -> tuple[Path, Path]:
        shard = self.root / key[:2]
        return shard / f"{key}.json", shard / f"{key}.body"

    def get(self, key: str) -> CachedResponse | None:
        """A cached response, or `None` — and a body disagreeing with its sidecar is `None` too.

        A miss rather than a raise, which is where this parts company with `FixtureCorrupt`: a
        fixture is a committed artifact whose contents are the point, while an entry here is
        only a copy of what the endpoint will hand over again, so forgetting it and re-fetching
        is the honest recovery. With `_write_atomically`, a torn entry is unlikely *and* unserved.
        """
        meta_path, body_path = self._paths(key)
        if not (meta_path.is_file() and body_path.is_file()):
            return None
        entry = ManifestEntry.model_validate_json(meta_path.read_bytes())
        body = body_path.read_bytes()
        if _digest(body) != entry.sha256:
            return None
        return CachedResponse(entry=entry, body=body, from_cache=True)

    def store(self, response: CachedResponse) -> None:
        """Body first, then sidecar, both atomic: `get` needs both, so a torn first store misses."""
        if response.status_code not in CACHEABLE_STATUSES:
            return
        meta_path, body_path = self._paths(response.entry.key)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        _write_atomically(body_path, response.body)
        _write_atomically(meta_path, response.entry.model_dump_json(indent=2).encode("utf-8"))


class FixtureResponseCache:
    """A read-only cache backed by a committed fixture directory and its manifest.

    Installed by the test suite. `store` is a no-op: fixtures are written by
    `eu/fetch_fixtures.py`, deliberately and reproducibly, never as a side effect of a test.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.entries: dict[str, ManifestEntry] = {}
        manifest = root / MANIFEST_NAME
        if manifest.is_file():
            for entry in read_manifest(manifest):
                self.entries[entry.key] = entry

    @property
    def offline(self) -> bool:
        return True

    def get(self, key: str) -> CachedResponse | None:
        """The pinned response, or `None` — after checking the body is the one that was pinned."""
        entry = self.entries.get(key)
        if entry is None:
            return None
        path = self.root / entry.file
        body = path.read_bytes()
        derived = _digest(body)
        if derived != entry.sha256:
            raise FixtureCorrupt(path, entry.sha256, derived)
        return CachedResponse(entry=entry, body=body, from_cache=True)

    def store(self, response: CachedResponse) -> None:
        return None


class Manifest(BaseModel):
    """The committed index of a fixture directory."""

    model_config = ConfigDict(frozen=True)

    note: str = ""
    entries: tuple[ManifestEntry, ...] = ()

    @classmethod
    def of(cls, entries: tuple[ManifestEntry, ...], *, note: str = "") -> Self:
        return cls(note=note, entries=tuple(sorted(entries, key=lambda item: item.file)))


def read_manifest(path: Path) -> tuple[ManifestEntry, ...]:
    return Manifest.model_validate_json(path.read_bytes()).entries


def write_manifest(path: Path, entries: tuple[ManifestEntry, ...], *, note: str = "") -> None:
    """Write a fixture manifest, sorted and pretty-printed so git diffs stay readable."""
    payload = Manifest.of(entries, note=note).model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def entry_for(
    *,
    key: str,
    url: str,
    accept: str | None,
    accept_language: str | None,
    status_code: int,
    content_type: str | None,
    fetched_at: datetime,
    body: bytes,
    file: str,
    source_sha256: str | None = None,
    trim: str | None = None,
) -> ManifestEntry:
    """Build a manifest entry, computing the digest and size from the body itself."""
    return ManifestEntry(
        key=key,
        url=url,
        accept=accept,
        accept_language=accept_language,
        status_code=status_code,
        content_type=content_type,
        fetched_at=fetched_at,
        file=file,
        sha256=_digest(body),
        size=len(body),
        source_sha256=source_sha256,
        trim=trim,
    )
