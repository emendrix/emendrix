"""The landing a "Watch this" link opens, signed out and signed in."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient, Response
from pydantic import SecretStr
from sqlalchemy import select

from emendrix_service.app import create_app
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import ItemKind
from emendrix_service.db.tables import WatchItem
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.settings import ServiceSettings
from tests.conftest import SITE_URL
from tests.test_svc_auth_flow import count, link_of, press
from tests.test_svc_auth_flow import settings as settings
from tests.test_svc_watch_fixtures import HOUSE, csrf, sign_in, watchlist_ids
from tests.test_svc_watch_fixtures import loaded as loaded

pytestmark = pytest.mark.anyio

ANNEX = f"/account/watch?act={HOUSE}&loc=AN%20I"


async def items(db: Db) -> list[tuple[ItemKind, str, str, str | None]]:
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
    assert "Add to a new watchlist" in page.text
    token = await csrf(client, ANNEX)
    form = {"csrf": token, "act": HOUSE, "loc": "AN I", "watchlist": "new"}
    first = await client.post("/account/watch", data=form)
    (wl,) = await watchlist_ids(loaded, user)
    assert first.status_code == 303
    assert first.headers["location"] == f"/account/?notice=added#wl-{wl}"
    assert "Add to My watchlist" in (await client.get(ANNEX)).text
    again = await client.post("/account/watch", data={**form, "watchlist": str(wl)})
    assert again.headers["location"] == f"/account/?notice=already#wl-{wl}"
    assert await items(loaded) == [(ItemKind.PROVISION, "toy", HOUSE, "AN I")]
    shown = await client.get(again.headers["location"])
    assert "already holds that item" in shown.text
    whole = await client.post(
        "/account/watch", data={"csrf": token, "act": HOUSE, "watchlist": str(wl)}
    )
    assert whole.headers["location"] == f"/account/?notice=added#wl-{wl}"
    assert (ItemKind.ACT, "toy", HOUSE, None) in await items(loaded)


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
