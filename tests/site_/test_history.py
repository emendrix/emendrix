"""The inversion: every committed change reached from its coordinate instead of from its event.

Two inputs, because the properties need two shapes. The toy transition is four changes on one
act in one event, which is where "every change is in exactly one history" is checked change by
change. The generated two-hundred-event tree is where the rest has teeth: one coordinate touched
twice inside one event, one coordinate touched by all two hundred, and an ordering that a sort
on the canonical string would get wrong at `AR 10`.

The dates the same pass gathers get a third input: neither corpus writes a date, so the two
above are what proves the empty case, and the present case is a real change with dates patched
onto it. The cross-act fold over that same input is asserted here rather than beside the page
that renders it, because it is a reading of the committed record and not a rendering decision;
what the page does with it is `test_dates_page.py`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from test_act_page_at_scale import _entries as _scaled_entries

from emendrix.core import Delta, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.history import ahead, cross_act_mentions, dates_named, histories, passed_within
from emendrix.site_.inputs import ActSite, SiteInputs, collect_site
from emendrix.site_.pages.event import render_event_page
from emendrix.site_.pages.texts import text_blocks
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
OBSERVED = date(2026, 8, 9)


def _run() -> EvalRun:
    return EvalRun.model_validate_json(latest_report(REPORTS).read_bytes())


def _delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return compute_delta(before, after)


def _act(*entries: ChangelogEntry) -> ActSite:
    site = collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=entries)
    assert len(site.acts) == 1
    return site.acts[0]


def _toy() -> ActSite:
    return _act(diff_only_entry(_delta(), detected_on=OBSERVED))


def _scaled() -> ActSite:
    return _act(*_scaled_entries())


def test_every_change_of_every_event_appears_in_exactly_one_history() -> None:
    """Nothing is dropped and nothing is counted twice: the histories partition the changes.

    Counted by `(entry key, index)` rather than by coordinate, because a coordinate an event
    touched twice is the case a count by coordinate would hide.
    """
    for act in (_toy(), _scaled()):
        expected = {
            (entry.key, index) for entry in act.entries for index in range(len(entry.changes))
        }
        seen = [
            (step.entry.key, step.index) for history in histories(act) for step in history.steps
        ]
        assert sorted(seen) == sorted(expected)
        assert len(seen) == len(set(seen))


def test_steps_run_newest_first_in_the_acts_own_order() -> None:
    """The same order the act's timeline publishes, so the two cannot disagree about newest."""
    act = _scaled()
    order = [entry.key for entry in act.entries]
    for history in histories(act):
        positions = [order.index(step.entry.key) for step in history.steps]
        assert positions == sorted(positions)


def test_a_coordinate_touched_twice_in_one_event_is_two_steps_with_two_anchors() -> None:
    """The generated events touch one article twice each, which is the only input that makes
    the anchor scheme emit its `-2` suffix. Collapsing the pair would drop a committed change
    from the one page whose job is to hold every change to that coordinate."""
    act = _scaled()
    found = [
        history
        for history in histories(act)
        if len({step.entry.key for step in history.steps}) < len(history.steps)
    ]
    assert found
    for history in found:
        anchors = [step.anchor for step in history.steps]
        assert len(anchors) == len(set(anchors))


def test_one_coordinate_carries_the_whole_generated_history() -> None:
    """Every generated event touches the toy's own annex, so one history is two hundred steps
    long: the shape the page's weight decision was made for."""
    act = _scaled()
    longest = max(histories(act), key=lambda history: len(history.steps))
    assert len(longest.steps) == len(act.entries)


def test_histories_are_sorted_the_way_the_act_page_lists_provisions() -> None:
    """By `sort_key`, so `AR 10` follows `AR 9` rather than `AR 1`."""
    act = _scaled()
    keys = [history.location.sort_key for history in histories(act)]
    assert keys == sorted(keys)
    numbers = [
        history.location.canonical
        for history in histories(act)
        if history.location.canonical.startswith("AR ")
        and " " not in history.location.canonical[3:]
    ]
    assert numbers[:3] == ["AR 1", "AR 2", "AR 3"]


