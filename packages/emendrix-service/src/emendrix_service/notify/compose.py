"""Stored facts into the lines of an email, by rules written here and nowhere else.

The wording rules hold the record's register. A date the text gained or lost is "a date in the
text changed", never a deadline; a date is called an application date only when `applies_from`
holds one read from the act's own application article, and otherwise the line says what the
date means was not read. A disputed line names which source saw what, in the sentence the site
prints beside the same change. No line says whether a change affects the reader.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date

from emendrix_record.locations import human
from emendrix_record.reasons import REASON_SENTENCES
from emendrix_service.notify.facts import (
    ChangeFacts,
    DigestInputs,
    EventFacts,
    ItemFacts,
    MatchKey,
    StoredSentence,
)
from emendrix_service.notify.matching import best, match, phrase
from emendrix_service.notify.model import (
    ChangeLine,
    Digest,
    DigestKind,
    EventBlock,
    SentenceLine,
)

__all__ = [
    "FALLBACK",
    "NOTE_PREFIX",
    "REMOVED_ITEM",
    "applies_phrase",
    "build_digest",
    "change_line",
    "dates_phrase",
    "dispute_phrase",
    "location_order",
]

FALLBACK = (
    "The citation gate quoted the provision here, because the model's own sentence did not "
    "resolve; the quotation is on the page."
)
"""Said in place of a sentence the gate wrote: it quotes provision text, which an email never
carries, so only its kind and its citations are shown and the page holds the words."""

NOTE_PREFIX = "Applicability note:"

REMOVED_ITEM = "a watch item since removed matched it when it was recorded"
"""The reason shown for a match no current item explains any more."""

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
_ROLES = {"AR": 0, "AN": 1}
_NUMBER = re.compile(r"^(\d+)(.*)$")


def _token_order(token: str) -> tuple[int, int, str]:
    number = _NUMBER.match(token)
    if number:
        return (0, int(number.group(1)), number.group(2))
    if token and set(token) <= set(_ROMAN):
        values = [_ROMAN[char] for char in token]
        total = sum(
            -v if v < after else v for v, after in zip(values, [*values[1:], 0], strict=True)
        )
        return (0, total, "")
    return (1, 0, token)


def location_order(location: str) -> tuple[tuple[int, int, str], ...]:
    """A sort key putting `AR 2` before `AR 10`, articles before annexes, `AN IV` before `AN V`."""
    tokens = location.split(" ")
    role = (_ROLES.get(tokens[0], 2), 0, tokens[0])
    return (role, *(_token_order(token) for token in tokens[1:]))


def _read_date(applies_from: str) -> date | None:
    try:
        return date.fromisoformat(applies_from)
    except ValueError:
        return None


def applies_phrase(applies_from: str) -> str:
    """What the record read of the application date, as stored in `applies_from`."""
    read = _read_date(applies_from)
    if read is not None:
        return f"application date: {read.isoformat()}, read from the act's own application article"
    if applies_from == "unchanged":
        return "application date: not moved by this change"
    return "the application date was not read"


def dates_phrase(change: ChangeFacts) -> str | None:
    """`a date in the text changed` with the dates removed and added, or `None` without any."""
    if not change.dates_removed and not change.dates_added:
        return None
    parts = ["a date in the text changed"]
    if change.dates_removed:
        parts.append("dates removed: " + ", ".join(d.isoformat() for d in change.dates_removed))
    if change.dates_added:
        parts.append("dates added: " + ", ".join(d.isoformat() for d in change.dates_added))
    if _read_date(change.applies_from) is None:
        parts.append("what these dates mean was not read")
    return "; ".join(parts)


def dispute_phrase(change: ChangeFacts) -> str | None:
    """`disputed: <the reason's sentence>`, or `None` for a change the signals agree on."""
    if not change.disputed:
        return None
    sentence = REASON_SENTENCES.get(change.dispute_reason or "")
    if sentence is None:
        return "disputed (no reason recorded)"
    return f"disputed: {sentence}"


def _sentence(stored: StoredSentence) -> SentenceLine:
    if stored.fallback:
        return SentenceLine(text=FALLBACK, citations=stored.citations)
    prefix = NOTE_PREFIX if stored.note else ""
    return SentenceLine(text=stored.text, prefix=prefix, citations=stored.citations)


def change_line(change: ChangeFacts, event: EventFacts, act_label: str, why: str) -> ChangeLine:
    """The line one watched change gets, linked to its block on the event page."""
    sentences = tuple(_sentence(stored) for stored in change.sentences)
    has_prose = any(not stored.note for stored in change.sentences)
    unexplained = None if has_prose else f"no explanation: {change.unexplained or 'none stored'}"
    return ChangeLine(
        location=human(change.location),
        title=f"{act_label} {human(change.location)}",
        heading=change.heading,
        change_type=change.change_type.lower(),
        disputed=change.disputed,
        dispute=dispute_phrase(change),
        dates_removed=change.dates_removed,
        dates_added=change.dates_added,
        dates=dates_phrase(change),
        applies=applies_phrase(change.applies_from),
        sentences=sentences,
        unexplained=unexplained,
        link=f"{event.url or ''}#{change.anchor}",
        why=why,
    )


def _why(change: ChangeFacts, items: Sequence[ItemFacts], label: str) -> str:
    hit = best(match(change, items))
    if hit is None:
        return REMOVED_ITEM
    item = next(item for item in items if item.item_id == hit.item_id)
    return phrase(hit, item, change, label)


def _distinct(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def build_digest(kind: DigestKind, inputs: DigestInputs) -> Digest:
    """The email for `inputs`: events oldest first, each event's lines in location order."""
    blocks: list[EventBlock] = []
    alerts = 0
    events = sorted(inputs.events, key=lambda e: (e.detected_on, e.corpus, e.act_key, e.event_key))
    for event in events:
        label = inputs.labels.get(f"{event.corpus}/{event.act_key}", event.act_key)
        items = [i for i in inputs.items if (i.corpus, i.act_key) == (event.corpus, event.act_key)]
        changes = sorted(
            (c for c in inputs.changes if c.event_key == event.event_key),
            key=lambda c: (location_order(c.location), c.occurrence),
        )
        lines: list[ChangeLine] = []
        for change in changes:
            key = MatchKey(
                event_key=change.event_key, location=change.location, occurrence=change.occurrence
            )
            line = change_line(change, event, label, _why(change, items, label))
            if key in inputs.date_alerts:
                line = line.model_copy(update={"date_alert": True})
                alerts += 1
            lines.append(line)
        if not lines:
            continue
        blocks.append(
            EventBlock(
                act_label=label,
                from_version=event.from_version,
                to_version=event.to_version,
                in_force=event.in_force,
                amending_acts=_distinct(a for c in changes for a in c.amending_acts),
                url=event.url or "",
                lines=tuple(lines),
            )
        )
    why = _distinct(line.why for block in blocks for line in block.lines)
    return Digest(
        kind=kind,
        watchlist_name=inputs.watchlist.name,
        events=tuple(blocks),
        date_alert_count=alerts,
        why=why,
    )
