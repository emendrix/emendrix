"""The published JSON Schemas: one per document a consumer of the record can fetch.

Generated from the models that write and read those documents, so a schema cannot describe a
field the code does not produce. They are built in serialisation mode because a consumer reads
what was written: dates are strings, and `dispute_reason`, which the model computes rather than
stores, appears as the read-only property every change read through the model carries.

Each document's `$id` is its own file name. JSON Schema 2020-12 resolves a relative `$id`
against the address the document was fetched from, so the same bytes are correct wherever they
are served and in the repository's own `docs/schema/`, and no deployment's address is written
into code. The text is produced here rather than read from `docs/` because a site built from an
installed package has no `docs/` to read.
"""

from __future__ import annotations

import json
from typing import Final

from pydantic import BaseModel

from emendrix.graph.report import EmittedChange
from emendrix.output.index_model import ActIndex, RootIndex
from emendrix.output.json_out import ChangelogEntry

__all__ = ["DIALECT", "SCHEMAS", "SUFFIX", "schema_document", "schema_documents"]

DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"
"""The JSON Schema dialect every document declares."""

SUFFIX: Final = ".schema.json"
"""What a schema's name is followed by in its file name."""

SCHEMAS: Final[dict[str, type[BaseModel]]] = {
    "act-index": ActIndex,
    "change": EmittedChange,
    "entry": ChangelogEntry,
    "index": RootIndex,
}
"""Each published name and the model whose serialised form it describes."""


def schema_document(name: str, model: type[BaseModel]) -> str:
    """The schema of `model`'s serialised form, as the text of `<name>.schema.json`."""
    schema = model.model_json_schema(mode="serialization")
    schema["$schema"] = DIALECT
    schema["$id"] = f"{name}{SUFFIX}"
    schema["title"] = name
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def schema_documents() -> dict[str, str]:
    """`<name>.schema.json` to its text, for every published schema, in name order."""
    return {f"{name}{SUFFIX}": schema_document(name, SCHEMAS[name]) for name in sorted(SCHEMAS)}
