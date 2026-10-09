"""The settings refuse a deployment that is missing something or would misbehave quietly."""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from emendrix_service.settings import ServiceSettings, load_settings, require, variable
from tests.conftest import SECRET_KEY, settings_values

REQUIRED = ("database_url", "site_url", "allowed_hosts", "secret_key")


def build(**changes: object) -> ServiceSettings:
    return ServiceSettings.model_validate({**settings_values(), **changes})


@pytest.mark.parametrize("name", REQUIRED)
def test_svc_each_required_setting_is_required(name: str) -> None:
    values = settings_values()
    del values[name]
    with pytest.raises(ValidationError, match=name):
        ServiceSettings.model_validate(values)


def test_svc_the_defaults_are_the_documented_ones(settings: ServiceSettings) -> None:
    assert (settings.bind, settings.port) == ("0.0.0.0", 8000)
    assert (settings.smtp_port, settings.smtp_starttls) == (587, True)
    assert (settings.timezone, settings.digest_hour) == ("Europe/Brussels", 7)
    assert settings.signup_open is True
    assert settings.signup_allowlist == ()
    assert build().shell is None
    assert settings.zone().key == "Europe/Brussels"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "example.org",
        "https://example.org/",
        "https://example.org/?a=1",
        "https://",
    ],
)
def test_svc_the_site_url_is_https_with_no_trailing_slash(url: str) -> None:
    with pytest.raises(ValidationError, match="site_url"):
        build(site_url=url)


def test_svc_a_site_url_may_carry_a_path() -> None:
    assert build(site_url="https://example.org/base").site_url == "https://example.org/base"


def test_svc_the_database_url_names_the_psycopg_dialect() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        build(database_url="postgresql://service:service@localhost/service")


def test_svc_the_secret_key_is_decoded_and_long_enough() -> None:
    assert build().secret_key.get_secret_value() == bytes(range(32))
    short = base64.b64encode(bytes(31)).decode("ascii")
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        build(secret_key=short)
    with pytest.raises(ValidationError, match="not base64"):
        build(secret_key="not base64 at all!")


def test_svc_the_secret_key_may_be_url_safe_and_unpadded() -> None:
    key = bytes([251] * 33)
    text = base64.urlsafe_b64encode(key).decode("ascii").rstrip("=")
    assert build(secret_key=text).secret_key.get_secret_value() == key


def test_svc_lists_are_comma_split_and_lower_cased() -> None:
    settings = build(allowed_hosts=" Example.org, service:8000 ,", signup_allowlist="A@Example.org")
    assert settings.allowed_hosts == ("example.org", "service:8000")
    assert settings.signup_allowlist == ("a@example.org",)
    with pytest.raises(ValidationError, match="allowed_hosts"):
        build(allowed_hosts=" , ")


def test_svc_a_service_link_in_place_of_a_port_is_named() -> None:
    with pytest.raises(ValidationError, match="enableServiceLinks"):
        build(port="tcp://10.43.0.7:8000")
    assert build(port="8080").port == 8080


def test_svc_an_unknown_zone_is_refused() -> None:
    with pytest.raises(ValidationError, match="IANA"):
        build(timezone="Europe/Atlantis")


def test_svc_secrets_never_print() -> None:
    settings = build(smtp_password="hunter2-smtp", webhook_secret="hook-secret")
    shown = repr(settings) + str(settings)
    for secret in ("hunter2-smtp", "hook-secret", "service:service", SECRET_KEY):
        assert secret not in shown


def test_svc_settings_are_frozen(settings: ServiceSettings) -> None:
    with pytest.raises(ValidationError):
        settings.port = 1


def test_svc_require_names_the_missing_variable(
    settings: ServiceSettings, capsys: pytest.CaptureFixture[str]
) -> None:
    require(settings, "site_url")
    with pytest.raises(SystemExit) as stopped:
        require(settings, "site_url", "changelogs")
    assert stopped.value.code == 2
    assert capsys.readouterr().err == ("emendrix-service: EMENDRIX_SERVICE_CHANGELOGS is not set\n")
    with pytest.raises(SystemExit):
        require(settings, "signup_allowlist")


def test_svc_require_refuses_a_name_that_is_not_a_setting(settings: ServiceSettings) -> None:
    with pytest.raises(ValueError, match="not a setting"):
        require(settings, "changelog")


@pytest.mark.usefixtures("no_service_environment")
def test_svc_load_settings_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in settings_values().items():
        text = ",".join(value) if isinstance(value, tuple) else str(value)
        monkeypatch.setenv(variable(name), text)
    monkeypatch.setenv(variable("signup_open"), "false")
    monkeypatch.setenv(variable("smtp_host"), "")
    settings = load_settings()
    assert settings.site_url == "https://example.org"
    assert settings.signup_open is False
    assert settings.smtp_host is None


@pytest.mark.usefixtures("no_service_environment")
def test_svc_load_settings_stops_on_a_missing_or_bad_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name, value in settings_values().items():
        text = ",".join(value) if isinstance(value, tuple) else str(value)
        monkeypatch.setenv(variable(name), text)
    monkeypatch.delenv(variable("secret_key"))
    with pytest.raises(SystemExit) as stopped:
        load_settings()
    assert stopped.value.code == 2
    assert capsys.readouterr().err == "emendrix-service: EMENDRIX_SERVICE_SECRET_KEY is not set\n"

    monkeypatch.setenv(variable("secret_key"), SECRET_KEY)
    monkeypatch.setenv(variable("port"), "tcp://10.43.0.7:8000")
    with pytest.raises(SystemExit):
        load_settings()
    error = capsys.readouterr().err
    assert error.startswith("emendrix-service: EMENDRIX_SERVICE_PORT is not valid: ")
    assert "enableServiceLinks" in error
