"""A composed email into an `OutgoingMail`: the subject, a text part, its HTML twin, the headers.

Every email carries `List-Unsubscribe` with the watchlist's one-click address and
`List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058), and both parts end with the
footer that carries the disclaimer, why the email came and how to stop it. A subject is built
from stored labels, so line breaks are folded out of it before the mail is built.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from pydantic import SecretBytes

from emendrix_service.mail.message import OutgoingMail
from emendrix_service.notify.model import ChangeLine, Digest, Heartbeat
from emendrix_service.signing import sign
from emendrix_service.web.templating import render_mail

__all__ = [
    "PREFIX",
    "digest_subject",
    "heartbeat_subject",
    "list_headers",
    "one_line",
    "render_digest",
    "render_heartbeat",
    "text_lines",
    "unsubscribe_url",
]

PREFIX: Final = "[Emendrix]"

METHODOLOGY: Final = "/methodology/"
"""Where the site says how a dispute is decided; a disputed line links it."""


def one_line(text: str) -> str:
    """`text` with every run of whitespace, line breaks included, folded to one space."""
    return " ".join(text.split())


def unsubscribe_url(site_url: str, watchlist_id: UUID, *, secret: SecretBytes) -> str:
    """The one-click address that stops this watchlist's email."""
    return f"{site_url}/u/unsubscribe/{sign('unsub', str(watchlist_id), secret=secret)}"


def list_headers(unsubscribe: str) -> tuple[tuple[str, str], ...]:
    """The RFC 2369 and RFC 8058 headers that let a mail client offer one-click unsubscribe."""
    return (
        ("List-Unsubscribe", f"<{unsubscribe}>"),
        ("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"),
    )


def _provisions(count: int) -> str:
    return f"{count} watched provision{'' if count == 1 else 's'}"


def digest_subject(digest: Digest) -> str:
    """The subject: a date change first on an instant email, else the act or the count of acts."""
    lines = digest.lines
    acts = tuple(dict.fromkeys(event.act_label for event in digest.events))
    if digest.kind == "instant" and digest.date_alert_count:
        dated = [line for line in lines if line.date_alert]
        if len(dated) == 1:
            subject = f"A date changed in {dated[0].title}"
        else:
            subject = f"Dates changed in {_provisions(len(dated))} of {acts[0]}"
    elif len(acts) == 1:
        subject = f"{acts[0]}: {_provisions(len(lines))} changed"
        in_force = [day for event in digest.events for day in event.in_force]
        if in_force:
            subject += f" (in force {max(in_force).isoformat()})"
    else:
        name = "Daily" if digest.kind == "daily" else "Weekly"
        subject = f"{name} digest: {_provisions(len(lines))} changed in {len(acts)} acts"
    return one_line(f"{PREFIX} {subject}")


def heartbeat_subject(heartbeat: Heartbeat) -> str:
    """The monthly note's subject, naming the quiet month."""
    return one_line(f"{PREFIX} Still watching: nothing changed in {heartbeat.month}")


def text_lines(line: ChangeLine, *, site_url: str) -> tuple[str, ...]:
    """One change as plain-text lines, the first a heading and the rest indented beneath it."""
    head = line.location if line.heading is None else f"{line.location}, {line.heading}"
    out = [f"* {head}: {line.change_type}"]
    if line.date_alert:
        out.append("  Date alert.")
    if line.dispute is not None:
        out.append(f"  {line.dispute} How disputes are decided: {site_url}{METHODOLOGY}")
    if line.dates is not None:
        out.append(f"  {line.dates}")
    out.append(f"  {line.applies}")
    for sentence in line.sentences:
        text = f"{sentence.prefix} {sentence.text}" if sentence.prefix else sentence.text
        out.append(f"  - {text}")
        out.extend(f"    {citation.label}: {citation.url}" for citation in sentence.citations)
    if line.unexplained is not None:
        out.append(f"  {line.unexplained}")
    out.append(f"  On the site: {line.link}")
    out.append(f"  Why: {line.why}")
    return tuple(out)


def _reason(name: str, cadence: str, why: tuple[str, ...]) -> str:
    reasons = "; ".join(why) if why else "it watches these provisions"
    return (
        f'your watchlist "{one_line(name)}" sends {cadence} email about what it watches: {reasons}.'
    )


def render_digest(
    digest: Digest, *, to: str, site_url: str, manage_url: str, unsubscribe_url: str
) -> OutgoingMail:
    """The email for `digest`, to `to`."""
    text, html = render_mail(
        "notify/digest",
        site_url=site_url,
        digest=digest,
        dated=[line for line in digest.lines if line.date_alert],
        texts=[
            [text_lines(line, site_url=site_url) for line in event.lines] for event in digest.events
        ],
        methodology=f"{site_url}{METHODOLOGY}",
        manage=manage_url,
        reason=_reason(digest.watchlist_name, digest.kind, digest.why),
        unsubscribe=unsubscribe_url,
    )
    return OutgoingMail(
        to=to,
        subject=digest_subject(digest),
        text=text,
        html=html,
        headers=list_headers(unsubscribe_url),
    )


def render_heartbeat(
    heartbeat: Heartbeat, *, to: str, site_url: str, manage_url: str, unsubscribe_url: str
) -> OutgoingMail:
    """The monthly "still watching" note, to `to`."""
    text, html = render_mail(
        "notify/heartbeat",
        site_url=site_url,
        heartbeat=heartbeat,
        manage=manage_url,
        reason=(
            f'your watchlist "{one_line(heartbeat.watchlist_name)}" has the monthly note on, '
            f"and nothing it watches changed in {heartbeat.month}."
        ),
        unsubscribe=unsubscribe_url,
    )
    return OutgoingMail(
        to=to,
        subject=heartbeat_subject(heartbeat),
        text=text,
        html=html,
        headers=list_headers(unsubscribe_url),
    )
