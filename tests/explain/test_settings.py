"""The config surface, and the model pin it defends.

The model id is the one string in this project that costs money when it is wrong, so it gets
a test rather than a comment. Env overrides are read from an explicit mapping in every test
here: the process environment is not a fixture, and a test that mutates it is a test that
fails differently on someone else's machine.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from emendrix.eval_.judge import DEFAULT_JUDGE_MODEL
from emendrix.explain import (
    DEFAULT_MODEL,
    PUBLISHED_RATES,
    CallUsage,
    CassetteMode,
    ExplainEngine,
    ExplainSettings,
    api_key_env,
    model_slug,
    rate_for,
)

# OpenRouter's published rates for `anthropic/claude-sonnet-5`, read off its `/api/v1/models`
# on 2026-08-08. Kept here rather than in `settings.py` so the pin and the arithmetic that
# depends on it move together.
EXPLAINER_INPUT_PER_MTOK = 2.00
EXPLAINER_OUTPUT_PER_MTOK = 10.00


def test_the_pinned_model_is_the_one_documented() -> None:
    """Confirmed 2026-08-08: Sonnet 5 via OpenRouter, $2.00 / $10.00 per 1M tokens.

    Note the id shape: OpenRouter spells this family `claude-sonnet-5` where Anthropic's own API
    spells the dated id differently. Asserting it here is what stops the difference from being
    discovered at the first live call.
    """
    assert DEFAULT_MODEL == "openrouter:anthropic/claude-sonnet-5"
    assert ExplainSettings().model_id == DEFAULT_MODEL


def test_the_judge_is_a_different_model_from_a_different_vendor() -> None:
    """The independence claim, such as it is, asserted rather than described.

    A judge that is the explainer is a model marking its own homework, and a judge weaker than
    the explainer measures the judge. Both ids were read off OpenRouter's `/api/v1/models` on
    2026-08-08; the judge's output rate is three times the explainer's, which is the only
    "stronger" this file can check without calling either of them.
    """
    assert DEFAULT_JUDGE_MODEL == "openrouter:openai/gpt-5.6-sol"
    # Different vendors, which is the stronger claim and implies the two are different models.
    # Asserted on the split rather than on the constants because a `!=` between two `Final`
    # literals is a comparison `mypy --strict` already knows the answer to.
    assert DEFAULT_JUDGE_MODEL.split("/")[0] != DEFAULT_MODEL.split("/")[0]
    explainer, judge = rate_for(DEFAULT_MODEL), rate_for(DEFAULT_JUDGE_MODEL)
    assert explainer is not None and judge is not None, "an unpriced model is an unbudgeted one"
    assert judge.output_per_mtok > explainer.output_per_mtok


def test_the_key_the_pinned_model_needs_is_the_one_the_setup_documents() -> None:
    """`.envrc.example` tells a reader to set `OPENROUTER_API_KEY`; this is why."""
    assert api_key_env(DEFAULT_MODEL) == "OPENROUTER_API_KEY"
    assert api_key_env("anthropic:claude-haiku-4-5") == "ANTHROPIC_API_KEY"
    assert api_key_env("nosuchprovider:model") is None


def test_the_defaults_are_the_ones_the_design_specifies() -> None:
    settings = ExplainSettings()
    assert settings.temperature is None
    assert settings.output_retries == 2
    assert settings.max_concurrency == 4
    assert settings.cassette_mode is CassetteMode.REPLAY


def test_the_text_cap_is_sized_for_the_corpus_and_not_for_its_largest_outlier() -> None:
    """40 000 since 2026-08-09, sized by measurement rather than by the largest text.

    Measured 2026-08-09 over the 55 pinned subset changes: the longest side below the one
    outlier is 36 535 characters, so every side but that outlier clears 40 000 with headroom,
    while the largest annex (roughly 51 000 characters a side) deliberately does not. A cap
    sized to fit one outlier is a cap that outlier chose. The context cap stays at 2 000 on
    purpose: no committed prompt carries the surrounding-context block, so any value there is
    untested by this corpus, and an unexercised number is not resized on no evidence.
    """
    settings = ExplainSettings()
    assert settings.text_char_cap == 40000
    assert settings.text_char_cap > 36535, "the corpus's longest non-outlier side arrives whole"
    assert settings.text_char_cap < 51156, "the largest annex still overruns, marked and counted"
    assert settings.context_char_cap == 2000


def test_no_sampling_parameter_is_sent_unless_one_is_configured() -> None:
    """The pinned model's OpenRouter listing does not advertise `temperature` (read 2026-08-08).

    Sending a sampling parameter a provider does not accept is how a recording run dies twenty
    calls in, so the key is absent from `ModelSettings` rather than present and zero. Nothing is
    lost: reproducibility in CI comes from cassette replay, never from a sampling parameter.
    """
    assert "temperature" not in ExplainEngine(ExplainSettings()).model_settings
    warmer = ExplainEngine(ExplainSettings(temperature=0.4)).model_settings
    assert warmer["temperature"] == 0.4
    assert warmer["max_tokens"] == ExplainSettings().max_output_tokens


def test_replay_is_the_default_so_no_run_reaches_a_provider_by_accident() -> None:
    """A default that calls a paid API is a default that bills someone for a typo."""
    assert ExplainSettings.from_env({}).cassette_mode is CassetteMode.REPLAY


def test_every_knob_has_an_env_override() -> None:
    settings = ExplainSettings.from_env(
        {
            "EMENDRIX_MODEL": "anthropic:claude-sonnet-4-6",
            "EMENDRIX_EXPLAIN_TEMPERATURE": "0.4",
            "EMENDRIX_EXPLAIN_MAX_TOKENS": "2048",
            "EMENDRIX_EXPLAIN_OUTPUT_RETRIES": "0",
            "EMENDRIX_EXPLAIN_MAX_CONCURRENCY": "8",
            "EMENDRIX_EXPLAIN_TEXT_CAP": "500",
            "EMENDRIX_EXPLAIN_CONTEXT_CAP": "250",
            "EMENDRIX_EXPLAIN_CASSETTES": "live",
            "EMENDRIX_EXPLAIN_CASSETTE_DIR": "/tmp/cassettes",
        }
    )
    assert settings.model_id == "anthropic:claude-sonnet-4-6"
    assert settings.temperature == 0.4
    assert settings.max_output_tokens == 2048
    assert settings.output_retries == 0
    assert settings.max_concurrency == 8
    assert settings.text_char_cap == 500
    assert settings.context_char_cap == 250
    assert settings.cassette_mode is CassetteMode.LIVE
    assert str(settings.cassette_dir) == "/tmp/cassettes"


def test_an_unknown_cassette_mode_is_rejected_rather_than_defaulted() -> None:
    with pytest.raises(ValueError, match="yolo"):
        ExplainSettings.from_env({"EMENDRIX_EXPLAIN_CASSETTES": "yolo"})


def test_a_bad_number_in_the_environment_names_the_variable_it_came_from() -> None:
    """What `pydantic-settings` is here for: a typed error instead of a bare `int()` failure.

    Without it, `EMENDRIX_EXPLAIN_MAX_TOKENS=banana` would surface as `invalid literal for
    int() with base 10: 'banana'` from somewhere inside a constructor, naming neither the
    variable nor the setting. An operator reading a container log needs the variable name.
    """
    with pytest.raises(ValidationError) as caught:
        ExplainSettings.from_env({"EMENDRIX_EXPLAIN_MAX_TOKENS": "banana"})
    error = caught.value.errors()[0]
    assert error["loc"] == ("EMENDRIX_EXPLAIN_MAX_TOKENS",)
    assert error["type"] == "int_parsing"


def test_constructing_settings_reads_no_environment_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`BaseSettings` reads the process by default; here it is wired shut on purpose.

    `ExplainSettings()` has to mean *the defaults* and nothing else, or every test that
    constructs one starts depending on the shell it was run from, and the model pin would be
    silently overridable by an exported variable nobody remembered. `from_env` is the only
    door the environment comes through, which is what makes that door reviewable.
    """
    monkeypatch.setenv("EMENDRIX_MODEL", "anthropic:not-the-pinned-model")
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "live")
    assert ExplainSettings().model_id == DEFAULT_MODEL
    assert ExplainSettings().cassette_mode is CassetteMode.REPLAY
    assert ExplainSettings.from_env().model_id == "anthropic:not-the-pinned-model"


