"""The pure rules of signing in: addresses, tokens, intents, the link decision, the window."""

from __future__ import annotations

from datetime import timedelta

import pytest

from emendrix_service.auth.logic import (
    Silent,
    WatchIntent,
    consent_version,
    decide_link,
    hash_token,
    link_expiry,
    local_path,
    may_sign_up,
    new_token,
    normalise_email,
    session_expiry,
)
from emendrix_service.auth.ratelimit import SlidingWindow
from emendrix_service.clock import FixedClock
from emendrix_service.db.enums import TokenPurpose
from tests.conftest import NOW


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  Alice@Example.ORG ", "Alice@example.org"),
        ("bob@example.org", "bob@example.org"),
        ("no-at-sign", None),
        ("two@@example.org", None),
        ("a b@example.org", None),
        ("alice@example.org\r\nBcc: x@example.org", None),
        ("<alice@example.org>", None),
        ("@example.org", None),
        ("alice@", None),
        ("alice@.example.org", None),
        ("x" * 65 + "@example.org", None),
        ("x@" + "d" * 250 + ".org", None),
    ],
)
def test_svc_auth_normalise_email(text: str, expected: str | None) -> None:
    assert normalise_email(text) == expected


def test_svc_auth_tokens_are_random_and_stored_by_hash() -> None:
    token, hashed = new_token()
    assert len(token) >= 43
    assert hashed == hash_token(token)
    assert new_token()[0] != token


def test_svc_auth_lifetimes() -> None:
    assert link_expiry(NOW) == NOW + timedelta(minutes=30)
    assert session_expiry(NOW) == NOW + timedelta(days=30)


def test_svc_auth_consent_version_is_twelve_hex_digits() -> None:
    version = consent_version(b"<p>notice</p>")
    assert len(version) == 12
    assert version != consent_version(b"<p>notice, revised</p>")


def test_svc_auth_intent_lands_on_the_watch_page() -> None:
    assert WatchIntent(corpus="eu", act_key="32017R0745").landing() == (
        "/account/watch?act=32017R0745"
    )
    with_location = WatchIntent(corpus="eu", act_key="32017R0745", location="AN I")
    assert with_location.landing() == "/account/watch?act=32017R0745&loc=AN+I"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/account/", "/account/"),
        ("/account/watch?act=X&loc=AN+I", "/account/watch?act=X&loc=AN+I"),
        ("https://example.org/account/", None),
        ("//example.org/account/", None),
        ("/account//example.org", None),
        ("/account/\\example.org", None),
        ("/u/feed/x.xml", None),
        ("", None),
        (None, None),
    ],
)
def test_svc_auth_local_path(value: str | None, expected: str | None) -> None:
    assert local_path(value) == expected


def decide(**overrides: object) -> TokenPurpose | Silent:
    values: dict[str, object] = {
        "asked": TokenPurpose.SIGNUP,
        "known": False,
        "active": False,
        "may_sign_up": True,
        "has_notice": True,
        "recent": 0,
    }
    values.update(overrides)
    return decide_link(**values)  # type: ignore[arg-type]


def test_svc_auth_the_link_decision() -> None:
    assert decide() is TokenPurpose.SIGNUP
    assert decide(known=True, active=True) is TokenPurpose.SIGNIN
    assert decide(known=True, active=False) is Silent.SUSPENDED
    assert decide(asked=TokenPurpose.SIGNIN) is Silent.UNKNOWN_ADDRESS
    assert decide(may_sign_up=False) is Silent.SIGNUP_CLOSED
    assert decide(has_notice=False) is Silent.NO_NOTICE
    assert decide(recent=3) is Silent.ADDRESS_LIMITED
    assert decide(known=True, active=True, recent=3) is Silent.ADDRESS_LIMITED
    assert decide(known=True, active=True, may_sign_up=False) is TokenPurpose.SIGNIN


def test_svc_auth_may_sign_up() -> None:
    closed = {"signup_open": False, "allowlist": ("invited@example.org",)}
    assert may_sign_up("anyone@example.org", signup_open=True, allowlist=())
    assert may_sign_up("Invited@example.org", **closed)  # type: ignore[arg-type]
    assert not may_sign_up("anyone@example.org", **closed)  # type: ignore[arg-type]


def test_svc_auth_sliding_window() -> None:
    clock = FixedClock(NOW)
    window = SlidingWindow(2, 60, clock)
    assert window.hit("a")
    assert window.hit("a")
    assert not window.hit("a")
    assert window.hit("b")
    clock.advance(timedelta(seconds=61))
    assert window.hit("a")
