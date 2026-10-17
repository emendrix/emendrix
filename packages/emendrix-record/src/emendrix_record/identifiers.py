"""A typed CAS, EC or CLP Index number, read by shape and check digit, or the reason it is none.

This is a reader's copy of the rules the pipeline recognises numbers in table rows by, because a
reader must not import `emendrix`. A contract test in the `emendrix` suite holds every reading
here to the pipeline's over values cut from its committed table fixtures, so a rule that moves
there fails a test rather than a lookup here.

The rules, as the pipeline states them (verified 2026-10-16 over every cached package of the
eight acts with substance tables):

- CAS: the other digits weighted 1, 2, 3 ... from the right, modulo 10, is the last digit.
  Leading zeros of the first group are dropped, and a first group left shorter than two digits
  is not a CAS number.
- EC: the first six digits weighted 1 to 6 from the left, modulo 11; a remainder of 10 is
  written `1`.
- CLP Index No: the eight digits weighted 1 to 8 from the left, modulo 11; 10 is written `X`.
- Without hyphens, 5 to 10 digits are read as a CAS number (hyphens before the last digit and
  before the two before it), and exactly 7 digits also as an EC number; every reading whose
  check passes is offered.

The acts print U+2010, U+2011, U+2012, U+2013 and U+2212 for `-` in a few cells, so those are
read as `-` first; whitespace is collapsed and trimmed.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["SCHEME_NAMES", "parse_identifier"]

SCHEME_NAMES: Final = {"cas": "CAS", "ec": "EC", "index": "Index No"}
"""How each scheme is named in a sentence."""

_HYPHENS: Final = str.maketrans(
    {chr(code): "-" for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2212)}
)
_WHITESPACE: Final = re.compile(r"\s+")
_CAS: Final = re.compile(r"(\d{2,7})-(\d{2})-(\d)")
_EC: Final = re.compile(r"([2-9]\d{2})-(\d{3})-(\d)")
_INDEX: Final = re.compile(r"(\d{3})-(\d{3})-(\d{2})-([\dX])")
_DIGITS: Final = re.compile(r"\d{5,10}")

Reading = tuple[str, str]
"""`(scheme, canonical value)`."""


def _cas(first: str, second: str, check: str) -> Reading | str:
    body = first + second
    expected = sum(int(digit) * weight for weight, digit in enumerate(reversed(body), 1)) % 10
    if len(first.lstrip("0")) < 2:
        return "its first group has fewer than two digits once leading zeros are dropped"
    if expected != int(check):
        return f"its CAS check digit is {check} where its other digits give {expected}"
    return "cas", f"{first.lstrip('0')}-{second}-{check}"


def _ec(first: str, second: str, check: str) -> Reading | str:
    remainder = sum(int(digit) * weight for weight, digit in enumerate(first + second, 1)) % 11
    expected = 1 if remainder == 10 else remainder
    if expected != int(check):
        return f"its EC check digit is {check} where its first six digits give {expected}"
    return "ec", f"{first}-{second}-{check}"


def _index(first: str, second: str, third: str, check: str) -> Reading | str:
    digits = first + second + third
    remainder = sum(int(digit) * weight for weight, digit in enumerate(digits, 1)) % 11
    expected = "X" if remainder == 10 else str(remainder)
    if expected != check:
        return f"its Index No check character is {check} where its eight digits give {expected}"
    return "index", f"{first}-{second}-{third}-{check}"


def _plain(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().translate(_HYPHENS)


def parse_identifier(text: str) -> tuple[Reading, ...] | str:
    """Every `(scheme, value)` reading of `text` whose check passes, or why there is none.

    The reason names the shape that was expected, or for each shape the value has, which check
    failed and what the digits give instead; it is a sentence a caller can repeat.
    """
    value = _plain(text)
    readings: list[Reading] = []
    failures: list[str] = []
    if "-" in value:
        shaped = (
            (_CAS.fullmatch(value), _cas, "CAS"),
            (_EC.fullmatch(value), _ec, "EC"),
            (_INDEX.fullmatch(value), _index, "Index No"),
        )
        for matched, check, name in shaped:
            if matched is None:
                continue
            read = check(*matched.groups())
            if isinstance(read, str):
                failures.append(f"read as {name}, {read}")
            else:
                readings.append(read)
    elif _DIGITS.fullmatch(value):
        read = _cas(value[:-3], value[-3:-1], value[-1])
        if isinstance(read, str):
            failures.append(f"read as CAS {value[:-3]}-{value[-3:-1]}-{value[-1]}, {read}")
        else:
            readings.append(read)
        if len(value) == 7:
            matched = _EC.fullmatch(f"{value[:3]}-{value[3:6]}-{value[6]}")
            read = "its first digit is not 2 to 9" if matched is None else _ec(*matched.groups())
            if isinstance(read, str):
                failures.append(f"read as EC {value[:3]}-{value[3:6]}-{value[6]}, {read}")
            else:
                readings.append(read)
    if readings:
        return tuple(readings)
    if failures:
        return f"{text.strip()!r} is not a CAS, EC or Index No: " + "; ".join(failures) + "."
    return (
        f"{text.strip()!r} is not shaped like a CAS number (`50-00-0`), an EC number "
        f"(`200-001-8`) or a CLP Index No (`603-148-00-X`), and is not 5 to 10 digits typed "
        f"without hyphens."
    )
