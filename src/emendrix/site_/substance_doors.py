"""The sentences that lead a reader to the substance pages, each worded once for every page.

A door says what is behind it and what is not: a page exists where an entry in the record prints
the number, and nothing about a number without one, because many entries name a group and print
none. The home page, the act pages of acts with a register, the event pages above their first
entry table, the not-found page, the API page and `/llms.txt` each print one of these, and none
restates it in other words.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.markup import Html, escape
from emendrix.site_.urls import substance_list_href, substances_href

__all__ = [
    "API_DOOR",
    "EVENT_DOOR",
    "LLMS_DOOR",
    "act_door",
    "home_door",
    "not_found_door",
]

_HOME: Final = (
    "Look up a CAS or EC number",
    ": every entry in the chemicals tables this record holds that prints it, and every change "
    "to that entry.",
)
_ACT: Final = (
    "Find an entry of this act by CAS or EC number",
    ": the row as printed, and every change to it the record holds.",
)

EVENT_DOOR: Final = (
    "Each CAS and EC number in these tables links to its own page, which lists every entry that "
    "prints it across the acts this record holds."
)
"""Above the first entry table of an event page."""

_NOT_FOUND: Final = (
    "A substance has a page only where an entry in the record prints its CAS or EC number, so a "
    "missing page is not a statement about the law; try the lookup on ",
    "the substances page",
    ".",
)

API_DOOR: Final = (
    "`/api/v1/substances.json` lists every CAS and EC number an entry in the record prints, and "
    "`/api/v1/substances/<scheme>-<value>.json` gives each one's entries and changes as data."
)
"""Under the API page's three ways in; its two paths are rows of the layout table too."""

LLMS_DOOR: Final = (
    "every CAS and EC number an entry in the record prints, with its page and its file; a "
    "number missing here is printed by no entry, which says nothing about the law."
)
"""The note of `/llms.txt`'s line linking the list."""


def _door(href: str, lead: str, rest: str) -> Html:
    return Html(f'<p class="lookup"><a href="{escape(href)}">{escape(lead)}</a>{escape(rest)}</p>')


def home_door(root: str) -> Html:
    """The home page's door, after the measured claim and before the record's other doors."""
    return _door(f"{root}{substances_href()}", *_HOME)


def act_door(root: str, act_slug: str) -> Html:
    """An act page's door to its own list of numbers, beside the follow links."""
    return _door(f"{root}{substance_list_href(act_slug)}", *_ACT)


def not_found_door(root: str) -> Html:
    """The not-found page's sentence, after the hint about act pages."""
    lead, link, rest = _NOT_FOUND
    href = escape(f"{root}{substances_href()}#lookup")
    return Html(f'<p>{escape(lead)}<a href="{href}">{escape(link)}</a>{escape(rest)}</p>')
