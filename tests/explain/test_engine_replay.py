"""Replay: the property CI depends on, and the one the cassettes exist for.

Four committed exchanges cover the four prompt shapes (`pinned_cases.py`). Replaying them
asserts three things:

1. **The keys are stable.** A prompt built today from the committed fixtures hashes to a key
   that is on disk. Drift in the parser, the diff or the prompt shows up here, loudly, as the
   miss it is, which is exactly what makes an unchanged green run mean something.
2. **Replay is exact.** What comes back is byte-for-byte the recorded `Explanation`.
3. **Replay is offline.** No key is read and no provider client is constructed. The engine is
   given an unroutable model id to prove it: if anything tried to build a provider for it, the
   test would fail rather than pass quietly.

**These are real exchanges with the pinned model, and this module still asserts nothing about
the quality of an explanation.** That line is drawn deliberately: replay being exact says the
machinery is honest, and says nothing at all about whether a sentence is a true account of the
difference. Blurring the two is the one failure the project's premise does not survive, so the
quality question lives where it can be answered with a stated reference and a published number,
in the eval harness. Re-record with:

    OPENROUTER_API_KEY=sk-or-v1-... uv run pytest -m "record and live" tests/explain
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pinned_cases import PinnedCase, pinned_cases
from pydantic_ai import Agent
from pydantic_ai.exceptions import UserError
from test_record_cassettes import CASSETTE_DIR

from emendrix.eu.cellar import CellarClient
from emendrix.explain import (
    DEFAULT_MODEL,
    Cassette,
    CassetteCorrupt,
    CassetteMiss,
    CassetteMode,
    CassetteStore,
    ExplainEngine,
    ExplainSettings,
    Explanation,
    api_key_env,
    build_prompt,
    cassette_key,
    model_slug,
)
from emendrix.explain.schema import SCHEMA_VERSION


@pytest.fixture
def settings() -> ExplainSettings:
    return ExplainSettings(cassette_mode=CassetteMode.REPLAY, cassette_dir=CASSETTE_DIR)


@pytest.fixture
def engine(settings: ExplainSettings) -> ExplainEngine:
    return ExplainEngine(settings, cassettes=CassetteStore(CASSETTE_DIR))


@pytest.fixture
def cases(client: CellarClient) -> tuple[PinnedCase, ...]:
    return pinned_cases(client)


def test_every_pinned_change_replays(engine: ExplainEngine, cases: tuple[PinnedCase, ...]) -> None:
    """A miss here means the prompt moved. Re-read the diff before re-recording."""
    assert len(cases) == 4
    for case in cases:
        result = asyncio.run(engine.explain_change(case.change, case.context))
        assert result.ok, f"{case.location}: {result.unavailable}"
        assert result.replayed
        assert result.explanation is not None
        assert result.explanation.sentences


def test_replay_returns_exactly_what_was_recorded(
    engine: ExplainEngine, settings: ExplainSettings, cases: tuple[PinnedCase, ...]
) -> None:
    store = CassetteStore(CASSETTE_DIR)
    for case in cases:
        result = asyncio.run(engine.explain_change(case.change, case.context))
        cassette = store.require(settings.model_id, result.cassette_key)
        assert result.explanation == cassette.output


def test_the_key_is_derivable_by_hand_from_the_committed_prompt(
    settings: ExplainSettings, cases: tuple[PinnedCase, ...]
) -> None:
    """Explainable is the point: the file name is the sha256 of what is inside it."""
    store = CassetteStore(CASSETTE_DIR)
    for case in cases:
        parts = build_prompt(case.change, case.context, settings)
        key = cassette_key(settings.model_id, parts.system, parts.user, SCHEMA_VERSION)
        cassette = store.require(settings.model_id, key)
        assert cassette.key == key
        assert cassette.system == parts.system
        assert cassette.user == parts.user
        assert store.path_for(settings.model_id, key).name == f"{key}.json"


def test_replay_reads_no_api_key(
    cases: tuple[PinnedCase, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The provider raises without a key. Replay does not, because it never asks."""
    needed = api_key_env(DEFAULT_MODEL)
    assert needed is not None
    monkeypatch.delenv(needed, raising=False)
    settings = ExplainSettings(cassette_mode=CassetteMode.REPLAY, cassette_dir=CASSETTE_DIR)

    with pytest.raises(UserError, match=needed):
        Agent(model=settings.model_id, output_type=Explanation)

    result = asyncio.run(
        ExplainEngine(settings, cassettes=CassetteStore(CASSETTE_DIR)).explain_change(
            cases[0].change, cases[0].context
        )
    )
    assert result.ok
    assert result.replayed


