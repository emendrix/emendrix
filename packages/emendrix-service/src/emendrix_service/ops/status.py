"""The status block: one plain-text page of counts an operator reads each morning.

The render is pure: it is handed the counts and the instant they were read at, and every line
names what it counts and over which window. It carries no address and no user id, because the
counts it is handed carry none, and the same text goes to the terminal and to the operator's
inbox. The email is the daily canary for the transport: a morning without it says the relay or
the scheduler stopped, which no count inside it can say.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service import DISCLAIMER
from emendrix_service.db.enums import DeliveryKind, MailEventKind
from emendrix_service.db.ops import (
    ActItems,
    Announcements,
    LastLoad,
    MailHealth,
    OutboxHealth,
    Population,
)
from emendrix_service.mail.message import OutgoingMail
from emendrix_service.notify.render import PREFIX

__all__ = ["DAY", "WEEK", "StatusReport", "operator_mail", "render"]

DAY: Final = timedelta(hours=24)
WEEK: Final = timedelta(days=7)

EVENT_LABELS: Final = {
    MailEventKind.HARD_BOUNCE: "hard bounces",
    MailEventKind.SOFT_BOUNCE: "soft bounces",
    MailEventKind.COMPLAINT: "complaints",
    MailEventKind.DELIVERED: "delivered",
}


class StatusReport(BaseModel):
    """Every count the block shows, read at one instant."""

    model_config = ConfigDict(frozen=True)

    at: datetime = Field(description="When the counts were read.")
    load: LastLoad | None = Field(description="The newest load; null before the first.")
    announcements: Announcements = Field(description="Events judged in the last 24 hours.")
    deliveries: dict[DeliveryKind, int] = Field(description="Deliveries in the last 24 hours.")
    outbox: OutboxHealth = Field(description="The queue now; failures in the last 24 hours.")
    mail: MailHealth = Field(description="Provider events in 7 days; suppressions now.")
    population: Population = Field(description="Accounts and watchlists.")
    acts: list[ActItems] = Field(description="Watch items per act.")


def _when(at: datetime) -> str:
    return at.strftime("%Y-%m-%d %H:%M UTC")


def _age(span: timedelta) -> str:
    minutes = max(0, int(span.total_seconds() // 60))
    if minutes < 120:
        return f"{minutes} min"
    return f"{minutes // 60} h"


def _counts(values: dict[str, int]) -> str:
    return ", ".join(f"{name.replace('_', ' ')} {count}" for name, count in values.items())


def _load_lines(load: LastLoad | None) -> list[str]:
    if load is None:
        return ["Last load: none recorded"]
    finished = f"finished {_when(load.finished_at)}" if load.finished_at else "did not finish"
    return [
        f"Last load: started {_when(load.started_at)}, {finished}",
        f"  root index digest {load.root_sha256[:16]}",
        f"  events upserted {load.upserted}, removed {load.removed}, skipped {load.skipped}",
    ]


def render(report: StatusReport) -> str:
    """The block as plain text, ending with the disclaimer."""
    outbox = report.outbox
    oldest = (
        f"oldest waiting {_age(report.at - outbox.oldest_queued_at)}"
        if outbox.oldest_queued_at
        else "none waiting"
    )
    people = report.population
    lines = [
        f"Emendrix account service status at {_when(report.at)}",
        "",
        *_load_lines(report.load),
        "Announcements, last 24 h: "
        f"eligible {report.announcements.eligible}, "
        f"not eligible {report.announcements.not_eligible}",
        "Deliveries, last 24 h: " + _counts({k.value: v for k, v in report.deliveries.items()}),
        f"Outbox: queued {outbox.queued} ({oldest}); failed: {outbox.failed_since} written in "
        f"the last 24 h, {outbox.failed_held} held in all",
        "Mail events, last 7 days: "
        + _counts({EVENT_LABELS[k]: v for k, v in report.mail.events.items()}),
        f"Suppressed addresses: {sum(report.mail.suppressions.values())} ("
        + _counts({k.value: v for k, v in report.mail.suppressions.items()})
        + ")",
        f"Accounts: {sum(people.users.values())} ("
        + _counts({k.value: v for k, v in people.users.items()})
        + ")",
        f"Watchlists: {sum(people.watchlists.values())} by cadence ("
        + _counts({k.value: v for k, v in people.watchlists.items()})
        + f"), paused {people.paused}",
        "Watch items per act:" + ("" if report.acts else " none"),
    ]
    for act in report.acts:
        total = sum(act.items.values())
        detail = _counts({k.value: v for k, v in act.items.items()})
        lines.append(f"  {act.corpus}/{act.act_key}: {total} ({detail})")
    lines += ["", "--", DISCLAIMER]
    return "\n".join(lines) + "\n"


def operator_mail(text: str, *, to: str, at: datetime) -> OutgoingMail:
    """The block as an email to the operator, its HTML part the same text preformatted."""
    return OutgoingMail(
        to=to,
        subject=f"{PREFIX} Status at {_when(at)}",
        text=text,
        html=f"<pre>{html.escape(text)}</pre>\n",
    )