def test_settings_are_a_frozen_value_type() -> None:
    settings = ExplainSettings()
    with pytest.raises(ValidationError):
        settings.model_id = "anthropic:something-else"


def test_nonsensical_settings_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ExplainSettings(max_concurrency=0)
    with pytest.raises(ValidationError):
        ExplainSettings(text_char_cap=0)
    with pytest.raises(ValidationError):
        ExplainSettings(temperature=2.0)


def test_the_model_id_survives_the_trip_through_a_directory_name() -> None:
    """The cassette path is derived from the model id, and a colon is not a directory."""
    assert model_slug(DEFAULT_MODEL) == "openrouter_anthropic_claude-sonnet-5"
    assert "/" not in model_slug("provider/with:slashes")


def test_cost_is_computed_at_the_published_rates() -> None:
    """Sanity on the arithmetic behind the $0.60 the flagship delta measured on 2026-08-08.

    The token counts are the ones the committed cassettes for `32024R1689@20260727` add up to,
    so this pins the arithmetic against a figure the README and the module docstring both quote.
    """
    usage = CallUsage(input_tokens=222495, output_tokens=15353, requests=45)
    delta = usage.cost_usd(
        input_per_mtok=EXPLAINER_INPUT_PER_MTOK, output_per_mtok=EXPLAINER_OUTPUT_PER_MTOK
    )
    assert delta == pytest.approx(0.60, abs=0.01)
    assert delta / 45 == pytest.approx(0.013, abs=0.001)


def test_every_model_this_project_pays_for_has_a_dated_rate() -> None:
    """A rate that is not in the table makes the report print "unpriced", which is honest but
    useless. A model this project has stopped calling stays priced while the changelog still
    quotes figures its recording produced: pricing those needs the rate that was paid."""
    priced = {rate.model_id for rate in PUBLISHED_RATES}
    assert {DEFAULT_MODEL, DEFAULT_JUDGE_MODEL} <= priced
    assert rate_for("openrouter:anthropic/claude-haiku-4.5") is not None
    assert rate_for("openrouter:nobody/never-pinned") is None


def test_usage_adds_up_field_by_field() -> None:
    total = CallUsage(input_tokens=10, output_tokens=2, requests=1, schema_repairs=1).plus(
        CallUsage(input_tokens=5, output_tokens=3, requests=2)
    )
    assert total == CallUsage(input_tokens=15, output_tokens=5, requests=3, schema_repairs=1)
