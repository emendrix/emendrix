"""The three ways to take the record away as data, worded once and rendered from here.

The JSON files, the MCP server and the CI workflow are each documented in full on `/api/`, and
every other page only points there. The home page's block, the About page's section and the
index at the top of `/api/` itself all render `take_away`, so no door can be worded two ways;
the footer and the not-found page link the page itself rather than restating the three.

The block is a door, not an advertisement, and its form follows from that:

- **A rule, not a surface.** Each door sits under a 2px rule in the text colour, with no fill,
  no radius and no tint. The site gives each surface one meaning: the raised panel with a rule
  in the act colour is a measured figure, and the tinted notice with a drawn `!` is the
  disclaimer. A block that borrowed either would read as one of them. Drawing it in borders
  alone also means no medium has to undo it: print has no tint to strip, and forced colours
  repaint a border in the system's text colour, so the block needs no rule in `media`.
- **Three columns, then one.** The list is a grid of columns at least 14rem wide, so a wide
  screen shows the three doors side by side, as parallel choices rather than steps, and a phone
  stacks them; nothing scrolls sideways at 320px. The doors are not numbered, because they are
  not a sequence.
- **A name, then a purpose.** The name is the link, set in the explanation size at the heading
  weight, and one line under it says in plain words what a reader gets, in the meta size and the
  muted colour. No arrow follows the name: a link-coloured, underlined name under its own rule
  already says it is a way somewhere, and on `/api/` the doors jump down the page, which an
  arrow pointing onward would misstate.

The block is a `<section>` named by its `<h2>`, so a screen reader announces a region with
three items. It reads nothing from the build: no figure, no date, no address but a relative
one, so it is the same bytes on every build. `here` renders the index on `/api/` itself, where
each door is a fragment on the same page and the first one lands on the layout table rather
than at the top of the page the reader is already reading.
"""

from __future__ import annotations

from typing import Final, NamedTuple

from emendrix.site_.markup import Html, escape, join

__all__ = ["DOORS", "Door", "take_away"]


class Door(NamedTuple):
    """One way to take the record away: where it opens, its name and what it is for."""

    href: str
    """Where the door opens, relative to the site root."""
    anchor: str
    """The id on `/api/` the door lands on from inside that page."""
    name: str
    purpose: str


DOORS: Final[tuple[Door, ...]] = (
    Door(
        "api/",
        "layout",
        "The JSON API",
        "Every change as JSON files: an index per act, one file per version, fetched with curl.",
    ),
    Door(
        "api/#mcp",
        "mcp",
        "The MCP server",
        "Ask a model client about the record, read-only, with no key.",
    ),
    Door(
        "api/#watch-in-ci",
        "watch-in-ci",
        "Watch from CI",
        "Open an issue when a provision you depend on changes.",
    ),
)
"""The doors in the order every rendering prints them: the files, then the two uses of them."""

_HEADING_ID: Final = "take-away"


def take_away(root: str, *, heading: str, note: str = "", here: bool = False) -> Html:
    """The doors as a named region: its heading, an optional sentence, then one item per door.

    `root` is the page's climb back to the site root. `note` is one sentence under the heading,
    for a page whose section needs to say why the doors are there. With `here` the links are
    fragments on the page itself, for the index at the top of `/api/`.
    """
    items = (
        Html(
            f'<li><a href="{escape("#" + door.anchor if here else root + door.href)}">'
            f"{escape(door.name)}</a> <span>{escape(door.purpose)}</span></li>"
        )
        for door in DOORS
    )
    return join(
        (
            Html(f'<section class="doors" aria-labelledby="{_HEADING_ID}">'),
            Html(f'<h2 id="{_HEADING_ID}">{escape(heading)}</h2>'),
            *((Html(f"<p>{escape(note)}</p>"),) if note else ()),
            Html("<ul>"),
            *items,
            Html("</ul>"),
            Html("</section>"),
        ),
        "\n",
    )
