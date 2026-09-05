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

Three scripts here do import the package, because what they measure *is* the package. All three
read through the same client, the same composition root and the same disk cache the loop uses,
write nothing, call no model and are offline unless `--fetch` is passed.

`instruction_effect_dates.py` measures how often an amending act says when its instructions take
effect (`src/emendrix/eu/instructions/effect.py`, and the two readers beside it). Its figures are
quoted in [`../../docs/limitations.md`](../../docs/limitations.md):

```bash
uv run python scripts/validation/instruction_effect_dates.py            # every cached act
uv run python scripts/validation/instruction_effect_dates.py --fetch    # and the rest
uv run python scripts/validation/instruction_effect_dates.py --verbose 32019R2033
uv run python scripts/validation/instruction_effect_dates.py --markup 32021R2117
```

`--markup` prints an act's final-provisions articles as the package holds them and reads nothing
else. `tests/fixtures/eu/celex_32021R2117.article6.xml` is that command's output, redirected, so
the markup a test asserts against was never retyped.

`instruction_claim_scoping.py` measures the other end: how many of the claims already published
in the changelog corpus the consolidation window takes back. It wants a clone of that corpus,
which is a separate repository and is never committed here, so a reading is dated by the commit
of the clone it was taken over:

```bash
git clone https://github.com/emendrix/changelogs /tmp/changelogs
uv run python scripts/validation/instruction_claim_scoping.py /tmp/changelogs
uv run python scripts/validation/instruction_claim_scoping.py /tmp/changelogs --verbose
```

`evidence_staleness.py` measures the one correction in this project that costs money. An
explanation is written about a particular pair of verbatim texts and cannot be recomputed, so a
parser fix that moves stored text leaves prose describing evidence the page no longer shows. It
re-derives both versions of every committed event through today's parser and reports, per change,
whether the evidence matches, differs, or cannot be derived, plus the transitions affected and how
many characters the differing changes carry. It wants the same corpus clone:

```bash
uv run python scripts/validation/evidence_staleness.py /tmp/changelogs
uv run python scripts/validation/evidence_staleness.py /tmp/changelogs --verbose
```

An entry written from 2026-09-05 carries an evidence digest and answers this by arithmetic. One
written before that carries none, and the script compares its stored text instead, counting the
two bases separately: what the model was shown is a fact only the run that made the call can
record, and nothing here writes a digest onto anything.

The rule for reading those two bases in that order lives in `emendrix.repair.staleness` and is
imported here rather than repeated, because `emendrix repair evidence --dry-run` selects and
prices the changes it would ask about with the same comparison. This script measures the reach
of a correction over a whole corpus in one parse per version; the command decides, per entry,
what a correction would cost and then carries it out.

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