def test_an_act_with_no_events_has_no_histories() -> None:
    """A quiet act is a real answer here too: no coordinate was touched, so no page is due."""
    assert histories(ActSite(act=_delta().act, label="quiet")) == ()


def _dated() -> SiteInputs:
    """The toy transition with dates hung on two of its four changes, in one event.

    Patched onto real changes because the toy corpus writes no date markup: every change of it
    moves none, which is the input the empty case below wants and the wrong one for every case
    above it. One date is added by two changes at two coordinates, which is the shape a list
    keyed by the date has to get right.
    """
    delta = _delta()
    changes = list(delta.changes)
    changes[0] = changes[0].model_copy(update={"dates_added": (date(2027, 12, 2),)})
    changes[3] = changes[3].model_copy(
        update={"dates_added": (date(2027, 12, 2),), "dates_removed": (date(2026, 8, 2),)}
    )
    entry = diff_only_entry(
        delta.model_copy(update={"changes": tuple(changes)}), detected_on=OBSERVED
    )
    return collect_site(generated_on=OBSERVED, run=_run(), report=Path("r.json"), entries=(entry,))


def test_dates_named_is_sorted_by_the_date_and_then_by_the_provision() -> None:
    """By the date first, because that is what makes the list a fact about the act rather than
    a second copy of its timeline; the provision breaks the tie in the order the act page's own
    index lists coordinates in."""
    site = _dated()
    mentions = dates_named(site.acts[0])
    assert [(one.on, one.location.canonical, one.added) for one in mentions] == [
        (date(2026, 8, 2), "AN I", False),
        (date(2027, 12, 2), "AR 2", True),
        (date(2027, 12, 2), "AN I", True),
    ]


def test_one_date_two_changes_name_is_two_mentions() -> None:
    """Two provisions naming one date are two facts, and each carries its own change: merging
    them would leave a row pointing at one of the two blocks that made it."""
    mentions = [one for one in dates_named(_dated().acts[0]) if one.on == date(2027, 12, 2)]
    assert len(mentions) == 2
    assert len({one.anchor for one in mentions}) == 2


def test_every_mention_names_a_block_that_exists_on_its_own_event_page() -> None:
    """The anchors are the event page's own, not a second set minted here, so every row of the
    act's list lands on the change block that moved the date."""
    site = _dated()
    act = site.acts[0]
    entry = act.entries[0]
    rendered = render_event_page(site, act, entry, text_blocks(entry))
    mentions = dates_named(act)
    assert mentions
    for one in mentions:
        assert f'id="{one.anchor}"' in rendered


def test_an_act_whose_changes_moved_no_date_names_none() -> None:
    """The toy corpus writes no date markup at all, which is the common case in the corpus too:
    most committed changes move no date and their acts get no list."""
    for act in (_toy(), _scaled()):
        assert dates_named(act) == ()


def test_the_cross_act_fold_carries_every_mention_with_its_act() -> None:
    """One act's list read across the whole site: nothing is merged and nothing is dropped."""
    site = _dated()
    found = cross_act_mentions(site)
    assert [(one.act.act.key, one.mention.on) for one in found] == [
        ("house-rules", date(2026, 8, 2)),
        ("house-rules", date(2027, 12, 2)),
        ("house-rules", date(2027, 12, 2)),
    ]
    assert all(one.superseded_by is None for one in found)


def test_ahead_is_strict_and_the_recent_window_is_inclusive_at_both_ends() -> None:
    """A date equal to the build date has arrived, so it is behind it and inside the window."""
    found = cross_act_mentions(_dated())
    assert [one.mention.on for one in ahead(found, date(2026, 8, 2))] == [date(2027, 12, 2)] * 2
    assert [one.mention.on for one in ahead(found, date(2027, 12, 2))] == []
    assert [one.mention.on for one in passed_within(found, date(2026, 8, 2), 1)] == [
        date(2026, 8, 2)
    ]
    assert passed_within(found, date(2026, 8, 1), 1) == ()
