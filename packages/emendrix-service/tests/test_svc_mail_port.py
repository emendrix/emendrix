"""The mail port's values refuse header injection; the recording double scripts its answers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from emendrix_service.mail.port import OutgoingMail, RecordingMailer, SendResult, send_now

pytestmark = pytest.mark.anyio

SENDER = "Emendrix alerts <alerts@example.org>"


def mail(**changes: object) -> OutgoingMail:
    values: dict[str, object] = {
        "to": "reader@example.org",
        "subject": "Your sign-in link",
        "text": "text",
        "html": "<p>html</p>",
    }
    return OutgoingMail.model_validate({**values, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"to": "reader@example.org\r\nBcc: x@example.org"},
        {"subject": "hi\nBcc: x@example.org"},
        {"headers": (("List-Unsubscribe", "<x>\r\nBcc: x@example.org"),)},
    ],
)
def test_svc_no_header_carries_a_line_break(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="line break"):
        mail(**changes)


async def test_svc_the_recording_mailer_accepts_and_remembers(mailer: RecordingMailer) -> None:
    result = await send_now(mailer, mail(), sender=SENDER)
    assert result.accepted
    assert mailer.sent == [mail()]
    assert mailer.attempts == [(SENDER, mail())]


async def test_svc_the_recording_mailer_plays_its_script() -> None:
    refused = SendResult(accepted=False, permanent=True, error="550 no such mailbox")
    mailer = RecordingMailer([refused])
    assert await send_now(mailer, mail(), sender=SENDER) == refused
    assert (await send_now(mailer, mail(), sender=SENDER)).accepted
    assert len(mailer.attempts) == 2
    assert len(mailer.sent) == 1


class _Raising:
    async def send(self, mail: OutgoingMail, *, sender: str) -> SendResult:
        raise ConnectionError("relay unreachable")


async def test_svc_send_now_turns_a_raise_into_a_transient_refusal() -> None:
    result = await send_now(_Raising(), mail(), sender=SENDER)
    assert result == SendResult(accepted=False, permanent=False, error="ConnectionError")
