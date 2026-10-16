# Table excerpts

Each file is one table of one consolidated version, cut from the CELLAR disk cache by the
committed command below on 2026-10-16: the table's ancestors reduced to their tags, attributes
and the headings a location is read from (so the parser places the table in the same container
it has in the full package), then the table with its header rows and its first N body rows.
Rows inside a `BLK` group are never trimmed. No excerpt splits a `ROWSPAN` group, checked by
reading each one. Nothing here is retyped.

The excerpt command numbers tables among the whole unit's tables (`--table`), which differs
from the profile's ordinal within the container where the unit holds tables in earlier
sections: CLP Annex VI's Table 3 is the unit's third table and the container's first.

An excerpt of a container's second table (`_t2`) is the only table in its excerpt, so a parse
of the excerpt sees it at ordinal 1; the tests read those through `read_tables` at ordinal 2.

| file | command |
|---|---|
| `02008R1272-20200101_AN-VI_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32008R1272 02008R1272-20200101 "AN VI" --table 3 --rows 80` |
| `02008R1272-20200501_AN-VI_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32008R1272 02008R1272-20200501 "AN VI" --table 3 --rows 80` |
| `02008R1272-20200501_AN-VI_t2.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32008R1272 02008R1272-20200501 "AN VI" --table 4 --rows 10` |
| `02009R1223-20150416_AN-V_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32009R1223 02009R1223-20150416 "AN V" --table 1 --rows 47` |
| `02009R1223-20150716_AN-V_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32009R1223 02009R1223-20150716 "AN V" --table 1 --rows 47` |
| `02012R0528-20210329_AN-I_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0528 02012R0528-20210329 "AN I" --table 1 --rows 40` |
| `02012R0528-20210610_AN-I_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0528 02012R0528-20210610 "AN I" --table 1 --rows 40` |
| `02012R0649-20220701_AN-I_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0649 02012R0649-20220701 "AN I" --table 1 --rows 10` |
| `02012R0649-20231101_AN-I_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0649 02012R0649-20231101 "AN I" --table 1 --rows 10` |
| `02012R0649-20220701_AN-I_t2.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0649 02012R0649-20220701 "AN I" --table 2 --rows 6` |
| `02012R0649-20231101_AN-I_t2.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0649 02012R0649-20231101 "AN I" --table 2 --rows 6` |
| `02012R0649-20261001_AN-V_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0649 02012R0649-20261001 "AN V" --table 1 --rows 12` |
| `02012R0649-20261001_AN-V_t2.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32012R0649 02012R0649-20261001 "AN V" --table 2 --rows 13` |
| `02019R1021-20251015_AN-I_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32019R1021 02019R1021-20251015 "AN I" --table 1 --rows 6` |
| `02019R1021-20251203_AN-I_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32019R1021 02019R1021-20251203 "AN I" --table 1 --rows 6` |
| `02009R1107-20221121_AN-III_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32009R1107 02009R1107-20221121 "AN III" --table 1 --rows 150` |
| `02009R1107-20260616_AN-III_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32009R1107 02009R1107-20260616 "AN III" --table 1 --rows 150` |
| `02023R1542-20250731_AN-I_t1.xml` | `uv run python scripts/validation/substance_tables.py excerpt 32023R1542 02023R1542-20250731 "AN I" --table 1 --rows 5` |

The pairs were chosen so that at least one keyed row moves inside the excerpt: CLP Annex VI
Table 3 row 80 (`006-044-00-7`) is amended between 2020-01-01 and 2020-05-01; Cosmetics Annex V
entry `39` is amended between 2015-04-16 and 2015-07-16; Biocides Annex I gains two entries
between 2021-03-29 and 2021-06-10; PIC Annex I Parts 1 and 2 gain entries at the top between
2022-07-01 and 2023-11-01; POPs Annex I's first six entries are amended between 2025-10-15 and
2025-12-03; Plant protection products Annex III gains entries 145 to 150 between 2022-11-21 and
2026-06-16. Batteries Annex I and PIC Annex V are one version each.
