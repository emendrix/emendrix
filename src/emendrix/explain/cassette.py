"""Model-response cassettes: JSON on disk, keyed by the prompt, and nothing clever.

There is no VCR here and no HTTP interception. The wrapper sits at the **explain-call
boundary**, around the project's own "hand these two strings to a model, get an `Explanation`
back" function, so a cassette is a readable record of an exchange rather than a replay of a wire
format nobody will open. It stores the prompt it answers, which means a reviewer can diff a
cassette in a pull request and see exactly what the model was asked, and re-derive the key by
hand if they doubt it.

**The key** is `sha256` over the canonical JSON of `(model_id, schema_version, system, user)`.
Model id is in it because two models given the same prompt are two different exchanges.
`schema_version` is in it because a changed `Explanation` shape must miss every existing
cassette loudly rather than replay a stale one into a new validator.

**Replay has no code path to a network call or an API key.** That is the property CI depends
on, and it is structural: in `REPLAY` mode a miss raises `CassetteMiss` naming the key it
wanted, and the engine never constructs a provider client at all.

`synthetic` is the honesty flag. A cassette recorded from a stub model is a valid test of the
replay machinery and worth nothing at all as evidence about explanation quality; the flag
follows it into `ExplainedChange` and into `RunStats` so no metric can quietly mix the two.

**The store is generic, and used twice.** `JsonCassetteStore` holds everything that is true of a
directory of hash-named exchanges — the name check on read, the tmp-and-rename on write — and
`eval_/judge.py` subclasses it for the faithfulness judge's verdicts. Nothing about the model
client lives here, which is what lets a package that must never import one reuse this.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix.explain.results import CallUsage
from emendrix.explain.schema import SCHEMA_VERSION, Explanation
from emendrix.explain.settings import api_key_env

__all__ = [
    "Cassette",
    "CassetteCorrupt",
    "CassetteMiss",
    "CassetteStore",
    "JsonCassette",
    "JsonCassetteStore",
    "cassette_key",
    "model_slug",
]

CASSETTE_VERSION: Final = 1
"""The on-disk envelope's own version, separate from the `Explanation` schema version."""

_UNSAFE: Final = re.compile(r"[^A-Za-z0-9._-]+")


class CassetteMiss(RuntimeError):
    """Replay was asked for an exchange nobody recorded. Loud on purpose.

    Not a first-class state: an absent cassette is a build or configuration fault — the prompt
    changed, or the pinned subset was never recorded — and turning it into a value would let a
    green CI run mean nothing.
    """

    def __init__(self, model_id: str, key: str, path: Path) -> None:
        super().__init__(
            f"no cassette for {model_id} at key {key}: expected {path}. "
            f"Record it with: uv run pytest -m 'record and live' tests/explain"
        )
        self.model_id = model_id
        self.key = key
        self.path = path


class CassetteCorrupt(RuntimeError):
    """A cassette on disk is not the exchange its file name claims. Loud, like a miss.

    The name is `sha256(model_id + system + user + schema_version)`, so a file whose contents
    do not hash back to its own name has been edited, mis-merged or moved. Replaying it would
    answer the wrong question with a straight face — the one failure mode a replay layer must
    not have.
    """

    def __init__(self, path: Path, expected: str, derived: str) -> None:
        super().__init__(
            f"{path} does not hash to its own name: expected {expected}, its contents derive "
            f"{derived}. It was edited or mis-merged; re-record it rather than repairing it."
        )
        self.path = path
        self.expected = expected
        self.derived = derived


def model_slug(model_id: str) -> str:
    """A filesystem-safe directory name for a provider-qualified model id."""
    return _UNSAFE.sub("_", model_id)


