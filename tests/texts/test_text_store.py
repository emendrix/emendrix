"""The text store: a tree written and read back, the bytes it is written as, and its refusals."""

from __future__ import annotations

import gzip
import io
from pathlib import Path

import pytest

from emendrix.core import ProvisionTree, VersionId
from emendrix.eu.identifiers import Celex, act_id
from emendrix.session import adapter_for
from emendrix.texts.codec import encode
from emendrix.texts.model import MARKER_FILE, STATES_FILE, StoredState, UnreadableVersion
from emendrix.texts.store import (
    NestedInWorktree,
    NotAStore,
    ReadOnlyStore,
    TextStore,
    inside_worktree,
)
from eu_pins import FIXTURE_DIR, MDR, OBSERVED_ON
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

MDR_VERSION = "02017R0745-20200424"


@pytest.fixture(scope="module")
def mdr_tree() -> ProvisionTree:
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        fetched = adapter.fetch_version(act_id(Celex.parse(MDR)), VersionId(MDR_VERSION))
    assert isinstance(fetched, ProvisionTree)
    return fetched


def _shape(tree: ProvisionTree) -> list[tuple[str, str | None, str, str, int]]:
    return [
        (node.location.canonical, node.heading, node.text, node.comparison_text, len(node.children))
        for node in tree.walk()
    ]


def _toy(version: VersionId) -> ProvisionTree:
    fetched = ToyCorpusAdapter(observed_on=OBSERVED_ON).fetch_version(HOUSE_RULES, version)
    assert isinstance(fetched, ProvisionTree)
    return fetched


def test_a_written_version_reads_back_as_the_same_tree(
    tmp_path: Path, mdr_tree: ProvisionTree
) -> None:
    store = TextStore.create_or_open(tmp_path / "store")
    store.write(mdr_tree, version=MDR_VERSION)
    rebuilt = TextStore.open(tmp_path / "store").tree("eu", MDR, MDR_VERSION)
    assert isinstance(rebuilt, ProvisionTree)
    assert _shape(rebuilt) == _shape(mdr_tree)
    assert rebuilt.unit_locations() == mdr_tree.unit_locations()
    assert (rebuilt.act, rebuilt.version, rebuilt.language) == (
        mdr_tree.act,
        mdr_tree.version,
        mdr_tree.language,
    )


def test_a_version_file_is_the_same_bytes_on_every_write(
    tmp_path: Path, mdr_tree: ProvisionTree
) -> None:
    first = TextStore.create_or_open(tmp_path / "a").write(mdr_tree, version=MDR_VERSION)
    second = TextStore.create_or_open(tmp_path / "b").write(mdr_tree, version=MDR_VERSION)
    data = first.read_bytes()
    assert data == second.read_bytes() == encode(mdr_tree, MDR_VERSION)
    assert data[4:8] == b"\0\0\0\0", "the gzip header's mtime is zero"
    assert data[3] & 0x08 == 0, "the gzip header names no file"
    lines = gzip.decompress(data).decode("utf-8").split("\n")
    assert lines[-1] == "" and len(lines) == 2 + sum(1 for _ in mdr_tree.walk())


