"""`notify`: judge every new event once, write what it owes each watchlist, mail instant ones.

Each event is handled in its own transaction: its announcement, its matches, and for an instant
watchlist the delivery, the assignment and the queued email commit together or not at all. The
announcement is written first, and a second run racing this one waits on its key and is then
refused, so it writes nothing for that event. Small transactions also keep this command from
holding locks the web process needs.

An eligible event whose page the catalogue does not name yet (`url` null) is left unjudged: an
email must never link a page that does not exist, and a run after the next site build judges it.
An ineligible one is judged at once, since it sends nothing.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db import Db, Tx
from emendrix_service.db import notify as store
from emendrix_service.db.enums import Cadence, DeliveryKind, OutboxPurpose
from emendrix_service.db.outbox import enqueue
from emendrix_service.notify.compose import build_digest
from emendrix_service.notify.eligibility import judge
from emendrix_service.notify.facts import ChangeFacts, EventFacts, ItemFacts, MatchKey, MatchRow
from emendrix_service.notify.matching import is_date_alert, match
from emendrix_service.notify.model import DigestKind
from emendrix_service.notify.render import render_digest, unsubscribe_url
from emendrix_service.settings import ServiceSettings

__all__ = ["NotifyCounts", "deliver", "notify", "owed"]

_log = logging.getLogger(__name__)


class NotifyCounts(BaseModel):
    """What one `notify` run did."""

    model_config = ConfigDict(frozen=True)

    announced: int = Field(default=0, description="Events judged by this run.")
    eligible: int = Field(default=0, description="Of those, events matched against watchlists.")
    deferred: int = Field(default=0, description="Events left unjudged: no page yet.")
    matches: int = Field(default=0, description="Matches written.")
    deliveries: int = Field(default=0, description="Instant emails queued.")
    failed: int = Field(default=0, description="Events whose transaction failed; retried next run.")


def owed(changes: list[ChangeFacts], items: list[ItemFacts]) -> list[MatchRow]:
    """One match per change and watchlist that any of the watchlist's items matches."""
    by_watchlist: dict[UUID, list[ItemFacts]] = defaultdict(list)
    for item in items:
        by_watchlist[item.watchlist_id].append(item)
    rows: list[MatchRow] = []
    for change in changes:
        key = MatchKey(
            event_key=change.event_key, location=change.location, occurrence=change.occurrence
        )
        for watchlist_id, own in by_watchlist.items():
            if match(change, own):
                alert = own[0].date_alerts and is_date_alert(change)
                rows.append(MatchRow(watchlist_id=watchlist_id, key=key, date_alert=alert))
    return rows


async def deliver(
    tx: Tx,
    settings: ServiceSettings,
    *,
    watchlist_id: UUID,
    kind: DigestKind,
    period_key: str,
    keys: list[MatchKey],
    now: datetime,
) -> bool:
    """Create the period's delivery, give it the matches at `keys` and queue its email.

    `False`, with nothing written, when the period already has its delivery or none of the
    matches is still unassigned; an empty delivery is removed again so the period is not spent.
    """
    watchlist = await store.watchlist_facts(tx, watchlist_id)
    if watchlist is None:
        return False
    delivery_id = await store.create_delivery(tx, watchlist_id, DeliveryKind(kind), period_key, now)
    if delivery_id is None:
        return False
    # Only a change the record still holds is assigned, so no email goes out with no lines.
    candidates = await store.digest_inputs(
        tx,
        watchlist,
        [MatchRow(watchlist_id=watchlist_id, key=key, date_alert=False) for key in keys],
    )
    held = {
        MatchKey(event_key=c.event_key, location=c.location, occurrence=c.occurrence)
        for c in candidates.changes
    }
    assigned = await store.assign(
        tx, delivery_id, watchlist_id, [key for key in keys if key in held]
    )
    if not assigned:
        await store.delete_delivery(tx, delivery_id)
        return False
    digest = build_digest(kind, await store.digest_inputs(tx, watchlist, assigned))
    unsubscribe = unsubscribe_url(settings.site_url, watchlist_id, secret=settings.secret_key)
    mail = render_digest(
        digest,
        to=watchlist.email,
        site_url=settings.site_url,
        manage_url=f"{settings.site_url}/account/",
        unsubscribe_url=unsubscribe,
    )
    outbox_id = await enqueue(
        tx,
        purpose=OutboxPurpose(kind),
        to=watchlist.email,
        mail=mail,
        user_id=watchlist.user_id,
        now=now,
    )
    await store.attach_outbox(tx, delivery_id, outbox_id)
    return True


async def _announce(
    tx: Tx,
    settings: ServiceSettings,
    event: EventFacts,
    *,
    live_since: date,
    bootstrap: bool,
    now: datetime,
) -> NotifyCounts | None:
    verdict = judge(event, live_since=live_since, bootstrap=bootstrap)
    if verdict.eligible and event.url is None:
        return NotifyCounts(deferred=1)
    if not await store.record_announcement(
        tx, event.event_key, verdict.eligible, verdict.stored(), now
    ):
        return None
    if not verdict.eligible:
        return NotifyCounts(announced=1)
    changes = await store.event_changes(tx, event.event_key)
    items = await store.active_items_for_act(tx, event.corpus, event.act_key)
    written = await store.insert_matches(tx, owed(changes, items), now)
    instant = {item.watchlist_id for item in items if item.cadence == Cadence.INSTANT}
    deliveries = 0
    for watchlist_id in sorted({row.watchlist_id for row in written} & instant):
        keys = [row.key for row in written if row.watchlist_id == watchlist_id]
        sent = await deliver(
            tx,
            settings,
            watchlist_id=watchlist_id,
            kind="instant",
            period_key=event.event_key,
            keys=keys,
            now=now,
        )
        deliveries += sent
    return NotifyCounts(announced=1, eligible=1, matches=len(written), deliveries=deliveries)


async def notify(db: Db, settings: ServiceSettings, now: datetime) -> NotifyCounts:
    """Judge every event not yet judged; match and mail the eligible ones."""
    if settings.live_since is None:
        raise ValueError("notify needs LIVE_SINCE")
    async with db.transaction() as tx:
        bootstrap = await store.announced_count(tx) == 0
        events = await store.unannounced_events(tx)
    totals = NotifyCounts()
    for event in events:
        try:
            async with db.transaction() as tx:
                counts = await _announce(
                    tx,
                    settings,
                    event,
                    live_since=settings.live_since,
                    bootstrap=bootstrap,
                    now=now,
                )
        except Exception as error:
            # One event that cannot be written must not hold back every event after it.
            _log.error("event %s was not announced: %s", event.event_key, type(error).__name__)
            counts = NotifyCounts(failed=1)
        if counts is not None:
            totals = NotifyCounts(
                announced=totals.announced + counts.announced,
                eligible=totals.eligible + counts.eligible,
                deferred=totals.deferred + counts.deferred,
                matches=totals.matches + counts.matches,
                deliveries=totals.deliveries + counts.deliveries,
                failed=totals.failed + counts.failed,
            )
    return totals
