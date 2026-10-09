"""The SMTP transport: the one module of the member that connects to a mail relay.

`SmtpMailer` is what the web process sends sign-in links through. This version declares it and
answers every send with a transient refusal, so a queued email stays queued until a transport
that sends is built.
"""

from __future__ import annotations

from emendrix_service.clock import Clock
from emendrix_service.mail.message import OutgoingMail, SendResult
from emendrix_service.settings import ServiceSettings

__all__ = ["SmtpMailer"]


class SmtpMailer:
    """A `Mailer` over the relay the settings name."""

    def __init__(self, settings: ServiceSettings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock

    async def send(self, mail: OutgoingMail, *, sender: str) -> SendResult:
        return SendResult(accepted=False, error="the SMTP transport is not built in this version")
