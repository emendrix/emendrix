"""The message builder writes two UTF-8 alternatives, our headers untouched, and nothing else."""

from __future__ import annotations

from email import message_from_bytes, policy
from email.message import EmailMessage
from uuid import UUID

from emendrix_service.mail.message import OutgoingMail
from emendrix_service.mail.mime import build_message, message_id_for, render
from tests.conftest import NOW

SENDER = "Emendrix alerts <alerts@example.org>"

UNSUBSCRIBE = "<https://example.org/u/unsubscribe/" + "a" * 120 + ">"
"""Longer than a folded header line, with no whitespace to fold at."""

MAIL = OutgoingMail(
    to="reader@example.org",
    subject="Änderungen: Article 6 changed",
    text="Article 6 changed. Größe.\n\nThis is not legal advice.",
    html='<p>Article 6 changed. Größe.</p><p><a href="https://example.org/x">x</a></p>',
    headers=(
        ("List-Unsubscribe", UNSUBSCRIBE),
        ("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"),
        ("X-Emendrix-Kind", "instant"),
    ),
)

OUTBOX_ID = UUID("00000000-0000-4000-8000-000000000007")


def built() -> EmailMessage:
    return build_message(MAIL, sender=SENDER, now=NOW, message_id=message_id_for(OUTBOX_ID, SENDER))


def parsed() -> EmailMessage:
    message = message_from_bytes(render(built()), policy=policy.default)
    assert isinstance(message, EmailMessage)
    return message


def test_svc_mail_mime_has_a_text_and_an_html_part_in_utf8() -> None:
    message = parsed()
    assert message.get_content_type() == "multipart/alternative"
    parts = list(message.iter_parts())
    assert [part.get_content_type() for part in parts] == ["text/plain", "text/html"]
    for part in parts:
        assert part.get_content_charset() == "utf-8"
        assert part["Content-Transfer-Encoding"] == "quoted-printable"
    assert "Größe" in parts[0].get_content()
    assert "Größe" in parts[1].get_content()


def test_svc_mail_mime_writes_the_headers_in_order() -> None:
    names = [name for name, _ in parsed().items()]
    assert names[:6] == ["From", "To", "Subject", "Date", "Message-ID", "MIME-Version"]
    custom = [name for name in names if name.startswith(("List-", "X-"))]
    assert custom == ["List-Unsubscribe", "List-Unsubscribe-Post", "X-Emendrix-Kind"]
    assert parsed()["Date"] == "Mon, 12 Oct 2026 05:00:00 +0000"


def test_svc_mail_mime_passes_the_unsubscribe_headers_through_unfolded() -> None:
    wire = render(built())
    assert b"\r\nList-Unsubscribe: " + UNSUBSCRIBE.encode() + b"\r\n" in wire
    assert b"\r\nList-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n" in wire
    assert wire.isascii()


def test_svc_mail_mime_message_id_is_stable_for_one_row() -> None:
    first = message_id_for(OUTBOX_ID, SENDER)
    assert first == message_id_for(OUTBOX_ID, "alerts@example.org")
    assert first == f"<{OUTBOX_ID}@example.org>"
    assert parsed()["Message-ID"] == first


def test_svc_mail_mime_a_header_twin_cannot_replace_ours() -> None:
    mail = MAIL.model_copy(update={"headers": (("From", "other@example.org"), ("Bcc", "x"))})
    message = build_message(mail, sender=SENDER, now=NOW, message_id="<m@example.org>")
    assert message.get_all("From") == [SENDER]
    assert message.get_all("Bcc") is None


def test_svc_mail_mime_adds_no_image_and_no_tracking() -> None:
    wire = render(built()).lower()
    assert b"<img" not in wire
    for marker in (b"utm_", b"pixel", b"track"):
        assert marker not in wire
    html = list(parsed().iter_parts())[1].get_content()
    assert html.rstrip("\r\n") == MAIL.html
