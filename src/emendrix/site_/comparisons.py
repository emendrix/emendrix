"""Comparisons a build has made before, reused only once they are shown to fit their texts.

The before and after texts of a committed changelog entry never change, so neither does the
comparison of them, yet every build used to recompute every one. Measured on the production
build on 2026-10-07, that recomputation was 99% of the build's time. So a build may be handed
the opcodes an earlier build computed, keyed by a hash of the algorithm and both texts, and use
them instead of running the matcher again.

**A cache can only make a build faster, never different.** That is the rule everything here is
written around. The key names the algorithm as well as the texts, so an answer one matcher gave
is never asked for under another. And a stored answer is never trusted on its key alone: `fits`
checks it against the tokens of the very texts it claims to describe, every time it is about to
be used, so a truncated, foreign or hand-edited entry is ignored and the comparison recomputed.
`compare_known` therefore returns what `worddiff.compare` returns for every input, whatever
table this tool wrote, and the tests hold it to that. The one entry the check cannot catch is a
hand-made one that is a different correct alignment of the same texts, which is why the
directory is the tool's own and nothing should be put in it by hand.

Only the opcodes and the two token counts are stored. The ratio is derived from the opcodes and
the spans are rebuilt by the code that renders them today, because a stored field the opcodes
already determine is one more thing that could disagree with them.

This module opens no file. `comparison_store` reads and writes the entries, and only the
command line calls it, so every page receives an in-memory table and nothing else.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Iterable, Iterator, Mapping
from types import MappingProxyType
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix.site_ import worddiff
from emendrix.site_.inputs import ActSite
from emendrix.site_.worddiff import (
    LINE_TOKEN_CEILING,
    Comparison,
    Granularity,
    Opcode,
    Tokens,
    assemble,
    tokenise,
)

__all__ = [
    "ALGORITHM",
    "NO_COMPARISONS",
    "Comparisons",
    "Resolved",
    "Stored",
    "compare_known",
    "comparison_key",
    "fits",
    "pairs",
    "resolve",
]

ALGORITHM: Final = (
    f"cydifflib-autojunk-off/ceiling-{LINE_TOKEN_CEILING}/tokens-1"
    f"/py{sys.version_info[0]}.{sys.version_info[1]}"
)
"""Everything that decides what the matcher returns for two texts, as one string in the key.

