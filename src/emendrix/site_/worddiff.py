"""A deterministic word-level diff for the unified track-changes view.

The stored provision texts are verbatim and stay verbatim; this module renders a
*comparison* of two of them. Which tokens differ is decided on words alone, so the amount
of whitespace between two words never counts as a change, and neither does a line break:
the matcher is built from `str.split()` and sees no whitespace at all.

What the matcher ignores, the rendering keeps. Stored text carries a line break at every
block boundary the source document opened, so a provision has a title, a subtitle and a
paragraph per line, and a view that joined every token with a single space would throw that
structure away and hand the reader one wall of prose. So each token is recorded with the
separator that followed it, `\\n` where the whitespace run that followed it contained a line
break and a space otherwise, and a span is rendered with the separators its own tokens had.

The two halves are deliberately independent: adding a line break to a document changes what
this module *renders* and cannot change what it *reports*, which is the property the tests
pin.

`SIMILARITY_FLOOR` exists because `difflib` on two texts with almost nothing in common
produces a wall of struck-through text interleaved with insertions, which reads worse than
the two texts shown whole. Below the floor the page falls back to stacked before/after
blocks and says so.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "LINE_TOKEN_CEILING",
    "SIMILARITY_FLOOR",
    "Comparison",
    "DiffSpan",
    "Granularity",
    "Opcode",
    "Tokens",
    "assemble",
    "compare",
    "opcodes",
    "similarity",
    "tokenise",
    "word_diff",
]

LINE_TOKEN_CEILING: Final = 20_000
"""Above this many tokens on either side, the comparison is made line by line instead.

`difflib` with `autojunk=False` costs roughly the product of the two token counts, so the
word-granularity comparison is fine for a provision and hopeless for a table. Measured on
the committed corpus on 2026-08-13: a 48 815-token provision takes 4.9 seconds a side and
CLP's Annex VI, at 266 289 tokens, takes 34.6. Annex VI appears in 30 of CLP's transitions,
which on its own is enough to push a whole-site rebuild past the hour a scheduled run gets.

20 000 is chosen below the knee rather than at it: 39 287 tokens still measured 0.3 seconds
and 48 815 measured 4.9, so the cost turns sharply somewhere between, and the ceiling sits
far enough below that the turn is never reached. For a table a line is a row, so above the
ceiling the unit of change becomes the row, which is what a reader of a classification
table wants anyway.
"""

SIMILARITY_FLOOR: Final = 0.5
"""Below this token-level ratio the unified view degenerates and the page stacks instead.

0.5 is where less than half of the shorter text survives into the longer one; at that point
the diff is mostly markup and the reader is better served by two clean texts.
"""

_WHITESPACE: Final = re.compile(r"\s+")

Granularity = Literal["word", "line"]
"""What a token was, and therefore what a reported change is a change to."""

Opcode = tuple[Literal["equal", "replace", "delete", "insert"], int, int, int, int]
"""One `SequenceMatcher.get_opcodes()` row: what to do, and the two token ranges it covers."""

Separator = Literal[" ", "\n", ""]
"""What sits between two tokens once the run of whitespace is reduced to its one decision.

`""` only ever follows the last token of a text, where there is nothing to separate it from.
"""


class DiffSpan(BaseModel):
    """One run of tokens: kept, removed, or added.

    `text` carries the separators its own tokens had, so a span that spanned a block boundary
    in the source still reads as two lines. `sep` is what follows the span, which the page
    needs because the boundary between two spans is a boundary between two texts and only
    this module knows what stood there.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["equal", "deleted", "inserted"]
    text: str = Field(min_length=1)
    sep: Separator = " "


class Comparison(BaseModel):
    """One comparison of two texts: the spans, the ratio, and the unit both were measured in.

    `granularity` rides along because it changes what a reported change means. At `word` a
    span is a run of words; at `line` it is a run of whole lines, so an untouched column of a
    changed table row is shown as changed with it. A page that marks text without saying
    which of the two it did would be overstating its own precision.
    """

    model_config = ConfigDict(frozen=True)

    granularity: Granularity
    ratio: float = Field(ge=0.0, le=1.0)
    spans: tuple[DiffSpan, ...] = ()


def _split(text: str) -> tuple[list[str], list[Separator]]:
    """The tokens, and for each one the separator that followed it in the source."""
    tokens = text.split()
    separators: list[Separator] = []
    position = 0
    for token in tokens:
        position = text.index(token, position) + len(token)
        run = _WHITESPACE.match(text, position)
        if run is None:
            separators.append("")
            continue
        separators.append("\n" if "\n" in run.group() else " ")
        position = run.end()
    return tokens, separators


def _render(tokens: Sequence[str], separators: Sequence[Separator], lo: int, hi: int) -> str:
    """Tokens `lo:hi` rejoined with the separators that stood between them."""
    parts: list[str] = []
    for index in range(lo, hi):
        parts.append(tokens[index])
        if index < hi - 1:
            parts.append(separators[index] or " ")
    return "".join(parts)


def _following(separators: Sequence[Separator], hi: int) -> Separator:
    """What followed the last token of a run ending at `hi`."""
    return separators[hi - 1] if 0 < hi <= len(separators) else " "