def cassette_key(
    model_id: str, system: str, user: str, schema_version: int = SCHEMA_VERSION
) -> str:
    """The sha256 identifying one exchange. Stable across runs, machines and Python versions."""
    payload = json.dumps(
        {
            "model_id": model_id,
            "schema_version": schema_version,
            "system": system,
            "user": user,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class JsonCassette(BaseModel):
    """What every hash-named JSON record in one of these directories has in common.

    One field and one method, and that is the whole of it: the key a record is filed under, and
    the byte-stable rendering that makes the file diffable. The *model* whose exchange it
    records is deliberately not here — the explain stage calls that field `model_id` and the
    faithfulness judge calls it `judge_model`, and forcing one name on both would rename a
    field in every committed cassette to save a line.
    """

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1, description="sha256 of the prompt — also the file name.")

    def to_json(self) -> str:
        """Byte-stable JSON — cassettes are committed and diffed like any other source."""
        payload = self.model_dump(mode="json")
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class Cassette(JsonCassette):
    """One recorded exchange, exactly as it sits on disk."""

    cassette_version: Literal[1] = CASSETTE_VERSION
    schema_version: int = SCHEMA_VERSION
    model_id: str = Field(min_length=1)
    synthetic: bool = Field(
        description="True when a stub model produced this. Never evidence about quality."
    )
    recorded_with: str = Field(
        min_length=1, description="What produced it, e.g. the pinned model id or 'TestModel'."
    )
    system: str = Field(min_length=1, description="The system prompt, verbatim and reviewable.")
    user: str = Field(min_length=1, description="The user message, verbatim and reviewable.")
    output: Explanation
    usage: CallUsage = CallUsage()


class JsonCassetteStore[T: JsonCassette](ABC):
    """A directory of hash-named JSON exchanges, one subdirectory per model. No I/O until asked.

    Two directories are stored this way, the explain stage's cassettes and the faithfulness
    judge's judgements, and the interesting half of a cassette store is the half they share:
    the file name is a hash of the exchange inside it, so a file that does not hash back to its
    own name is a hand-edit, a bad merge or a stray copy, and replaying it would answer the
    wrong question with a straight face. That check is written once, here, and so is the
    exception it raises, `CassetteCorrupt`, which exists for this condition alone.

    Subclasses supply three things: how to parse their payload, which field on it names the
    model, and how to re-derive the key from its contents. Everything a store does with those
    is the same in both.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @abstractmethod
    def _parse(self, text: str) -> T:
        """The payload type's own validator. The one place a subclass names its model."""

    @abstractmethod
    def _model_of(self, cassette: T) -> str:
        """The model this record *says* it came from — its `model_id`/`judge_model` field."""

    @abstractmethod
    def _derived_key(self, cassette: T) -> str:
        """The key this record's own contents hash to, computed from scratch and never read."""

    def path_for(self, model_id: str, key: str) -> Path:
        return self.directory / model_slug(model_id) / f"{key}.json"

    def load(self, model_id: str, key: str) -> T | None:
        """The recorded exchange, or `None`. Verifies the file is the exchange it claims to be.

        The file name is a hash of the prompt inside it, so that claim is checkable — and it is
        checked here rather than trusted, because trusting it means a hand-edited or
        badly-merged cassette replays as the answer to a question it was never asked. Deriving
        the key by hand is the property that makes cassettes explainable; doing it only
        in a test would leave the property true of four files and unenforced everywhere else.

        Three ways the claim can fail, and all three are the same failure: the contents hash to
        something else, the record's own `key` field disagrees with its file name, or it was
        filed under a model it does not name.
        """
        path = self.path_for(model_id, key)
        if not path.is_file():
            return None
        cassette = self._parse(path.read_text(encoding="utf-8"))
        derived = self._derived_key(cassette)
        if derived != key or cassette.key != key or self._model_of(cassette) != model_id:
            raise CassetteCorrupt(path, key, derived)
        return cassette

    def write(self, cassette: T) -> Path:
        """Write one record, tmp-and-rename, like the watch state and every other artifact here.

        A process killed mid-write leaves the committed file intact rather than half-written,
        which matters more than usual here: a half-written cassette is precisely a file that
        does not hash to its own name.
        """
        path = self.path_for(self._model_of(cassette), cassette.key)
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch = path.with_name(f"{path.name}.tmp")
        scratch.write_text(cassette.to_json(), encoding="utf-8")
        scratch.replace(path)
        return path

    def keys(self, model_id: str) -> tuple[str, ...]:
        """Every recorded key for one model, sorted — for inventory, not for lookup."""
        directory = self.directory / model_slug(model_id)
        if not directory.is_dir():
            return ()
        return tuple(sorted(path.stem for path in directory.glob("*.json")))


class CassetteStore(JsonCassetteStore[Cassette]):
    """A directory of explain-stage cassettes, one subdirectory per model."""

    def _parse(self, text: str) -> Cassette:
        return Cassette.model_validate_json(text)

    def _model_of(self, cassette: Cassette) -> str:
        return cassette.model_id

    def _derived_key(self, cassette: Cassette) -> str:
        return cassette_key(
            cassette.model_id, cassette.system, cassette.user, cassette.schema_version
        )

    def require(self, model_id: str, key: str) -> Cassette:
        """`load`, but a miss is a `CassetteMiss` naming the key and the file it wanted."""
        cassette = self.load(model_id, key)
        if cassette is None:
            raise CassetteMiss(model_id, key, self.path_for(model_id, key))
        return cassette

    def save(self, cassette: Cassette, *, allow_downgrade: bool = False) -> Path:
        """Write a cassette, refusing to replace a real recording with a synthetic one.

        The recorder runs the same command with or without an API key — with one it records
        against the pinned model, without one it records against a stub. That is convenient
        and it is a trap: once real cassettes exist, a keyless re-run would quietly replace
        them with placeholder text and every downstream number would still look green. So the
        downgrade is refused by default and has to be asked for.
        """
        if cassette.synthetic and not allow_downgrade:
            existing = self.load(cassette.model_id, cassette.key)
            if existing is not None and not existing.synthetic:
                path = self.path_for(cassette.model_id, cassette.key)
                needed = api_key_env(cassette.model_id) or "the provider's API key variable"
                raise ValueError(
                    f"refusing to overwrite the real recording at {path} with synthetic "
                    f"output; set {needed} to re-record it for real, or pass "
                    f"allow_downgrade=True if you mean it"
                )
        return self.write(cassette)
