# Reports

Measured numbers, dated, committed, and generated. Never hand-edited.

```
eval/YYYY-MM-DD-<git short sha>.md      the run, written for a person
eval/YYYY-MM-DD-<git short sha>.json    the same run, for anything that reads numbers
faithfulness-review-YYYY-MM-DD.md       the human spot-review sheet, generated unticked
faithfulness-signoff-YYYY-MM-DD.json    that sheet's result, written by a person
judge-benchmark-YYYY-MM-DD.md           how far the LLM judge agrees with that person
```

The date comes from the CLI boundary and the revision from `git rev-parse --short HEAD`, so the
sha names the commit the corpus was *scored at*: the parent of the commit that adds the report.
Two runs of the same corpus at the same revision produce byte-identical files; the Markdown and
the JSON always describe the same run. One report per date: a re-score on the same day at a later
revision supersedes the earlier file, and `emendrix eval publish-readme` refuses to guess between
two reports that share a date rather than picking one alphabetically.

Every date in a file name here is the **run date passed at the CLI boundary**, which is not always
the day the work happened. A review sheet takes its name from the run it was generated for and a
ticked sheet is never overwritten, so each new sheet takes the next free date and can carry a date
later than the day it was read. The one date that always means what it says is `reviewed_on`
inside a sign-off: that is the day a person read the twenty triples.

Each report is **layered**. The deterministic sections come first (localisation, classification,
corroboration, coverage, every disagreement verbatim) and the model layer follows: citation
grounding over the pinned explanation subset, then the sampled faithfulness check, under its own
heading and never folded into the grounding number.

```bash
uv run emendrix eval run                 # score both layers offline and write both files
uv run emendrix eval run --no-model      # the deterministic layers alone
uv run emendrix eval run --no-write      # just the headline, no files
uv run emendrix eval publish-readme      # regenerate the README's metrics section from the newest
```

Two artifacts are generated from the newest report here and never by hand: the README's metrics
table (`uv run emendrix eval publish-readme`) and the site's methodology page
(`uv run emendrix site build`). Both render the same `MetricRow` objects
(`src/emendrix/eval_/metric_rows.py`), so they cannot disagree about a figure or about the caveat
attached to it, and a test regenerates each and fails on any difference.

Every published number in this repository is generated from the newest committed report here.
Nothing in a report is edited afterwards: if a figure is wrong, the fix is in the code that
measured it, and the next report says so. What the numbers do and do not mean travels inside each
report, as fixed text, so a figure can never be quoted without its caveat
(`src/emendrix/eval_/prose.py`, `src/emendrix/eval_/model_report.py`).

The faithfulness worksheet is generated with every writing run and is **filled in by a person**.
Nothing in emendrix ticks one of its boxes, and a sheet that carries a tick is never overwritten
by a later run. The report says `human review: pending` until the newest
`faithfulness-signoff-YYYY-MM-DD.json` says otherwise: that file is written by hand, carries the
reviewer, the date, a summary line and a verdict per triple, and is guarded by a digest over the
exact sample it reviewed. When the sample moves, the published line reverts to `pending` by itself.

One sign-off per sheet, named for the sheet, and they accumulate. A review is a dated artifact
like the report beside it, and an older one stays readable rather than surviving only in git
history: it is the label set the judge benchmark below is scored against, and a benchmark whose
labels live in a commit is one nobody reruns. The newest is the only one a report may publish,
and the digest decides whether even that one is published at all.

```bash
uv run emendrix eval sample-digest       # the digest, and the 20 entries a review has to cover
```

Because a sign-off carries a verdict per entry, it is also a small labelled set the LLM judge
itself can be scored against, and `judge-benchmark-YYYY-MM-DD.md` is that score: the reviewer's
verdicts joined to each judge's committed verdicts on the same twenty prompts, with the direction
of every disagreement. It is **not** the faithfulness rate and is never folded into it. Faithfulness
asks whether the shipped sentences follow from the evidence the writer was given, the pipeline
header and the two capped texts since 2026-08-09 and the two texts alone before it; this asks
whether a judge agrees with a person about that, over twenty entries read by one reviewer in one
afternoon. A benchmark scored under one question does not compare with one scored under the other,
which is why each report names the rubric digest its judges answered under.

The benchmark reads one named sign-off rather than the newest, because a judgement is an answer to
one exact prompt: the committed judgements answer the sample reviewed on 2026-08-08, and scoring
a later review's twenty prompts would need those twenty recorded first. `--signoff` moves it.

```bash
uv run emendrix eval judge-benchmark     # score the judges against the committed hand review
```

**Not legal advice.** These reports describe agreement between machine-computed readings of
published legal texts. They say nothing about whether any change matters to anyone, and nothing
here is a substitute for reading the official consolidated text on
[EUR-Lex](https://eur-lex.europa.eu/) or for professional legal counsel.
