"""The SMTP transport classifies every answer of a relay, against a stand-in for the client.

`aiosmtpd` is not locked in this workspace, so no SMTP server runs here: the client class the
transport builds is replaced by a fake that answers as a relay would. The one real connection
is to a port on this machine nothing listens on, which is refused before any byte is sent.
"""

from __future__ import annotations

import socket
from types import TracebackType
from typing import ClassVar

import pytest
from aiosmtplib import (
    SMTPConnectError,
    SMTPDataError,
    SMTPRecipientRefused,
    SMTPRecipientsRefused,
    SMTPResponse,
    SMTPSenderRefused,
)

from emendrix_service.clock import FixedClock
from emendrix_service.mail import transport
from emendrix_service.mail.message import OutgoingMail, SendResult
from emendrix_service.mail.transport import SmtpMailer, redact, smtp_settings_complete
from emendrix_service.settings import ServiceSettings
from tests.conftest import settings_values

pytestmark = pytest.mark.anyio

SENDER = "Emendrix alerts <alerts@example.org>"

MAIL = OutgoingMail(
    to="reader@example.org",
    subject="Article 6 changed",
    text="text",
    html="<p>html</p>",
    headers=(("Message-ID", "<fixed@example.org>"),),
)


def smtp_settings(**changes: object) -> ServiceSettings:
    values = {
        **settings_values(),
        "smtp_host": "relay.example.org",
        "smtp_port": 2587,
        "smtp_username": "user",
        "smtp_password": "password",
        "mail_from": SENDER,
        **changes,
    }
    return ServiceSettings.model_validate(values)


class FakeSmtp:
    """Answers as a relay would; `answer` is the reply text or the exception to raise."""

    answer: ClassVar[str | Exception] = "2.0.0 Ok: queued as 4Xy7Q2"
    connect_error: ClassVar[Exception | None] = None
    made: ClassVar[list[FakeSmtp]] = []

    def __init__(self, **options: object) -> None:
        self.options = options
        self.sent: list[tuple[str, list[str], bytes]] = []
        FakeSmtp.made.append(self)

    async def __aenter__(self) -> FakeSmtp:
        if FakeSmtp.connect_error is not None:
            raise FakeSmtp.connect_error
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        return None

    async def sendmail(
        self, sender: str, recipients: list[str], message: bytes
    ) -> tuple[dict[str, SMTPResponse], str]:
        self.sent.append((sender, recipients, message))
        if isinstance(FakeSmtp.answer, Exception):
            raise FakeSmtp.answer
        return {}, FakeSmtp.answer


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> type[FakeSmtp]:
    monkeypatch.setattr(FakeSmtp, "answer", "2.0.0 Ok: queued as 4Xy7Q2")
    monkeypatch.setattr(FakeSmtp, "connect_error", None)
    monkeypatch.setattr(FakeSmtp, "made", [])
    monkeypatch.setattr(transport, "SMTP", FakeSmtp)
    return FakeSmtp


async def send(clock: FixedClock, **changes: object) -> SendResult:
    return await SmtpMailer(smtp_settings(**changes), clock).send(MAIL, sender=SENDER)


async def test_svc_mail_transport_accepted(fake: type[FakeSmtp], clock: FixedClock) -> None:
    result = await send(clock)
    assert (result.accepted, result.provider_message_id, result.error) == (True, "4Xy7Q2", "")
    (client,) = fake.made
    assert client.options == {
        "hostname": "relay.example.org",
        "port": 2587,
        "username": "user",
        "password": "password",
        "start_tls": True,
        "timeout": 30.0,
    }
    ((envelope_from, recipients, wire),) = client.sent
    assert (envelope_from, recipients) == ("alerts@example.org", ["reader@example.org"])
    assert b"\r\nMessage-ID: <fixed@example.org>\r\n" in wire
    assert b"\r\nDate: Mon, 12 Oct 2026 05:00:00 +0000\r\n" in wire


