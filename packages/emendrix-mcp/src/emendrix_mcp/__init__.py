"""emendrix-mcp: a read-only MCP server over a published emendrix changelogs repository.

It hands a calling model the verified record as stored and decides nothing: no model, no diff,
no classifier, no network beyond the port it listens on. It reads the published files of one
changelogs repository and one site build from directories it is given, through
`emendrix_record`.

Nothing here is legal advice. See `README.md`.
"""

from emendrix_record import DISCLAIMER

__all__ = ["DISCLAIMER", "__version__"]

__version__ = "0.1.0"
