"""The comparison directory on disk: deterministic bytes in, anything unreadable out as absent.

A build must never fail over this directory, so every way an entry can be broken reads as no
entry at all, and the comparison is computed again. A broken file is also named as unreadable,
which is what lets a build count it as rejected rather than as never written. Writing is the one
place that may fail, and it fails with one exception of its own so the command line can say so
and carry on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from emendrix.site_.comparison_store import StoreUnwritable, read_stored, write_stored
from emendrix.site_.comparisons import NO_COMPARISONS, Stored, comparison_key, resolve

_PAIRS = [
    ("pay within one month of receipt", "pay within two weeks of receipt"),
    ("a b c", "a c"),
    ("", "inserted whole"),
]


def _entries() -> dict[str, Stored]:
    return dict(resolve(_PAIRS, NO_COMPARISONS).table)


def _file(directory: Path, key: str) -> Path:
    return directory / key[:2] / f"{key}.json"


def test_what_is_written_reads_back_as_the_same_models(tmp_path: Path) -> None:
    entries = _entries()
    assert write_stored(tmp_path, entries) == len(entries)
    assert read_stored(tmp_path, sorted(entries)).found == entries
    assert read_stored(tmp_path, sorted(entries)).unreadable == ()
    assert not [path for path in tmp_path.rglob("*") if path.suffix == ".tmp"]


def test_the_bytes_are_deterministic(tmp_path: Path) -> None:
    entries = _entries()
    write_stored(tmp_path / "one", entries)
    write_stored(tmp_path / "two", entries)
    write_stored(tmp_path / "two", entries)
    for key in entries:
        first = _file(tmp_path / "one", key).read_bytes()
        assert first == _file(tmp_path / "two", key).read_bytes()
        assert first.endswith(b"}\n") and first.count(b"\n") == 1
        assert b", " not in first and b": " not in first
        payload = json.loads(first)
        assert list(payload) == sorted(payload) == ["a", "b", "granularity", "opcodes", "schema"]
        assert payload["schema"] == 1


def test_a_key_never_written_is_absent_and_not_unreadable(tmp_path: Path) -> None:
    read = read_stored(tmp_path / "nowhere", [comparison_key("x", "y")])
    assert read.found == {} and read.unreadable == ()


_BROKEN: dict[str, bytes] = {
    "empty": b"",
    "truncated": b'{"a":6,"b":6,"granularity":"word","opcodes":[["equal",0,',
    "not json": b"\x00\xffnot json at all",
    "an empty object": b"{}\n",
    "another schema": b'{"a":0,"b":0,"granularity":"word","opcodes":[],"schema":2}\n',
    "no schema": b'{"a":0,"b":0,"granularity":"word","opcodes":[]}\n',
    "a wrong type": b'{"a":"many","b":0,"granularity":"word","opcodes":[],"schema":1}\n',
    "an unknown tag": b'{"a":1,"b":1,"granularity":"word","opcodes":[["swap",0,1,0,1]],'
    b'"schema":1}\n',
    "a negative count": b'{"a":-1,"b":0,"granularity":"word","opcodes":[],"schema":1}\n',
    "a list": b"[1, 2, 3]\n",
}


@pytest.mark.parametrize("broken", sorted(_BROKEN))
def test_a_broken_entry_reads_as_absent(tmp_path: Path, broken: str) -> None:
    key = comparison_key("before", broken)
    path = _file(tmp_path, key)
    path.parent.mkdir(parents=True)
    path.write_bytes(_BROKEN[broken])
    read = read_stored(tmp_path, [key])
    assert read.found == {} and read.unreadable == (key,)


def test_a_directory_where_an_entry_should_be_reads_as_absent(tmp_path: Path) -> None:
    key = comparison_key("before", "after")
    _file(tmp_path, key).mkdir(parents=True)
    read = read_stored(tmp_path, [key])
    assert read.found == {} and read.unreadable == (key,)


def test_a_directory_under_a_regular_file_cannot_be_written(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(StoreUnwritable):
        write_stored(blocker / "cache", _entries())
    read = read_stored(blocker / "cache", sorted(_entries()))
    assert read.found == {} and read.unreadable == (), "nothing is there to have been damaged"
