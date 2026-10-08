"""The MCP server object: seven read-only tools and four resources over one `Record`.

Building it opens nothing: no transport and no socket. Every tool is a thin wrapper that hands
its arguments to the function in `tools_*.py` that answers it, so the descriptions here are the
only thing a calling model reads that the functions do not already say.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from emendrix_mcp import DISCLAIMER, __version__
from emendrix_mcp.record import Record
from emendrix_mcp.resources import register_resources
from emendrix_mcp.tools import describe
from emendrix_mcp.tools_event import (
    DisputesResult,
    EventResult,
    HistoryResult,
    get_event,
    list_disputed,
    provision_history,
)
from emendrix_mcp.tools_read import (
    ActsResult,
    Basis,
    ChangesResult,
    ProvisionsResult,
    changes_since,
    find_provisions,
    list_acts,
)
from emendrix_mcp.tools_text import ChangeResult, get_change

__all__ = ["INSTRUCTIONS", "NAME", "TOOLS", "build_server"]

NAME: Final = "emendrix"

INSTRUCTIONS: Final = (
    "A reader of verified change records: what changed in which provision of a watched EU act, "
    "between which consolidated versions, whether three independent signals agree about it, "
    "and the file every fact was read from. Every fact was computed by a deterministic "
    "pipeline and is returned as stored. It gives no legal advice, does not read or interpret "
    "law, and decides nothing: it never works out whether, where or how something changed, "
    "and it cannot search law text or resolve a free reference such as 'Art. 50(2)'. Name an "
    "act by its key, a provision by its canonical location string (`AR 50`, `AN I`) as "
    "`list_acts` and `find_provisions` give them, and say the provenance you relied on. "
    f"{DISCLAIMER}"
)

TOOLS: Final = (
    "list_acts",
    "find_provisions",
    "changes_since",
    "provision_history",
    "get_change",
    "get_event",
    "list_disputed",
)

_READ_ONLY: Final = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, open_world_hint=False
)

Act = Annotated[str, Field(description="The act's key, or `corpus/key`, as `list_acts` gives it.")]
Location = Annotated[
    str, Field(description="A canonical location string such as `AR 50`, as the record stores it.")
]
Version = Annotated[
    str, Field(description="The version an event produced, or its entry key, as stored.")
]


def build_server(record: Record) -> MCPServer:
    """The configured server over `record`, with no transport attached."""
    server = MCPServer(NAME, instructions=INSTRUCTIONS, version=__version__)

    @server.tool(
        name="list_acts",
        annotations=_READ_ONLY,
        description=describe(
            "List the acts the record holds, with each act's label, aliases and sector from the "
            "site catalogue, its newest version, `updated_on` and the counts its index carries. "
            "`query` matches names case-insensitively; `domain` matches the catalogue's sector. "
            "An empty list means no held act matches."
        ),
    )
    def list_acts_tool(
        query: Annotated[str | None, Field(description="Part of a key, title or alias.")] = None,
        domain: Annotated[str | None, Field(description="A catalogue sector.")] = None,
    ) -> ActsResult:
        return list_acts(record, query, domain)

    @server.tool(
        name="find_provisions",
        annotations=_READ_ONLY,
        description=describe(
            "Find touched provisions of one act whose canonical location string or stored "
            "heading contains `query`, each with its newest row. It never reads law text; an "
            "empty list means no touched provision of the act has that name in the window."
        ),
    )
    def find_provisions_tool(
        act: Act,
        query: Annotated[str, Field(description="Part of a location (`AR 5`) or a heading.")],
    ) -> ProvisionsResult:
        return find_provisions(record, act, query)

    @server.tool(
        name="changes_since",
        annotations=_READ_ONLY,
        description=describe(
            "List recorded changes whose `basis` date is on or after `since`, newest first, "
            "with each row's event and provision pages: `updated_on` (the event or its latest "
            "repair), `detected_on` (when the run saw the event) or `in_force` (the change's "
            "in-force date; rows without one are left out). `omitted` counts rows past `limit`. "
            "An empty list means no recorded change in the window has that date."
        ),
    )
    def changes_since_tool(
        since: Annotated[date, Field(description="The earliest date, YYYY-MM-DD.")],
        acts: Annotated[list[str] | None, Field(description="Act keys; all when omitted.")] = None,
        basis: Annotated[Basis, Field(description="Which stored date to compare.")] = "updated_on",
        include_disputed: Annotated[bool, Field(description="Keep disputed rows.")] = True,
        limit: Annotated[int, Field(description="At most this many rows, 1 to 500.")] = 50,
    ) -> ChangesResult:
        chosen = None if acts is None else tuple(acts)
        return changes_since(record, since, chosen, basis, include_disputed, limit)

    @server.tool(
        name="provision_history",
        annotations=_READ_ONLY,
        description=describe(
            "Every recorded change to one top-level provision, newest first, with the window "
            "the record covers for the act. An empty list means no recorded change to that "
            "provision in the window, and the result says so in words."
        ),
    )
    def provision_history_tool(act: Act, location: Location) -> HistoryResult:
        return provision_history(record, act, location)

    @server.tool(
        name="get_change",
        annotations=_READ_ONLY,
        description=describe(
            "One change in full: the verbatim text before and after, each side cut at "
            "`max_chars` (1 to 50000) with a marker '[… N characters omitted, continue with "
            "offset=M]' and paged by `offset`; the cited sentences with their URLs; "
            "`changed_within`; the three signals with their detail; `dispute_reason` and its "
            "sentence; `in_force`; `applies_from` with its reason; amending acts; the gate "
            "outcome or why it is unexplained. `occurrence` counts repeats of one location "
            "in one event from 1."
        ),
    )
    def get_change_tool(
        act: Act,
        version: Version,
        location: Location,
        occurrence: Annotated[int, Field(description="Which repeat, from 1.")] = 1,
        max_chars: Annotated[int, Field(description="Characters per side, 1 to 50000.")] = 8000,
        offset: Annotated[int, Field(description="Where each side's page starts.")] = 0,
    ) -> ChangeResult:
        return get_change(record, act, version, location, occurrence, max_chars, offset)

    @server.tool(
        name="get_event",
        annotations=_READ_ONLY,
        description=describe(
            "One event of one act: its counts, repairs and stored corroboration (each signal's "
            "units, the pairwise agreements and disagreements), the units only the metadata or "
            "only the instruction parse names, and every row of the event."
        ),
    )
    def get_event_tool(act: Act, version: Version) -> EventResult:
        return get_event(record, act, version)

    @server.tool(
        name="list_disputed",
        annotations=_READ_ONLY,
        description=describe(
            "Disputed rows grouped by their stored `dispute_reason`, each group with the "
            "sentence the site prints for that code. `omitted` counts rows past `limit`. An "
            "empty list means no recorded change in the window is disputed for that filter."
        ),
    )
    def list_disputed_tool(
        act: Annotated[str | None, Field(description="One act's key; all when omitted.")] = None,
        reason: Annotated[str | None, Field(description="One `dispute_reason` code.")] = None,
        limit: Annotated[int, Field(description="At most this many rows, 1 to 2000.")] = 200,
    ) -> DisputesResult:
        return list_disputed(record, act, reason, limit)

    register_resources(server, record)
    return server
