"""The day an amending act took effect, read from the notice the Publications Office publishes.

The fifth answer to when an instruction takes effect, and the only one that does not come out
of the act's own words. Every act named here is one of the pinned notices, so what is asserted
is what the corpus writes rather than a shape invented for a test.

The reason to trust the read is in the first test: on `32024R1860` the notice's application
date and the date the markup reader takes out of the act's own Article 3 are the same day, read
two independent ways.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from xml.etree import ElementTree

import pytest

from emendrix.eu.cache import CachedResponse, ManifestEntry
from emendrix.eu.cellar import ABSENT_STATUSES, CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eu.identifiers import Celex, ResourceRef
from emendrix.eu.instructions import (
    ActDates,
    DateKind,
    EffectDateSource,
    NoticeDate,
    parse_act_dates,
    parse_instructions,
)
from emendrix.eu.instructions.final_provisions import read_effect_dates
from emendrix.eu.signals import act_dates
from eu_pins import AI_ACT, DIGITAL_OMNIBUS, MDR_POSTPONEMENT, REACH, package

MDR_2024_AMENDER = "32024R1860"
"""The one pinned act whose notice and whose own prose both date the same instruction."""

STAGED = "32017R0745"
"""The MDR's own notice: eight staged application dates and the `1001-01-01` sentinel."""


def dates_of(client: CellarClient, celex: str) -> ActDates:
    """The act's published dates, through the composition root that reads them in the loop."""
    return act_dates(client, Celex.parse(celex))


def _client(status: int) -> CellarClient:
    """A client whose every request is answered with one status and an empty body."""
    return CellarClient(_Answering(status), observed_on=date(2026, 9, 5))


# ------------------------------------------------------- what the notice says, and the check


def test_the_notice_of_the_2024_amender_publishes_both_of_its_dates(
    client: CellarClient,
) -> None:
    """`32024R1860`: entry into force on the day of publication, one part deferred.

    The comment on the first is `DATPUB V ART 3`, the Publications Office recording that it
    applied the act's own Article 3 to the publication date. That arithmetic is why this tier
    exists: the act's text states the rule and never the day.
    """
    found = dates_of(client, MDR_2024_AMENDER)
    assert [(entry.kind, entry.value) for entry in found.entries] == [
        (DateKind.ENTRY_INTO_FORCE, date(2024, 7, 9)),
        (DateKind.APPLICATION, date(2025, 1, 10)),
    ]
    assert found.entries[0].comment == "DATPUB V ART 3"
    assert found.entries[1].comment == "MA/PART V ART 3"


def test_the_published_application_date_is_the_date_the_act_s_own_markup_states(
    client: CellarClient,
) -> None:
    """Two independent readings of one day, and they agree.

    The markup reader takes 10 January 2025 out of `<DATE ISO="20250110">` in Article 3 of
    `32024R1860` and attaches it to `AR 1 PO 1`; the notice publishes the same day as that
    act's application date. Agreement on the acts where both can be read is the evidence for
    reading the notice on the acts where only it can.
    """
    published = dates_of(client, MDR_2024_AMENDER)
    staged = [entry.value for entry in published.entries if entry.staged]
    parse = parse_instructions(package(client, MDR_2024_AMENDER, MDR_2024_AMENDER))
    deferred = [record for record in parse.records if record.source_ref == "AR 001 (1)"]

    assert staged == [date(2025, 1, 10)]
    assert deferred[0].effect_date == date(2025, 1, 10)
    assert deferred[0].effect_source is EffectDateSource.FINAL_PROVISIONS


# ------------------------------------------------------------------ the two counted hazards


def test_an_implausible_value_is_counted_and_never_becomes_a_date(
    client: CellarClient,
) -> None:
    """`1001-01-01` is the corpus's own sentinel for a day a later decision will fix.

    17 of the 295 cached notices carried one on 2026-09-05, the MDR's among them. It is not a
    day any act applies from, so it is counted and no entry is built from it.
    """
    found = dates_of(client, STAGED)
    assert found.implausible == ("1001-01-01",)
    assert date(1001, 1, 1) not in {entry.value for entry in found.entries}
    assert found.default is None


