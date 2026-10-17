"""The second search file, and the script's reading of a number typed with or without hyphens.

The script's check-digit rules are a third copy of the ones the pipeline identifies numbers by
(`emendrix.eu.substances.read_identifier`), so they are run here, under Node, over the same
values `tests/eu/test_substance_numbers.py` holds the committed fixtures to printing, and every
reading has to equal the pipeline's. Node is how the script runs anywhere but a browser; a
machine without it skips that one test, and CI's runner has it.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from toy_substances import substance_site

from emendrix.eu.substances import read_identifier
from emendrix.site_.assets import search_js
from emendrix.site_.search_index import SUBSTANCE_INDEX, search_index_json, substance_index_json

FIXTURE_VALUES = (
    "1333-74-0",
    "215-605-7",
    "001-001-00-9",
    "001-003-00-X",
    "418-070-1",
    "309-00-2",
    "231-106-7",
    "231-100-4",
    "200-233-3",
    "424-550-1",
    "15110-84-6",
    "14110-84-6",
)
"""Each value `tests/eu/test_substance_numbers.py` checks the fixtures still print."""

TYPED = (
    *FIXTURE_VALUES,
    *(value.replace("-", "") for value in FIXTURE_VALUES),
    "0" + FIXTURE_VALUES[0],
    FIXTURE_VALUES[0].replace("-", chr(0x2011)),
    " " + FIXTURE_VALUES[2] + " ",
    FIXTURE_VALUES[3].lower(),
    FIXTURE_VALUES[0][:-1] + "1",
    "12",
    "hydrogen",
)
"""The fixture values as a reader might type them: as printed, without hyphens, with a leading
zero, with a non-ASCII hyphen, padded, in lower case, with a changed digit, and not numbers."""


def test_the_second_file_labels_every_number_and_the_index_no_that_lands_on_one() -> None:
    rows = json.loads(substance_index_json(substance_site()))["entries"]
    assert {row["kind"] for row in rows} == {"substance"}
    by_label = {row["label"]: row for row in rows}
    assert sorted(by_label) == ["toy-1", "toy-2", "toy-4", "toy-9", "toy-e1", "toy-e2", "toy-i1"]
    assert by_label["toy-i1"]["url"] == by_label["toy-1"]["url"] == "substances/cas-toy-1/"
    assert by_label["toy-e1"]["url"] == "substances/ec-toy-e1/"
    assert by_label["toy-1"]["title"] == "Alpha compound · house-rules"


def test_the_main_index_does_not_move_when_registers_arrive() -> None:
    site = substance_site()
    bare = site.model_copy(update={"substances": type(site.substances)()})
    assert search_index_json(site) == search_index_json(bare)
    assert json.loads(substance_index_json(bare)) == {"entries": []}
    assert "toy-1" not in search_index_json(site)


def test_the_script_fetches_the_second_file_only_when_it_can_answer() -> None:
    script = search_js()
    assert f'fetched("{SUBSTANCE_INDEX}")' in script
    assert "digits || numbers ?" in script
    assert "container.dataset.substances !== undefined" in script
    assert 'substance: "Substance"' in script
    assert "query.length >= 4 && label.startsWith(query)" in script


def _readings(values: tuple[str, ...]) -> list[list[list[str]]]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed, and it is what runs the script outside a browser")
    harness = (
        "const vm = require('vm');"
        "const context = {document: {getElementById: () => null}};"
        f"vm.runInNewContext({json.dumps(search_js())}, context);"
        f"process.stdout.write(JSON.stringify({json.dumps(list(values))}"
        ".map((value) => context.readIdentifier(value))));"
    )
    done = subprocess.run(
        [node, "-e", harness], capture_output=True, text=True, check=True, timeout=60
    )
    loaded: list[list[list[str]]] = json.loads(done.stdout)
    return loaded


def test_the_script_reads_every_typed_value_as_the_pipeline_does() -> None:
    found = _readings(TYPED)
    for value, read in zip(TYPED, found, strict=True):
        expected = [[one.scheme, one.value] for one in read_identifier(value)]
        assert read == expected, value
    assert ["cas", "1333-74-0"] in found[TYPED.index("1333740")]
    assert found[TYPED.index("2311004")] == [["cas", "2311-00-4"], ["ec", "231-100-4"]]
