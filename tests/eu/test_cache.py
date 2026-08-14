"""The disk cache and the fixture cache: keys, round-trips, and the offline guarantee."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from emendrix.eu.cache import (
    CachedResponse,
    DiskResponseCache,
    FixtureCorrupt,
    FixtureMissing,
    FixtureResponseCache,
    cache_key,
    default_cache_dir,
    entry_for,
    read_manifest,
    write_manifest,
)
from emendrix.eu.http import ACCEPT_TREE_NOTICE, ACCEPT_ZIP, CellarHttp

FETCHED_AT = datetime(2026, 8, 6, 9, 30, tzinfo=UTC)
URL = "https://publications.europa.eu/resource/celex/32024R1689"


def _response(
    *, url: str = URL, accept: str = ACCEPT_TREE_NOTICE, status: int = 200, body: bytes = b"<x/>"
) -> CachedResponse:
    key = cache_key("GET", url, accept, "eng")
    return CachedResponse(
        entry=entry_for(
            key=key,
            url=url,
            accept=accept,
            accept_language="eng",
            status_code=status,
            content_type="application/xml",
            fetched_at=FETCHED_AT,
            body=body,
            file=f"{key}.body",
        ),
        body=body,
    )


def test_the_key_covers_everything_that_negotiates_the_content() -> None:
    """One URL answers with a tree notice, a branch notice or a zip, so Accept is part of it."""
    tree = cache_key("GET", URL, ACCEPT_TREE_NOTICE, "eng")
    assert tree != cache_key("GET", URL, "application/xml;notice=branch", "eng")
    assert tree != cache_key("GET", URL, ACCEPT_TREE_NOTICE, "fra")
    assert tree != cache_key("GET", URL + "x", ACCEPT_TREE_NOTICE, "eng")


def test_the_key_is_stable_across_runs_and_machines() -> None:
    assert cache_key("GET", URL, ACCEPT_ZIP, "eng") == (
        "94a294413231e73b42acc480c04d025ba47e6ab205fb6059e1c6d79639da2b91"
    )


def test_disk_cache_round_trips_the_body_byte_for_byte(tmp_path: Path) -> None:
    cache = DiskResponseCache(tmp_path)
    body = b"PK\x03\x04not really a zip\x00\xff"
    response = _response(accept=ACCEPT_ZIP, body=body)
    assert cache.get(response.entry.key) is None

    cache.store(response)
    found = cache.get(response.entry.key)
    assert found is not None
    assert found.body == body
    assert found.from_cache is True
    assert found.entry.fetched_at == FETCHED_AT
    assert found.entry.content_type == "application/xml"


@pytest.mark.parametrize("status", [200, 404, 406])
def test_answers_are_cached_even_when_they_are_refusals(tmp_path: Path, status: int) -> None:
    """A 404 and a 406 are answers about the document; re-asking would be waste."""
    cache = DiskResponseCache(tmp_path)
    response = _response(status=status, body=b"Resource ... not found.")
    cache.store(response)
    assert cache.get(response.entry.key) is not None


def test_server_errors_are_not_cached(tmp_path: Path) -> None:
    cache = DiskResponseCache(tmp_path)
    response = _response(status=503, body=b"try later")
    cache.store(response)
    assert cache.get(response.entry.key) is None


def test_a_re_store_killed_half_way_cannot_leave_a_truncated_body_behind(tmp_path: Path) -> None:
    """The gap tmp-and-rename closes, staged as the crash that would actually produce it.

    A *first* write that dies leaves a body with no sidecar, which `get` already reads as a
    miss. A *re-store* that dies is the dangerous one: the sidecar already on disk is still
    there and still valid, so without an atomic rename the cache would serve a half-written
    document under a confident-looking manifest entry, indefinitely and without complaint.
    """
    cache = DiskResponseCache(tmp_path)
    original = _response(body=b"the whole document, as the server sent it")
    cache.store(original)

    replacement = _response(body=b"a longer replacement document from a later fetch")
    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(
            Path, "replace", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("killed"))
        )
        with pytest.raises(KeyboardInterrupt):
            cache.store(replacement)

    found = cache.get(original.entry.key)
    assert found is not None, "the entry that was already there must survive intact"
    assert found.body == original.body
    assert list(tmp_path.rglob("*.tmp")) == [], "the scratch file must not be left lying about"


def test_a_body_that_disagrees_with_its_sidecar_is_a_miss_not_a_served_document(
    tmp_path: Path,
) -> None:
    """Belt to the atomic write's braces, and a miss, deliberately, unlike a fixture.

    A fixture that disagrees with its manifest is a repository fault worth stopping for. An
    entry here is only a copy of something the endpoint will hand over again, so forgetting it
    and re-fetching is the honest recovery rather than an error anyone needs to see.
    """
    cache = DiskResponseCache(tmp_path)
    response = _response(body=b"the whole document, as the server sent it")
    cache.store(response)

    body_path = next(tmp_path.rglob("*.body"))
    body_path.write_bytes(b"the whole document, as the ser")  # what a torn write would leave

    assert cache.get(response.entry.key) is None


def test_the_cache_lives_outside_the_repo() -> None:
    assert Path.cwd() not in default_cache_dir().parents
    assert default_cache_dir().name == "emendrix"


def test_a_fixture_cache_cannot_reach_the_network(tmp_path: Path) -> None:
    """The offline guarantee: a miss raises, naming the request, instead of opening a socket."""
    http = CellarHttp(cache=FixtureResponseCache(tmp_path))
    with pytest.raises(FixtureMissing, match="no fixture for GET"):
        http.get("/resource/celex/32024R1689", accept=ACCEPT_TREE_NOTICE)
    assert http.network_calls == 0


def test_a_fixture_cache_never_writes(tmp_path: Path) -> None:
    cache = FixtureResponseCache(tmp_path)
    cache.store(_response())
    assert list(tmp_path.iterdir()) == []
    assert cache.offline is True


def test_a_fixture_that_is_not_what_it_was_pinned_as_is_refused_on_read(tmp_path: Path) -> None:
    """Checked on the read path, not only in a test: every number is computed from these bytes.

    A body edited by hand, re-trimmed by different rules, or swapped by a bad merge keeps a
    valid manifest entry and a valid file name. Served, it would be scored under the pin of the
    document it replaced, which is the fixture-set version of replaying the wrong cassette.
    """
    response = _response(body=b"the pinned bytes")
    (tmp_path / response.entry.file).write_bytes(b"different bytes entirely")
    write_manifest(tmp_path / "manifest.json", (response.entry,))

    cache = FixtureResponseCache(tmp_path)
    with pytest.raises(FixtureCorrupt) as raised:
        cache.get(response.entry.key)
    assert raised.value.expected == response.entry.sha256
    assert "fetch_fixtures" in str(raised.value), "the error must say how to fix itself"


def test_an_intact_fixture_passes_the_check(tmp_path: Path) -> None:
    """The guard must not cost a false positive on the honest path."""
    response = _response(body=b"the pinned bytes")
    (tmp_path / response.entry.file).write_bytes(response.body)
    write_manifest(tmp_path / "manifest.json", (response.entry,))

    found = FixtureResponseCache(tmp_path).get(response.entry.key)
    assert found is not None and found.body == response.body


def test_the_committed_manifest_matches_the_committed_bytes(
    fixture_cache: FixtureResponseCache,
) -> None:
    """Every fixture is a real response with a recorded digest, nothing hand-edited."""
    entries = read_manifest(fixture_cache.root / "manifest.json")
    assert entries, "fixtures are pinned by `uv run python -m emendrix.eu.fetch_fixtures`"
    for entry in entries:
        response = fixture_cache.get(entry.key)
        assert response is not None, entry.file
        assert len(response.body) == entry.size
        assert entry.sha256 == hashlib.sha256(response.body).hexdigest()
        # Two addresses only: documents on `/resource/`, notification windows on `/webapi/`.
        assert entry.url.startswith(
            ("https://publications.europa.eu/resource/", "https://publications.europa.eu/webapi/")
        )
        if entry.trim:
            assert entry.source_sha256 and entry.source_sha256 != entry.sha256
