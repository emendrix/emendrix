"""The landing a "Watch this" link opens, signed out and signed in."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient, Response
from pydantic import SecretStr
from sqlalchemy import select

from emendrix_service.app import create_app
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.accounts import create_user_with_consents
from emendrix_service.db.enums import ItemKind
from emendrix_service.db.tables import WatchItem
from emendrix_service.db.watchlists import add_item, create_watchlist
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ServiceSettings
from tests.conftest import NOW, SITE_URL
from tests.test_svc_auth_flow import count, link_of, press
from tests.test_svc_auth_flow import settings as settings
from tests.test_svc_watch_account import assert_clean
from tests.test_svc_watch_fixtures import HOUSE, csrf, sign_in, watchlist_ids
from tests.test_svc_watch_fixtures import loaded as loaded

pytestmark = pytest.mark.anyio

ANNEX = f"/account/watch?act={HOUSE}&loc=AN%20I"


def words(text: str) -> str:
    """What a reader sees between the header and the footer, tags left out."""
    return re.sub(r"<[^>]+>", " ", text.split("</header>", 1)[1].split("<footer", 1)[0])


async def items(db: Db) -> list[tuple[ItemKind, str | None, str | None, str | None]]:
    async with db.transaction() as tx:
        rows = await tx.scalars(select(WatchItem).order_by(WatchItem.created_at))
        return [(row.kind, row.corpus, row.act_key, row.location) for row in rows]


async def sign_up(
    http: AsyncClient, email: str, *, consent: bool = True, path: str = ANNEX
) -> Response:
    form = {"csrf": await csrf(http, path), "act": HOUSE, "loc": "AN I", "email": email}
    if consent:
        form["consent"] = "yes"
    return await http.post("/account/watch", data=form)


async def test_svc_watch_landing_signed_out_names_what_is_watched(
    client: AsyncClient, loaded: Db
) -> None:
    page = await client.get(f"/account/watch?act={HOUSE}&loc=Annex%201")
    assert page.status_code == 200
    assert "Watch Annex I of House Rules of Flat 3B" in page.text
    assert 'name="loc" value="AN I"' in page.text
    assert 'name="consent" value="yes"' in page.text
    assert 'href="/account/privacy"' in page.text
    assert "it does not say whether the change affects you" in page.text
    assert "by invitation" not in page.text


async def test_svc_watch_landing_sign_up_carries_the_item_to_the_first_watchlist(
    client: AsyncClient, loaded: Db, mailer: RecordingMailer
) -> None:
    page = await sign_up(client, "reader@example.org")
    assert page.status_code == 200
    assert "Check your inbox" in page.text
    (mail,) = mailer.sent
    assert (
        mail.subject == "Confirm your address to start watching Annex I of House Rules of Flat 3B"
    )
    assert "reader@example.org" not in page.text
    confirmed = await press(client, link_of(mail))
    assert (confirmed.status_code, confirmed.headers["location"]) == (303, "/account/")
    assert await items(loaded) == [(ItemKind.PROVISION, "toy", HOUSE, "AN I")]
    account = await client.get("/account/")
    assert "Annex I" in account.text and "Cleaning rota" in account.text


async def test_svc_watch_landing_wants_the_consent_and_an_address(
    client: AsyncClient, loaded: Db, mailer: RecordingMailer
) -> None:
    unticked = await sign_up(client, "reader@example.org", consent=False)
    assert unticked.status_code == 400
    assert "Tick the box" in unticked.text
    assert 'value="reader@example.org"' in unticked.text
    garbled = await sign_up(client, "not an address")
    assert garbled.status_code == 400
    assert "not an email address" in garbled.text
    assert mailer.sent == []


async def test_svc_watch_landing_signed_in_adds_once(client: AsyncClient, loaded: Db) -> None:
    user = await sign_in(loaded, client, "reader@example.org")
    page = await client.get(ANNEX)
    assert "Start watching" in page.text and "watchlist" not in words(page.text).lower()
    assert '<a class="back" href="/account/">' in page.text
    token = await csrf(client, ANNEX)
    form = {"csrf": token, "act": HOUSE, "loc": "AN I", "watchlist": "new"}
    first = await client.post("/account/watch", data=form)
    (wl,) = await watchlist_ids(loaded, user)
    assert first.status_code == 303
    assert first.headers["location"] == f"/account/?list={wl}&notice=added"
    one = (await client.get(ANNEX)).text
    assert "Add to your list" in one and "You already watch this." in one
    assert "My watchlist" not in one and "watchlist" not in words(one).lower()
    again = await client.post("/account/watch", data={**form, "watchlist": str(wl)})
    assert again.headers["location"] == f"/account/?list={wl}&notice=already"
    assert await items(loaded) == [(ItemKind.PROVISION, "toy", HOUSE, "AN I")]
    shown = await client.get(again.headers["location"])
    assert "Your list already holds that, so nothing was added." in shown.text
    whole = await client.post(
        "/account/watch", data={"csrf": token, "act": HOUSE, "watchlist": str(wl)}
    )
    assert whole.headers["location"] == f"/account/?list={wl}&notice=added"
    assert (ItemKind.ACT, "toy", HOUSE, None) in await items(loaded)


async def test_svc_watch_landing_several_lists_offer_a_choice(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "reader@example.org")
    async with loaded.transaction() as tx:
        first = await create_watchlist(tx, user, "Devices", NOW)
        await create_watchlist(tx, user, "Chemicals", NOW + timedelta(seconds=1))
        await add_item(tx, user, first, ItemKind.PROVISION, "toy", HOUSE, "AN I", NOW)
    page = (await client.get(ANNEX)).text
    assert '<label for="watchlist">List' in page and "Add to the chosen list" in page
    assert "Already watched in: Devices." in page


async def test_svc_watch_landing_unknown_act_and_unread_location(
    client: AsyncClient, loaded: Db
) -> None:
    unknown = await client.get("/account/watch?act=32099R9999")
    assert unknown.status_code == 404
    assert "not watched by this site" in unknown.text
    assert 'href="/acts/"' in unknown.text
    assert (await client.get("/account/watch")).status_code == 404
    assert (await client.get("/account/watch?act=%00")).status_code == 404
    assert (await client.get("/account/watch?act=" + "9" * 500)).status_code == 404
    odd = await client.get(f"/account/watch?act={HOUSE}&loc=AR%201%00")
    assert odd.status_code == 200 and 'name="loc"' not in odd.text
    unread = await client.get(f"/account/watch?act={HOUSE}&loc=Article%206(1)(a)")
    assert unread.status_code == 200
    assert "“Article 6(1)(a)” is not a location this page can read" in unread.text
    assert 'name="loc"' not in unread.text
    assert "Watch House Rules of Flat 3B" in unread.text


async def test_svc_watch_landing_before_any_load(client: AsyncClient, db: Db) -> None:
    page = await client.get(f"/account/watch?act={HOUSE}")
    assert page.status_code == 503
    assert "has not been loaded" in page.text
    assert "<form" not in page.text


@pytest.fixture
async def closed(
    settings: ServiceSettings, clock: FixedClock, loaded: Db, worker_url: str
) -> AsyncIterator[tuple[AsyncClient, RecordingMailer]]:
    configured = settings.model_copy(
        update={
            "database_url": SecretStr(worker_url),
            "signup_open": False,
            "signup_allowlist": ("invited@example.org",),
        }
    )
    mailer = RecordingMailer()
    app = create_app(configured, clock=clock, mailer=mailer, db=loaded)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=SITE_URL) as http:
            yield http, mailer


async def test_svc_watch_landing_closed_sign_up(
    closed: tuple[AsyncClient, RecordingMailer], loaded: Db
) -> None:
    http, mailer = closed
    assert "Sign-up is by invitation for now" in (await http.get(ANNEX)).text
    stranger = await sign_up(http, "stranger@example.org")
    assert mailer.sent == []
    invited = await sign_up(http, "invited@example.org")
    assert invited.content == stranger.content
    (mail,) = mailer.sent
    assert mail.to == "invited@example.org"
    await press(http, link_of(mail))
    assert await items(loaded) == [(ItemKind.PROVISION, "toy", HOUSE, "AN I")]
    assert await count(loaded, WatchItem) == 1


FORMALDEHYDE = "/account/watch?substance=cas-50-00-0"


async def numbers(db: Db) -> list[str | None]:
    async with db.transaction() as tx:
        query = select(WatchItem.identifier).where(WatchItem.kind == ItemKind.SUBSTANCE)
        return list(await tx.scalars(query))


async def test_svc_watch_landing_a_substance_signed_out_is_watched_once_confirmed(
    client: AsyncClient, loaded: Db, mailer: RecordingMailer
) -> None:
    page = await client.get(FORMALDEHYDE)
    assert page.status_code == 200
    assert "Watch CAS 50-00-0" in page.text
    assert 'name="substance" value="cas-50-00-0"' in page.text and 'name="act"' not in page.text
    assert "print no number" in page.text and "does not say whether the change affects" in page.text
    assert 'href="/account/signin?next=/account/watch%3Fsubstance%3Dcas-50-00-0"' in page.text
    form = {
        "csrf": await csrf(client, FORMALDEHYDE),
        "substance": "cas-50-00-0",
        "email": "reader@example.org",
        "consent": "yes",
    }
    sent = await client.post("/account/watch", data=form)
    assert sent.status_code == 200 and "Check your inbox" in sent.text
    (mail,) = mailer.sent
    assert mail.subject == "Confirm your address to start watching CAS 50-00-0"
    path = link_of(mail)
    assert "?" not in path, "the link carries the number as its intent, not a next"
    assert await numbers(loaded) == []
    confirmed = await press(client, path)
    assert (confirmed.status_code, confirmed.headers["location"]) == (303, "/account/")
    assert await numbers(loaded) == ["cas:50-00-0"]
    assert "CAS 50-00-0" in words((await client.get("/account/")).text)


async def test_svc_watch_landing_a_substance_known_address_gets_a_signin_link(
    client: AsyncClient, loaded: Db, mailer: RecordingMailer
) -> None:
    async with loaded.transaction() as tx:
        await create_user_with_consents(tx, "known@example.org", "000000000000", NOW)
    form = {
        "csrf": await csrf(client, FORMALDEHYDE),
        "substance": "cas-50-00-0",
        "email": "known@example.org",
        "consent": "yes",
    }
    sent = await client.post("/account/watch", data=form)
    assert sent.status_code == 200 and "Check your inbox" in sent.text
    (mail,) = mailer.sent
    assert mail.subject == "Sign in to Emendrix"
    confirmed = await press(client, link_of(mail))
    assert (confirmed.status_code, confirmed.headers["location"]) == (303, FORMALDEHYDE)
    assert await numbers(loaded) == []
    landed = await client.get(FORMALDEHYDE)
    assert "Start watching" in landed.text


async def test_svc_watch_landing_a_substance_signed_in_adds_once(
    client: AsyncClient, loaded: Db
) -> None:
    user = await sign_in(loaded, client, "reader@example.org")
    async with loaded.transaction() as tx:
        wl = await create_watchlist(tx, user, "My watchlist", NOW)
    hyphenless = await client.get("/account/watch?substance=cas-50000")
    assert "Add to your list" in hyphenless.text
    assert 'name="substance" value="cas-50-00-0"' in hyphenless.text
    form = {"csrf": await csrf(client, FORMALDEHYDE), "substance": "cas-50-00-0"}
    first = await client.post("/account/watch", data={**form, "watchlist": str(wl)})
    assert first.headers["location"] == f"/account/?list={wl}&notice=added"
    assert "You already watch this." in (await client.get(FORMALDEHYDE)).text
    again = await client.post("/account/watch", data={**form, "watchlist": str(wl)})
    assert again.headers["location"] == f"/account/?list={wl}&notice=already"
    ec = await client.post(
        "/account/watch", data={**form, "substance": "ec-200-001-8", "watchlist": str(wl)}
    )
    assert ec.headers["location"] == f"/account/?list={wl}&notice=added"
    assert sorted(n or "" for n in await numbers(loaded)) == ["cas:50-00-0", "ec:200-001-8"]
    refused = await client.post("/account/watch", data={**form, "substance": "cas-50-00-1"})
    assert refused.status_code == 400
    assert len(await numbers(loaded)) == 2


async def test_svc_watch_landing_a_value_that_is_no_number_says_why(
    client: AsyncClient, loaded: Db
) -> None:
    wrong = await client.get("/account/watch?substance=cas-50-00-1")
    assert wrong.status_code == 400
    assert "This is not a CAS or EC number" in wrong.text
    assert "its CAS check digit is 1 where its other digits give 0" in wrong.text
    assert "<form" not in words(wrong.text) and 'name="substance"' not in wrong.text
    crossed = await client.get("/account/watch?substance=cas-200-001-8")
    assert crossed.status_code == 400 and "is not a CAS number" in crossed.text
    both = await client.get("/account/watch?substance=2000002")
    assert both.status_code == 200 and "reads two ways" in both.text
    assert 'href="/account/watch?substance=cas-2000-00-2">Watch CAS 2000-00-2' in both.text
    assert 'href="/account/watch?substance=ec-200-000-2">Watch EC 200-000-2' in both.text
    index = await client.get("/account/watch?substance=index-605-001-00-5")
    assert index.status_code == 200 and "An Index No cannot be watched" in index.text
    assert "No change the record holds names a row keyed 605-001-00-5" in index.text
    assert f'href="{SITE_URL}/substances/"' in index.text
    for page in (wrong, both, index):
        assert "regulated" not in page.text and "restricted" not in page.text
        assert_clean(page.text)
