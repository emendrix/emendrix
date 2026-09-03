"""The inversion: every committed change reached from its coordinate instead of from its event.

Two inputs, because the properties need two shapes. The toy transition is four changes on one
act in one event, which is where "every change is in exactly one history" is checked change by
change. The generated two-hundred-event tree is where the rest has teeth: one coordinate touched
twice inside one event, one coordinate touched by all two hundred, and an ordering that a sort
on the canonical string would get wrong at `AR 10`.
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
from emendrix.site_.history import histories
from emendrix.site_.inputs import ActSite, collect_site
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
