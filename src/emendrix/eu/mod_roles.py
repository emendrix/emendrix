"""The modification-role vocabulary, and what each role means as a change.

Split out of `modmeta.py` along the same seam `core/location_codes.py` is split from
`core/location.py`: this module is the *vocabulary* — which roles exist, what they mean, and
what happens to one nobody has seen before — while `modmeta.py` is the *notice* they are read
out of.

**The readings are empirical.** Authority table `fd_375` publishes SKOS with `inScheme` and no
English labels at all (verified 2026-08-05), so every
row below was established by reading annotations against the texts they describe. Counts are
over the 540 modification annotations of the three pinned acts, spanning 2006 to 2026:

| Role | Count | Reading (empirical) |
|---|---|---|
| `R` | 331 | replace |
| `J` | 155 | insert / adjoin |
| `M` | 26 | modify — pre-2013 REACH amendments, mostly on annexes |
| `A` | 10 | add — appendices, notes, entries |
| `DEL` | 13 | delete |
| `C` | 4 | correct / complete |

A seventh value, `TXT`, occurs once. It is a *location* code sitting in a role field — a
data-quality defect, not a role — and `UnknownRole` is where it lands, counted rather than
crashed on.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from emendrix.core import ChangeType

__all__ = ["ROLE_CHANGE_TYPE", "ModRole", "RoleCode", "UnknownRole", "parse_role"]

_TEMPLATE: Final = re.compile(r"^\{(\w+)\|[^}]*\}$")
_UNKNOWN_WRAPPER: Final = re.compile(r"^UNKNOWN\((.+)\)$")


class ModRole(StrEnum):
    """The roles observed across three acts and 540 annotations. See the module docstring."""

    R = "R"  # replace
    J = "J"  # insert / adjoin
    M = "M"  # modify
    A = "A"  # add
    DEL = "DEL"  # delete
    C = "C"  # correct / complete


ROLE_CHANGE_TYPE: Final[dict[ModRole, ChangeType]] = {
    ModRole.R: ChangeType.MODIFIED,
    ModRole.M: ChangeType.MODIFIED,
    ModRole.C: ChangeType.MODIFIED,
    ModRole.J: ChangeType.INSERTED,
    ModRole.A: ChangeType.INSERTED,
    ModRole.DEL: ChangeType.DELETED,
}
"""Role to change type: the classification convention the corroborator scores against.

Deliberately coarse — `R`, `M` and `C` all mean *this text is not what it was*, which is what
`MODIFIED` says, and no evidence distinguishes them further. Note that this is the kind **at
the annotated location**: a `J` on `AR 5 PA 1 ALN 1 PTA (bb)` inserts a point into Article 5,
and collapsing that to "Article 5 was modified" is `SignalClaim.unit_kind`
(`emendrix.core.claims`), not this table.
"""


class UnknownRole(BaseModel):
    """A role code outside `ModRole` — the `UNKNOWN(str)` escape hatch, counted not crashed on."""

    model_config = ConfigDict(frozen=True)

    raw: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _accept_plain_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            wrapped = _UNKNOWN_WRAPPER.match(data)
            return {"raw": wrapped.group(1) if wrapped else data}
        return data

    @model_serializer
    def _serialize(self) -> str:
        return f"UNKNOWN({self.raw})"

    def __str__(self) -> str:
        return self.raw


RoleCode = ModRole | UnknownRole
"""A role, known or not. Nothing downstream may assume it is in the vocabulary."""


def parse_role(raw: str | None) -> RoleCode | None:
    """`'{J|http://…/fd_375/J}'` → `ModRole.J`; an unknown code → `UnknownRole`; `''` → `None`.

    The field is a `{CODE|authority-uri}` template, not a plain string, and legacy notices
    write the bare code, so both forms are read. Confirmed on the pinned notices 2026-08-05.
    """
    if raw is None:
        return None
    text = raw.strip()
    matched = _TEMPLATE.match(text)
    code = (matched.group(1) if matched else text).strip().upper()
    if not code:
        return None
    try:
        return ModRole(code)
    except ValueError:
        return UnknownRole(raw=code)


def change_type_of(role: RoleCode | None) -> ChangeType | None:
    """What a role says happened, at its own location. `None` when the role is unknown."""
    return ROLE_CHANGE_TYPE.get(role) if isinstance(role, ModRole) else None
