"""Naming the instrument that made an event: what is harvested, what is preferred, what is said.

The toy corpus is the second implementor here as everywhere: its amending act's key is
`house-rules-amendment-1`, which is not a CELEX, so the composition root renders no number and
no address for it and every surface has to fall back to the key. That is the case the fallbacks
exist for, and it is asserted rather than assumed.
"""

from __future__ import annotations

from datetime import date

from site_entries import attributed_entry, unattributed_entry

from emendrix.core import ActId, Signal, SignalClaim
from emendrix.site_.amending import (
    AmendingAct,
    amenders,
    amending_keys,
    amending_lines,
    by_words,
    collect_amending,
    mentioned_keys,
)

OBSERVED = date(2026, 8, 9)


def _acts(*names: str) -> tuple[AmendingAct, ...]:
    return tuple(AmendingAct(key=f"k{index}", label=name) for index, name in enumerate(names))


def test_the_short_name_prefers_the_label_then_the_number_then_the_key() -> None:
    """The three names in the order a heading wants them, and a key is always an answer."""
    full = AmendingAct(key="32026R1744", number="Regulation (EU) 2026/1744", label="Omnibus")
    assert full.short == "Omnibus"
    assert full.model_copy(update={"label": ""}).short == "Regulation (EU) 2026/1744"
    assert AmendingAct(key="32026R1744").short == "32026R1744"


def test_by_words_names_at_most_two_instruments_and_counts_the_rest() -> None:
    """A title has room for a name, not a list: one committed event folds seven instruments."""
    assert by_words(()) == ""
    assert by_words(_acts("A")) == "by A"
    assert by_words(_acts("A", "B")) == "by A and B"
    assert by_words(_acts("A", "B", "C")) == "by A and 2 others"


def test_the_keys_of_an_entry_are_its_changes_own_mentions_in_order_and_once_each() -> None:
    entry = attributed_entry()
    assert amending_keys(entry) == ("house-rules-amendment-1",)
    assert amending_keys(unattributed_entry()) == ()


def test_a_title_is_harvested_from_a_claim_when_the_change_carries_none() -> None:
    """The metadata path mints an amending act with no title, so the instruction parse's claim
    is where a recorded official title actually is; both places are read and the first
    non-empty wins."""
    entry = attributed_entry()
    untitled = entry.model_copy(
        update={
            "changes": tuple(
                emitted.model_copy(
                    update={
                        "change": emitted.change.model_copy(
                            update={
                                "amending_acts": tuple(
                                    ActId(corpus=act.corpus, key=act.key)
                                    for act in emitted.change.amending_acts
                                )
                            }
                        )
                    }
                )
                for emitted in entry.changes
            )
        }
    )
    assert all(
        act.display_name is None
        for emitted in untitled.changes
        for act in emitted.change.amending_acts
    )
    report = untitled.corroboration
    assert report is not None
    claimed = untitled.model_copy(
        update={
            "corroboration": report.model_copy(
                update={
                    "signals": tuple(
                        units.model_copy(
                            update={
                                "claims": (
                                    SignalClaim(
                                        location=units.units[0],
                                        amending_act=ActId(
                                            corpus="toy",
                                            key="house-rules-amendment-1",
                                            display_name="Rule change, June",
                                        ),
                                    ),
                                )
                            }
                        )
                        if units.signal is Signal.CORPUS_METADATA
                        else units
                        for units in report.signals
                    )
                }
            )
        }
    )
    collected = collect_amending((claimed,))
    assert collected["house-rules-amendment-1"].title == "Rule change, June"


def test_an_entry_with_no_corroboration_contributes_its_changes_mentions_only() -> None:
    """A diff-only entry never corroborated anything, so there is no claim list to walk and
    guarding it is the difference between a build and a crash."""
    entry = attributed_entry().model_copy(update={"corroboration": None})
    assert entry.corroboration is None
    assert mentioned_keys((entry,)) == ("house-rules-amendment-1",)


def test_the_mapping_is_sorted_by_key_so_two_builds_agree() -> None:
    entry = attributed_entry()
    collected = collect_amending(
        (entry,),
        labels={"house-rules-amendment-1": "June change", "zzz": "never mentioned"},
        numbers={"house-rules-amendment-1": ""},
        urls={},
    )
    assert list(collected) == sorted(collected)
    assert "zzz" not in collected
    assert collected["house-rules-amendment-1"].label == "June change"


def test_an_unknown_key_resolves_to_itself_rather_than_disappearing() -> None:
    entry = attributed_entry()
    (only,) = amenders({}, entry)
    assert only.key == "house-rules-amendment-1"
    assert only.short == "house-rules-amendment-1"
    assert only.number == "" and only.eurlex_url == ""


def test_the_line_links_the_number_and_keeps_the_key_beside_it() -> None:
    act = AmendingAct(
        key="32020R0561",
        number="Regulation (EU) 2020/561",
        eurlex_url="https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32020R0561",
        title="Regulation (EU) 2020/561 of the European Parliament and of the Council",
        label="MDR postponement",
    )
    (line, official) = amending_lines((act,), full=True)
    assert 'class="amending">Amended by <a href="https://eur-lex.europa.eu/' in line
    assert ">Regulation (EU) 2020/561</a>" in line
    assert '<span class="ttl">MDR postponement</span>' in line
    assert "<code>32020R0561</code>" in line
    assert official == f'<p class="official">{act.title}</p>'
    assert amending_lines((act,), full=False) == [line]


def test_a_key_that_is_not_a_celex_is_shown_bare_and_unlinked() -> None:
    """No number, no address, no code beside a name that is the code: the toy corpus's shape."""
    (line,) = amending_lines((AmendingAct(key="house-rules-amendment-1"),), full=True)
    assert line == '<p class="amending">Amended by house-rules-amendment-1</p>'


def test_an_event_naming_nothing_gets_no_line_at_all() -> None:
    """The sentence for that class is `attribution`'s; a second line would be a second answer."""
    assert amending_lines((), full=True) == []
