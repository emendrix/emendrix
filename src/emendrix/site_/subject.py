"""What a provision is about, decided once for every place its coordinate is printed.

A provision's title is printed in four places: the change heading on a version page, the
provision page's heading, the version's in-page index and the act page's index. Each used to
decide for itself whether the stored heading said more than the coordinate, and one decision
made four times is four chances to disagree. `provision_title` is the one decision.

**An annex whose stored heading is only its coordinate is titled from its own text.** Formex
often titles an annex `ANNEX II` and puts what the annex is about in the title of its first
group, which the parser does not read as the heading; the verbatim text keeps it, because a
block boundary opens a line there, so the subject is the stored text's second line. It is read
back from the stored text rather than from the source because committed changelogs are never
rewritten: a parser change would title only what is emitted after it, and this serves every
change already published.

The rule is narrow on purpose, and measured: `tests/site_/test_subject.py` runs it over every
committed Formex package against a structural reading and pins how often it fires and that it
is never wrong. A missing subject leaves the coordinate alone, which is what the page printed
before; a wrong one would be a false statement about the law. So the rule says nothing whenever
it is unsure, and what it does say is printed character for character.
"""

from __future__ import annotations

import re
from typing import Final

from emendrix.core import Change, LocationCode

__all__ = ["annex_subject", "is_capitals", "provision_title"]

_LONGEST: Final = 200
"""A subject line is a title. A longer line is a provision, or a title better left unprinted."""

_BLOCK_WORDS: Final = frozenset(
    {
        "CHAPTER",
        "PART",
        "SECTION",
        "SUBSECTION",
        "TITLE",
        "ANNEX",
        "APPENDIX",
        "FOREWORD",
        "CONTENTS",
        "TABLE",
        "INTRODUCTION",
        "ENTRY",
    }
)
"""First words of a line that heads a division of the annex rather than naming the whole of it."""

_ROMAN: Final = r"(?=[IVXLCDM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
# Excludes a line that opens with a number, `1.`, `(a)`, `IV.`, `B)`, as a first provision does.
# A Roman numeral must be a well-formed one, so `CIVIL AVIATION` is a word and not a number.
_NUMBERED: Final = re.compile(rf"\(?(?:[0-9]|{_ROMAN}[.) ]|[^\W\d_][.)])")
# Excludes a line with no word in it: a run of three letters is the least a subject holds.
_WORDY: Final = re.compile(r"[^\W\d_]{3}")
# The line's first word, letters only, so `PART:` and `PART` are one word.
_FIRST_WORD: Final = re.compile(r"[^\W\d_]+")


def _same(one: str, other: str) -> bool:
    """Equal once case is folded and whitespace, the no-break space included, is collapsed."""
    return one.casefold().split() == other.casefold().split()


def is_capitals(title: str) -> bool:
    """True where the title holds no lower-case letter, which the sheet sets in small capitals."""
    return not any(char.islower() for char in title)


def annex_subject(heading: str | None, human: str, text: str | None) -> str | None:
    """The annex's subject, read from the second line of its stored text, or `None`.

    The first line must be the annex's own title, equal to the stored heading or to the
    coordinate once case and whitespace are folded, or the text does not open where this
    rule expects and nothing is read. The second line, its two ends trimmed, is accepted only
    if it is 1 to 200 characters, holds no lower-case letter and a run of three letters, does
    not open with a numbering token and does not open with a word that heads a division.
    """
    if text is None:
        return None
    lines = text.split("\n")
    if len(lines) < 2:
        return None
    first = lines[0]
    if not (_same(first, human) or (heading is not None and _same(first, heading))):
        return None
    candidate = lines[1].strip()
    if not 1 <= len(candidate) <= _LONGEST:
        return None
    if not is_capitals(candidate) or _WORDY.search(candidate) is None:
        return None
    if _NUMBERED.match(candidate) is not None:
        return None
    word = _FIRST_WORD.match(candidate)
    if word is not None and word.group() in _BLOCK_WORDS:
        return None
    return candidate


def provision_title(change: Change) -> str | None:
    """What the provision is about, where the page can say more than its coordinate.

    The stored heading where it says more than the coordinate; else, for a top-level annex
    only, the subject `annex_subject` reads from the newest stored text; else `None`.
    """
    heading = change.heading
    named = change.location.human
    if heading and not _same(heading, named):
        return heading
    segments = change.location.segments
    if len(segments) != 1 or segments[0].code != LocationCode.AN:
        return None
    return annex_subject(heading, named, change.after or change.before)
