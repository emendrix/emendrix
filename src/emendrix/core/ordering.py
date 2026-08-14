"""Deterministic ordering of enumerator strings.

Provisions are not numbered numerically: `4a` follows `4`, annexes count in Roman
numerals (`III`, `IX`, `XIV`), and sub-coordinates are dotted (`8.6.2`). This module
turns such a string into a comparable key so that output ordering is stable across runs.
Changelogs are diffed in git, so ordering is part of the contract.

It deliberately knows nothing about provisions, corpora or legislation: it orders
strings the way a table of contents does, and nothing more.
"""

import re
from typing import Final

__all__ = ["SortKey", "natural_key", "roman_value"]

# A key element is (kind, number, text): numeric chunks sort before textual ones,
# so `AR 4` < `AR 4a` and `AN I` < `AN XIV`.
SortKey = tuple[tuple[int, int, str], ...]

_NUMERIC: Final = 0
_TEXTUAL: Final = 1

_ROMAN_PATTERN: Final = re.compile(
    r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$",
)
_ROMAN_DIGITS: Final[dict[str, int]] = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}
# A single `L`, `C`, `D` or `M` is far more often a part/column/note letter than a
# Roman 50/100/500/1000, so those are read as text. `I`, `V` and `X` are read as
# numbers, because annexes really are numbered that way.
_ROMAN_SINGLE_LETTERS: Final = frozenset({"I", "V", "X"})

_CHUNKS: Final = re.compile(r"\d+|\D+")


def roman_value(token: str) -> int | None:
    """The value of a Roman numeral, or `None` if the token is not read as one."""
    if not token or not _ROMAN_PATTERN.match(token):
        return None
    if len(token) == 1 and token not in _ROMAN_SINGLE_LETTERS:
        return None
    total = 0
    previous = 0
    for char in reversed(token):
        current = _ROMAN_DIGITS[char]
        total += -current if current < previous else current
        previous = max(previous, current)
    return total


def natural_key(value: str) -> SortKey:
    """A comparable key for an enumerator such as `5`, `4a`, `8.6.2`, `XIV` or `(bb)`.

    Roman numerals compare by value; everything else compares chunk by chunk, digits
    numerically and the rest lexicographically. Empty input yields an empty key, which
    sorts before every non-empty one.
    """
    roman = roman_value(value)
    if roman is not None:
        return ((_NUMERIC, roman, ""),)
    key: list[tuple[int, int, str]] = []
    for match in _CHUNKS.finditer(value):
        chunk = match.group()
        if chunk.isdigit():
            key.append((_NUMERIC, int(chunk), ""))
        else:
            key.append((_TEXTUAL, 0, chunk))
    return tuple(key)