def test_unknown_location_codes_survive_the_round_trip(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    store.write(_toy(V1), version=str(V1))
    rebuilt = store.tree("toy", "house-rules", str(V1))
    assert isinstance(rebuilt, ProvisionTree)
    assert _shape(rebuilt) == _shape(_toy(V1))
    assert rebuilt.find("AN I SLOT 2") is not None


def test_has_versions_and_acts_are_sorted_and_answer_from_disk(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    store.write(_toy(V2), version="v2")
    store.write(_toy(V1), version="v1")
    assert store.has("toy", "house-rules", "v1")
    assert not store.has("toy", "house-rules", "v3")
    assert store.versions("toy", "house-rules") == ("v1", "v2")
    assert store.versions("toy", "nothing") == ()
    assert store.acts() == (("toy", "house-rules"),)
    assert store.read("toy", "house-rules", "v3") is None
    assert store.tree("toy", "house-rules", "v3") is None


def test_a_file_is_named_by_the_version_asked_for_not_the_one_served(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    store.write(_toy(V1), version="v0")
    stored = store.read("toy", "house-rules", "v0")
    assert stored is not None and not isinstance(stored, UnreadableVersion)
    assert (stored.header.version, stored.header.served_version) == ("v0", "v1")


def _gzip(text: str) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as out:
        out.write(text.encode("utf-8"))
    return buffer.getvalue()


def test_a_truncated_file_reads_as_unreadable(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    path = store.write(_toy(V1), version="v1")
    path.write_bytes(path.read_bytes()[:40])
    read = store.read("toy", "house-rules", "v1")
    assert isinstance(read, UnreadableVersion) and "decompress" in read.detail
    assert isinstance(store.tree("toy", "house-rules", "v1"), UnreadableVersion)


def test_a_bad_line_reads_as_unreadable(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    path = store.write(_toy(V1), version="v1")
    lines = gzip.decompress(path.read_bytes()).decode("utf-8").split("\n")
    path.write_bytes(_gzip("\n".join([lines[0], "{not json", *lines[2:]])))
    read = store.read("toy", "house-rules", "v1")
    assert isinstance(read, UnreadableVersion) and "validate" in read.detail


def test_a_node_whose_parent_is_not_open_above_it_is_unreadable(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    path = store.write(_toy(V1), version="v1")
    lines = gzip.decompress(path.read_bytes()).decode("utf-8").split("\n")
    slot = next(line for line in lines if '"AN I SLOT 2"' in line)
    rotated = [lines[0], slot, *(line for line in lines[1:] if line != slot)]
    path.write_bytes(_gzip("\n".join(rotated)))
    rebuilt = store.tree("toy", "house-rules", "v1")
    assert isinstance(rebuilt, UnreadableVersion) and "parent" in rebuilt.detail


def test_a_header_that_disagrees_with_its_file_is_unreadable(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    path = store.write(_toy(V1), version="v1")
    lines = gzip.decompress(path.read_bytes()).decode("utf-8").split("\n")
    path.write_bytes(_gzip("\n".join([lines[0], *lines[2:]])))
    read = store.read("toy", "house-rules", "v1")
    assert isinstance(read, UnreadableVersion) and "counts" in read.detail


def test_states_merge_by_version_sort_and_leave_unchanged_bytes_alone(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    late = StoredState(version="v3", state="consolidation_pending", detail="later")
    early = StoredState(version="v1", state="english_unavailable")
    assert store.record_states("toy", "house-rules", [late, early])
    path = store.act_dir("toy", "house-rules") / STATES_FILE
    recorded = store.states("toy", "house-rules")
    assert not isinstance(recorded, UnreadableVersion)
    assert [state.version for state in recorded.states] == ["v1", "v3"]
    before = path.read_bytes()
    assert not store.record_states("toy", "house-rules", [late])
    assert path.read_bytes() == before
    store.write(_toy(V1), version="v1")
    assert store.record_states("toy", "house-rules", [])
    recorded = store.states("toy", "house-rules")
    assert not isinstance(recorded, UnreadableVersion)
    assert [state.version for state in recorded.states] == ["v3"], "a stored version's state goes"


def test_no_states_writes_no_states_file(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    assert not store.record_states("toy", "house-rules", [])
    assert not (store.act_dir("toy", "house-rules") / STATES_FILE).exists()


def test_a_store_is_created_with_its_marker_and_reopened(tmp_path: Path) -> None:
    root = tmp_path / "new"
    TextStore.create_or_open(root)
    assert (root / MARKER_FILE).is_file()
    assert TextStore.create_or_open(root).writable
    assert not TextStore.open(root).writable


def test_a_dry_run_creates_nothing_and_cannot_write(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path / "absent", dry_run=True)
    assert not (tmp_path / "absent").exists()
    with pytest.raises(ReadOnlyStore):
        store.write(_toy(V1), version="v1")


def test_a_directory_emendrix_did_not_create_is_refused(tmp_path: Path) -> None:
    (tmp_path / "somebody.txt").write_text("theirs", encoding="utf-8")
    with pytest.raises(NotAStore, match=MARKER_FILE):
        TextStore.create_or_open(tmp_path)
    with pytest.raises(NotAStore):
        TextStore.open(tmp_path)


def test_a_path_inside_a_working_tree_is_refused(tmp_path: Path) -> None:
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    assert inside_worktree(tmp_path / "repo" / "texts") == (tmp_path / "repo").resolve()
    assert inside_worktree(tmp_path / "beside") is None
    for path in (tmp_path / "repo" / "texts", tmp_path / "repo"):
        with pytest.raises(NestedInWorktree):
            TextStore.create_or_open(path)
    assert not (tmp_path / "repo" / "texts").exists()


def test_a_read_only_store_refuses_to_write(tmp_path: Path) -> None:
    TextStore.create_or_open(tmp_path)
    store = TextStore.open(tmp_path)
    with pytest.raises(ReadOnlyStore):
        store.write(_toy(V1), version="v1")
    with pytest.raises(ReadOnlyStore):
        store.record_states("toy", "house-rules", [])