@pytest.mark.parametrize(
    "raw", ["1001-01-01", "0001-01-01", "2130-01-01", "not a date", "2026-02-30"]
)
def test_the_test_is_the_value_s_own_implausibility(raw: str) -> None:
    """Any value outside the span a legal act's dates fall in, not one matched literal."""
    notice = (
        b"<NOTICE><WORK><RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE>"
        b"<VALUE>" + raw.encode() + b"</VALUE><ANNOTATION>"
        b"<TYPE_OF_DATE>{EV|http://example.invalid/EV}</TYPE_OF_DATE>"
        b"</ANNOTATION></RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE></WORK></NOTICE>"
    )
    found = parse_act_dates(notice)
    assert found.entries == ()
    assert found.implausible == (raw,)
    assert found.default is None


def test_an_act_with_several_staged_dates_publishes_no_act_wide_answer(
    client: CellarClient,
) -> None:
    """The MDR's notice states eight application dates and says which part each covers nowhere.

    Its comments name Article 123(3), the provision that *states* each date, never the
    provisions the date reaches. Picking one of the eight would be the guess the two-clocks
    rule forbids, so the notice answers nothing at all for that act and is counted.
    """
    found = dates_of(client, STAGED)
    assert len(found.unplaced) == 8
    assert {entry.comment.startswith("MA/PART") for entry in found.unplaced} == {True}
    assert found.default is None


def test_one_staged_date_beside_an_act_wide_one_is_still_a_staged_act(
    client: CellarClient,
) -> None:
    """`32022R2065` applies from one day and defers one part to another, and that is enough.

    The notice does not say which part, so the act-wide value it also carries cannot be applied
    to the instructions the deferred part covers, and none of them is dated from here.
    """
    found = dates_of(client, "32022R2065")
    assert sorted(entry.value for entry in found.entries) == [
        date(2022, 2, 17),
        date(2022, 11, 16),
    ]
    assert [entry.value for entry in found.unplaced] == [date(2022, 11, 16)]
    assert found.default is None


def test_an_unknown_type_of_date_is_carried_raw_and_places_nothing() -> None:
    """The `UNKNOWN(str)` escape hatch: a code outside the vocabulary is counted, never read."""
    notice = (
        b"<NOTICE><WORK><RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE>"
        b"<VALUE>2024-07-09</VALUE><ANNOTATION>"
        b"<TYPE_OF_DATE>{XX|http://example.invalid/XX}</TYPE_OF_DATE>"
        b"</ANNOTATION></RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE></WORK></NOTICE>"
    )
    found = parse_act_dates(notice)
    assert found.unknown_kinds == (("XX", 1),)
    assert found.unplaced == found.entries
    assert found.default is None


class _Answering(CellarHttp):
    """A server that answers one status to everything, so both refusal paths can be exercised."""

    def __init__(self, status: int) -> None:
        super().__init__()
        self.status = status

    def get(
        self,
        target: ResourceRef | str,
        *,
        accept: str,
        accept_language: str | None = "eng",
    ) -> CachedResponse:
        entry = ManifestEntry(
            key="",
            url=self.url_for(target),
            status_code=self.status,
            fetched_at=datetime(2026, 9, 5, tzinfo=UTC),
            file="",
            sha256="",
            size=0,
        )
        return CachedResponse(entry=entry, body=b"")


@pytest.mark.parametrize("status", sorted(ABSENT_STATUSES))
def test_a_notice_the_corpus_does_not_have_is_an_empty_read(status: int) -> None:
    """`404` and `406` are the corpus saying there is no such document, which is an answer."""
    assert act_dates(_client(status), Celex.parse(DIGITAL_OMNIBUS)) == ActDates()


@pytest.mark.parametrize("status", [403, 429, 500])
def test_a_server_refusing_this_client_is_not_an_act_without_dates(status: int) -> None:
    """Reading a refusal as an absent notice would suppress an act's dates on its strength.

    The refusal is also remembered for the life of a signal source, so one 403 would silence
    that act's dating until the process ends. `eu/cellar.py` draws this line on the same
    endpoint and for the same reason, and this fails as loudly as it does.
    """
    with pytest.raises(LookupError, match=str(status)):
        act_dates(_client(status), Celex.parse(DIGITAL_OMNIBUS))


def test_a_notice_with_no_work_element_is_an_empty_read() -> None:
    """A counted gap, never an exception: the act is then dated from its own text alone."""
    assert parse_act_dates(b"<NOTICE/>") == ActDates()


# --------------------------------------------------------------- what the tier then answers


