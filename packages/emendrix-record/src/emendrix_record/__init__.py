"""emendrix-record: the published emendrix record as a reader sees it.

The models of the root index, an act index, one payload and the site catalogue; `Record`, the
reader that reads each of those files fresh on every call; the dispute-reason sentences; and
two pure helpers over the record's keys, the anchor rule (`links`) and canonical locations
(`locations`). It reads published files only: no model, no network, no clock, no writes.

Nothing here is legal advice. See `README.md`.
"""

__all__ = ["DISCLAIMER", "__version__"]

__version__ = "0.1.0"

DISCLAIMER = (
    "Not legal advice: this output is machine-computed from published texts, "
    "carries no lawyer's review, and is engineering assistance only."
)
"""Carried by every output a reader of the record shows. The same sentence as the pipeline's,
held equal to it by a test in the `emendrix` suite, because this distribution cannot import
that one."""
