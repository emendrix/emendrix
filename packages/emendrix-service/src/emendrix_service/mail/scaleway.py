"""Scaleway Transactional Email's delivery events, as its Topics and Events service posts them.

Pure: bytes in, a value out, nothing read or written. The provider delivers webhooks only
through Topics and Events, which speaks the SNS protocol: an HTTPS subscription first receives a
`SubscriptionConfirmation` envelope whose `SubscribeURL` must be opened once by hand, and each
event then arrives as a `Notification` envelope whose `Message` is the event's JSON as a string.

Read on 2026-10-09 from the provider's pages "Understanding webhook event payloads" and "Use
webhooks with SNS topics" (scaleway.com/en/docs/transactional-email/...). The event types listed
there are `email_queued`, `email_delivered`, `email_deferred`, `email_dropped`,
`email_mailbox_not_found`, `email_spam`, `email_blocklisted`, `blocklist_created` and
`unknown_type`. The ones read here map as:

- `email_dropped` (a definitive rejection or a hard bounce), `email_mailbox_not_found`:
  hard bounce;
- `email_spam` (identified as spam by the provider or the receiving server): complaint, the
  only type the pages offer for one;
- `email_deferred`: soft bounce;
- `email_delivered`: delivered;
- every other type is ignored and counted.

Every payload example names the recipient `email_to`; another page of the same documentation
names it `email_rcpt_to`, so both are read. The message is `email_id`, the instant `created_at`
(RFC 3339), falling back to the envelope's `Timestamp`. The pages' examples are not all valid
JSON, so nothing beyond these fields is relied on.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db.enums import MailEventKind

__all__ = ["KINDS", "Confirmation", "Envelope", "Notification", "ProviderEvent", "parse_envelope"]

KINDS: Final = {
    "email_dropped": MailEventKind.HARD_BOUNCE,
    "email_mailbox_not_found": MailEventKind.HARD_BOUNCE,
    "email_spam": MailEventKind.COMPLAINT,
    "email_deferred": MailEventKind.SOFT_BOUNCE,
    "email_delivered": MailEventKind.DELIVERED,
}

RECIPIENT_FIELDS: Final = ("email_to", "email_rcpt_to")

QUIET_TYPES: Final = frozenset({"UnsubscribeConfirmation"})
"""Envelope types that are valid and carry nothing to act on."""


class ProviderEvent(BaseModel):
    """One event about one message; `kind` is `None` for a type this service ignores."""

    model_config = ConfigDict(frozen=True)

    kind: MailEventKind | None = Field(description="What happened, or `None` when ignored.")
    recipient: str | None = Field(description="The address the message went to, if named.")
    provider_message_id: str | None = Field(description="The provider's id of the message.")
    at: datetime | None = Field(description="When the provider saw it, if stated and readable.")


class Confirmation(BaseModel):
    """The first post to a new subscription: it stays pending until `subscribe_url` is opened."""

    model_config = ConfigDict(frozen=True)

    subscribe_url: str = Field(description="The address that confirms the subscription.")


class Notification(BaseModel):
    """A post carrying events."""

    model_config = ConfigDict(frozen=True)

    events: tuple[ProviderEvent, ...] = Field(description="The events, in the order posted.")


Envelope = Confirmation | Notification


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _instant(value: object) -> datetime | None:
    text = _text(value)
    if text is None:
        return None
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.utcoffset() is not None else None


def _event(payload: dict[str, object], fallback: datetime | None) -> ProviderEvent:
    kind = KINDS.get(str(payload.get("type")))
    recipient = next((r for r in map(_text, map(payload.get, RECIPIENT_FIELDS)) if r), None)
    return ProviderEvent(
        kind=kind,
        recipient=recipient,
        provider_message_id=_text(payload.get("email_id")),
        at=_instant(payload.get("created_at")) or fallback,
    )


def _events(message: object, fallback: datetime | None) -> tuple[ProviderEvent, ...] | None:
    if not isinstance(message, str):
        return None
    try:
        decoded: object = json.loads(message)
    except ValueError:
        return None
    events: list[ProviderEvent] = []
    for payload in decoded if isinstance(decoded, list) else [decoded]:
        if not isinstance(payload, dict):
            return None
        events.append(_event(payload, fallback))
    return tuple(events)


def parse_envelope(body: bytes) -> Envelope | None:
    """The envelope `body` holds, or `None` when it is not one."""
    try:
        decoded: object = json.loads(body)
    except ValueError:
        return None
    if not isinstance(decoded, dict):
        return None
    kind = decoded.get("Type")
    if kind == "SubscriptionConfirmation":
        url = _text(decoded.get("SubscribeURL"))
        return Confirmation(subscribe_url=url) if url else None
    if kind == "Notification":
        events = _events(decoded.get("Message"), _instant(decoded.get("Timestamp")))
        return Notification(events=events) if events is not None else None
    if isinstance(kind, str) and kind in QUIET_TYPES:
        return Notification(events=())
    return None
