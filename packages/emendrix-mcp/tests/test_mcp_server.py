"""The built server, read through the SDK's own in-process client.

What a calling model sees is the tool list, each tool's description and schemas, and the
resources, so those are what is checked, through the same client API any MCP host uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import anyio
import mcp

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.record import Record
from emendrix_mcp.resources import ACT, ACTS, CHANGE, METHODOLOGY
from emendrix_mcp.server import TOOLS, build_server
from emendrix_mcp.tools import APPLIES_FROM_SENTENCE, DISPUTED_SENTENCE, WINDOW_SENTENCE
from emendrix_mcp.tools_text import get_change

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _with_client[T](use: Callable[[mcp.Client], Awaitable[T]]) -> T:
    server = build_server(Record(FIXTURES / "changelogs", FIXTURES / "catalogue.json"))

    async def main() -> T:
        async with mcp.Client(server) as client:
            return await use(client)

    return anyio.run(main)


def test_the_server_lists_exactly_the_seven_tools() -> None:
    async def use(client: mcp.Client) -> list[str]:
        return [tool.name for tool in (await client.list_tools()).tools]

    assert sorted(_with_client(use)) == sorted(TOOLS)
    assert len(TOOLS) == 7


def test_every_tool_description_says_what_an_answer_means() -> None:
    async def use(client: mcp.Client) -> list[mcp.types.Tool]:
        return list((await client.list_tools()).tools)

    for tool in _with_client(use):
        assert tool.description is not None
        for sentence in (DISCLAIMER, APPLIES_FROM_SENTENCE, DISPUTED_SENTENCE, WINDOW_SENTENCE):
            assert sentence in tool.description, (tool.name, sentence)
        assert tool.output_schema is not None, tool.name
        assert "disclaimer" in tool.output_schema["properties"], tool.name


def test_the_server_lists_the_four_resources() -> None:
    async def use(client: mcp.Client) -> tuple[set[str], set[str]]:
        static = {str(resource.uri) for resource in (await client.list_resources()).resources}
        listed = (await client.list_resource_templates()).resource_templates
        return static, {template.uri_template for template in listed}

    static, templates = _with_client(use)
    assert static == {ACTS, METHODOLOGY}
    assert templates == {ACT, CHANGE}


def test_the_instructions_say_what_the_server_is_and_is_not() -> None:
    async def use(client: mcp.Client) -> str | None:
        return client.instructions

    instructions = _with_client(use)
    assert instructions is not None
    assert DISCLAIMER in instructions
    assert "decides nothing" in instructions and "no legal advice" in instructions


def test_a_tool_call_returns_its_structured_result() -> None:
    async def use(client: mcp.Client) -> object:
        arguments = {"act": "house-rules", "version": "v3", "location": "AR 9"}
        result = await client.call_tool("get_change", arguments)
        assert not result.is_error
        return result.structured_content

    content = _with_client(use)
    assert isinstance(content, dict)
    assert content["disclaimer"] == DISCLAIMER
    assert content["change"]["row"]["dispute_reason"] == "textless_metadata_only"


def test_the_change_resource_is_the_first_page_of_get_change() -> None:
    record = Record(FIXTURES / "changelogs", FIXTURES / "catalogue.json")

    async def use(client: mcp.Client) -> str:
        read = await client.read_resource("emendrix://changes/house-rules/v2/AR%202")
        content = read.contents[0]
        assert isinstance(content, mcp.types.TextResourceContents)
        return content.text

    expected = get_change(record, "house-rules", "v2", "AR 2").model_dump_json(indent=2)
    assert _with_client(use) == expected


def test_the_act_resource_reads_by_key() -> None:
    async def use(client: mcp.Client) -> str:
        content = (await client.read_resource("emendrix://acts/house-rules")).contents[0]
        assert isinstance(content, mcp.types.TextResourceContents)
        return content.text

    text = _with_client(use)
    assert '"key": "house-rules"' in text and DISCLAIMER in text
