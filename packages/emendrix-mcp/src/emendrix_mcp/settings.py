"""What one running server is told about its deployment, and nothing it could work out itself.

Every value comes from outside the code: the directories it reads, the `Host` values it
accepts, and where it listens. No hostname has a default, because a host written into the code
would be one deployment's address served by every other. `cli.py` builds this from the
environment and the command line; nothing else reads either.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["DEFAULT_BIND", "DEFAULT_PORT", "MCP_PATH", "Settings"]

MCP_PATH: Final = "/mcp"
"""The one fixed part of the address. The host in front of it is the deployment's."""

DEFAULT_BIND: Final = "0.0.0.0"
"""Every interface, because the server runs in a container that a proxy reaches over its network."""

DEFAULT_PORT: Final = 8000


class Settings(BaseModel):
    """One server's configuration, complete and checked before anything is read or bound."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    changelogs: Path = Field(description="The directory of a changelogs repository, read-only.")
    catalogue: Path | None = Field(
        default=None,
        description="A site build's `api/v1/catalogue.json`; without it permalinks are "
        "reported unavailable.",
    )
    allowed_hosts: tuple[str, ...] = Field(
        min_length=1, description="The `Host` values a request to the endpoint may carry."
    )
    bind: str = Field(default=DEFAULT_BIND, description="The address to listen on.")
    port: int = Field(default=DEFAULT_PORT, ge=1, le=65535, description="The port to listen on.")
