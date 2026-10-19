"""The register: one version's whole table reading, rendered byte-stable with its gaps counted.

Built over invented keys and cells (`toy_snapshot`), so nothing here is law and nothing knows
which act, annex or column: the generic half of the writer. The committed schema is held to the
model by the drift test, as every other committed schema is.
"""

from __future__ import annotations

import json
from pathlib import Path

from emendrix import DISCLAIMER
from emendrix.core import (
    ActId,
    EntryTable,
    Identifier,
    KeyRef,
    ProvisionLocation,
    TableEntry,
    TableReading,
    TableRef,
    VersionId,
)
from emendrix.graph.report import RegisterSnapshot
from emendrix.output import REGISTER_SCHEMA, register_for, register_path, render_register
from emendrix.output.schemas import COMMITTED, SCHEMAS, schema_documents

REPO = Path(__file__).resolve().parents[2]
TOY = ActId(corpus="toy", key="house-rules", display_name="House Rules of Flat 3B")
UNIT = ProvisionLocation.parse("AN I")


def _entry(
    key: str | None, text: str, *, occurrence: int = 1, code: str | None = None
) -> TableEntry:
    return TableEntry(
        unit=UNIT,
        container=UNIT,
        table=1,
        key=key,
        occurrence=occurrence,
        rows=((key, text, code),),
        identifiers=() if code is None else (Identifier(scheme="code", value=code),),
        name=text,
    )


def toy_reading() -> TableReading:
    """One table of house rules: two numbered rows, a number printed twice, an unnumbered row."""
    return TableReading(
        tables=(
            EntryTable(
                unit=UNIT, container=UNIT, table=1, key_label="No", header=(("No", "Rule", "Code"),)
            ),
        ),
        entries=(
            _entry("2", "Keep the stairwell clear", code="100-00-5"),
            _entry("10", "Bicycles stay in the yard"),
            _entry("2", "Quiet after ten", occurrence=2),
            _entry(None, "Unnumbered note on bins"),
        ),
        unrecognised=(
            TableRef(
                unit=ProvisionLocation.parse("AN II"),
                container=ProvisionLocation.parse("AN II"),
                table=1,
            ),
        ),
    )


def toy_snapshot() -> RegisterSnapshot:
    """The reading as the loop hands it to the writer, for the act's version `v3`."""
    return RegisterSnapshot(act=TOY, version=VersionId("v3"), reading=toy_reading())


def test_the_register_carries_the_whole_reading_in_document_order() -> None:
    register = register_for(toy_snapshot())
    assert (register.corpus, register.key, register.version) == ("toy", "house-rules", "v3")
    assert register.register_schema == REGISTER_SCHEMA
    assert register.disclaimer == DISCLAIMER
    assert [(entry.key, entry.occurrence) for entry in register.entries] == [
        ("2", 1),
        ("10", 1),
        ("2", 2),
        (None, 1),
    ]
    assert register.tables == toy_reading().tables
    assert register.unrecognised == toy_reading().unrecognised


def test_the_coverage_counts_what_the_reading_could_not_key_or_read() -> None:
    coverage = register_for(toy_snapshot()).coverage
    assert coverage.unrecognised_tables == 1
    assert coverage.unkeyed_rows == 1
    assert coverage.failed_check_digits == 0
    assert coverage.repeated_keys == (KeyRef(container=UNIT, table=1, key="2"),)


def test_the_rendered_register_is_indented_newline_terminated_and_byte_stable() -> None:
    text = render_register(register_for(toy_snapshot()))
    assert text.endswith("}\n")
    assert text.startswith('{\n  "register_schema": "1.0",\n')
    assert text == render_register(register_for(toy_snapshot()))
    document = json.loads(text)
    assert list(document) == [
        "register_schema",
        "disclaimer",
        "corpus",
        "key",
        "version",
        "tables",
        "entries",
        "unrecognised",
        "coverage",
    ]
    assert document["entries"][0]["rows"] == [["2", "Keep the stairwell clear", "100-00-5"]]
    assert document["entries"][0]["identifiers"] == [{"scheme": "code", "value": "100-00-5"}]
    assert document["unrecognised"] == [{"unit": "AN II", "container": "AN II", "table": 1}]


def test_the_register_sits_beside_the_act_index() -> None:
    assert register_path(TOY) == "toy/house-rules/register.json"


def test_the_committed_register_schema_is_what_the_model_generates() -> None:
    """The register's schema is committed with the others and served with them."""
    assert "register" in COMMITTED
    assert "register" in SCHEMAS
    committed = (REPO / "docs" / "schema" / "register.schema.json").read_text(encoding="utf-8")
    assert committed == schema_documents(COMMITTED)["register.schema.json"]
    properties = json.loads(committed)["properties"]
    assert set(properties) == set(json.loads(render_register(register_for(toy_snapshot()))))
