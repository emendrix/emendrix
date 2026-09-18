"""A link that leaves the site, said the same way wherever one is printed.

Every internal link on the site climbs the tree relatively and stays on it; a handful point at
EUR-Lex, the official home of the texts this site compares. A reader who follows one leaves the
site, and should know that before the page changes under them, so the link carries a cue drawn
by the sheet (`.ext::after`) and, for a screen reader, the same fact in words. One function, so
no two outbound links can announce themselves differently.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.markup import Html, escape

__all__ = ["external"]

_SPOKEN: Final = " (external, EUR-Lex)"
"""What a screen reader hears after the link's words. The cue the sheet draws is not read out,
so the words carry it; every outbound link this site prints goes to EUR-Lex."""


def external(href: str, words: str) -> Html:
    """`words`, linking `href` off the site, marked for the eye and for the ear."""
    return Html(
        f'<a class="ext" href="{escape(href)}">{escape(words)}'
        f'<span class="visually-hidden">{escape(_SPOKEN)}</span></a>'
    )
