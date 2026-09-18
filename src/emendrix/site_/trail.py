"""Where a page sits in the site: one trail per page type, read by two renderings.

A page's trail is printed twice, once as the breadcrumb a reader sees at the top of the page
and once as the `BreadcrumbList` a search engine prints under a result. Built apart, the two
would drift the first time one of them was reworded, and a reader would follow a trail the
machine-readable copy never stated. So the rungs are built here, once, as names and
site-root-relative paths, and `identity` turns them into links while `seo` turns them into
absolute addresses. Neither consumer names a rung itself.

Every trail is the URL's own: a rung exists only where the address has a directory, so no page
invents a level its path does not carry. The last rung is the page itself. The names are the
reader's words, a version by its date rather than by its pair of consolidated-version codes,
and the act by its short label, because a breadcrumb under a search result has no room for a
regulation's long form.

The module holds names and paths only. It knows nothing of HTML or of schema.org, which is
why it imports neither consumer.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct
from emendrix.site_.clocks import version_name
from emendrix.site_.head import SITE_NAME
from emendrix.site_.inputs import ActSite
from emendrix.site_.urls import (
    act_href,
    amendment_href,
    amendments_href,
    event_href,
    provision_href,
)

__all__ = [
    "ACTS_ROSTER",
    "AMENDING_ROSTER",
    "Rung",
    "act_trail",
    "amending_trail",
    "page_trail",
    "provision_trail",
    "version_trail",
]

ACTS_ROSTER: Final = "All watched acts"
"""The acts roster's rung, and that page's own heading."""

AMENDING_ROSTER: Final = "Amending acts"
"""The amending-acts roster's rung, and that page's own heading and header-bar link."""

_ACTS_PATH: Final = "acts/"
"""The roster's own path, which is also the directory `act_href` puts every act page under.

`test_seo.py` checks the breadcrumb's middle rung against a file the build wrote, so the
roster and the rung cannot drift apart silently.
"""


class Rung(BaseModel):
    """One step of a trail: what the page is called and where it lives."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="The page's name in the reader's words.")
    path: str = Field(description="Site-root-relative, no leading slash; '' is the home page.")


_HOME: Final = Rung(name=SITE_NAME, path="")


def page_trail(name: str, path: str) -> tuple[Rung, ...]:
    """Two rungs, home and the page: the rosters and the pages about the site."""
    return (_HOME, Rung(name=name, path=path))


def act_trail(act: ActSite) -> tuple[Rung, ...]:
    """Home, the acts roster, the act."""
    return (
        *page_trail(ACTS_ROSTER, _ACTS_PATH),
        Rung(name=act.label, path=act_href(act.slug)),
    )


def version_trail(act: ActSite, entry: ChangelogEntry) -> tuple[Rung, ...]:
    """The act's trail, then the version by the name its heading gives it."""
    return (
        *act_trail(act),
        Rung(name=version_name(entry), path=event_href(act.slug, entry.key)),
    )


def provision_trail(act: ActSite, location: ProvisionLocation) -> tuple[Rung, ...]:
    """The act's trail, then the provision in its human form."""
    return (
        *act_trail(act),
        Rung(name=location.human, path=provision_href(act.slug, location.canonical)),
    )


def amending_trail(instrument: AmendingAct) -> tuple[Rung, ...]:
    """Home, the amending-acts roster, the amending act by its short name."""
    return (
        *page_trail(AMENDING_ROSTER, amendments_href()),
        Rung(name=instrument.short, path=amendment_href(instrument.key)),
    )
