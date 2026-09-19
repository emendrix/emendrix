"""An official title cut for a roster row so that what survives is what the act is about.

A roster row prints an official title beside the act's own name, number and identifier, so the
title's opening clause, `Commission Implementing Regulation (EU) 2024/2512 of 18 September 2024`,
repeats what the row already says. Cutting from the start, as the changelog's `short_title`
does, then spends the whole budget on that clause and on the acts the instrument amends, and
stops before the subject: on 2026-09-19 all 140 recorded amending-act titles were over the cap,
and 80 of them state their subject in an `as regards …` or `with regard to …` tail.

`subject_cut` drops the opening clause the row repeats, and where the rest is still too long
keeps its head and that tail. Every elision is marked with `[…]`, the marker `short_title`
uses, and no character that is kept is changed: a no-break space stays one, because verbatim
means verbatim. A title the opening rule does not recognise is cut exactly as `short_title` cuts
it, so the rule can only ever keep more of the subject than the changelog does, never invent a
shape. `short_title` itself is left alone because it renders the committed public changelogs,
and a change there would move published output.
"""

from __future__ import annotations

import re
from typing import Final

from emendrix.output.markdown import TITLE_CAP, short_title

__all__ = ["subject_cut"]

MARK: Final = "[…]"

_S = r"[\s\xa0]+"
_OPENING: Final = re.compile(
    rf"^(?:(?:Commission|Council){_S})?(?:(?:Delegated|Implementing){_S})?"
    rf"(?:Regulation|Directive|Decision){_S}(?:\((?:EU|EC|EEC|Euratom)\){_S})?(?:No{_S})?"
    rf"\d+/\d+(?:/\w+)?{_S}of{_S}"
    rf"(?:the{_S}European{_S}Parliament{_S}(?:and{_S})?of{_S}the{_S}Council{_S}(?:of{_S})?)?"
    rf"\d{{1,2}}{_S}\w+{_S}\d{{4}}[\s\xa0,]*"
)
"""The number-and-date clause an official title opens with, in the forms the corpus records:
`Regulation (EU) No 1169/2011 of the European Parliament and of the Council of 25 October
2011`, a Commission or Council act with its `Delegated` or `Implementing`, and a Directive
numbered `2014/17/EU` without the parenthesis."""

_TAIL: Final = re.compile(rf"{_S}(as{_S}regards|with{_S}regard{_S}to){_S}")
"""Where an amending act's title usually states its subject, after the acts it amends."""

_MIN_HEAD: Final = 20
"""A head shorter than this names no act and only costs the reader a second marker."""


def _words(text: str, room: int) -> str:
    """The start of `text` in at most `room` characters, ending on a whole word, unmarked."""
    if len(text) <= room:
        return text
    return text[:room].rsplit(" ", 1)[0].rstrip(" ,;")


def _cut(text: str, room: int) -> str:
    """`text` in at most `room` characters, cut on a whole word and marked when it is cut."""
    if len(text) <= room:
        return text
    return f"{_words(text, room - len(MARK) - 1)} {MARK}"


def subject_cut(title: str, cap: int = TITLE_CAP) -> str:
    """`title` in about `cap` characters, keeping its subject; every elision marked `[…]`.

    Returns the title whole when it fits, `short_title(title)` when the opening clause is not
    recognised, and otherwise the rest after that clause: whole, or its head and its
    `as regards` / `with regard to` tail, or that tail alone when too little room is left for a
    head worth reading, or its head alone when it has no such tail, each shortening marked.
    """
    if len(title) <= cap:
        return title
    opening = _OPENING.match(title)
    rest = title[opening.end() :] if opening else ""
    if not rest:
        return short_title(title)
    lead = f"{MARK} "
    if len(lead) + len(rest) <= cap:
        return lead + rest
    phrase = _TAIL.search(rest)
    if phrase is None:
        return lead + _cut(rest, cap - len(lead))
    middle = f" {MARK} "
    subject = rest[phrase.start(1) :]
    tail = _cut(subject, cap - len(lead) - len(middle) - _MIN_HEAD)
    room = cap - len(lead) - len(middle) - len(tail)
    before = rest[: phrase.start()]
    if len(before) <= room:
        return lead + _cut(rest, cap - len(lead))
    head = _words(before, room)
    if len(head) < _MIN_HEAD:
        return lead + _cut(subject, cap - len(lead))
    return lead + head + middle + tail
