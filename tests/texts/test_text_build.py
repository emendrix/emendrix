"""`build_store` over the toy corpus: written once, states kept, failures counted, limits held."""

from __future__ import annotations

from pathlib import Path

from emendrix.core import ActId, ProvisionTree, Unavailable, VersionDescriptor, VersionId
from emendrix.texts.build import build_store
from emendrix.texts.model import STATES_FILE, UnreadableVersion
from emendrix.texts.store import TextStore
from eu_pins import OBSERVED_ON
from toy_corpus import HOUSE_RULES, V2, ToyCorpusAdapter


def _toy(language: str = "ENG") -> ToyCorpusAdapter:
    return ToyCorpusAdapter(observed_on=OBSERVED_ON, language=language)


class _Failing:
    """The toy corpus, except one version whose fetch raises the way a missing fixture does."""

    def __init__(self, failing: VersionId | None = None, *, listing: bool = False) -> None:
        self.inner = _toy()
        self.failing = failing
        self.listing = listing

    def discover_versions(self, act: ActId) -> list[VersionDescriptor]:
        if self.listing:
            raise LookupError("no tree notice: HTTP 503")
        return self.inner.discover_versions(act)

    def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
        if version == self.failing:
            raise LookupError(f"no fixture for {version}")
        return self.inner.fetch_version(act, version)


def test_a_first_build_writes_and_a_second_writes_nothing(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    first = build_store(_toy(), store, [HOUSE_RULES])
    assert (first.total.listed, first.total.written, first.total.already_stored) == (3, 2, 0)
    assert first.total.states == {"consolidation_pending": 1}
    states = store.act_dir("toy", "house-rules") / STATES_FILE
    recorded = states.read_bytes()
    stored = {path.name: path.read_bytes() for path in states.parent.iterdir()}

    second = build_store(_toy(), store, [HOUSE_RULES])
    assert (second.total.written, second.total.already_stored) == (0, 2)
    assert second.total.states == {"consolidation_pending": 1}, "a state is asked again"
    assert states.read_bytes() == recorded
    assert {path.name: path.read_bytes() for path in states.parent.iterdir()} == stored


def test_an_english_unavailable_answer_lands_in_states_and_is_counted(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    summary = build_store(_toy("FRA"), store, [HOUSE_RULES])
    assert summary.total.written == 0
    assert summary.acts[0].states == {"english_unavailable": 3}
    recorded = store.states("toy", "house-rules")
    assert not isinstance(recorded, UnreadableVersion)
    assert [(state.version, state.state) for state in recorded.states] == [
        ("v1", "english_unavailable"),
        ("v2", "english_unavailable"),
        ("v3", "english_unavailable"),
    ]


def test_a_raising_fetch_is_counted_and_stored_nowhere(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    summary = build_store(_Failing(V2), store, [HOUSE_RULES])
    assert (summary.total.written, summary.total.fetch_failed) == (1, 1)
    assert summary.acts[0].failures == ("v2: no fixture for v2",)
    assert not store.has("toy", "house-rules", "v2")
    recorded = store.states("toy", "house-rules")
    assert not isinstance(recorded, UnreadableVersion)
    assert "v2" not in [state.version for state in recorded.states]


def test_a_listing_that_raises_is_counted_and_the_run_goes_on(tmp_path: Path) -> None:
    summary = build_store(_Failing(listing=True), TextStore.create_or_open(tmp_path), [HOUSE_RULES])
    assert summary.total.listing_failed == 1
    assert summary.acts[0].failures == ("listing: no tree notice: HTTP 503",)


def test_the_limit_stops_after_that_many_writes(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    summary = build_store(_toy(), store, [HOUSE_RULES], limit=1)
    assert (summary.total.written, summary.total.left) == (1, 2)
    assert store.versions("toy", "house-rules") == ("v1",)


def test_a_dry_run_lists_and_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "store"
    summary = build_store(
        _toy(), TextStore.create_or_open(root, dry_run=True), [HOUSE_RULES], dry_run=True
    )
    assert summary.dry_run
    assert (summary.total.listed, summary.total.left, summary.total.written) == (3, 3, 0)
    assert not root.exists()


def test_a_rebuild_writes_stored_versions_again_to_the_same_bytes(tmp_path: Path) -> None:
    store = TextStore.create_or_open(tmp_path)
    build_store(_toy(), store, [HOUSE_RULES])
    path = store.version_path("toy", "house-rules", "v1")
    before = path.read_bytes()
    again = build_store(_toy(), store, [HOUSE_RULES], rebuild=True)
    assert (again.total.written, again.total.already_stored) == (2, 0)
    assert path.read_bytes() == before