async def test_svc_mail_transport_reply_without_an_id(
    fake: type[FakeSmtp], clock: FixedClock
) -> None:
    fake.answer = "2.0.0 Ok"
    result = await send(clock, smtp_username=None, smtp_password=None, smtp_starttls=False)
    assert (result.accepted, result.provider_message_id) == (True, None)
    assert fake.made[0].options["username"] is None
    assert fake.made[0].options["start_tls"] is False


@pytest.mark.parametrize(
    "error",
    [
        SMTPRecipientsRefused(
            [SMTPRecipientRefused(550, "5.1.1 <reader@example.org>: unknown", "reader@example.org")]
        ),
        SMTPRecipientRefused(550, "5.2.1 mailbox disabled for reader@example.org", "x"),
    ],
)
async def test_svc_mail_transport_a_5xx_for_the_recipient_is_permanent(
    fake: type[FakeSmtp], clock: FixedClock, error: Exception
) -> None:
    fake.answer = error
    result = await send(clock)
    assert (result.accepted, result.permanent) == (False, True)
    assert result.error.startswith(("550 5.1.1", "550 5.2.1"))
    assert "reader@example.org" not in result.error
    assert "[address]" in result.error


@pytest.mark.parametrize(
    "error",
    [
        SMTPRecipientsRefused(
            [SMTPRecipientRefused(451, "4.3.0 try again later", "reader@example.org")]
        ),
        SMTPDataError(451, "4.3.0 local error"),
        SMTPDataError(554, "5.7.1 message refused for reader@example.org"),
        SMTPSenderRefused(553, "5.7.1 sender not allowed", "alerts@example.org"),
        SMTPRecipientsRefused(
            [SMTPRecipientRefused(554, "5.7.1 relay access denied", "reader@example.org")]
        ),
    ],
)
async def test_svc_mail_transport_a_4xx_or_our_own_fault_is_transient(
    fake: type[FakeSmtp], clock: FixedClock, error: Exception
) -> None:
    fake.answer = error
    result = await send(clock)
    assert (result.accepted, result.permanent) == (False, False)
    assert result.error[:3] in {"451", "553", "554"}
    assert "reader@example.org" not in result.error


async def test_svc_mail_transport_a_connection_error_is_transient(
    fake: type[FakeSmtp], clock: FixedClock
) -> None:
    fake.connect_error = SMTPConnectError("Error connecting to relay.example.org on port 2587")
    result = await send(clock)
    assert (result.accepted, result.permanent) == (False, False)
    assert result.error.startswith("SMTPConnectError")


async def test_svc_mail_transport_a_refused_connection_is_transient(clock: FixedClock) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    result = await send(clock, smtp_host="127.0.0.1", smtp_port=port, smtp_username=None)
    assert (result.accepted, result.permanent) == (False, False)
    assert result.error


async def test_svc_mail_transport_refuses_to_send_without_its_settings(
    fake: type[FakeSmtp], clock: FixedClock
) -> None:
    result = await send(clock, smtp_host=None)
    assert (result.accepted, result.permanent) == (False, False)
    assert fake.made == []


def test_svc_mail_transport_names_the_first_missing_setting() -> None:
    assert smtp_settings_complete(smtp_settings()) is None
    assert smtp_settings_complete(smtp_settings(smtp_host=None)) == "smtp_host"
    assert smtp_settings_complete(smtp_settings(mail_from=None)) == "mail_from"
    assert smtp_settings_complete(smtp_settings(smtp_password=None)) == "smtp_password"
    assert smtp_settings_complete(smtp_settings(smtp_username=None, smtp_password=None)) is None


def test_svc_mail_transport_redact_removes_every_address() -> None:
    text = "550 <Reader.Name+tag@sub.example.org>: no such user\r\n(reader@example.org)"
    assert redact(text) == "550 <[address]>: no such user ([address])"