def _split_lines(text: str) -> tuple[list[str], list[Separator]]:
    """The lines, and for each one the separator that followed it: always a break.

    The line-granularity counterpart of `_split`. A line is kept whole, inner whitespace
    included, which is the one behavioural difference between the two granularities: at word
    granularity respacing a line is invisible, and here it reports the line as changed. That
    is the price of comparing a two-million-character table at all, and the page says which
    granularity it used rather than leaving the reader to infer it.
    """
    lines = text.split("\n")
    breaks: list[Separator] = ["\n"] * (len(lines) - 1)
    return lines, [*breaks, ""]


def _granularity(before: str, after: str) -> Granularity:
    """Word by word until a text is too large for that to finish, then line by line."""
    longest = max(before.count(" ") + before.count("\n"), after.count(" ") + after.count("\n"))
    return "line" if longest > LINE_TOKEN_CEILING else "word"


class Tokens(BaseModel):
    """Both texts cut into the tokens the matcher compares, and the separators the page renders.

    Cut once per comparison. The matcher and the renderer both read it, and so does the check
    that a stored answer still describes these texts, so none of them tokenises again.
    """

    model_config = ConfigDict(frozen=True)

    granularity: Granularity = Field(description="What a token is: a word or a whole line.")
    a: tuple[str, ...] = Field(description="The tokens of the older text, in order.")
    a_separators: tuple[Separator, ...] = Field(description="What followed each token of `a`.")
    b: tuple[str, ...] = Field(description="The tokens of the newer text, in order.")
    b_separators: tuple[Separator, ...] = Field(description="What followed each token of `b`.")


def tokenise(before: str, after: str) -> Tokens:
    """Both texts as tokens, at the granularity their size allows."""
    granularity = _granularity(before, after)
    split = _split if granularity == "word" else _split_lines
    a, a_separators = split(before)
    b, b_separators = split(after)
    return Tokens(
        granularity=granularity,
        a=tuple(a),
        a_separators=tuple(a_separators),
        b=tuple(b),
        b_separators=tuple(b_separators),
    )


def opcodes(tokens: Tokens) -> tuple[Opcode, ...]:
    """What the matcher makes of two token sequences. The one place a matcher is run."""
    return tuple(_matcher(list(tokens.a), list(tokens.b)).get_opcodes())


def assemble(tokens: Tokens, ops: Sequence[Opcode]) -> Comparison:
    """The comparison the page renders, built from the tokens and the matcher's opcodes.

    The ratio is `difflib`'s own formula, `2 * M / T` with `M` the tokens inside matching
    blocks, and the matching blocks of non-zero size are exactly the `equal` opcodes, so this is
    the float `SequenceMatcher.ratio()` returns for the same input, not an approximation of it.
    """
    matched = sum(a1 - a0 for tag, a0, a1, _, _ in ops if tag == "equal")
    total = len(tokens.a) + len(tokens.b)
    return Comparison(
        granularity=tokens.granularity,
        ratio=2.0 * matched / total if total else 1.0,
        spans=_spans(ops, tokens.a, tokens.a_separators, tokens.b, tokens.b_separators),
    )


def compare(before: str, after: str) -> Comparison:
    """Both texts as one sequence of spans, plus the ratio and the granularity used.

    One `SequenceMatcher` answers both questions. Building two, which is what calling
    `similarity` and then `word_diff` does, doubles the cost of the most expensive thing the
    site build does.
    """
    tokens = tokenise(before, after)
    return assemble(tokens, opcodes(tokens))


def _matcher(a: list[str], b: list[str]) -> SequenceMatcher[str]:
    # autojunk=False: the heuristic silently degrades matches on long texts and would make
    # the rendering depend on text length in a way no reader could predict. It is also the
    # reason `LINE_TOKEN_CEILING` exists: with the heuristic off, cost grows with the square
    # of the token count, and a 266 000-token provision takes tens of seconds a side.
    return SequenceMatcher(a=a, b=b, autojunk=False)


def similarity(before: str, after: str) -> float:
    """Token-level similarity in [0, 1], the quantity `SIMILARITY_FLOOR` is compared to."""
    return compare(before, after).ratio


def word_diff(before: str, after: str) -> tuple[DiffSpan, ...]:
    """The two texts as one sequence of spans, in reading order."""
    return compare(before, after).spans


def _spans(
    ops: Sequence[Opcode],
    a: Sequence[str],
    a_separators: Sequence[Separator],
    b: Sequence[str],
    b_separators: Sequence[Separator],
) -> tuple[DiffSpan, ...]:
    """The opcodes rendered back into spans, in reading order."""
    spans: list[DiffSpan] = []

    def add(kind: Literal["equal", "deleted", "inserted"], text: str, sep: Separator) -> None:
        # A run of blank lines renders to nothing at line granularity. It carries no content
        # to mark, so it is dropped rather than given an empty span the model would reject.
        if text:
            spans.append(DiffSpan(kind=kind, text=text, sep=sep))

    for tag, a0, a1, b0, b1 in ops:
        if tag == "equal":
            add("equal", _render(a, a_separators, a0, a1), _following(a_separators, a1))
            continue
        if a1 > a0:
            # A removal shown next to its replacement is separated by a space whatever stood
            # after it, because the two are alternatives rather than consecutive text.
            add(
                "deleted",
                _render(a, a_separators, a0, a1),
                " " if b1 > b0 else _following(a_separators, a1),
            )
        if b1 > b0:
            add("inserted", _render(b, b_separators, b0, b1), _following(b_separators, b1))
    return tuple(spans)
