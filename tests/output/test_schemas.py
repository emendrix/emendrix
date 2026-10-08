"""The published contract: the committed JSON Schemas, and the page that documents the API.

The schemas under `docs/schema/` are generated from the models, so the drift test below fails
whenever a model's serialised shape moves, and also after a pydantic upgrade, because
`model_json_schema` output differs between pydantic minor versions. Both failures are intended:
the committed files are what consumers download, and they move only when someone regenerates
and reads them.

No JSON Schema validator is a dependency of this project, and adding one for these tests is
not worth a lockfile change, so documents are checked against their schemas by top-level key.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from index_entries import write_payload
from toy_entries import disputed_entry, toy_entry

from emendrix import DISCLAIMER
from emendrix.core.changes import DisputeReason
from emendrix.output import act_index, render_index
from emendrix.output.schemas import DIALECT, SCHEMAS, SUFFIX, schema_documents

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "docs" / "schema"
API_DOC = REPO / "docs" / "api.md"

LAYOUT = (
    "/api/",
    "/api/v1/index.json",
    "/api/v1/<act_dir>/index.json",
    "/api/v1/<act_dir>/changes/<version>.json",
    "/api/v1/catalogue.json",
    "/api/v1/schema/<name>.schema.json",
)
"""Every path the API serves, as the layout table of `docs/api.md` names it."""

_REGENERATE = (
    "uv run python -c 'from pathlib import Path; from emendrix.output.schemas import "
    'schema_documents; [Path("docs/schema", n).write_text(t, encoding="utf-8") '
    "for n, t in schema_documents().items()]'"
)


def _schema(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(schema_documents()[f"{name}{SUFFIX}"])
    return loaded


def test_the_committed_schemas_are_what_the_models_generate() -> None:
    generated = schema_documents()
    committed = {
        path.name: path.read_text(encoding="utf-8") for path in sorted(SCHEMA_DIR.glob("*.json"))
    }
    model_names = {f"{name}{SUFFIX}" for name in SCHEMAS}
    assert model_names <= set(committed), sorted(model_names - set(committed))
    assert {name: committed[name] for name in model_names} == generated, (
        f"the schemas under {SCHEMA_DIR} differ from the models; if the change is intended, "
        f"run `{_REGENERATE}` from the repository root and read the diff"
    )


def test_every_schema_identifies_itself_by_its_own_file_name() -> None:
    for file_name, text in schema_documents().items():
        document = json.loads(text)
        assert document["$id"] == file_name
        assert "/" not in document["$id"] and ":" not in document["$id"]
        assert document["$schema"] == DIALECT
        assert document["title"] == file_name.removesuffix(SUFFIX)
        assert text.endswith("}\n")


def test_the_change_schema_carries_the_computed_dispute_reason() -> None:
    change = _schema("change")["$defs"]["Change"]
    assert "dispute_reason" in change["properties"]
    assert change["properties"]["dispute_reason"]["readOnly"] is True


def test_an_act_index_event_lists_the_units_no_change_carries() -> None:
    event = _schema("act-index")["$defs"]["EventRow"]["properties"]
    assert "instruction_only_units" in event
    assert "metadata_only_units" in event


def test_a_payload_has_only_keys_its_schema_names() -> None:
    properties = _schema("entry")["properties"]
    change_properties = _schema("change")["properties"]
    for entry in (toy_entry(), disputed_entry()):
        document = json.loads(entry.to_json())
        assert set(document) <= set(properties), set(document) - set(properties)
        for change in document["changes"]:
            assert set(change) <= set(change_properties)


def test_an_index_has_only_keys_its_schema_names(tmp_path: Path) -> None:
    write_payload(tmp_path, disputed_entry())
    document = json.loads(render_index(act_index(tmp_path, "toy/house-rules")))
    assert set(document) <= set(_schema("act-index")["properties"])


def test_the_api_page_names_every_path_reason_and_the_disclaimer() -> None:
    text = API_DOC.read_text(encoding="utf-8")
    for path in LAYOUT:
        assert f"`{path}`" in text, path
    for reason in DisputeReason:
        assert f"`{reason.value}`" in text, reason
    paragraphs = [part for part in text.split("\n\n") if part.strip()]
    assert paragraphs[1].strip() == DISCLAIMER
    assert paragraphs[-1].strip() == DISCLAIMER


def test_the_ci_snippet_fetches_the_api_under_its_own_user_agent() -> None:
    text = API_DOC.read_text(encoding="utf-8")
    section = text.split("## Watch a provision from CI", 1)[1]
    match = re.search(r"```yaml\n(.*?)```", section, re.DOTALL)
    assert match is not None
    snippet = match.group(1)
    assert "emendrix-snippet/1" in snippet
    assert "/api/v1/" in snippet
    assert ".provisions[$l][0].version" in snippet
    assert "Not legal advice" in snippet
