"""An email states stored facts with links, the disclaimer and one-click unsubscribe headers."""

from __future__ import annotations

import base64
from datetime import date
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import SecretBytes

from emendrix_service import DISCLAIMER
from emendrix_service.db.enums import Cadence, ItemKind
from emendrix_service.notify.compose import build_digest
from emendrix_service.notify.facts import (
    ChangeFacts,
    Citation,
    DigestInputs,
    EventFacts,
    ItemFacts,
    MatchKey,
    StoredSentence,
    WatchlistFacts,
)
from emendrix_service.notify.model import Digest, DigestKind, Heartbeat
from emendrix_service.notify.render import render_digest, render_heartbeat, unsubscribe_url
from emendrix_service.signing import verify
from tests.conftest import NOW, SECRET_KEY, SITE_URL

WATCHLIST = UUID(int=7)
SECRET = SecretBytes(base64.b64decode(SECRET_KEY))
UNSUBSCRIBE = unsubscribe_url(SITE_URL, WATCHLIST, secret=SECRET)


def event(act_key: str, version: str, *in_force: date) -> EventFacts:
    return EventFacts(
        event_key=f"eu/{act_key}@{version}",
        corpus="eu",
        act_key=act_key,
        from_version="v1",
        to_version=version,
        detected_on=date(2026, 10, 9),
        in_force=in_force,
        url=f"{SITE_URL}/acts/{act_key}/{version}/",
    )


def change(key: str, location: str, **facts: object) -> ChangeFacts:
    values: dict[str, object] = {
        "event_key": key,
        "location": location,
        "change_type": "MODIFIED",
        "anchor": f"c-{location.replace(' ', '-').lower()}",
        "unexplained": "diff-only mode: the explain stage did not run for this entry",
        **facts,
    }
    return ChangeFacts.model_validate(values)


def act_item(act_key: str, location: str | None = None) -> ItemFacts:
    return ItemFacts(
        item_id=uuid5(NAMESPACE_OID, f"{act_key} {location}"),
        watchlist_id=WATCHLIST,
        kind=ItemKind.ACT if location is None else ItemKind.PROVISION,
        corpus="eu",
        act_key=act_key,
        location=location,
    )


def compose(
    kind: DigestKind,
    events: list[EventFacts],
    changes: list[ChangeFacts],
    items: list[ItemFacts],
    *,
    alerts: tuple[ChangeFacts, ...] = (),
) -> Digest:
    labels = {"eu/32024R1689": "AI Act", "eu/32017R0745": "MDR"}
    inputs = DigestInputs(
        watchlist=WatchlistFacts(
            watchlist_id=WATCHLIST,
            user_id=UUID(int=8),
            email="reader@example.org",
            name="Weekly",
            cadence=Cadence.WEEKLY,
            created_at=NOW,
        ),
        events=tuple(events),
        changes=tuple(changes),
        labels=labels,
        items=tuple(items),
        date_alerts=frozenset(
            MatchKey(event_key=c.event_key, location=c.location, occurrence=c.occurrence)
            for c in alerts
        ),
    )
    return build_digest(kind, inputs)


def mail_of(digest: Digest) -> tuple[str, str, str, dict[str, str]]:
    mail = render_digest(
        digest,
        to="reader@example.org",
        site_url=SITE_URL,
        manage_url=f"{SITE_URL}/account/",
        unsubscribe_url=UNSUBSCRIBE,
    )
    return mail.subject, mail.text, mail.html, dict(mail.headers)


MDR = event("32017R0745", "v2", date(2026, 7, 27), date(2026, 7, 1))
AI = event("32024R1689", "v2", date(2026, 7, 27))


def test_svc_notify_one_act_names_it_and_its_newest_in_force_date() -> None:
    changes = [change(MDR.event_key, f"AR {n}") for n in (2, 10, 3)]
    subject, text, _, _ = mail_of(compose("weekly", [MDR], changes, [act_item("32017R0745")]))
    assert subject == "[Emendrix] MDR: 3 watched provisions changed (in force 2026-07-27)"
    assert text.index("Article 2") < text.index("Article 3") < text.index("Article 10")


def test_svc_notify_no_in_force_date_leaves_it_out_of_the_subject() -> None:
    quiet = event("32017R0745", "v3")
    digest = compose("daily", [quiet], [change(quiet.event_key, "AR 2")], [act_item("32017R0745")])
    assert mail_of(digest)[0] == "[Emendrix] MDR: 1 watched provision changed"


def test_svc_notify_several_acts_are_counted() -> None:
    changes = [change(MDR.event_key, "AR 2"), *(change(AI.event_key, f"AR {n}") for n in (1, 4))]
    items = [act_item("32017R0745"), act_item("32024R1689")]
    subject = mail_of(compose("weekly", [MDR, AI], changes, items))[0]
    assert subject == "[Emendrix] Weekly digest: 3 watched provisions changed in 2 acts"


def test_svc_notify_an_instant_date_alert_leads_the_subject() -> None:
    moved = change(
        AI.event_key,
        "AR 113",
        dates_removed=(date(2026, 8, 2),),
        dates_added=(date(2027, 12, 2), date(2028, 8, 2)),
    )
    other = change(AI.event_key, "AR 4")
    digest = compose("instant", [AI], [moved, other], [act_item("32024R1689")], alerts=(moved,))
    subject, text, html, _ = mail_of(digest)
    assert subject == "[Emendrix] A date changed in AI Act Article 113"
    assert digest.date_alert_count == 1
    assert "A date in the text changed in 1 of them" in text
    expected = (
        "a date in the text changed; dates removed: 2026-08-02; dates added: 2027-12-02, "
        "2028-08-02; what these dates mean was not read"
    )
    assert expected in text
    assert expected in html
    assert "deadline" not in text + html


