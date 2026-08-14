"""The HTTP layer: retries where they help, none where they would only annoy a server.

Everything here runs against an `httpx.MockTransport`: no socket is opened, and the responses
replay the exact bodies CELLAR returned on 2026-08-06.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from emendrix.eu.cache import DiskResponseCache
from emendrix.eu.http import (
    ACCEPT_ZIP,
    BASE_URL,
    POLITE_DELAY_ENV,
    POLITE_DELAY_S,
    USER_AGENT,
    CellarHttp,
    polite_delay,
)
from emendrix.eu.identifiers import ResourceRef

# Verbatim from CELLAR on 2026-08-06.
NOT_FOUND = b"Resource [system 'consolidation' - id '2024R1689%2F20240712.ENG.fmx4'] not found."
NOT_ACCEPTABLE = (
    b"None of the requests returned successfully a redirection. The following exception was "
    b"thrown: [Not found work ['cellar:b93c5306-b410-11f0-b37f-01aa75e...'] + language(s) [eng]"
)


def make_client(
    responses: list[httpx.Response], tmp_path: Path, **kwargs: float | int
) -> tuple[CellarHttp, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return queue.pop(0) if queue else responses[-1]

    http = CellarHttp(
        cache=DiskResponseCache(tmp_path),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
        polite_delay_s=0.0,
        **kwargs,  # type: ignore[arg-type]
    )
    return http, seen


def test_the_polite_delay_reads_the_flag_then_the_environment_then_the_default() -> None:
    """A backfill is the one workload that wants to turn it up, so it must be reachable."""
    assert polite_delay(environment={}) == POLITE_DELAY_S
    assert polite_delay(environment={POLITE_DELAY_ENV: "4.5"}) == 4.5
    assert polite_delay(2.0, environment={POLITE_DELAY_ENV: "4.5"}) == 2.0


@pytest.mark.parametrize("value", ["slowly", "-1", ""])
def test_a_polite_delay_that_is_not_a_wait_is_refused_by_name(value: str) -> None:
    """Reading it as the default instead would be a quiet decision to hammer a public endpoint."""
    with pytest.raises(ValueError, match=POLITE_DELAY_ENV):
        polite_delay(environment={POLITE_DELAY_ENV: value})


def test_it_sends_the_negotiation_headers_and_identifies_itself(tmp_path: Path) -> None:
    http, seen = make_client([httpx.Response(200, content=b"<NOTICE/>")], tmp_path)
    response = http.get(
        ResourceRef(system="consolidation", identifier="2024R1689/20260727.ENG.fmx4"),
        accept=ACCEPT_ZIP,
    )
    assert response.ok
    request = seen[0]
    assert str(request.url) == (f"{BASE_URL}/resource/consolidation/2024R1689%2F20260727.ENG.fmx4")
    assert request.headers["accept"] == ACCEPT_ZIP
    assert request.headers["accept-language"] == "eng"
    assert request.headers["user-agent"] == USER_AGENT
    assert USER_AGENT.startswith("emendrix/")
    assert "github.com/emendrix/emendrix" in USER_AGENT, "the contact URL has to resolve"


def test_https_is_the_base(tmp_path: Path) -> None:
    """Verified 2026-08-06: HTTPS answers identically to plain HTTP, so the base is HTTPS."""
    assert BASE_URL.startswith("https://")


def test_the_second_ask_never_leaves_the_machine(tmp_path: Path) -> None:
    http, seen = make_client([httpx.Response(200, content=b"<NOTICE/>")], tmp_path)
    first = http.get("/resource/celex/32024R1689", accept=ACCEPT_ZIP)
    second = http.get("/resource/celex/32024R1689", accept=ACCEPT_ZIP)
    assert len(seen) == 1
    assert http.network_calls == 1
    assert second.body == first.body
    assert second.from_cache and not first.from_cache


@pytest.mark.parametrize(
    ("status", "body"), [(404, NOT_FOUND), (406, NOT_ACCEPTABLE), (403, b"nope")]
)
def test_a_refusal_is_returned_not_retried(tmp_path: Path, status: int, body: bytes) -> None:
    """A 404 and a 406 are answers about the document; retrying only annoys the server."""
    http, seen = make_client([httpx.Response(status, content=body)], tmp_path)
    response = http.get("/resource/celex/whatever", accept=ACCEPT_ZIP)
    assert response.status_code == status
    assert response.ok is False
    assert len(seen) == 1
    assert response.text() == body.decode()


def test_server_errors_are_retried_then_reported(tmp_path: Path) -> None:
    http, seen = make_client([httpx.Response(503)] * 3, tmp_path)
    with pytest.raises(ConnectionError, match="after 3 attempts"):
        http.get("/resource/celex/32024R1689", accept=ACCEPT_ZIP)
    assert len(seen) == 3


def test_a_retry_can_succeed(tmp_path: Path) -> None:
    http, seen = make_client([httpx.Response(500), httpx.Response(200, content=b"ok")], tmp_path)
    assert http.get("/resource/celex/32024R1689", accept=ACCEPT_ZIP).body == b"ok"
    assert len(seen) == 2


def test_transport_failures_are_retried(tmp_path: Path) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectTimeout("timed out", request=request)
        return httpx.Response(200, content=b"ok")

    http = CellarHttp(
        cache=DiskResponseCache(tmp_path),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
        polite_delay_s=0.0,
    )
    assert http.get("/resource/celex/32024R1689", accept=ACCEPT_ZIP).body == b"ok"
    assert attempts["n"] == 3


def test_backoff_grows_and_the_first_call_does_not_wait(tmp_path: Path) -> None:
    waits: list[float] = []
    http = CellarHttp(
        cache=DiskResponseCache(tmp_path),
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
        sleep=waits.append,
        backoff_s=2.0,
        polite_delay_s=1.0,
    )
    with pytest.raises(ConnectionError):
        http.get("/resource/celex/32024R1689", accept=ACCEPT_ZIP)
    assert waits == [2.0, 4.0]
