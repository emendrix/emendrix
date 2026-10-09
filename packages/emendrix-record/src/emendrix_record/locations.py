"""Canonical locations: containment, the few typed forms read as one, and a human form.

A canonical location is `ROLE value` pairs joined by single spaces, a top-level unit first:
`AR 5`, `AN III`, `AR 5 PA 1 ALN 1 PTA (bb)`. Everything here is a mechanical rule over that
string, written down in each function, and nothing reads law text or guesses.

`parse_location` refuses a point (`Article 6(1)(a)`) on purpose. Below a paragraph the record
spells coordinates in more than one order, `AR n PA m ALN k PTA (x)` and `AR n PA m PTA (x)`
(both found in the committed corpus on 2026-10-09), so `(1)(a)` has two canonical readings and
choosing one would be a guess. A reader who wants a point names its paragraph, or types the
canonical string.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["ANNEX_LIMIT", "human", "parse_location", "within"]

ANNEX_LIMIT: Final = 39
"""The largest annex number read in Arabic or Roman; a larger one is refused, not guessed at."""

_CANONICAL: Final = re.compile(r"^(AR|AN) \S+( [A-Z]{2,3} \S+)*$")
_ARTICLE: Final = re.compile(r"^(?:[Aa]rticle|[Aa]rt\.) (\d+[a-z]*)(?:\((\d+[a-z]*)\))?$")
_ANNEX: Final = re.compile(r"^[Aa]nnex ([0-9]+|[IVXivx]+)$")
_NUMERALS: Final = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


def _roman(number: int) -> str:
    digits: list[str] = []
    for value, numeral in _NUMERALS:
        while number >= value:
            digits.append(numeral)
            number -= value
    return "".join(digits)


_ROMAN: Final = frozenset(_roman(number) for number in range(1, ANNEX_LIMIT + 1))


def within(inner: str, outer: str) -> bool:
    """Whether `inner` is `outer` or lies beneath it.

    Token-prefix containment: both are split on single spaces and `outer`'s tokens must be the
    first tokens of `inner`, whole. So `AR 6 PA 1` is within `AR 6`, `AR 60` is not, and every
    location is within itself.
    """
    outer_tokens = outer.split(" ")
    return inner.split(" ")[: len(outer_tokens)] == outer_tokens


def _annex(value: str) -> str | None:
    if value.isdigit():
        number = int(value)
        return _roman(number) if 1 <= number <= ANNEX_LIMIT and value[0] != "0" else None
    numeral = value.upper()
    return numeral if numeral in _ROMAN else None


def parse_location(text: str) -> str | None:
    """The canonical location `text` names, or `None` when it is not one of the forms read.

    Whitespace runs are collapsed first. Then, in order:

    - a canonical string (`AR 6`, `AN I`, `AR 6 PA 1`) is returned as it is;
    - `Article 6`, `Art. 6`, `Article 6a` give `AR 6`, `AR 6a`, and `Article 6(1)` gives
      `AR 6 PA 1`;
    - `Annex IV` gives `AN IV`, and `Annex 4` gives `AN IV` too, for 1 to `ANNEX_LIMIT`.

    Anything else, a point such as `Article 6(1)(a)` included, gives `None`.
    """
    collapsed = " ".join(text.split())
    if _CANONICAL.match(collapsed):
        return collapsed
    article = _ARTICLE.match(collapsed)
    if article:
        number, paragraph = article.groups()
        return f"AR {number}" if paragraph is None else f"AR {number} PA {paragraph}"
    annex = _ANNEX.match(collapsed)
    if annex:
        numeral = _annex(annex.group(1))
        return None if numeral is None else f"AN {numeral}"
    return None


def human(canonical: str) -> str:
    """`AR 6` as `Article 6`, `AN IV` as `Annex IV` and `AR 6 PA 1` as `Article 6(1)`.

    Those three shapes are the only ones rewritten. Any other location is returned unchanged,
    because a role this function does not name has no spelling it could print without a guess.
    """
    tokens = canonical.split(" ")
    match tokens:
        case ["AR", number]:
            return f"Article {number}"
        case ["AN", numeral]:
            return f"Annex {numeral}"
        case ["AR", number, "PA", paragraph]:
            return f"Article {number}({paragraph})"
        case _:
            return canonical