def test_replay_builds_no_provider_client(
    cases: tuple[PinnedCase, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not an unobserved request: the agent is never constructed at all.

    A provider that does not exist would raise the moment pydantic-ai tried to resolve it, so
    an engine that survives a whole replay pointed at one has demonstrably built nothing.
    """
    needed = api_key_env(DEFAULT_MODEL)
    assert needed is not None
    monkeypatch.delenv(needed, raising=False)
    settings = ExplainSettings(cassette_mode=CassetteMode.REPLAY, cassette_dir=CASSETTE_DIR)
    impostor = settings.model_copy(update={"model_id": "no-such-provider:no-such-model"})

    with pytest.raises(ValueError, match="Unknown provider"):
        Agent(model=impostor.model_id, output_type=Explanation)

    engine = ExplainEngine(impostor, cassettes=CassetteStore(CASSETTE_DIR))
    with pytest.raises(CassetteMiss) as raised:
        asyncio.run(engine.explain_change(cases[0].change, cases[0].context))
    assert "no-such-provider:no-such-model" in str(raised.value)


def test_a_missing_cassette_fails_loudly_and_names_the_file(
    settings: ExplainSettings, cases: tuple[PinnedCase, ...]
) -> None:
    """An unrecorded prompt is a build fault, not a first-class state. It raises."""
    empty = CassetteStore(CASSETTE_DIR.parent / "cassettes-that-do-not-exist")
    engine = ExplainEngine(settings, cassettes=empty)
    with pytest.raises(CassetteMiss) as raised:
        asyncio.run(engine.explain_change(cases[0].change, cases[0].context))
    assert "record and live" in str(raised.value), "the error must say how to fix itself"
    assert raised.value.path.suffix == ".json"


def test_a_corrupt_cassette_fails_loudly_rather_than_counting_as_unexplained(
    settings: ExplainSettings, cases: tuple[PinnedCase, ...], tmp_path: Path
) -> None:
    """The corruption alarm has to survive the engine's broad `except`, or it is not an alarm.

    Swallowed, a hand-edited or mis-merged cassette becomes one more `ExplanationUnavailable`,
    and every model-layer floor absorbs it: `unexplained` rises by one exactly as `replayed`
    falls by one, so the run stays green and the published grounding rate is computed over a
    quietly smaller denominator. The whole point of hashing a cassette to its own name is that
    this cannot happen.
    """
    parts = build_prompt(cases[0].change, cases[0].context, settings)
    key = cassette_key(settings.model_id, parts.system, parts.user, SCHEMA_VERSION)
    source = CassetteStore(CASSETTE_DIR).path_for(settings.model_id, key)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["user"] = "a different question entirely"

    tampered = CassetteStore(tmp_path).path_for(settings.model_id, key)
    tampered.parent.mkdir(parents=True)
    tampered.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    engine = ExplainEngine(settings, cassettes=CassetteStore(tmp_path))
    with pytest.raises(CassetteCorrupt) as raised:
        asyncio.run(engine.explain_change(cases[0].change, cases[0].context))
    assert "re-record it" in str(raised.value)


def test_a_replayed_call_reports_no_new_requests(
    engine: ExplainEngine, cases: tuple[PinnedCase, ...]
) -> None:
    """Tokens were spent once, at recording time. Re-billing them every CI run would misreport."""
    result = asyncio.run(engine.explain_change(cases[0].change, cases[0].context))
    assert result.usage.requests == 0
    assert result.usage.input_tokens > 0


def test_the_committed_cassettes_say_what_recorded_them() -> None:
    """The honesty flag, asserted the other way round now that these are real.

    `synthetic` is what stops a stub's output being read as evidence about a model, and it only
    works if it is checked: a set that quietly went back to stub output would otherwise keep
    every downstream number looking green.
    """
    directory = CASSETTE_DIR / model_slug(DEFAULT_MODEL)
    files = sorted(directory.glob("*.json"))
    assert len(files) == 4
    for path in files:
        cassette = Cassette.model_validate_json(path.read_text(encoding="utf-8"))
        assert not cassette.synthetic, f"{path.name} was recorded from a stub"
        assert cassette.recorded_with == cassette.model_id == DEFAULT_MODEL


def test_the_cassettes_on_disk_are_byte_stable_when_rewritten() -> None:
    """Committed artifacts are diffed in git, so serialisation may not wobble."""
    directory = CASSETTE_DIR / model_slug(DEFAULT_MODEL)
    for path in sorted(directory.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        assert Cassette.model_validate_json(text).to_json() == text


def test_a_schema_version_bump_misses_every_existing_cassette(
    settings: ExplainSettings, cases: tuple[PinnedCase, ...]
) -> None:
    """Stale cassettes must not replay into a new validator."""
    parts = build_prompt(cases[0].change, cases[0].context, settings)
    current = cassette_key(settings.model_id, parts.system, parts.user, SCHEMA_VERSION)
    bumped = cassette_key(settings.model_id, parts.system, parts.user, SCHEMA_VERSION + 1)
    assert current != bumped
    assert CassetteStore(CASSETTE_DIR).load(settings.model_id, bumped) is None