The interpreter's version is in it because `difflib`, which `cydifflib` compiles, ships with the
interpreter. `tokens-1` moves whenever tokenisation or the choice of granularity changes
behaviour. Any change to what the matcher returns for a given input must change this string: it
is the only way stored answers are invalidated, and it is safe because an old entry is then
simply never asked for.
"""


class Stored(BaseModel):
    """One comparison as kept between builds: the opcodes, and what they were computed over."""

    model_config = ConfigDict(frozen=True)

    schema_: Literal[1] = Field(
        alias="schema",
        description="The entry format; an entry without it, or with another, is unread.",
    )
    granularity: Granularity = Field(description="Whether the tokens were words or lines.")
    a: int = Field(ge=0, description="How many tokens the older text had.")
    b: int = Field(ge=0, description="How many tokens the newer text had.")
    opcodes: tuple[Opcode, ...] = Field(
        description="`SequenceMatcher.get_opcodes()` verbatim, as `[tag, a0, a1, b0, b1]` rows."
    )


Comparisons = Mapping[str, Stored]
"""Stored comparisons by `comparison_key`, the table every rendering layer is handed."""

NO_COMPARISONS: Final[Comparisons] = MappingProxyType({})
"""The empty table every layer defaults to, with which a build computes everything itself."""


def comparison_key(before: str, after: str) -> str:
    """The lowercase hex SHA-256 of the algorithm and both texts, each prefixed by its length.

    The length prefixes make the encoding unambiguous, so `("ab", "c")` and `("a", "bc")` are
    different keys. Nothing short of the full texts is hashed: a key that is not the content is
    a cache that can lie.
    """
    digest = hashlib.sha256()
    for part in (ALGORITHM, before, after):
        raw = part.encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def fits(stored: Stored, tokens: Tokens) -> bool:
    """Whether a stored entry is a correct diff of exactly these tokens. Never raises.

    The opcodes must tile both sequences from the start to the end with no gap or overlap, each
    tag must have the ranges its meaning requires, rows must alternate between `equal` and a
    difference as `get_opcodes` emits them, and every `equal` must cover identical tokens. Any
    entry that passes describes a correct diff of these texts; the key is what says it is the
    one this algorithm produces.
    """
    if stored.granularity != tokens.granularity:
        return False
    if stored.a != len(tokens.a) or stored.b != len(tokens.b):
        return False
    i = j = 0
    previous = ""
    for tag, a0, a1, b0, b1 in stored.opcodes:
        if a0 != i or b0 != j or a1 < a0 or b1 < b0:
            return False
        # `get_opcodes` merges adjacent matches and adjacent differences, so its rows alternate
        # between `equal` and not; a split run would render as two spans where it gives one.
        if previous and (previous == "equal") == (tag == "equal"):
            return False
        previous = tag
        if tag in ("equal", "replace") and (a1 == a0 or b1 == b0):
            return False
        if (tag == "delete" and (b1 != b0 or a1 == a0)) or (
            tag == "insert" and (a1 != a0 or b1 == b0)
        ):
            return False
        if tag == "equal" and (a1 - a0 != b1 - b0 or tokens.a[a0:a1] != tokens.b[b0:b1]):
            return False
        i, j = a1, b1
    return i == stored.a and j == stored.b


def _store(tokens: Tokens, ops: tuple[Opcode, ...]) -> Stored:
    return Stored(
        schema=1, granularity=tokens.granularity, a=len(tokens.a), b=len(tokens.b), opcodes=ops
    )


def compare_known(before: str, after: str, known: Comparisons) -> Comparison:
    """`worddiff.compare(before, after)`, reusing a stored answer where one fits.

    The texts are tokenised once, and the tokens serve the check, the matcher if it has to run,
    and the rendering. With an empty table no key is even computed.
    """
    tokens = tokenise(before, after)
    stored = known.get(comparison_key(before, after)) if known else None
    if stored is not None and fits(stored, tokens):
        return assemble(tokens, stored.opcodes)
    return assemble(tokens, worddiff.opcodes(tokens))


def pairs(acts: Iterable[ActSite]) -> Iterator[tuple[str, str]]:
    """Every `(before, after)` a build of these acts compares, duplicates included.

    This must be exactly the set `diffview.render_texts` compares: a change with both texts.
    The two change together. If they drift, a build handed a resolved table still writes the
    right bytes but computes whatever was missed while it renders, and the test that builds a
    whole site with the matcher made to raise is what catches that.
    """
    for act in acts:
        for entry in act.entries:
            for emitted in entry.changes:
                before, after = emitted.change.before, emitted.change.after
                if before is not None and after is not None:
                    yield before, after


class Resolved(BaseModel):
    """Every comparison a build will ask for, and how each came to be in the table."""

    model_config = ConfigDict(frozen=True)

    table: dict[str, Stored] = Field(description="Every key the build will ask for.")
    computed: tuple[str, ...] = Field(
        description="Sorted keys that were missing or did not fit, so were computed here."
    )
    reused: int = Field(ge=0, description="Stored entries that fitted and were used as found.")
    rejected: int = Field(ge=0, description="Stored entries that existed and did not fit.")


def resolve(pairs: Iterable[tuple[str, str]], stored: Comparisons) -> Resolved:
    """A full table for these pairs: stored entries that fit, and fresh ones for the rest.

    A pair seen twice is resolved once, so `reused + len(computed)` is the number of distinct
    pairs and `rejected` counts entries that were found and then recomputed.
    """
    table: dict[str, Stored] = {}
    computed: list[str] = []
    reused = rejected = 0
    for before, after in pairs:
        key = comparison_key(before, after)
        if key in table:
            continue
        tokens = tokenise(before, after)
        found = stored.get(key)
        if found is not None and fits(found, tokens):
            table[key] = found
            reused += 1
            continue
        if found is not None:
            rejected += 1
        table[key] = _store(tokens, worddiff.opcodes(tokens))
        computed.append(key)
    return Resolved(table=table, computed=tuple(sorted(computed)), reused=reused, rejected=rejected)
