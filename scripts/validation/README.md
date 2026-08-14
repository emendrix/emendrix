# scripts/validation

One-off validation code, outside the package and exempt from its rules. It exists so that the
numbers behind this project's data-source claims are reproducible artifacts rather than
assertions. It is **not** production code and nothing under `src/emendrix/` imports it:

- stdlib + `httpx` only, no package structure, no tests, exempt from the ~300-line module cap;
- it hits live Publications Office endpoints, which no other part of the repository does at test
  time, and CI never runs it;
- `src/emendrix/` reimplements all of it properly (typed, cached, fixture-driven).

`trace.py` fetches with a 3-second delay and caches every response under `.cache/` (gitignored), so
a second run of any command below is offline and free.

## Commands behind the committed reports

Each command writes `results/<name>.txt`; those files are committed and are the measured record.

```bash
uv run python scripts/validation/trace.py --write versions     32017R0745
uv run python scripts/validation/trace.py --write versions     32006R1907
uv run python scripts/validation/trace.py --write annotations  32017R0745
uv run python scripts/validation/trace.py --write annotations  32006R1907
uv run python scripts/validation/trace.py --write annotations  32024R1689

uv run python scripts/validation/trace.py --write trace 32024R1689 original 20260727
uv run python scripts/validation/trace.py --write trace 32017R0745 20170505 20200424
uv run python scripts/validation/trace.py --write trace 32017R0745 20230311 20230320
uv run python scripts/validation/trace.py --write trace 32017R0745 20230320 20240709
uv run python scripts/validation/trace.py --write trace 32017R0745 20240709 20250110
uv run python scripts/validation/trace.py --write trace 32006R1907 20220501 20221014
uv run python scripts/validation/trace.py --write trace 32006R1907 20081012 20090120 \
  --substitution preparation:mixture
```

`versions` inventories an act's consolidated versions and their English manifestations.
`annotations` inventories its CELLAR modification annotations (the observed role and location
vocabulary corroboration needs). `trace` runs the three-way comparison for one version pair:

1. structural Formex diff of the two consolidated texts;
2. CELLAR modification annotations whose `START_OF_VALIDITY` falls in `(date(A), date(B)]`;
3. a deliberately naive parse of the amending acts' instruction prose;

and prints per-signal provision sets, P/R/F1 of (1) against (2), and the disagreements.

`--substitution OLD:NEW` answers "how many diff-only units does one blanket word substitution
explain?" Used for the REACH 2008→2009 trace, where the amending act orders one such substitution
"throughout the text" and CELLAR annotates it once.

## Reading the output

- `original` as a version tag means the act as published in the OJ, used when the first consolidated
  version is not available in English.
- Units are keyed as `AR 5`, `AR 10a`, `AN VI`: the top-level provision, which is the unit of change.
- `P n/a` means both compared sets were empty; it is not a score of zero.

Nothing here interprets law. Every claim it makes is either a count, a set comparison, or a
verbatim quotation from a fetched document.
