"""The differing passages of a twin pair, capped so that a map never becomes a copy of the text.

Each non-equal word opcode of the two comparison texts is one passage, carrying up to
`CONTEXT_WORDS` equal words either side, each side cut at `PASSAGE_CHARS` with a visible
`CUT`. At most `MAX_PASSAGES` are kept; the rest are counted. When the kept passages'
characters on either side exceed `WITHHELD_SHARE` of that side's comparison text, none is kept
and the pair says the passages were withheld: past that share an excerpt reproduces the
provision by another route, and the provision's text is the publisher's to serve.

Passages are excerpts of comparison text, words joined by single spaces, for reading where two
provisions differ. They are not verbatim text and nothing calls them so.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from emendrix.twins.model import Passage

__all__ = [
    "CONTEXT_WORDS",
    "CUT",
    "MAX_PASSAGES",
    "PASSAGE_CHARS",
    "WITHHELD_SHARE",
    "Excerpt",
    "excerpt",
]

CONTEXT_WORDS: Final = 6
PASSAGE_CHARS: Final = 400
MAX_PASSAGES: Final = 12
WITHHELD_SHARE: Final = 0.30
CUT: Final = "[…]"


@dataclass(frozen=True)
class Excerpt:
    """What a pair may show: the kept passages, how many more there were, or that none may be."""

    passages: tuple[Passage, ...]
    omitted: int
    withheld: bool


def _cut(text: str) -> tuple[str, bool]:
    if len(text) <= PASSAGE_CHARS:
        return text, False
    return text[:PASSAGE_CHARS] + CUT, True


def _span(words: Sequence[str], start: int, end: int) -> tuple[str, bool]:
    return _cut(" ".join(words[max(0, start - CONTEXT_WORDS) : end + CONTEXT_WORDS]))


def excerpt(a_text: str, b_text: str) -> Excerpt:
    """The passages two comparison texts differ by, under the caps above. Empty when equal."""
    if a_text == b_text:
        return Excerpt(passages=(), omitted=0, withheld=False)
    a_words, b_words = a_text.split(), b_text.split()
    matcher = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False)
    found: list[Passage] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        left, left_cut = _span(a_words, i1, i2)
        right, right_cut = _span(b_words, j1, j2)
        found.append(Passage(a=left, b=right, cut=left_cut or right_cut))
    kept = tuple(found[:MAX_PASSAGES])
    # The share counts what a page would show: the kept passages, context and markers included.
    shown_a = sum(len(passage.a) for passage in kept)
    shown_b = sum(len(passage.b) for passage in kept)
    if shown_a > WITHHELD_SHARE * len(a_text) or shown_b > WITHHELD_SHARE * len(b_text):
        return Excerpt(passages=(), omitted=0, withheld=True)
    return Excerpt(passages=kept, omitted=max(0, len(found) - MAX_PASSAGES), withheld=False)
