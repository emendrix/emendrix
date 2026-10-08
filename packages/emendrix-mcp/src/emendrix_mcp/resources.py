"""The server's resources: the acts, one act, one change's first page, and the methodology.

Each is the JSON of the tool result that answers the same question, so a client reading a
resource and a model calling a tool are handed the same bytes. The methodology resource names
where the published rates live and restates none of them, so it cannot fall out of step with
them.
"""

from __future__ import annotations

from typing import Final

from mcp.server import MCPServer

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.reads import Unavailable
from emendrix_mcp.record import Record
from emendrix_mcp.tools_event import describe_act
from emendrix_mcp.tools_read import list_acts
from emendrix_mcp.tools_text import get_change

__all__ = ["ACT", "ACTS", "CHANGE", "METHODOLOGY", "methodology", "register_resources"]

ACTS: Final = "emendrix://acts"
ACT: Final = "emendrix://acts/{act}"
CHANGE: Final = "emendrix://changes/{act}/{version}/{location}"
METHODOLOGY: Final = "emendrix://methodology"

_JSON: Final = "application/json"

_NO_ADDRESS: Final = (
    "permalink unavailable: the site catalogue this server reads names no methodology page"
)


def methodology(record: Record) -> str:
    """Where the published rates live, and that this server states none of them."""
    catalogue = record.catalogue()
    where = catalogue.reason if isinstance(catalogue, Unavailable) else _NO_ADDRESS
    return (
        "How the record is made and how well it is measured is published on the methodology "
        "page of the site that serves this record: the rates, what each does and does not "
        "mean, and the date each was measured. This server restates no figure, so nothing it "
        f"says about them can go stale.\n\nMethodology page: {where}.\n\n{DISCLAIMER}\n"
    )


def register_resources(server: MCPServer, record: Record) -> None:
    """Register the four resources over `record`."""

    @server.resource(
        ACTS,
        name="acts",
        description="Every act the record holds, as `list_acts` returns them.",
        mime_type=_JSON,
    )
    def acts() -> str:
        return list_acts(record).model_dump_json(indent=2)

    @server.resource(
        ACT,
        name="act",
        description="One act, named by its bare key: its events newest first, the provisions it "
        "touched and the watch window the record covers.",
        mime_type=_JSON,
    )
    def act(act: str) -> str:
        return describe_act(record, act).model_dump_json(indent=2)

    @server.resource(
        CHANGE,
        name="change",
        description="One change, as the first page of `get_change` returns it (occurrence 1). "
        "`act` is the bare key, without its corpus.",
        mime_type=_JSON,
    )
    def change(act: str, version: str, location: str) -> str:
        return get_change(record, act, version, location).model_dump_json(indent=2)

    @server.resource(
        METHODOLOGY,
        name="methodology",
        description="Where the published rates live; it restates none of them.",
        mime_type="text/plain",
    )
    def methodology_text() -> str:
        return methodology(record)
