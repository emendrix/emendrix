"""The shared composition root: one wiring, however many commands enter the loop through it."""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import ActId, VersionId
from emendrix.eu.http import POLITE_DELAY_ENV, POLITE_DELAY_S
from emendrix.session import adapter_for, manual_event

OBSERVED = date(2026, 8, 8)
ACT = ActId(corpus="toy", key="house-rules")


def test_the_polite_delay_reaches_the_client_the_loop_fetches_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The knob is on the HTTP client, so a path to it that stops at the CLI is no path at all."""
    monkeypatch.delenv(POLITE_DELAY_ENV, raising=False)
    with adapter_for(None, OBSERVED) as adapter:
        assert adapter.client.http.polite_delay_s == POLITE_DELAY_S
    monkeypatch.setenv(POLITE_DELAY_ENV, "4")
    with adapter_for(None, OBSERVED) as adapter:
        assert adapter.client.http.polite_delay_s == 4.0
    with adapter_for(None, OBSERVED, polite_delay_s=0.25) as adapter:
        assert adapter.client.http.polite_delay_s == 0.25


def test_a_manual_event_names_the_command_that_asserted_it() -> None:
    """`trigger` is how a reader tells an operator's assertion from a poll's finding."""
    event = manual_event(ACT, "v1", "v2", OBSERVED, trigger="manual: emendrix backfill")
    assert event.act == ACT
    assert event.previous_version == VersionId("v1")
    assert event.new_version == VersionId("v2")
    assert event.target_version == VersionId("v2")
    assert event.trigger == "manual: emendrix backfill"
    assert event.observed_on == OBSERVED
