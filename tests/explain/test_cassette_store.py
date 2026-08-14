"""The store itself: key derivation, serialisation, and the guard on the downgrade footgun.

Kept apart from `test_engine_replay.py`, which exercises the *committed* cassettes and must not
write anything. Everything here runs on `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from emendrix.explain import (
    Cassette,
    CassetteCorrupt,
    CassetteMiss,
    CassetteStore,
    CitedSentence,
    Explanation,
    cassette_key,
    model_slug,
)

MODEL = "openrouter:anthropic/claude-haiku-4.5"
OUTPUT = Explanation(sentences=(CitedSentence(text="It changed.", citations=("k",)),))


def cassette(*, synthetic: bool = True, user: str = "user message") -> Cassette:
    return Cassette(
        model_id=MODEL,
        key=cassette_key(MODEL, "system prompt", user),
        synthetic=synthetic,
        recorded_with="TestModel" if synthetic else MODEL,
        system="system prompt",
        user=user,
        output=OUTPUT,
    )


def test_the_key_depends_on_the_model_the_prompt_and_the_schema_version() -> None:
    """All four inputs must move the key, or a stale cassette replays into a changed world."""
    base = cassette_key("m", "sys", "usr", 1)
    assert base != cassette_key("other", "sys", "usr", 1)
    assert base != cassette_key("m", "SYS", "usr", 1)
    assert base != cassette_key("m", "sys", "USR", 1)
    assert base != cassette_key("m", "sys", "usr", 2)
    assert base == cassette_key("m", "sys", "usr", 1)


def test_the_key_is_a_sha256_hex_digest() -> None:
    key = cassette_key(MODEL, "sys", "usr")
    assert len(key) == 64
    assert set(key) <= set("0123456789abcdef")


def test_a_saved_cassette_round_trips_and_lands_where_the_key_says(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    written = cassette()
    path = store.save(written)
    assert path.parent.name == model_slug(MODEL)
    assert path.name == f"{written.key}.json"
    assert store.load(MODEL, written.key) == written


def test_the_json_on_disk_is_byte_stable(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    written = cassette()
    first = store.save(written).read_text(encoding="utf-8")
    second = store.save(written).read_text(encoding="utf-8")
    assert first == second
    assert first.endswith("\n")
    assert json.loads(first)["synthetic"] is True


def test_a_miss_names_the_file_and_says_how_to_record_it(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    with pytest.raises(CassetteMiss) as raised:
        store.require(MODEL, "deadbeef")
    assert raised.value.key == "deadbeef"
    assert "record and live" in str(raised.value)
    assert raised.value.path.name == "deadbeef.json"


def test_a_keyless_rerun_cannot_downgrade_a_real_cassette_to_a_synthetic_one(
    tmp_path: Path,
) -> None:
    """The recorder runs the same command with or without a key. This is why that is safe."""
    store = CassetteStore(tmp_path)
    real = cassette(synthetic=False)
    store.save(real)
    with pytest.raises(ValueError, match="refusing to overwrite the real recording"):
        store.save(cassette(synthetic=True))
    assert store.load(MODEL, real.key) == real


def test_a_downgrade_is_possible_when_it_is_asked_for(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    real = cassette(synthetic=False)
    store.save(real)
    store.save(cassette(synthetic=True), allow_downgrade=True)
    replaced = store.load(MODEL, real.key)
    assert replaced is not None and replaced.synthetic


def test_a_real_recording_always_replaces_a_synthetic_one_without_asking(tmp_path: Path) -> None:
    """The guard is one-directional: recording for real is the thing that must stay easy."""
    store = CassetteStore(tmp_path)
    store.save(cassette(synthetic=True))
    store.save(cassette(synthetic=False))
    stored = store.load(MODEL, cassette().key)
    assert stored is not None and not stored.synthetic


def test_no_scratch_file_is_left_behind(tmp_path: Path) -> None:
    """Written tmp-and-rename, so a crash mid-write cannot corrupt a committed artifact."""
    store = CassetteStore(tmp_path)
    store.save(cassette())
    assert [path.name for path in tmp_path.rglob("*.tmp")] == []


def test_the_inventory_lists_only_this_models_keys(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    first, second = cassette(user="one"), cassette(user="two")
    store.save(first)
    store.save(second)
    assert store.keys(MODEL) == tuple(sorted((first.key, second.key)))
    assert store.keys("anthropic:some-other-model") == ()


def test_a_hand_edited_cassette_is_refused_rather_than_replayed(tmp_path: Path) -> None:
    """The file name is a hash of the prompt inside it. A body that hashes to anything else lies.

    Someone "polishing" a recorded sentence, or a bad merge that swaps two bodies while the
    filenames survive, would otherwise replay silently as the answer to a question that was
    never asked: the one failure mode a replay layer must not have.
    """
    store = CassetteStore(tmp_path)
    written = cassette()
    path = store.save(written)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["user"] = "a different question entirely"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(CassetteCorrupt) as raised:
        store.load(MODEL, written.key)
    assert raised.value.expected == written.key
    assert raised.value.derived != written.key
    assert "re-record it" in str(raised.value)


def test_a_cassette_filed_under_the_wrong_name_is_refused(tmp_path: Path) -> None:
    """Two cassettes whose contents were swapped keep valid JSON and valid names. Not valid."""
    store = CassetteStore(tmp_path)
    first, second = cassette(user="one"), cassette(user="two")
    store.save(first)
    store.save(second)
    store.path_for(MODEL, first.key).write_text(
        store.path_for(MODEL, second.key).read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(CassetteCorrupt):
        store.load(MODEL, first.key)


def test_an_intact_cassette_passes_the_check(tmp_path: Path) -> None:
    """The guard must not cost a false positive on the honest path."""
    store = CassetteStore(tmp_path)
    written = cassette()
    store.save(written)
    assert store.require(MODEL, written.key) == written
