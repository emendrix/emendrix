"""The explain stage's configuration, and the one place a model identifier is written down.

## The pinned model, confirmed 2026-08-08

`openrouter:anthropic/claude-sonnet-5`, reached through OpenRouter rather than Anthropic
directly. Routing is the author's choice: one key and one account for every provider a reviewer
might want to compare against. It costs a hop and a second party in the request path, neither of
which matters for a bounded compare-two-texts call.

Read off OpenRouter's own `/api/v1/models` on **2026-08-08**, not from memory: the id *shape*
differs from Anthropic's own and guessing it wrong is a 404 at the first live call.

| | |
|---|---|
| Status | Listed and active, canonical slug `anthropic/claude-sonnet-5-20260630` |
| Context window | 1 000 000 tokens, 128 000 of them completion |
| Price | **$2.00** in, **$10.00** out, per 1M tokens |
| Structured outputs | Advertised, which is the whole reason it can be used at all here |
| `temperature` | **Not advertised.** See `ExplainSettings.temperature` |

The provider needs `OPENROUTER_API_KEY`; `.envrc.example` documents the local setup.

Why a mid tier and not the cheapest model. The task looks bounded to the limit (*read two
verbatim texts already known to differ and write one sentence about the difference*), so the
obvious reading is that capability buys phrasing quality and nothing else. A hand review of
twenty shipped explanations on 2026-08-08 measured that reading and found it wrong: five of the
seven failures were failures of the explainer's *reading* rather than of its phrasing, three of
them stating a legal conclusion the text does not carry and one describing text past the
truncation marker. Those are capability failures, and the pin is set for them. Measured over the
2026-08-08 recording of the AI Act's 45-change flagship delta: 222 495 input and 15 353 output
tokens, about 4 900 in and 340 out per change, **$0.60** for the delta.

Sampling is not pinned, because the pinned model does not accept the parameter; see
`ExplainSettings.temperature`. Reproducibility in CI comes from cassette replay and never from a
sampling parameter.

Everything here is overridable by environment variable so a reviewer can point the same code
at a different model without editing it. Nothing here reads a clock or a network.

## How the environment is read

`pydantic-settings`, with its default wired shut. Out of the box `BaseSettings` reads the
process environment on *every* construction, which would quietly make `ExplainSettings()` mean
"defaults, unless this machine happens to export `EMENDRIX_MODEL`", and a test whose result
depends on the shell it ran in is not a test. So `settings_customise_sources` keeps only the
init source, and the environment is reached exactly once, deliberately, through `from_env`.

The library earns its place on the other half: each variable name is declared beside the field
it sets rather than in a constructor fifty lines below, and `EMENDRIX_EXPLAIN_MAX_TOKENS=banana`
raises a `ValidationError` that names the variable instead of a bare `ValueError` from
inside `int()`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

__all__ = [
    "DEFAULT_CASSETTE_DIR",
    "DEFAULT_MODEL",
    "PUBLISHED_RATES",
    "CassetteMode",
    "ExplainSettings",
    "ModelRate",
    "api_key_env",
    "rate_for",
]

DEFAULT_MODEL: Final = "openrouter:anthropic/claude-sonnet-5"
"""Confirmed 2026-08-08; see the module docstring for the pricing check behind it.

Editing this constant is what switches the explainer, and exporting `EMENDRIX_MODEL` is not:
every cassette recorder constructs `ExplainSettings` directly, and this class reads no
environment by construction, so a recording run labels its files with whatever is written here.
"""

DEFAULT_CASSETTE_DIR: Final = Path(__file__).resolve().parents[3] / "tests" / "cassettes"
"""Where the committed cassettes live when emendrix is run from a source checkout.

