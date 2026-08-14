"""First-class states behave like data: they discriminate, count and round-trip."""

from datetime import date

from pydantic import TypeAdapter

from emendrix.core.identifiers import ActId, VersionId
from emendrix.core.states import (
    ConsolidationPending,
    EnglishUnavailable,
    StructuredTextUnavailable,
    Unavailable,
)

ACT = ActId(corpus="test", key="act")
OBSERVED_ON = date(2026, 8, 5)

_UNAVAILABLE = TypeAdapter[Unavailable](Unavailable)


def test_states_round_trip_through_their_tagged_union() -> None:
    states: list[Unavailable] = [
        ConsolidationPending(act=ACT, in_force=date(2026, 7, 27), observed_on=OBSERVED_ON),
        EnglishUnavailable(
            act=ACT,
            version=VersionId("20240712"),
            available_languages=("DEU", "FRA"),
            observed_on=OBSERVED_ON,
        ),
        StructuredTextUnavailable(
            act=ACT,
            version=VersionId("20110505"),
            formats_offered=("pdf", "xhtml"),
            observed_on=OBSERVED_ON,
        ),
    ]
    for state in states:
        assert _UNAVAILABLE.validate_python(_UNAVAILABLE.dump_python(state)) == state


def test_states_are_countable_by_tag() -> None:
    assert ConsolidationPending(act=ACT, observed_on=OBSERVED_ON).state == "consolidation_pending"
    assert EnglishUnavailable(act=ACT, observed_on=OBSERVED_ON).state == "english_unavailable"
    assert (
        StructuredTextUnavailable(act=ACT, observed_on=OBSERVED_ON).state
        == "structured_text_unavailable"
    )


def test_the_observation_date_is_always_supplied_by_the_caller() -> None:
    """Nothing in the core reads a clock, so `observed_on` has no default."""
    assert "observed_on" in ConsolidationPending.model_fields
    assert ConsolidationPending.model_fields["observed_on"].is_required()