def test_svc_notify_an_application_date_is_named_only_when_it_was_read() -> None:
    read = change(
        AI.event_key, "AR 113", dates_added=(date(2027, 12, 2),), applies_from="2027-12-02"
    )
    unread = change(AI.event_key, "AR 5")
    unchanged = change(AI.event_key, "AR 6", applies_from="unchanged")
    _, text, _, _ = mail_of(
        compose("weekly", [AI], [read, unread, unchanged], [act_item(AI.act_key)])
    )
    assert "application date: 2027-12-02, read from the act's own application article" in text
    assert "dates added: 2027-12-02\n" in text
    assert "the application date was not read" in text
    assert "application date: not moved by this change" in text


def test_svc_notify_the_disclaimer_and_unsubscribe_headers_are_in_every_email() -> None:
    _, text, html, headers = mail_of(
        compose("weekly", [AI], [change(AI.event_key, "AR 4")], [act_item(AI.act_key)])
    )
    assert DISCLAIMER in text
    assert DISCLAIMER in html
    assert headers == {
        "List-Unsubscribe": f"<{UNSUBSCRIBE}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    token = UNSUBSCRIBE.removeprefix(f"{SITE_URL}/u/unsubscribe/")
    assert verify("unsub", token, secret=SECRET) == str(WATCHLIST)
    assert UNSUBSCRIBE in text
    assert "you watch AI Act" in text


def test_svc_notify_a_disputed_line_carries_its_reason_sentence() -> None:
    disputed = change(AI.event_key, "AR 9", disputed=True, dispute_reason="textless_metadata_only")
    unknown = change(AI.event_key, "AR 10", disputed=True)
    _, text, html, _ = mail_of(compose("weekly", [AI], [disputed, unknown], [act_item(AI.act_key)]))
    sentence = "Only the EU's own amendment metadata names it, and it carries no text."
    assert f"disputed: {sentence}" in text
    assert "disputed (no reason recorded)" in text
    assert f"{SITE_URL}/methodology/" in text
    assert f'href="{SITE_URL}/methodology/"' in html


def test_svc_notify_sentences_and_citations_are_carried_as_stored() -> None:
    cited = Citation(label="Art. 2, v2", url="https://example.org/eur-lex/ar-2")
    explained = change(
        AI.event_key,
        "AR 2",
        sentences=(
            StoredSentence(text="Something about this provision changed.", citations=(cited,)),
            StoredSentence(text="A quoted passage.", fallback=True),
        ),
    )
    _, text, html, _ = mail_of(compose("weekly", [AI], [explained], [act_item(AI.act_key)]))
    assert "- Something about this provision changed.\n    Art. 2, v2: " in text
    assert "The citation gate quoted the provision here" in text
    assert "A quoted passage." not in text + html
    assert "no explanation" not in text
    assert f'<a href="{cited.url}">Art. 2, v2</a>' in html
    assert f"{AI.url}#c-ar-2" in text


def test_svc_notify_an_unexplained_change_says_why() -> None:
    _, text, _, _ = mail_of(
        compose("weekly", [AI], [change(AI.event_key, "AR 4")], [act_item(AI.act_key)])
    )
    assert "no explanation: diff-only mode: the explain stage did not run for this entry" in text


def test_svc_notify_the_html_part_escapes_headings_and_the_subject_has_one_line() -> None:
    hostile = change(AI.event_key, "AR 4", heading="<script>alert(1)</script> & co")
    digest = compose("weekly", [AI], [hostile], [act_item(AI.act_key)])
    _, text, html, _ = mail_of(digest)
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; co" in html
    assert "<script>alert(1)</script> & co" in text
    renamed = digest.model_copy(
        update={
            "events": tuple(
                block.model_copy(update={"act_label": "AI\r\nBcc: x@example.org"})
                for block in digest.events
            )
        }
    )
    subject = mail_of(renamed)[0]
    assert "\r" not in subject and "\n" not in subject


def test_svc_notify_the_container_reason_is_said_in_full() -> None:
    whole = change(AI.event_key, "AR 6")
    _, text, _, _ = mail_of(compose("weekly", [AI], [whole], [act_item(AI.act_key, "AR 6 PA 1")]))
    assert (
        "Why: you watch AI Act Article 6(1); this change is to Article 6, and the record does "
        "not say which part of it moved"
    ) in text


def test_svc_notify_the_monthly_note() -> None:
    mail = render_heartbeat(
        Heartbeat(watchlist_name="Weekly", month="October", watched=("AI Act Article 6",)),
        to="reader@example.org",
        site_url=SITE_URL,
        manage_url=f"{SITE_URL}/account/",
        unsubscribe_url=UNSUBSCRIBE,
    )
    assert mail.subject == "[Emendrix] Still watching: nothing changed in October"
    assert DISCLAIMER in mail.text and DISCLAIMER in mail.html
    assert "AI Act Article 6" in mail.text
    assert dict(mail.headers)["List-Unsubscribe"] == f"<{UNSUBSCRIBE}>"


def test_svc_notify_no_em_dash_reaches_an_email() -> None:
    digest = compose("weekly", [AI], [change(AI.event_key, "AR 4")], [act_item(AI.act_key)])
    _, text, html, _ = mail_of(digest)
    assert chr(0x2014) not in text + html
