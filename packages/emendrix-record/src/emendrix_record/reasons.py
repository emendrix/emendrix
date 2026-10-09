"""What each `dispute_reason` code means, one plain sentence per code.

The site prints the same sentences beside a disputed change, and a test in the `emendrix` suite
holds this copy equal to the site's key for key, so whoever reads the record through this
distribution and a reader of the page are told the same thing. A sentence says which source saw
what, never why the legislator did anything.
"""

from __future__ import annotations

from typing import Final

__all__ = ["REASON_SENTENCES"]

REASON_SENTENCES: Final[dict[str, str]] = {
    "kind_mismatch": "No one kind of change is named by every source that found it.",
    "textless_both_others": "Two sources name it, and neither carries any text.",
    "textless_metadata_only": "Only the EU's own amendment metadata names it, and it carries "
    "no text.",
    "textless_instruction_only": "Only the amending act's instructions name it, and they carry "
    "no text.",
    "both_others_silent": "Only the text comparison found it.",
    "metadata_silent": "The source that does not name it is the EU's own amendment metadata.",
    "instruction_silent": "The source that does not name it is the amending act's instructions.",
}
