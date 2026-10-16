"""CAS, EC and CLP Index numbers: recognised by shape and check digit, never by a list.

Every rule below was verified on 2026-10-16 over every English Formex package the CELLAR disk
cache held for the eight acts with substance tables, with the counts stated at each rule. A
value whose check fails is not an identifier: it is counted by the caller and never published,
while the cell that printed it stays verbatim.

Hyphens: the acts print U+2010, U+2011, U+2012, U+2013 and U+2212 for `-` in a few cells
(3 Cosmetics cells, all versions summed), so every reading maps those to ASCII first.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Final, Literal

from emendrix.core import Identifier, normalize_for_comparison

__all__ = [
    "CAS",
    "EC",
    "INDEX",
    "SCHEMES",
    "Scheme",
    "cas",
    "ec",
    "identifiers_in",
    "index",
    "plain",
    "read_identifier",
]

Scheme = Literal["cas", "ec", "index"]
SCHEMES: Final[tuple[Scheme, ...]] = ("cas", "ec", "index")

_HYPHENS: Final = str.maketrans(
    {chr(code): "-" for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2212)}
)
CAS: Final = re.compile(r"(?<![\d-])(\d{2,7})-(\d{2})-(\d)(?![\d-])")
EC: Final = re.compile(r"(?<![\d-])([2-9]\d{2})-(\d{3})-(\d)(?![\d-])")
INDEX: Final = re.compile(r"(?<![\d-])(\d{3})-(\d{3})-(\d{2})-([\dX])(?![\d-])")
"""The token shapes, as measured. Each refuses to start or end inside a longer digit run."""

_DIGITS: Final = re.compile(r"^\d{5,10}$")


def plain(text: str) -> str:
    """Comparison text with every hyphen form the acts print mapped to `-`."""
    return normalize_for_comparison(text).translate(_HYPHENS)


def _cas_value(first: str, second: str, check: str) -> str | None:
    """Canonical CAS or `None`: digits weighted 1, 2, 3 ... from the right, modulo 10.

    The canonical form drops leading zeros of the first group (`0050-00-0` is `50-00-0`); a
    first group left shorter than two digits is not a CAS number at all.
    """
    body = first + second
    total = sum(int(digit) * weight for weight, digit in enumerate(reversed(body), 1))
    trimmed = first.lstrip("0")
    if total % 10 != int(check) or len(trimmed) < 2:
        return None
    return f"{trimmed}-{second}-{check}"


def _ec_value(first: str, second: str, check: str) -> str | None:
    """Canonical EC or `None`: the six digits weighted 1 to 6 from the left, modulo 11.

    A remainder of 10 is issued and written `1`: of the 224 distinct EC-shaped values in the
    cache whose remainder is 10, 223 end in `1` (verified 2026-10-16), and `200-233-3` in
    REACH Annex IV is the one that does not and fails.
    """
    total = sum(int(digit) * weight for weight, digit in enumerate(first + second, 1))
    remainder = total % 11
    written = 1 if remainder == 10 else remainder
    if written != int(check):
        return None
    return f"{first}-{second}-{check}"


def _index_value(first: str, second: str, third: str, check: str) -> str | None:
    """Canonical Index No or `None`: the eight digits weighted 1 to 8 from the left, modulo 11.

    A result of 10 is written `X`. Over 4449 distinct Index numbers in every cached version of
    CLP Annex VI the rule holds for 4449 (verified 2026-10-16); no modulo-10 rule reaches 10 %.
    """
    total = sum(int(digit) * weight for weight, digit in enumerate(first + second + third, 1))
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    if expected != check:
        return None
    return f"{first}-{second}-{third}-{check}"


def _whole(
    pattern: re.Pattern[str], value: Callable[..., str | None], scheme: Scheme, text: str
) -> Identifier | None:
    matched = pattern.fullmatch(plain(text))
    if matched is None:
        return None
    canonical = value(*matched.groups())
    return None if canonical is None else Identifier(scheme=scheme, value=canonical)


def cas(text: str) -> Identifier | None:
    """The CAS number a whole token spells, if its shape and check digit hold."""
    return _whole(CAS, _cas_value, "cas", text)


def ec(text: str) -> Identifier | None:
    """The EC number a whole token spells, if its shape and check digit hold."""
    return _whole(EC, _ec_value, "ec", text)


def index(text: str) -> Identifier | None:
    """The CLP Index number a whole token spells, if its shape and check character hold."""
    return _whole(INDEX, _index_value, "index", text)


_READERS: Final[dict[Scheme, tuple[re.Pattern[str], Callable[..., str | None]]]] = {
    "cas": (CAS, _cas_value),
    "ec": (EC, _ec_value),
    "index": (INDEX, _index_value),
}


def identifiers_in(text: str, schemes: Iterable[Scheme]) -> tuple[tuple[Identifier, ...], int]:
    """Every valid identifier of the given schemes in a cell, and how many shaped values failed.

    Every match of each scheme's pattern in the cell's comparison text, in order and
    deduplicated: a cell may hold several (170 CLP Annex VI CAS cells do). A dash cell holds
    none. A shaped value whose check fails is counted, not returned.
    """
    found: list[Identifier] = []
    failed = 0
    flat = plain(text)
    for scheme in schemes:
        pattern, value = _READERS[scheme]
        for matched in pattern.finditer(flat):
            canonical = value(*matched.groups())
            if canonical is None:
                failed += 1
                continue
            identifier = Identifier(scheme=scheme, value=canonical)
            if identifier not in found:
                found.append(identifier)
    return tuple(found), failed


def read_identifier(text: str) -> tuple[Identifier, ...]:
    """Every identifier a typed value can be read as, hyphens present or not.

    With hyphens the value is read as a whole CAS, EC or Index token. Without them, 5 to 10
    digits are read as a CAS number by inserting hyphens before the last digit and before the
    two before it, and exactly 7 digits also as an EC number; every reading whose check passes
    is returned, so `50000` yields CAS `50-00-0` and a 7-digit value may yield two readings.
    """
    value = plain(text)
    if "-" in value:
        readings = (cas(value), ec(value), index(value))
        return tuple(one for one in readings if one is not None)
    if not _DIGITS.match(value):
        return ()
    candidates = [cas(f"{value[:-3]}-{value[-3:-1]}-{value[-1]}")]
    if len(value) == 7:
        candidates.append(ec(f"{value[:3]}-{value[3:6]}-{value[6]}"))
    return tuple(one for one in candidates if one is not None)
