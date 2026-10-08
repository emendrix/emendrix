"""emendrix-mcp: a read-only MCP server over a published emendrix changelogs repository.

It hands a calling model the verified record as stored and decides nothing: no model, no diff,
no classifier, no network beyond the port it listens on. It reads the published files of one
changelogs repository and one site build from directories it is given.

Nothing here is legal advice. See `README.md`.
"""

__all__ = ["DISCLAIMER", "__version__"]

__version__ = "0.1.0"

DISCLAIMER = (
    "Not legal advice: this output is machine-computed from published texts, "
    "carries no lawyer's review, and is engineering assistance only."
)
"""Carried by every tool result. The same sentence as the pipeline's, held equal to it by a test
in the `emendrix` suite, because this distribution cannot import that one."""