Resolved from this file rather than the working directory so `uv run pytest` and
`uv run emendrix` agree. An installed wheel has no `tests/` directory beside it, which is
correct: cassettes are a test and evaluation artifact, and every caller that needs them in
anger passes the directory explicitly.
"""


class CassetteMode(StrEnum):
    """How the explain call meets the cassette store.

    `REPLAY` is the only mode CI ever runs. It has no code path to a network call and none to
    an API key: a prompt nobody recorded fails loudly with the key it was looking for, rather
    than quietly reaching for a provider.
    """

    REPLAY = "replay"
    RECORD = "record"
    LIVE = "live"


_PROVIDER_KEY_ENV: Final[Mapping[str, str]] = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google-gla": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}
"""Provider prefix → the environment variable pydantic-ai reads its key from.

Only the providers a reviewer is plausibly going to point `EMENDRIX_MODEL` at; pydantic-ai
knows thirty-odd. Read from pydantic-ai's own provider sources on 2026-08-06 rather than
assumed — the mapping is not derivable from the prefix (`google-gla` reads `GOOGLE_API_KEY`).
"""


class ModelRate(BaseModel):
    """A published price, with the date it was read off the provider's own listing."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    input_per_mtok: float = Field(ge=0.0, description="US dollars per 1M input tokens.")
    output_per_mtok: float = Field(ge=0.0, description="US dollars per 1M output tokens.")
    checked_on: date = Field(description="When this rate was verified against the listing.")


PUBLISHED_RATES: Final[tuple[ModelRate, ...]] = (
    ModelRate(
        model_id=DEFAULT_MODEL,
        input_per_mtok=2.00,
        output_per_mtok=10.00,
        checked_on=date(2026, 8, 8),
    ),
    # The eval layer's faithfulness judge (`eval_/faithfulness.py`), priced here so that every
    # model this project pays for has its rate written down in one reviewable place. Read off
    # OpenRouter's `/api/v1/models` on 2026-08-08, same call as the line above. That listing also
    # publishes a higher rate ($10.00 / $45.00) above 272 000 prompt tokens, which no prompt this
    # project sends comes close to: the explain cap is 40 000 characters a side, roughly
    # 10 000 tokens, so a two-sided prompt stays an order of magnitude under that step.
    ModelRate(
        model_id="openrouter:openai/gpt-5.6-sol",
        input_per_mtok=5.00,
        output_per_mtok=30.00,
        checked_on=date(2026, 8, 8),
    ),
    # The explainer pin this project ran before 2026-08-08. It stays priced because figures from
    # its recording are still quoted in `CHANGELOG.md`: a reader pricing them against a table that
    # has forgotten the model would get "unpriced" for a run this project actually paid for.
    # Read 2026-08-06.
    ModelRate(
        model_id="openrouter:anthropic/claude-haiku-4.5",
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        checked_on=date(2026, 8, 6),
    ),
)
"""Every model this project spends money on, at the rate its provider publishes.

A rate that is not in this table is not known, and a cost computed from a guess is worse than no
cost at all — `rate_for` answers `None` and the report says "unpriced" rather than inventing one.
"""


def rate_for(model_id: str) -> ModelRate | None:
    """The published rate for a model id, or `None` when this repository has not checked one."""
    return next((rate for rate in PUBLISHED_RATES if rate.model_id == model_id), None)


def api_key_env(model_id: str) -> str | None:
    """The env var a live call with this model needs, or `None` when none is recorded here.

    Used for error messages and by the cassette recorder to decide whether a real recording
    is even possible. `None` is not "no key needed" — it is "this code cannot tell you",
    which is why callers phrase it as a question rather than an assertion.
    """
    provider, _, _ = model_id.partition(":")
    return _PROVIDER_KEY_ENV.get(provider)


class _MappingEnv(EnvSettingsSource):
    """An environment source reading a mapping it is handed, rather than the process.

    The reason `from_env(env=...)` still exists after the move to `pydantic-settings`: the
    process environment is not a fixture, and a test that mutates it fails differently on
    someone else's machine. `case_sensitive=True` on the settings class is what lets this be
    a plain `dict()` — the aliases and the variables are both upper case, so there is no
    normalisation step to get wrong.
    """

    def __init__(self, settings_cls: type[BaseSettings], env: Mapping[str, str]) -> None:
        self._env = env
        super().__init__(settings_cls)

    def _load_env_vars(self) -> Mapping[str, str | None]:
        return dict(self._env)


