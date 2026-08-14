"""emendrix: a regulatory change engine.

Watches EU legislation for amendments, computes what actually changed between two
consolidated versions, and emits a reviewable changelog.

Nothing here is legal advice. See `README.md`.
"""

__all__ = ["DISCLAIMER", "__version__"]

__version__ = "0.1.0"

DISCLAIMER = (
    "Not legal advice: this output is machine-computed from published texts, "
    "carries no lawyer's review, and is engineering assistance only."
)
"""Carried by every user-facing output. It lives at the root because the CLI, the watcher and
the changelog renderer are all obliged to print it, and none of them owns it."""
