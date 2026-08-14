"""How much of a long text the model is shown, and when that leaves it nothing to describe.

One job, kept apart from the literal prompt in `prompt.py`: that file is read as a
specification of the only non-deterministic step in the loop, and the arithmetic of what
survives a character cap is not part of what a reviewer is reading it for.

Two rules live here and they are the same rule twice. A cap that bites without saying so is a
quiet lie about what the model was shown, so `cap_text` leaves a marker naming the count it
dropped. A cap that removes the *whole* difference is worse than a lie about the evidence, it is
the absence of any, so `shows_no_difference` detects that case and the stage refuses to ask.
Neither raises: both are counted outcomes that reach the report.
"""

from __future__ import annotations

from typing import Final

from emendrix.core import Change, ChangeType

__all__ = ["NO_EVIDENCE_PAST_CAP", "cap_text", "shows_no_difference"]

_TRUNCATION: Final = "\n[… truncated by emendrix: {dropped} characters omitted …]"

NO_EVIDENCE_PAST_CAP: Final = (
    "the difference between the two versions lies beyond the characters this stage can show, so "
    "no explanation was requested"
)
"""Why a prompt can be built, be perfectly well formed, and still show the model nothing.

`cap_text` is a prefix cap, so a modification whose whole difference falls past the limit
produces two identical blocks. Asking a model about those is asking it to describe a difference
it was shown no evidence of, and what comes back is unverifiable prose the citation gate passes,
because the citation is to a real unit. Such a change ships with its verbatim texts, carrying
this reason instead of sentences, and the count reaches the report.

The refusal is about the whole difference being invisible, never about truncation as such: a
truncated prompt whose visible prefixes differ is thin evidence, and the stage still asks. The
expected refusal count over the 55 pinned subset changes is zero, derived 2026-08-09 from the
committed fixtures without a model call: the corpus's one candidate is an annex of roughly
51 000 characters a side whose first difference falls at character 8 484, well inside the
40 000-character cap. A zero means this corpus does not exercise the refusal, not that the case
is gone; synthetic tests keep the machinery honest, and a text whose difference falls past
40 000 characters is refused the same way.
"""


def cap_text(text: str, limit: int) -> tuple[str, int]:
    """Cap `text` at `limit` characters, leaving a marker naming what was dropped.

    Public because it defines *what the model was shown*, and three other places need exactly
    that string rather than the verbatim provision: the faithfulness judge, the human review
    worksheet and the gate's check that an applicability note quotes the after text. All of them
    audit whether the shipped prose follows from the evidence the model had, and a judge shown a
    shorter prefix than the explainer marks accurate sentences unfaithful for describing text it
    cannot see. Measured 2026-08-08 with the judge on its own shorter prefix: 2 of 3 failures in
    a 20-triple sample were that artifact and nothing else.
    """
    if len(text) <= limit:
        return text, 0
    dropped = len(text) - limit
    return text[:limit] + _TRUNCATION.format(dropped=dropped), dropped


def shows_no_difference(change: Change, limit: int) -> bool:
    """Whether the two texts a prompt would carry, capped at `limit`, are the same string.

    Exact equality on the capped bodies, with the truncation markers excluded because they
    report how much was dropped rather than what was shown: two texts of different lengths get
    different markers while carrying identical evidence. Not a normalised comparison either. A
    difference at the last visible character is thin evidence, but it is evidence, and the model
    can describe it.

    `MODIFIED` only. A `DEFERRED` change carries its dates in the prompt header (`DATES REMOVED`,
    `DATES ADDED`), so it has evidence of the change even when its two capped bodies match, and
    one such change is in the shipped MDR transition. A rule that ignored the change type would
    silence a change the pipeline explains perfectly well.

    Equality here already implies at least one side was cut, because the two verbatim texts of a
    modification are known to differ.
    """
    if change.change_type is not ChangeType.MODIFIED:
        return False
    if change.before is None or change.after is None:
        return False
    return change.before[:limit] == change.after[:limit]
