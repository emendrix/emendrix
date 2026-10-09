"""The reader of the record, `emendrix-record`, stays in step with what this package writes.

Every reader beside the pipeline (the MCP server among them) reads through that member, which
cannot import `emendrix`, so it carries its own models of the index, the catalogue and one
payload, its own copy of the disclaimer, of the dispute-reason sentences and of the anchor
rule. This module and `test_record_fixture.py` are the only places that import both, and this
one holds every copy to its original, and the tools `docs/api.md` and the `/api/` page list to
the ones the MCP server registers.

The models are compared through their JSON Schemas, walked recursively: `emendrix`'s in
serialisation mode, which is what it writes, against the member's in validation mode, which is
what it accepts. For the index and the catalogue the member must accept every field the writer
emits, because the server hands those documents over whole. For a payload it reads a subset,
so the direction turns: every field the member declares must be one the writer emits, with a
type the member accepts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import mcp
import pytest
from pydantic import BaseModel

import emendrix
import emendrix_record
from emendrix.graph.report import EmittedChange
from emendrix.output import ChangelogEntry
from emendrix.output import index_model as written
from emendrix.site_ import api_files
from emendrix.site_.dispute import REASON_SENTENCES
from emendrix.site_.pages.api_prose import MCP
from emendrix.site_.urls import change_anchor, entry_anchors
from emendrix_mcp.server import build_server
from emendrix_record import links
from emendrix_record import models as read
from emendrix_record import payload as payload_models
from emendrix_record.reasons import REASON_SENTENCES as RECORD_REASON_SENTENCES
from emendrix_record.record import Record

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "packages" / "emendrix-record" / "tests" / "fixtures"

Schema = dict[str, Any]

WHOLE: tuple[tuple[type[BaseModel], type[BaseModel]], ...] = (
    (read.RootIndex, written.RootIndex),
    (read.ActIndex, written.ActIndex),
    (read.Catalogue, api_files.Catalogue),
)
"""Documents the member reads whole: it must accept every field the writer emits."""

SUBSET: tuple[tuple[type[BaseModel], type[BaseModel]], ...] = (
    (payload_models.Payload, ChangelogEntry),
    (payload_models.ChangeRecord, EmittedChange),
)
"""Documents the member reads part of: every field it declares must be one the writer emits."""


def _resolve(schema: Schema, root: Schema) -> Schema:
    while "$ref" in schema:
        name = schema["$ref"].removeprefix("#/$defs/")
        schema = {**root["$defs"][name], **{k: v for k, v in schema.items() if k != "$ref"}}
    return schema


def _type(schema: Schema) -> str | None:
    if "type" in schema:
        kind: str = schema["type"]
        return kind
    if "const" in schema:
        value = schema["const"]
        return {str: "string", bool: "boolean", int: "integer", float: "number"}.get(type(value))
    return None


def _values(schema: Schema) -> set[Any] | None:
    if "const" in schema:
        return {schema["const"]}
    return set(schema["enum"]) if "enum" in schema else None


class _Walk:
    """One comparison: `member` read from `member_root`, `writer` read from `writer_root`."""

    def __init__(self, member_root: Schema, writer_root: Schema, *, subset: bool) -> None:
        self.member_root = member_root
        self.writer_root = writer_root
        self.subset = subset

    def mismatches(self, member: Schema, writer: Schema, path: str) -> Iterator[str]:
        member = _resolve(member, self.member_root)
        writer = _resolve(writer, self.writer_root)
        if "anyOf" in writer:
            for branch in writer["anyOf"]:
                yield from self.mismatches(member, branch, path)
            return
        if "anyOf" in member:
            if not any(
                not list(self.mismatches(branch, writer, path)) for branch in member["anyOf"]
            ):
                yield f"{path}: no branch of the member's type accepts {writer}"
            return
        if not member or member.keys() <= {"description", "title", "default", "readOnly"}:
            return
        yield from self._scalar(member, writer, path)
        if _type(writer) == "object":
            yield from self._object(member, writer, path)
        elif _type(writer) == "array":
            yield from self._array(member, writer, path)

    def _scalar(self, member: Schema, writer: Schema, path: str) -> Iterator[str]:
        kinds = (_type(member), _type(writer))
        if kinds[0] != kinds[1] and kinds != ("number", "integer"):
            yield f"{path}: the member reads {kinds[0]} where the writer emits {kinds[1]}"
            return
        allowed, emitted = _values(member), _values(writer)
        if allowed is not None and (emitted is None or not emitted <= allowed):
            yield f"{path}: the member accepts {allowed} where the writer emits {emitted}"
        if "format" in member and member["format"] != writer.get("format"):
            yield f"{path}: the member reads format {member['format']}, the writer emits " + str(
                writer.get("format")
            )

    def _object(self, member: Schema, writer: Schema, path: str) -> Iterator[str]:
        ours: Schema = member.get("properties", {})
        theirs: Schema = writer.get("properties", {})
        names = ours if self.subset else theirs
        for name in names:
            if name not in ours:
                yield f"{path}.{name}: the writer emits it and the member has no such field"
            elif name not in theirs:
                yield f"{path}.{name}: the member declares it and the writer emits no such field"
            else:
                yield from self.mismatches(ours[name], theirs[name], f"{path}.{name}")
        if isinstance(writer.get("additionalProperties"), dict):
            yield from self.mismatches(
                member.get("additionalProperties", {}),
                writer["additionalProperties"],
                f"{path}[*]",
            )

    def _array(self, member: Schema, writer: Schema, path: str) -> Iterator[str]:
        if "prefixItems" in writer:
            ours = member.get("prefixItems", [member.get("items", {})] * len(writer["prefixItems"]))
            for position, (mine, theirs) in enumerate(
                zip(ours, writer["prefixItems"], strict=True)
            ):
                yield from self.mismatches(mine, theirs, f"{path}[{position}]")
        else:
            yield from self.mismatches(
                member.get("items", {}), writer.get("items", {}), f"{path}[]"
            )


def _mismatches(member: type[BaseModel], writer: type[BaseModel], *, subset: bool) -> list[str]:
    ours = member.model_json_schema(mode="validation")
    theirs = writer.model_json_schema(mode="serialization")
    walk = _Walk(ours, theirs, subset=subset)
    return list(walk.mismatches(ours, theirs, member.__name__))


@pytest.mark.parametrize(("member", "writer"), WHOLE, ids=lambda model: model.__name__)
def test_the_member_accepts_every_field_the_writer_emits(
    member: type[BaseModel], writer: type[BaseModel]
) -> None:
    assert _mismatches(member, writer, subset=False) == []


@pytest.mark.parametrize(("member", "writer"), SUBSET, ids=lambda model: model.__name__)
def test_every_payload_field_the_member_reads_is_one_the_writer_emits(
    member: type[BaseModel], writer: type[BaseModel]
) -> None:
    assert _mismatches(member, writer, subset=True) == []


def test_the_walk_notices_a_field_the_member_lacks() -> None:
    class Narrow(BaseModel):
        acts: tuple[str, ...]

    class Retyped(BaseModel):
        structural_diff: int
        corpus_metadata: str
        instruction_parse: str

    class Nested(BaseModel):
        signals: Retyped

    assert _mismatches(Narrow, written.RootIndex, subset=False)
    assert _mismatches(read.RootIndex, written.ActRow, subset=True)
    assert _mismatches(Nested, written.ProvisionRow, subset=True) == [
        "Nested.signals.structural_diff: the member reads integer where the writer emits string"
    ]


def test_the_disclaimer_is_the_same_sentence() -> None:
    assert emendrix_record.DISCLAIMER == emendrix.DISCLAIMER


def test_the_dispute_reason_sentences_are_the_sites() -> None:
    assert {code.value: text for code, text in REASON_SENTENCES.items()} == RECORD_REASON_SENTENCES


def _documents(pattern: str) -> list[Path]:
    found = sorted((FIXTURES / "changelogs").glob(pattern))
    assert found, pattern
    return found


def test_every_member_model_parses_the_fixture() -> None:
    whole: list[tuple[type[BaseModel], Path]] = [
        (read.RootIndex, FIXTURES / "changelogs" / "index.json"),
        *((read.ActIndex, path) for path in _documents("*/*/index.json")),
        (read.Catalogue, FIXTURES / "catalogue.json"),
    ]
    for model, path in whole:
        raw = path.read_bytes()
        assert model.model_validate_json(raw).model_dump(mode="json") == json.loads(raw), path
    for path in _documents("*/*/changes/*.json"):
        payload = payload_models.Payload.model_validate_json(path.read_bytes())
        entry = ChangelogEntry.model_validate_json(path.read_bytes())
        assert len(payload.changes) == len(entry.changes) > 0
        for ours, theirs in zip(payload.changes, entry.changes, strict=True):
            assert ours.change.provision.location == theirs.change.location.canonical
            assert ours.change.before == theirs.change.before
            assert ours.change.after == theirs.change.after


def test_links_match_the_site() -> None:
    """The member's anchor rule is the site's, for every fixture location and a deep one."""
    entries = [
        ChangelogEntry.model_validate_json(path.read_bytes())
        for path in _documents("*/*/changes/*.json")
    ]
    locations = {change.change.location.canonical for entry in entries for change in entry.changes}
    locations |= {"AR 5 PA 1 ALN 1 PTA (bb)"}
    for canonical in sorted(locations):
        for occurrence in (1, 2, 3):
            ours = links.change_anchor("v2", canonical, occurrence)
            assert ours == change_anchor("v2", canonical, occurrence)
        assert links.location_slug(canonical) in links.change_anchor("v2", canonical)
    for entry in entries:
        canonicals = [change.change.location.canonical for change in entry.changes]
        assert links.entry_anchors(entry.key, canonicals) == entry_anchors(entry.key, canonicals)
    for refused in (0, -1):
        with pytest.raises(ValueError):
            links.change_anchor("v2", "AR 5", refused)
        with pytest.raises(ValueError):
            change_anchor("v2", "AR 5", refused)


def _registered() -> list[str]:
    server = build_server(Record(FIXTURES / "changelogs", FIXTURES / "catalogue.json"))

    async def main() -> list[str]:
        async with mcp.Client(server) as client:
            return [tool.name for tool in (await client.list_tools()).tools]

    return anyio.run(main)


def test_the_documented_tools_are_the_ones_the_server_registers() -> None:
    """`docs/api.md` lists every tool in a table, in the order the server registers them."""
    text = (REPO / "docs" / "api.md").read_text(encoding="utf-8")
    section = text.split("\n## MCP server\n", 1)[1].split("\n### ", 1)[0]
    documented = re.findall(r"^\| `([a-z_]+)` \|", section, re.MULTILINE)
    assert documented == _registered()


def test_the_api_page_names_the_tools_the_server_registers() -> None:
    """The `/api/` page lists the tools in one sentence, in the order the server registers them."""
    listed = MCP.split("seven tools are", 1)[1].split("four resources", 1)[0]
    assert re.findall(r"`([a-z_]+)`", listed) == _registered()
