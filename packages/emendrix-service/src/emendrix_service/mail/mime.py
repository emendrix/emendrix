"""An `OutgoingMail` as the bytes a relay receives: text and HTML alternatives, our own headers.

Pure: the instant and the message id are handed in, so one outbox row renders to the same bytes
on every attempt. The message carries nothing the reader did not ask for: no tracking pixel, no
rewritten link, no image.

Headers are written with a line limit of 998 rather than the usual 78. A long
`List-Unsubscribe` value has no whitespace to fold at, and under the usual limit the email
package re-encodes it as RFC 2047 encoded words, which no mail client reads as a link.
"""

from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime, parseaddr
from typing import Final
from uuid import UUID

from emendrix_service.mail.message import OutgoingMail

__all__ = ["MESSAGE_ID", "POLICY", "build_message", "message_id_for", "render", "sender_domain"]

POLICY: Final = SMTP.clone(max_line_length=998)
"""CRLF line ends, and headers folded only past the hard limit of RFC 5322."""

MESSAGE_ID: Final = "Message-ID"

RESERVED: Final = frozenset(
    {"from", "to", "subject", "date", "message-id", "mime-version", "cc", "bcc"}
    | {"content-type", "content-transfer-encoding"}
)
"""Headers the builder writes itself; a twin passed in `OutgoingMail.headers` is left out."""


def sender_domain(sender: str) -> str:
    """The domain of the address in `sender` (`Name <user@domain>`), or `localhost`."""
    _, address = parseaddr(sender)
    domain = address.rpartition("@")[2]
    return domain or "localhost"


def message_id_for(outbox_id: UUID, sender: str) -> str:
    """The `Message-ID` of one outbox row, the same on every attempt to send it."""
    return f"<{outbox_id}@{sender_domain(sender)}>"


def build_message(
    mail: OutgoingMail, *, sender: str, now: datetime, message_id: str
) -> EmailMessage:
    """`mail` as a multipart/alternative message from `sender`, dated `now`."""
    message = EmailMessage(policy=POLICY)
    message["From"] = sender
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message["Date"] = format_datetime(now)
    message[MESSAGE_ID] = message_id
    message["MIME-Version"] = "1.0"
    for name, value in mail.headers:
        if name.lower() not in RESERVED:
            message[name] = value
    message.set_content(mail.text, charset="utf-8", cte="quoted-printable")
    message.add_alternative(mail.html, subtype="html", charset="utf-8", cte="quoted-printable")
    return message


def render(message: EmailMessage) -> bytes:
    """The message as sent on the wire, under `POLICY`."""
    return message.as_bytes(policy=POLICY)
