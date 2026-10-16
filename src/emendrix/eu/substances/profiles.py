"""Which table of which act is read as entries, and by which columns.

A profile names a table by position (act, unit, the located container the parser gives the
node holding it, and the table's 1-based ordinal among every table in that container) and by a
fail-closed header requirement: words that must appear, whole, in the header cell of a named
column. Both are needed and neither alone is trusted. POPs Annex I holds two tables with the
same header, and only the position tells Part A from Part B; a table at a profiled position
whose header has changed shape is **unrecognised**, counted and never read, so a renumbered or
replaced table cannot be misread as the one the profile describes.

Every profile below was read off the markup on 2026-10-16, over every English consolidated
version the CELLAR disk cache held: REACH 64 versions, CLP 32, Cosmetics 41, Biocides 10, PIC
10, POPs 15, Plant protection products 9, Batteries 3. Each header requirement holds in every
version listed there, with these measured consequences: REACH Annex IV printed `EINECS No` in
2007 (the match is case-insensitive); REACH Annex XVII's main table printed "Designation of the
substance ..." without "Column 1" until 2009-02-20; PIC Annex V Part 2 is unrecognised in its
four versions before 2019-05-01, whose two-column table had no "No" column. Column numbers are
1-based grid columns with spans copied, as the row reader lays them out. Labels in `key_label`
are the column names the acts print, or "Entry" where an act refers to its rows as entries in
prose; none is legal content.

Name keys (PIC, POPs, Biocides, REACH Annex XVII Appendix 12) were re-measured on 2026-10-16
with the package reader over every cached version of each act, original included, summing
keys added and removed over consecutive pairs and keys printed twice in one table: PIC, 10
versions, 440 added, 50 removed, 0 repeated; POPs, 15 versions, 14 added, 3 removed, 0 repeated;
Biocides, 10 versions, 12 added, 1 removed, 0 repeated; REACH Appendix 12, 62 readable versions
of 64, 33 added, 0 removed, 0 repeated. Every removal is a first line the act rewrote (a
formula joined to the name, a synonym added), which a name key reads as a removal plus an
addition: the known limit of the form.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import normalize_for_comparison
from emendrix.eu.substances.keys import KeyForm

__all__ = ["PROFILES", "TableProfile", "header_matches", "profiles_for"]

VERIFIED_ON: Final = date(2026, 10, 16)


class TableProfile(BaseModel):
    """Which table of an act holds entries, which column keys them, which carry identifiers."""

    model_config = ConfigDict(frozen=True)

    act: str = Field(description="CELEX number of the consolidated act, such as `32008R1272`.")
    unit: str = Field(description="Canonical location of the top-level unit, such as `AN VI`.")
    container: str = Field(description="Canonical location the parser gives the node holding it.")
    table: int = Field(ge=1, description="1-based ordinal among every table in the container.")
    header: tuple[tuple[int, str], ...] = Field(
        description="`(column, words)` requirements, every one of which must hold."
    )
    key_form: KeyForm
    key_col: int = Field(ge=1)
    key_label: str | None = Field(description="How the act names the key; `None` for a name.")
    cas_cols: tuple[int, ...] = ()
    ec_cols: tuple[int, ...] = ()
    index_cols: tuple[int, ...] = ()
    name_col: int = Field(ge=1)
    verified_on: date = Field(description="When the header and columns were read off the markup.")


Header = tuple[tuple[int, str], ...]
Cols = tuple[int, ...]
Spec = tuple[str, str, int, Header, KeyForm, int, str | None, int, Cols, Cols, Cols]
"""One profile as a row: unit, container, table, header, key form, key column, key label, name
column, CAS columns, EC columns, Index columns. Kept as rows so the whole table reads at once."""

_CLP_3: Final[Header] = ((1, "Index No"), (4, "CAS No"), (10, "Specific Conc. Limits"))
_CLP_3_2: Final[Header] = ((1, "Index No"), (4, "CAS No"), (7, "Concentration Limits"))
_REACH_IV: Final[Header] = ((1, "Einecs No"), (3, "CAS No"))
_REACH_XIV: Final[Header] = ((1, "Entry Nr"), (2, "Substance"))
_RESTRICTION: Final[Header] = ((1, "Designation"), (2, "Conditions of restriction"))
_REACH_APP: Final[Header] = ((1, "Substances"), (2, "Index No"), (4, "CAS No"))
_REACH_APP_8: Final[Header] = ((2, "CAS No"), (3, "Index No"), (5, "Substances"))
_REACH_APP_12: Final[Header] = ((1, "Substances"), (2, "Index"), (3, "CAS No"))
_REACH_APP_13: Final[Header] = ((1, "Substance name"), (2, "EC No"), (3, "CAS No"))
_COSMETICS_II: Final[Header] = ((1, "Reference number"), (3, "CAS number"))
_COSMETICS: Final[Header] = ((1, "Reference number"), (4, "CAS number"), (5, "EC number"))
_COSMETICS_IV: Final[Header] = ((1, "Reference number"), (3, "Colour index"), (4, "CAS number"))
_BIOCIDES_I: Final[Header] = ((1, "EC number"), (2, "Name/group"))
_PIC_I_1: Final[Header] = ((1, "Chemical"), (2, "CAS No"), (5, "Subcategory"))
_PIC_I_2: Final[Header] = ((1, "Chemical"), (2, "CAS No"), (5, "Category"), (6, "Use limitation"))
_PIC_I_3: Final[Header] = ((1, "Chemical"), (2, "Relevant CAS"), (3, "HS code"))
_PIC_V_1: Final[Header] = ((1, "Description of chemicals"), (2, "Additional details"))
_PIC_V_2: Final[Header] = ((1, "No"), (2, "Description of chemicals"))
_POPS: Final[Header] = ((1, "Substance"), (2, "CAS No"), (3, "EC No"))
_PPP_III: Final[Header] = ((1, "No"), (4, "CAS number"), (5, "EC number"))

_NONE: Final[Cols] = ()

_SPECS: Final[dict[str, tuple[Spec, ...]]] = {
    "32008R1272": (
        ("AN VI", "AN VI SCT 3", 1, _CLP_3, "index", 1, "Index No", 2, (4,), (3,), (1,)),
        ("AN VI", "AN VI SCT 3", 2, _CLP_3_2, "index", 1, "Index No", 2, (4,), (3,), (1,)),
    ),
    "32006R1907": (
        ("AN IV", "AN IV", 1, _REACH_IV, "text", 1, "Einecs No", 2, (3,), (1,), _NONE),
        ("AN XIV", "AN XIV", 1, _REACH_XIV, "number", 1, "Entry", 2, (2,), (2,), _NONE),
        ("AN XVII", "AN XVII", 1, _RESTRICTION, "number", 1, "Entry", 1, (1,), (1,), _NONE),
        *(
            (
                "AN XVII",
                f"AN XVII APP {n}",
                1,
                _REACH_APP,
                "index",
                2,
                "Index No",
                1,
                (4,),
                (3,),
                (2,),
            )
            for n in (1, 2, 4, 5, 6)
        ),
        ("AN XVII", "AN XVII APP 8", 1, _REACH_APP_8, "number", 1, "No", 5, (2,), (4,), (3,)),
        ("AN XVII", "AN XVII APP 12", 1, _REACH_APP_12, "name", 1, None, 1, (3,), (4,), (2,)),
        ("AN XVII", "AN XVII APP 13", 1, _REACH_APP_13, "text", 3, "CAS No", 1, (3,), (2,), _NONE),
    ),
    "32009R1223": (
        ("AN II", "AN II", 1, _COSMETICS_II, "number", 1, "Reference number", 2, (3,), (4,), _NONE),
        ("AN III", "AN III", 1, _COSMETICS, "number", 1, "Reference number", 2, (4,), (5,), _NONE),
        ("AN IV", "AN IV", 1, _COSMETICS_IV, "number", 1, "Reference number", 2, (4,), (5,), _NONE),
        ("AN V", "AN V", 1, _COSMETICS, "number", 1, "Reference number", 2, (4,), (5,), _NONE),
        ("AN VI", "AN VI", 1, _COSMETICS, "number", 1, "Reference number", 2, (4,), (5,), _NONE),
    ),
    "32012R0528": (("AN I", "AN I", 1, _BIOCIDES_I, "name", 2, None, 2, (4,), (1,), _NONE),),
    "32012R0649": (
        ("AN I", "AN I", 1, _PIC_I_1, "name", 1, None, 1, (2,), (3,), _NONE),
        ("AN I", "AN I", 2, _PIC_I_2, "name", 1, None, 1, (2,), (3,), _NONE),
        ("AN I", "AN I", 3, _PIC_I_3, "name", 1, None, 1, (2,), _NONE, _NONE),
        ("AN V", "AN V", 1, _PIC_V_1, "name", 2, None, 2, (3,), (3,), _NONE),
        ("AN V", "AN V", 2, _PIC_V_2, "number", 1, "No", 2, (3,), (3,), _NONE),
    ),
    "32019R1021": (
        ("AN I", "AN I", 1, _POPS, "name", 1, None, 1, (2,), (3,), _NONE),
        ("AN IV", "AN IV", 1, _POPS, "name", 1, None, 1, (2,), (3,), _NONE),
    ),
    "32009R1107": (("AN III", "AN III", 1, _PPP_III, "number", 1, "No", 2, (4,), (5,), _NONE),),
    "32023R1542": (("AN I", "AN I", 1, _RESTRICTION, "number", 1, "Entry", 1, (1,), (1,), _NONE),),
}


def _profile(act: str, spec: Spec) -> TableProfile:
    unit, container, table, header, form, key_col, label, name_col, cas, ec, index = spec
    return TableProfile(
        act=act,
        unit=unit,
        container=container,
        table=table,
        header=header,
        key_form=form,
        key_col=key_col,
        key_label=label,
        cas_cols=cas,
        ec_cols=ec,
        index_cols=index,
        name_col=name_col,
        verified_on=VERIFIED_ON,
    )


PROFILES: Final[dict[str, tuple[TableProfile, ...]]] = {
    act: tuple(_profile(act, spec) for spec in specs) for act, specs in _SPECS.items()
}
"""Every profiled table, by the CELEX number of its act, in document order within an act."""


def profiles_for(act: str) -> tuple[TableProfile, ...]:
    """The profiles of one act; empty for every act without a substance table."""
    return PROFILES.get(act, ())


def header_matches(profile: TableProfile, header_rows: Sequence[Sequence[str | None]]) -> bool:
    """Whether every `(column, words)` requirement holds in some header row of the table.

    Words match whole and case-insensitively on comparison text, so `Category` does not match
    `Subcategory` and `EINECS No` matches `Einecs No`. A position a span covers (`None`) is not
    a header cell of its own and never matches.
    """
    for column, words in profile.header:
        pattern = re.compile(r"\b" + re.escape(words) + r"\b", re.IGNORECASE)
        cells = (row[column - 1] for row in header_rows if len(row) >= column)
        if not any(
            cell is not None and pattern.search(normalize_for_comparison(cell)) for cell in cells
        ):
            return False
    return True
