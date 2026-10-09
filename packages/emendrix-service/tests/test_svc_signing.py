"""A token verifies only for its own purpose, its own key and its own bytes."""

from __future__ import annotations

import pytest
from pydantic import SecretBytes

from emendrix_service.settings import ServiceSettings
from emendrix_service.signing import sign, verify


def test_svc_a_token_round_trips(settings: ServiceSettings) -> None:
    for payload in ("3f2b8c1e-0000-4000-8000-000000000001", "", "ünïcode.with.dots"):
        token = sign("unsub", payload, secret=settings.secret_key)
        assert verify("unsub", token, secret=settings.secret_key) == payload


def test_svc_a_token_is_deterministic_and_url_safe(settings: ServiceSettings) -> None:
    first = sign("csrf", "abc", secret=settings.secret_key)
    assert first == sign("csrf", "abc", secret=settings.secret_key)
    assert first.count(".") == 1
    assert all(c.isalnum() or c in "-_." for c in first)


def test_svc_a_token_does_not_verify_for_another_purpose(settings: ServiceSettings) -> None:
    token = sign("csrf", "abc", secret=settings.secret_key)
    assert verify("unsub", token, secret=settings.secret_key) is None


def test_svc_a_token_does_not_verify_under_another_key(settings: ServiceSettings) -> None:
    token = sign("csrf", "abc", secret=settings.secret_key)
    assert verify("csrf", token, secret=SecretBytes(bytes(32))) is None


def test_svc_a_tampered_payload_is_refused(settings: ServiceSettings) -> None:
    token = sign("unsub", "watchlist-1", secret=settings.secret_key)
    _, mac = token.split(".")
    forged = sign("unsub", "watchlist-2", secret=settings.secret_key).split(".")[0]
    assert verify("unsub", f"{forged}.{mac}", secret=settings.secret_key) is None


@pytest.mark.parametrize("cut", [1, 2, 5])
def test_svc_a_truncated_token_is_refused(settings: ServiceSettings, cut: int) -> None:
    token = sign("unsub", "watchlist-1", secret=settings.secret_key)
    assert verify("unsub", token[:-cut], secret=settings.secret_key) is None


@pytest.mark.parametrize("token", ["", ".", "abc", "abc.", ".abc", "a.b.c", "é.é", "YQ.!!"])
def test_svc_a_malformed_token_is_refused(settings: ServiceSettings, token: str) -> None:
    assert verify("unsub", token, secret=settings.secret_key) is None


def test_svc_a_purpose_is_required(settings: ServiceSettings) -> None:
    with pytest.raises(ValueError, match="purpose"):
        sign("", "abc", secret=settings.secret_key)
