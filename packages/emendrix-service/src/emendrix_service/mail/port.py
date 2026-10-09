"""The seam between composing an email and sending it, and the double tests send through.

Every caller holds a `Mailer` and never a transport, so a test passes a `RecordingMailer` and
reads what would have gone out, and nothing in the suite can reach a relay. The recording double
lives here rather than under `tests/` so every member test and every later module type-checks
against the one shape.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Protocol

from emendrix_service.mail.message import OutgoingMail, SendResult

__all__ = ["Mailer", "OutgoingMail", "RecordingMailer", "SendResult", "send_now"]


class Mailer(Protocol):
    """Something that hands one email to a relay and says what the relay answered."""

    async def send(self, mail: OutgoingMail, *, sender: str) -> SendResult:
        """Send `mail` from `sender`. A refusal is a result, never an exception."""
        ...


class RecordingMailer:
    """A `Mailer` that sends nothing and remembers everything.

    `attempts` holds every call as `(sender, mail)`; `sent` holds the mails it accepted. Each
    call takes the next of `results` when any are left and accepts otherwise, so a test can
    script a refusal followed by a success.
    """

    def __init__(self, results: Iterable[SendResult] = ()) -> None:
        self.sent: list[OutgoingMail] = []
        self.attempts: list[tuple[str, OutgoingMail]] = []
        self._results = deque(results)

    async def send(self, mail: OutgoingMail, *, sender: str) -> SendResult:
        self.attempts.append((sender, mail))
        if self._results:
            result = self._results.popleft()
        else:
            result = SendResult(accepted=True, provider_message_id=f"recorded-{len(self.sent)}")
        if result.accepted:
            self.sent.append(mail)
        return result


async def send_now(mailer: Mailer, mail: OutgoingMail, *, sender: str) -> SendResult:
    """Send `mail` straight away, after the transaction that queued it has committed.

    A transport that raises instead of answering is reported as a transient refusal, so a page
    that has already committed its work is never turned into an error by the relay; the outbox
    row stays queued and the drain retries it.
    """
    try:
        return await mailer.send(mail, sender=sender)
    except Exception as error:
        return SendResult(accepted=False, error=type(error).__name__)
