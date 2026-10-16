"""The four key forms a table profile may name, each read from one cell of the first row.

A key is what tells one entry of a table from the next between two versions. The acts number
their rows four ways, and the form is a property of the table, stated in its profile:

- `index`: the leading CLP Index number of the cell. Missing, or failing its check character,
  the row is unkeyed; a token that fails is reported so the caller can count it. Never a
  fallback to the raw text, because a misprinted key would then pair with nothing honestly.
- `number`: the leading entry number, `46a` or `68`, followed by `.`, a space or the end. A
  cell without one is keyed by its comparison text: Cosmetics prints `x` for a row its
  consolidation has not numbered yet, and that is its key.
- `text`: the cell's comparison text (REACH Annex IV's EC number as printed; REACH Annex XVII
  Appendix 13's CAS cell, which may hold two numbers).
- `name`: the first line of the cell as comparison text, footnote markers `(#)`, `(+)`, `(*)`,
  `(**)` and a trailing `*` removed, case folded. A marker is a token of its own, set off by
  whitespace, so the stereo descriptor in `(+)-Tartaric acid` (Biocides Annex I, read
  2026-10-16) stays part of the name. Measured 2026-10-16 over the PIC and POPs transitions:
  this form removes the 15 PIC removal-plus-addition pairs that were only `Aldicarb` becoming
  `Aldicarb (#)` or a changed capital, and 3 POPs pairs where the first cell carried a formula
  the amendment rewrote. A renaming still reads as a removal plus an addition, which is a
  known limit of name keys.

An empty key cell (nothing, or a lone dash or slash) leaves the row unkeyed under every form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from emendrix.core import normalize_for_comparison
from emendrix.eu.substances.numbers import index, plain

__all__ = ["EMPTY_MARKS", "KeyForm", "KeyReading", "entry_name", "first_line", "read_key"]

KeyForm = Literal["index", "number", "text", "name"]

EMPTY_MARKS: Final = frozenset({"", "-", "/", chr(0x2013), chr(0x2014)})
"""What a cell holds when it holds nothing: empty, a hyphen, a slash, an en or em dash."""

_INDEX_LEAD: Final = re.compile(r"^(\d{3}-\d{3}-\d{2}-[\dX])(?![\d-])")
_NUMBER_LEAD: Final = re.compile(r"^(\d+[a-z]?)(?:\.|\s|$)")
_NUMBER_PREFIX: Final = re.compile(r"^\d+[a-z]?\.?\s*")
_MARKERS: Final = re.compile(r"(?<!\S)\((?:#|\+|\*\*?)\)(?!\S)")
_TRAILING_STAR: Final = re.compile(r"\*+$")


@dataclass(frozen=True)
class KeyReading:
    """A key, or why there is none: `failed` is an Index token whose check did not hold."""

    key: str | None
    failed: bool = False


def first_line(verbatim: str) -> str:
    """The first line of a cell's verbatim text, leading and trailing whitespace dropped."""
    return verbatim.strip().split("\n", 1)[0].strip()


def read_key(verbatim: str, form: KeyForm) -> KeyReading:
    """The key the cell yields under `form` (see the module docstring for each form)."""
    if form == "name":
        return KeyReading(_name_key(verbatim))
    value = normalize_for_comparison(verbatim)
    if value in EMPTY_MARKS:
        return KeyReading(None)
    if form == "index":
        lead = _INDEX_LEAD.match(plain(value))
        if lead is None:
            return KeyReading(None)
        valid = index(lead[1])
        return KeyReading(None, failed=True) if valid is None else KeyReading(valid.value)
    if form == "number":
        lead = _NUMBER_LEAD.match(value)
        return KeyReading(value if lead is None else lead[1])
    return KeyReading(value)


def _name_key(verbatim: str) -> str | None:
    line: str = normalize_for_comparison(first_line(verbatim))
    line = _MARKERS.sub("", line)
    line = _TRAILING_STAR.sub("", line)
    key = normalize_for_comparison(line).casefold()
    return None if key in EMPTY_MARKS else key


def entry_name(verbatim: str, *, drop_number: bool) -> str | None:
    """The first line of the name cell; with `drop_number`, a leading entry number removed.

    `drop_number` is for tables whose name column is also the numbered key column (REACH
    Annex XVII, Batteries Annex I), where the first line reads `46a. Substance name`.
    """
    line = first_line(verbatim)
    if drop_number:
        line = _NUMBER_PREFIX.sub("", line, count=1)
    return line or None