class ExplainSettings(BaseSettings):
    """Every knob the explain stage has, with sane defaults and an env override each.

    Constructing one reads **no** environment; `from_env` is the only door the environment
    comes through, and the source override below plus `_MappingEnv` are what it costs to keep
    that true. The module docstring says why it is worth paying.
    """

    model_config = SettingsConfigDict(frozen=True, case_sensitive=True, populate_by_name=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Init values only. The environment arrives through `from_env`, or not at all."""
        return (init_settings,)

    model_id: str = Field(default=DEFAULT_MODEL, min_length=1, validation_alias="EMENDRIX_MODEL")
    temperature: Annotated[float, Field(ge=0.0, le=1.0)] | None = Field(
        default=None,
        validation_alias="EMENDRIX_EXPLAIN_TEMPERATURE",
        description="Sampling temperature, or `None` to send none at all. Default: none.",
    )
    """`None`, and `engine._build_agent` then omits the key from `ModelSettings` entirely.

    The pinned model's OpenRouter listing does not advertise `temperature` (read off
    `/api/v1/models` on 2026-08-08; the judge's listing does not advertise it either, which is why
    `eval_/faithfulness.py` sets none). Sending a sampling parameter a provider does not accept is
    how a recording run dies twenty calls in, and a pinned temperature is not what makes CI
    reproducible: cassette replay is. A reviewer pointing `EMENDRIX_MODEL` at a model that does
    take one sets `EMENDRIX_EXPLAIN_TEMPERATURE`.
    """
    max_output_tokens: int = Field(
        default=1024, gt=0, validation_alias="EMENDRIX_EXPLAIN_MAX_TOKENS"
    )
    output_retries: int = Field(
        default=1,
        ge=0,
        validation_alias="EMENDRIX_EXPLAIN_OUTPUT_RETRIES",
        description="Schema-repair attempts pydantic-ai may make. Not the gate's retry.",
    )
    max_concurrency: int = Field(
        default=4,
        gt=0,
        validation_alias="EMENDRIX_EXPLAIN_MAX_CONCURRENCY",
        description="Changes explained at once; they are independent.",
    )
    text_char_cap: int = Field(
        default=40000,
        gt=0,
        validation_alias="EMENDRIX_EXPLAIN_TEXT_CAP",
        description="Per-side cap on the before/after text. Overrun is marked, never silent.",
    )
    """40 000 since 2026-08-09, sized so the corpus's provisions arrive whole: measured that day
    over the 55 pinned subset changes, the longest side below the one outlier is 36 535
    characters, and 40 000 characters is roughly 10 000 tokens against the pinned model's
    1 000 000-token window. It deliberately does not swallow the largest annex (roughly 51 000
    characters a side): a cap sized to fit the single largest text is a cap that one outlier
    chose. Overrun is still marked and counted.
    """
    context_char_cap: int = Field(
        default=2000,
        gt=0,
        validation_alias="EMENDRIX_EXPLAIN_CONTEXT_CAP",
        description="Cap on the surrounding-provision text, marked the same way.",
    )
    """2 000, and deliberately not sized against anything. The block is orientation rather than
    evidence: sentences must follow from the two verbatim texts, and this block only situates
    them. No committed prompt carries the block (checked 2026-08-09; no case in the corpus
    supplies a surrounding text), so any value here is untested; it gets measured when a caller
    first supplies the text, not resized on nothing.
    """
    cassette_mode: CassetteMode = Field(
        default=CassetteMode.REPLAY, validation_alias="EMENDRIX_EXPLAIN_CASSETTES"
    )
    cassette_dir: Path = Field(
        default=DEFAULT_CASSETTE_DIR, validation_alias="EMENDRIX_EXPLAIN_CASSETTE_DIR"
    )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        """Settings with every `EMENDRIX_*` override applied. `env=None` reads the process."""
        return cls(**_MappingEnv(cls, os.environ if env is None else env)())
