"""Whether two comparison texts differ in their numbering and in nothing else.

Two acts written as variants of each other often hold provisions whose words are the same and
whose numbers are not: their own article number, and the numbers of the provisions they refer
to. Such a pair has nothing to show but renumbering. The test replaces every number in a
numbering position with `#` and compares what is left; any other difference, a year, a word,
a comma, keeps the texts apart.

A numbering position is the number after `Article`, `Annex`, `Chapter`, `Section`, `Title`, `Part`,
`point` or `paragraph` (either case, singular or plural), with the further numbers joined to it by
`,`, `and`, `or` or `to`; and a parenthesised point label standing as a word of its own, `(a)`,
`(iv)`, `(30)`, at most three digits so `(2021)` stays text. A number is arabic with an optional
letter suffix and dotted parts (`20`, `4a`, `2.2`), an upper-case Roman numeral (`IV`) or a single
capital (`Part A`), any of them followed by parenthesised sub-labels (`10(8)`, `5(1)(a)`). A number
anywhere else is text: `26 May 2021` and `2021` are not numbering, so a changed date or a changed
amount is never one."""

from __future__ import annotations

import re
from typing import Final

__all__ = ["numbering_only", "without_numbering"]

# Numbers are masked only after a numbering noun or as a lone point label, so a date or an
# amount that differs keeps the pair apart.
_NUMBER: Final = r"(?:\d+(?:\.\d+)*[a-z]?|[IVXLC]+[a-z]?|[A-Z])(?:\((?:\d+[a-z]?|[a-z]{1,4})\))*"
_NOUN: Final = r"(?i:articles?|annex(?:es)?|chapters?|sections?|titles?|parts?|points?|paragraphs?)"
_JOIN: Final = r"(?:,\s*|\s+(?:and|or|to)\s+)"
_REFERENCE: Final = re.compile(rf"\b({_NOUN}\s+){_NUMBER}((?:{_JOIN}{_NUMBER})*)(?![\w/])")
_JOINED: Final = re.compile(rf"({_JOIN}){_NUMBER}")
# A label standing alone: `device(s)` and `(EU)` are not one, `(a)` before `(i)` is.
_LABEL: Final = re.compile(r"(?<!\S)\((?:\d{1,3}[a-z]?|[a-z]{1,4})\)(?![\w(])")


def _masked(found: re.Match[str]) -> str:
    rest = _JOINED.sub(lambda joined: f"{joined.group(1)}#", found.group(2))
    return f"{found.group(1)}#{rest}"


def without_numbering(text: str) -> str:
    """The text, whitespace collapsed, with every number in a numbering position as `#`."""
    collapsed = " ".join(text.split())
    return _LABEL.sub("(#)", _REFERENCE.sub(_masked, collapsed))


def numbering_only(a_text: str, b_text: str) -> bool:
    """True when the texts differ beyond whitespace and are equal once numbering is masked."""
    left, right = without_numbering(a_text), without_numbering(b_text)
    return " ".join(a_text.split()) != " ".join(b_text.split()) and left == right
