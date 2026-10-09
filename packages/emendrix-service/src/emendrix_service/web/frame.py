"""The frame every account tab shares: the page head, the banners, and the tabs.

A tab's route builds one `AccountFrame` and renders through `frame_context`, which hands the
template everything `web/_account_head.html` names, so `StrictUndefined` never trips on a
route that forgot one. Everything here is pure: who reads, which list and what the notice says
are decided by the route and passed in.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EYEBROW",
    "PAUSED_NAMED",
    "PAUSED_ONE",
    "PAUSED_REST",
    "SUSPENDED_LEAD",
    "SUSPENDED_REST",
    "SUSPENDED_SENTENCE",
    "TABS",
    "AccountFrame",
    "PausedNote",
    "Tab",
    "TabLink",
    "frame_context",
    "tab_links",
]

Tab = Literal["watching", "delivery", "account"]

TABS: Final[tuple[tuple[Tab, str, str], ...]] = (
    ("watching", "Watching", "/account/"),
    ("delivery", "Delivery", "/account/delivery"),
    ("account", "Account", "/account/settings"),
)
"""Each tab's key, label and path, in the order the tabs stand."""

_LISTED: Final[frozenset[Tab]] = frozenset({"watching", "delivery"})
"""The tabs that show one list at a time, so carry the chosen list in their links."""

EYEBROW: Final = "Your account"

SUSPENDED_LEAD: Final = "No email is reaching {email}."
SUSPENDED_REST: Final = (
    "Mail to it was refused or marked as unwanted, so sending has stopped and nothing can be "
    "changed. Everything you watch is kept."
)
SUSPENDED_SENTENCE: Final = f"{SUSPENDED_LEAD} {SUSPENDED_REST}"
"""The suspended banner; the banner sets its lead in bold."""

PAUSED_ONE: Final = "Email is paused."
PAUSED_NAMED: Final = "Email for {name} is paused."
PAUSED_REST: Final = "Nothing is sent until you resume. Your feed keeps working."

_FROZEN = ConfigDict(frozen=True)


class PausedNote(BaseModel):
    """One paused list, as its banner names it."""

    model_config = _FROZEN

    name: str | None = Field(description="The list's name; None when the reader has one list.")
    resume_action: str = Field(description="Where the banner's resume form posts.")

    @property
    def lead(self) -> str:
        """The banner's first sentence, which says which email is paused."""
        return PAUSED_ONE if self.name is None else PAUSED_NAMED.format(name=self.name)

    @property
    def rest(self) -> str:
        """The banner after its first sentence."""
        return PAUSED_REST


class AccountFrame(BaseModel):
    """What the head of one account tab shows."""

    model_config = _FROZEN

    tab: Tab = Field(description="The tab this page is.")
    heading: str = Field(description="The page's h1.")
    lede: str = Field(description="The sentence under the h1.")
    email: str = Field(description="The reader's address, for the suspended banner.")
    item_count: int = Field(description="Watched items over all lists, shown on the Watching tab.")
    list_query: str = Field(
        description="'' or '?list=<uuid>', appended to the Watching and Delivery tab links."
    )
    suspended: bool = Field(description="Whether mail to the reader's address has stopped.")
    paused: tuple[PausedNote, ...] = Field(description="One note per paused list.")
    notice: str | None = Field(description="The notice to show, already looked up from its code.")
    eyebrow: str = Field(default=EYEBROW, description="The line above the h1.")

    @property
    def suspended_lead(self) -> str:
        """The suspended banner's first sentence, which names the address."""
        return SUSPENDED_LEAD.format(email=self.email)

    @property
    def suspended_rest(self) -> str:
        """The suspended banner after its first sentence."""
        return SUSPENDED_REST


class TabLink(BaseModel):
    """One tab as the navigation draws it."""

    model_config = _FROZEN

    label: str = Field(description="The tab's label.")
    href: str = Field(description="Where the tab links.")
    current: bool = Field(description="Whether this page is the tab.")
    count: int | None = Field(description="The number beside the label, or None for none.")


def tab_links(frame: AccountFrame) -> tuple[TabLink, ...]:
    """The three tabs for `frame`, in order."""
    return tuple(
        TabLink(
            label=label,
            href=path + frame.list_query if key in _LISTED else path,
            current=key == frame.tab,
            count=frame.item_count if key == "watching" else None,
        )
        for key, label, path in TABS
    )


def frame_context(frame: AccountFrame) -> dict[str, object]:
    """The template variables `web/_account_head.html` reads."""
    return {"frame": frame, "tabs": tab_links(frame), "frame_eyebrow": frame.eyebrow}
