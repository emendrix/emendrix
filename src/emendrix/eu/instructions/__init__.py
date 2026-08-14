"""The third signal: what an amending act's own instructions say it changed.

An amending act is a list of orders (*"in Article 1(2), point (g) is replaced by the
following:"*, *"paragraph 5 is deleted;"*), and they are read structurally rather than by
regex over flattened prose. The drafting never names what it inserts, so a naive regex reaches
precision 1.000 / recall 0.857 on the Digital Omnibus and **all six of its misses are
insertions**; the number lives in the quoted `ARTICLE` element next to the instruction, which
the Formex parser recovers.

Every instruction is one `NP`: its enumerator in `NO.P`, its clause in `TXT`, and in its `P`
either a nested `LIST` of sub-instructions or the `QUOT.S` block holding the replacement text.
The clause is read with the quoted text and the sub-list excluded, because a replacement text
is another act's prose and matching an instruction verb inside it would pollute the one signal
whose value is its independence.

## Where a location comes from, in order

1. The clause's own reference, resolved inside its parent's (`eu/references.py`).
2. For an insertion, the quoted provision's identifier — `AR 4a`, `AR 5 PA 1a`, or an
   `INCL.ELEMENT` pointing at the annex document the act ships alongside (`AN XIV`).
3. Nothing: the clause is counted as an unread instruction and never guessed at.

**An insertion clause that names only a top-level unit is inserting into it, not creating it.**
The drafting never names what it inserts, so the `AR 3` of *"the following points are
inserted:"* is the host and the record is `AR 3` MODIFIED. Only rule 2 produces an insertion
of a unit.

**Which articles are read.** An amending act amends several acts in parallel articles, so the
instructions of one act's article must not be attributed to another's
(`eu/formex/amending.py`). Where **no** article names an act at all (`32020R0561` names the MDR
only in the regulation's own title) every instruction article is read, and the caller says
which act the result is about.

**A measured cross-check, never ground truth.** Two drafting shapes seen on the pinned acts
are not handled: an instruction can **delegate** (*"Annexes VI to X … are amended in accordance
with the Annex to this Regulation"*, `32022R0477`, on which the naive parser scores 0.000) and
can express **ranges**. Both are counted as unread instructions rather than approximated.

Measured 2026-08-06 over the pinned amending acts: `32026R1744` → 84 records over 45 units,
0 unread, exactly the 45 units its metadata names; `32020R0561` → 9 units, exactly the 9 its
metadata names. `tests/eu/test_instructions.py` asserts both.
"""

from __future__ import annotations

from emendrix.eu.instructions.model import (
    InstructionParse,
    InstructionRecord,
    UnreadInstruction,
)
from emendrix.eu.instructions.read import (
    AMEND,
    INSTRUCTION_VERBS,
    instruction_signal,
    parse_instructions,
)

__all__ = [
    "AMEND",
    "INSTRUCTION_VERBS",
    "InstructionParse",
    "InstructionRecord",
    "UnreadInstruction",
    "instruction_signal",
    "parse_instructions",
]
