"""EMIT hands the output writer a register snapshot, and only for an act with a profiled table.

A run over two committed REACH packages, offline through the pinned fixture set, carries the
newer version's whole table reading; a run over the toy corpus, which has no tables, carries
none. The snapshot rides in memory and never in the serialised report. The model is the stub
`citing_offered`, so nothing here is evidence about explanations.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from emendrix.core import ProvisionTree, VersionId
from emendrix.eu.identifiers import Celex, act_id
from emendrix.graph import PipelineDeps, PipelineState, RunReport, build_pipeline, run_pipeline
from emendrix.graph.cli import _write_changelog
from emendrix.output import register_path
from emendrix.session import adapter_for
from emendrix.watch.events import AmendmentEvent
from eu_pins import FIXTURE_DIR, OBSERVED_ON, REACH
from stub_engine import citing_offered, engine
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

BEFORE = VersionId("02006R1907-20160203")
AFTER = VersionId("02006R1907-20160308")


def _event(act_key: str, before: VersionId, after: VersionId) -> AmendmentEvent:
    act = HOUSE_RULES if act_key == HOUSE_RULES.key else act_id(Celex.parse(act_key))
    return AmendmentEvent(
        act=act,
        target_version=after,
        new_version=after,
        previous_version=before,
        trigger="fixture:register",
        observed_on=OBSERVED_ON,
    )


def _run(deps: PipelineDeps, event: AmendmentEvent) -> RunReport:
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps, watch=False),
            PipelineState(observed_on=OBSERVED_ON, events=(event,)),
        )
    )
    assert final.report is not None
    return final.report


def test_a_reach_run_emits_the_newer_side_whole(tmp_path: Path) -> None:
    with adapter_for(FIXTURE_DIR, OBSERVED_ON) as adapter:
        deps = PipelineDeps(
            adapter=adapter, engine=engine(citing_offered()), observed_on=OBSERVED_ON
        )
        report = _run(deps, _event(REACH, BEFORE, AFTER))
        after = adapter.fetch_version(act_id(Celex.parse(REACH)), AFTER)
    assert isinstance(after, ProvisionTree)
    (delta,) = report.deltas
    snapshot = delta.register_snapshot
    assert snapshot is not None
    assert snapshot.version == AFTER
    assert len(snapshot.reading.entries) == len(after.table_entries.entries) > 0
    assert snapshot.reading == after.table_entries
    assert "register_snapshot" not in report.model_dump_json()

    _write_changelog(report, tmp_path / "changelog")
    written = tmp_path / "changelog" / register_path(delta.act)
    assert written.is_file()
    assert f'"version": "{AFTER}"' in written.read_text(encoding="utf-8")


def test_a_toy_run_emits_no_snapshot() -> None:
    deps = PipelineDeps(
        adapter=ToyCorpusAdapter(observed_on=OBSERVED_ON),
        engine=engine(citing_offered()),
        observed_on=OBSERVED_ON,
    )
    report = _run(deps, _event(HOUSE_RULES.key, V1, V2))
    (delta,) = report.deltas
    assert delta.register_snapshot is None
