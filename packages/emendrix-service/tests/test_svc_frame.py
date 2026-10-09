"""The account frame: the header slot, the tabs, the banners and the list switcher, no database."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi import Request
from markupsafe import Markup

from emendrix_service.db.enums import Cadence, ItemKind
from emendrix_service.db.watchlists import WatchItemView, WatchlistView
from emendrix_service.settings import ServiceSettings
from emendrix_service.watch.lists import list_choices, list_query, paused_notes, pick_list
from emendrix_service.web.frame import (
    SUSPENDED_SENTENCE,
    AccountFrame,
    PausedNote,
    frame_context,
    tab_links,
)
from emendrix_service.web.identity import account_slot
from emendrix_service.web.templating import environment
from tests.conftest import settings_values

FIRST = UUID("00000000-0000-4000-8000-000000000001")
SECOND = UUID("00000000-0000-4000-8000-000000000002")
STRANGER = UUID("00000000-0000-4000-8000-000000000009")


def watchlist(id: UUID, name: str, *, items: int = 0, paused: bool = False) -> WatchlistView:
    return WatchlistView(
        id=id,
        name=name,
        cadence=Cadence.WEEKLY,
        date_alerts=True,
        heartbeat=False,
        paused=paused,
        has_feed=False,
        items=tuple(
            WatchItemView(
                id=UUID(int=index + 100),
                kind=ItemKind.ACT,
                corpus="eu",
                act_key=f"3202{index}R0001",
                location=None,
            )
            for index in range(items)
        ),
    )


def frame(**changes: object) -> AccountFrame:
    values: dict[str, object] = {
        "tab": "watching",
        "heading": "What you watch",
        "lede": "A lede.",
        "email": "reader@example.org",
        "item_count": 3,
        "list_query": "",
        "suspended": False,
        "paused": (),
        "notice": None,
    }
    return AccountFrame.model_validate({**values, **changes})


def fake_request() -> Request:
    settings = ServiceSettings.model_validate(settings_values())
    app = SimpleNamespace(state=SimpleNamespace(settings=settings))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app})


def render(template: str, **context: object) -> str:
    return environment().get_template(template).render(request=fake_request(), **context)


# --- the header slot ---------------------------------------------------------------------------


def test_svc_frame_slot_signed_out_is_the_plain_link() -> None:
    assert account_slot(None) == Markup('<a class="account" href="/account/">Account</a>')


def test_svc_frame_slot_signed_in_names_the_reader() -> None:
    assert account_slot("reader@example.org") == Markup(
        '<a class="account account--in" href="/account/"'
        ' aria-label="Your account, signed in as reader@example.org">'
        '<span class="account-initial" aria-hidden="true">R</span>'
        '<span class="account-email">reader@example.org</span></a>'
    )


def test_svc_frame_slot_escapes_the_address() -> None:
    slot = str(account_slot("a<b>@example.org"))
    assert "<b>" not in slot
    assert slot.count("a&lt;b&gt;@example.org") == 2
    assert '<span class="account-initial" aria-hidden="true">A</span>' in slot


def test_svc_frame_slot_marks_the_account_tab_current() -> None:
    assert 'aria-current="page"' in account_slot("reader@example.org", current=True)
    assert "aria-current" not in account_slot("reader@example.org")


# --- the tabs ----------------------------------------------------------------------------------


def test_svc_frame_tabs_without_a_list_query() -> None:
    tabs = tab_links(frame(tab="delivery"))
    assert [(t.label, t.href, t.current, t.count) for t in tabs] == [
        ("Watching", "/account/", False, 3),
        ("Delivery", "/account/delivery", True, None),
        ("Account", "/account/settings", False, None),
    ]


def test_svc_frame_tabs_carry_the_list_query_where_a_list_is_shown() -> None:
    query = f"?list={SECOND}"
    tabs = tab_links(frame(tab="account", list_query=query))
    assert [t.href for t in tabs] == [
        f"/account/{query}",
        f"/account/delivery{query}",
        "/account/settings",
    ]
    assert [t.current for t in tabs] == [False, False, True]


# --- the lists ---------------------------------------------------------------------------------


def test_svc_frame_pick_list() -> None:
    lists = [watchlist(FIRST, "Medical devices"), watchlist(SECOND, "AI compliance")]
    assert pick_list(lists, str(SECOND)) == lists[1]
    assert pick_list(lists, str(STRANGER)) == lists[0]
    assert pick_list(lists, "not-a-uuid") == lists[0]
    assert pick_list(lists, "") == lists[0]
    assert pick_list([], str(FIRST)) is None


def test_svc_frame_list_choices_and_query() -> None:
    one = [watchlist(FIRST, "Mine", items=2)]
    two = [*one, watchlist(SECOND, "Theirs", items=1)]
    assert list_query(one, FIRST) == ""
    assert list_query(two, SECOND) == f"?list={SECOND}"
    choices = list_choices(two, SECOND)
    assert [(c.name, c.item_count, c.current) for c in choices] == [
        ("Mine", 2, False),
        ("Theirs", 1, True),
    ]


def test_svc_frame_paused_notes_name_a_list_only_among_several() -> None:
    alone = paused_notes([watchlist(FIRST, "Mine", paused=True)])
    assert alone == (PausedNote(name=None, resume_action=f"/account/watchlists/{FIRST}/resume"),)
    assert alone[0].lead == "Email is paused."
    several = paused_notes([watchlist(FIRST, "Mine"), watchlist(SECOND, "Theirs", paused=True)])
    assert several == (
        PausedNote(name="Theirs", resume_action=f"/account/watchlists/{SECOND}/resume"),
    )
    assert several[0].lead == "Email for Theirs is paused."


# --- the templates -----------------------------------------------------------------------------


def test_svc_frame_head_renders_in_order() -> None:
    note = PausedNote(name=None, resume_action=f"/account/watchlists/{FIRST}/resume")
    page = render(
        "web/_account_head.html", **frame_context(frame(paused=(note,), notice="List created."))
    )
    order = [
        '<p class="account-eyebrow">Your account</p>',
        "<h1>What you watch</h1>",
        '<p class="account-lede">A lede.</p>',
        '<div class="banner banner--info" role="status">',
        "<strong>Email is paused.</strong> Nothing is sent until you resume.",
        f'action="/account/watchlists/{FIRST}/resume"',
        'name="csrf"',
        '<input type="hidden" name="back" value="watching">',
        '<button type="submit" class="secondary">Resume email</button>',
        '<div class="banner banner--ok" role="status">',
        "<p>List created.</p>",
        '<nav class="tabs" aria-label="Account">',
        '<a href="/account/" aria-current="page">Watching <span class="count">3</span>',
        '<a href="/account/delivery">Delivery</a>',
        '<a href="/account/settings">Account</a>',
    ]
    positions = [page.index(fragment) for fragment in order]
    assert positions == sorted(positions)
    assert "style=" not in page and "<script" not in page


def test_svc_frame_head_suspended_is_an_alert_without_a_resume_form() -> None:
    note = PausedNote(name=None, resume_action=f"/account/watchlists/{FIRST}/resume")
    page = render(
        "web/_account_head.html",
        **frame_context(frame(suspended=True, paused=(note,), email="a<b>@example.org")),
    )
    assert '<div class="banner banner--alert" role="alert">' in page
    assert "<strong>No email is reaching a&lt;b&gt;@example.org.</strong>" in page
    rest = SUSPENDED_SENTENCE.split("{email}. ", 1)[1]
    assert rest in page
    assert "<form" not in page and "Resume email" not in page
    assert page.index('role="alert"') < page.index('<nav class="tabs"')


def test_svc_frame_head_first_visit_eyebrow() -> None:
    page = render("web/_account_head.html", **frame_context(frame(eyebrow="Welcome")))
    assert '<p class="account-eyebrow">Welcome</p>' in page
    assert "banner" not in page


def test_svc_frame_switcher_needs_two_lists() -> None:
    one = [watchlist(FIRST, "Mine", items=2)]
    assert render("watch/_lists.html", choices=list_choices(one, FIRST), base="/account/") == ""
    two = [*one, watchlist(SECOND, "<Theirs>", items=1)]
    page = render("watch/_lists.html", choices=list_choices(two, SECOND), base="/account/delivery")
    assert '<ul class="lists" aria-label="Your lists">' in page
    assert f'<a href="/account/delivery?list={FIRST}">Mine <span class="count">2</span>' in page
    assert (
        f'<a href="/account/delivery?list={SECOND}" aria-current="true">'
        '&lt;Theirs&gt; <span class="count">1</span>'
    ) in page
    assert page.count('aria-current="true"') == 1
    assert '<a class="new" href="/account/?new=1#new-list">' in page
    assert "style=" not in page
