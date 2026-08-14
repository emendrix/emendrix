"""The schema is the contract with the model, so it is tested like one.

Two properties matter more than the rest and are checked first: a sentence cannot ship
without a citation, and no answer can run past three sentences. Both are enforced by the type
rather than requested in prose, which is what makes them true of a *malformed* model as well
as a cooperative one.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from emendrix.explain import (
    MAX_SENTENCES,
    SCHEMA_VERSION,
    CitedSentence,
    Explanation,
    ExplanationUnavailable,
)


def sentence(text: str = "The duty changed.", *citations: str) -> CitedSentence:
    return CitedSentence(text=text, citations=citations or ("AR 4@v2",))


def test_a_sentence_without_a_citation_is_rejected() -> None:
    """A claim without a resolvable citation does not ship, and it is the type that says so."""
    with pytest.raises(ValidationError):
        CitedSentence(text="Something changed.", citations=())


def test_an_empty_sentence_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CitedSentence(text="", citations=("AR 4@v2",))


def test_more_than_three_sentences_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Explanation(sentences=tuple(sentence() for _ in range(MAX_SENTENCES + 1)))


def test_no_sentences_at_all_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Explanation(sentences=())


def test_three_sentences_are_accepted() -> None:
    explanation = Explanation(sentences=tuple(sentence() for _ in range(MAX_SENTENCES)))
    assert len(explanation.sentences) == MAX_SENTENCES
    assert explanation.sentence_count == MAX_SENTENCES


def test_cited_keys_gathers_every_key_including_the_applicability_note() -> None:
    """The gate's containment check reads one set; assembling it is the schema's job."""
    explanation = Explanation(
        sentences=(sentence("A.", "k1", "k2"), sentence("B.", "k2")),
        applicability_note=sentence("It applies from 2 August 2028.", "k3"),
    )
    assert explanation.cited_keys == frozenset({"k1", "k2", "k3"})
    assert explanation.sentence_count == 3


def test_the_applicability_note_is_optional_and_defaults_absent() -> None:
    """Many unknowns is the correct outcome, so omitting the note must be the easy path."""
    assert Explanation(sentences=(sentence(),)).applicability_note is None


def test_the_schema_the_model_sees_has_no_field_for_a_url() -> None:
    """The model cannot invent a link because there is nowhere to put one."""
    schema = Explanation.model_json_schema()
    rendered = repr(schema)
    assert "url" not in rendered.lower()
    assert "http" not in rendered.lower()


def test_the_schema_the_model_sees_states_the_sentence_ceiling() -> None:
    """A constraint the JSON schema carries is one the provider can enforce, not just ask for."""
    schema = Explanation.model_json_schema()
    assert schema["properties"]["sentences"]["maxItems"] == MAX_SENTENCES
    assert schema["properties"]["sentences"]["minItems"] == 1


def test_explanations_are_frozen_value_types() -> None:
    explanation = Explanation(sentences=(sentence(),))
    with pytest.raises(ValidationError):
        explanation.sentences = ()


def test_unavailable_is_a_value_that_must_say_why() -> None:
    """First-class states, never exceptions, and a state with no reason explains nothing."""
    assert ExplanationUnavailable(reason="provider timed out").state == "explanation_unavailable"
    with pytest.raises(ValidationError):
        ExplanationUnavailable(reason="")


def test_the_schema_version_is_an_integer_that_cassette_keys_can_carry() -> None:
    assert isinstance(SCHEMA_VERSION, int)
    assert SCHEMA_VERSION >= 1