def test_the_flagship_amender_is_dated_by_its_notice_and_by_nothing_else(
    client: CellarClient,
) -> None:
    """`32026R1744` enters into force three days after a publication its text does not date.

    Its own words leave all 95 instructions undated, which is what the four text tiers measure.
    The notice publishes the day, and the fifth tier reaches every one of them.
    """
    published = dates_of(client, DIGITAL_OMNIBUS)
    assert published.default == date(2026, 7, 27)

    parse = parse_instructions(package(client, DIGITAL_OMNIBUS, DIGITAL_OMNIBUS), dates=published)
    assert parse.matched == 95
    assert parse.dated == 95
    assert {record.effect_source for record in parse.records} == {EffectDateSource.NOTICE}
    assert {record.effect_date for record in parse.records} == {date(2026, 7, 27)}


def test_the_act_s_own_words_win_where_it_writes_them(client: CellarClient) -> None:
    """The tier sits below the act's own text: `AR 1 PO 1` keeps the date Article 3 gave it."""
    parse = parse_instructions(
        package(client, MDR_2024_AMENDER, MDR_2024_AMENDER),
        dates=ActDates(entries=(NoticeDate(value=date(2024, 7, 9), kind=DateKind.APPLICATION),)),
    )
    deferred = [record for record in parse.records if record.source_ref == "AR 001 (1)"]
    assert deferred[0].effect_date == date(2025, 1, 10)
    assert deferred[0].effect_source is EffectDateSource.FINAL_PROVISIONS

    # The tier is live in the same call: what Article 3 does not defer takes the notice's day.
    others = [record for record in parse.records if record.source_ref.startswith("AR 001 ")]
    assert {record.effect_source for record in others} == {
        EffectDateSource.FINAL_PROVISIONS,
        EffectDateSource.NOTICE,
    }


def test_an_act_that_gives_itself_no_day_is_dated_by_its_notice(client: CellarClient) -> None:
    """`32020R0561` is a document of dates and gives its own Article 2 none of them.

    Every date in it belongs to the act it postpones, so not one is attached to a coordinate
    this parser wrote and the four text tiers date nothing. The notice states the day the act
    itself took effect, which is a fact about this act and not about the one it amends.
    """
    published = dates_of(client, MDR_POSTPONEMENT)
    assert published.default == date(2020, 4, 24)

    parse = parse_instructions(package(client, MDR_POSTPONEMENT, MDR_POSTPONEMENT), dates=published)
    assert parse.dated == 26
    assert {record.effect_source for record in parse.records} == {EffectDateSource.NOTICE}


def test_a_default_the_act_s_own_text_withdrew_stays_withdrawn() -> None:
    """A dated statement the markup reader cannot attribute takes the act's default away.

    *"Articles 95 to 98"* names two units and means four, so the act's own date is withdrawn
    from the whole act rather than applied to instructions it deliberately took out of it. A
    second source cannot say which instructions that statement was about either, so the notice
    does not fill the hole the first reader left.
    """
    article = ElementTree.fromstring(
        "<ARTICLE IDENTIFIER='003'><ALINEA>This Regulation shall apply from "
        "<DATE ISO='20210628'>28 June 2021</DATE>.</ALINEA><ALINEA>Articles 95 to 98 of this "
        "Regulation shall apply from <DATE ISO='20260626'>26 June 2026</DATE>.</ALINEA></ARTICLE>"
    )
    found = read_effect_dates(
        [article],
        dates=ActDates(entries=(NoticeDate(value=date(2019, 12, 25), kind=DateKind.APPLICATION),)),
    )
    assert found.default is None
    assert found.unread == 1
    assert found.published == date(2019, 12, 25)
    assert found.for_clause("Article 4 is deleted;", "AR 001 (7)") == (
        None,
        EffectDateSource.UNREAD,
    )


def test_the_parse_reads_no_notice_of_its_own(client: CellarClient) -> None:
    """The dates arrive as a value. A parse handed none reads the act's text and stops there.

    Nothing under `eu/instructions/` fetches: the notice is a second document and the
    composition root is where a second document is asked for.
    """
    parse = parse_instructions(package(client, DIGITAL_OMNIBUS, DIGITAL_OMNIBUS))
    assert parse.matched == 95
    assert parse.dated == 0
    assert {record.effect_source for record in parse.records} == {EffectDateSource.UNREAD}


def test_an_amended_act_s_own_notice_is_read_by_the_same_rule(client: CellarClient) -> None:
    """The read is of a notice, not of an amending act, and the rule does not change with one.

    REACH and the AI Act are both staged and neither publishes an act-wide answer, asserted
    here so the rule is not read as being about amending acts alone.
    """
    assert dates_of(client, REACH).default is None
    assert dates_of(client, AI_ACT).default is None
