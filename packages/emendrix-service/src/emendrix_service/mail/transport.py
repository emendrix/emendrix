"""The SMTP transport: the one module of the member that connects to a mail relay.

`SmtpMailer` speaks to any relay the settings name, one connection per email: volumes are
small, and a pooled connection's failure modes (a relay closing an idle session, a half-sent
message on a reused socket) cost more than a handshake. Every outcome is a `SendResult`:

- accepted: with the relay's id for the message when its reply names one (`queued as X`);
- refused with a 5xx for the recipient at `RCPT`: permanent, never retried;
- anything else (a 4xx, a refusal at `DATA`, a refused login or sender, an address the client
  cannot write, a connection that fails or times out): transient.

Only a recipient refusal is permanent, because a permanent refusal suppresses the address and
suspends its account. A refusal of the login, the sender, the message or the relay's policy
(`5.7.x`, such as an unverified sender domain) is the deployment's fault or the message's, and
counting it permanent would suppress every address tried while it lasted; retried, the row
fails after its last attempt and the address stays deliverable.

An error keeps the reply's code and text with every address replaced, because a relay's reply
often repeats the recipient, and the error is stored and logged.
"""

from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Final
from uuid import uuid4

from aiosmtplib import (
    SMTP,
    SMTPException,
    SMTPRecipientRefused,
    SMTPRecipientsRefused,
    SMTPResponseException,
)

from emendrix_service.clock import Clock
from emendrix_service.mail.message import OutgoingMail, SendResult
from emendrix_service.mail.mime import MESSAGE_ID, build_message, render, sender_domain
from emendrix_service.settings import ServiceSettings

__all__ = ["TIMEOUT", "SmtpMailer", "classify", "redact", "smtp_settings_complete"]

TIMEOUT: Final = 30.0
"""Seconds any one step of the conversation with the relay may take."""

ERROR_LENGTH: Final = 500

ADDRESS: Final = re.compile(r"[^\s<>()\[\]\"',;:@]+@[^\s<>()\[\]\"',;:@]+")

QUEUED_AS: Final = re.compile(r"queued as\s+<?([A-Za-z0-9][A-Za-z0-9._:-]*)", re.IGNORECASE)


def redact(text: str) -> str:
    """`text` on one line with every address replaced and its length capped."""
    return ADDRESS.sub("[address]", " ".join(text.split()))[:ERROR_LENGTH]


def smtp_settings_complete(settings: ServiceSettings) -> str | None:
    """The first setting sending needs and does not have, or `None` when nothing is missing."""
    if not settings.smtp_host:
        return "smtp_host"
    if not settings.mail_from:
        return "mail_from"
    if settings.smtp_username and settings.smtp_password is None:
        return "smtp_password"
    return None


def _refused(code: int, text: str, *, permanent: bool) -> SendResult:
    return SendResult(accepted=False, permanent=permanent, error=redact(f"{code} {text}"))


def _blames_recipient(code: int, text: str) -> bool:
    return 500 <= code < 600 and not text.lstrip().startswith("5.7.")


def classify(error: Exception) -> SendResult:
    """What one exception raised while sending means for the row being sent."""
    if isinstance(error, SMTPRecipientsRefused) and error.recipients:
        first = error.recipients[0]
        permanent = all(_blames_recipient(r.code, r.message) for r in error.recipients)
        return _refused(first.code, first.message, permanent=permanent)
    if isinstance(error, SMTPRecipientRefused):
        return _refused(
            error.code, error.message, permanent=_blames_recipient(error.code, error.message)
        )
    if isinstance(error, SMTPResponseException):
        return _refused(error.code, error.message, permanent=False)
    if isinstance(error, ValueError):
        return SendResult(accepted=False, error="an address the client cannot write")
    detail = error.message if isinstance(error, SMTPException) else str(error)
    return SendResult(accepted=False, error=redact(f"{type(error).__name__}: {detail}"))


def provider_id(reply: str) -> str | None:
    """The relay's id for an accepted message, when its reply names one."""
    found = QUEUED_AS.search(reply)
    return found.group(1) if found else None


class SmtpMailer:
    """A `Mailer` over the relay the settings name.

    A `Message-ID` among the mail's headers is used as the message's id, which is how the drain
    gives every attempt at one outbox row the same id; without one, a fresh id is made.
    """

    def __init__(self, settings: ServiceSettings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock

    async def send(self, mail: OutgoingMail, *, sender: str) -> SendResult:
        settings = self._settings
        if smtp_settings_complete(settings) is not None:
            return SendResult(accepted=False, error="the SMTP settings are incomplete")
        given = [value for name, value in mail.headers if name.lower() == MESSAGE_ID.lower()]
        message_id = given[0] if given else f"<{uuid4()}@{sender_domain(sender)}>"
        message = build_message(mail, sender=sender, now=self._clock.now(), message_id=message_id)
        password = settings.smtp_password
        client = SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=password.get_secret_value() if password is not None else None,
            start_tls=settings.smtp_starttls,
            timeout=TIMEOUT,
        )
        try:
            async with client:
                _, reply = await client.sendmail(parseaddr(sender)[1], [mail.to], render(message))
        except (SMTPException, OSError, ValueError) as error:
            return classify(error)
        return SendResult(accepted=True, provider_message_id=provider_id(reply))
