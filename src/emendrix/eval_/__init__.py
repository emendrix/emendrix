"""`emendrix.eval_`: the measured-honesty machinery, deterministic layers and model layers.

The trailing underscore keeps the package from shadowing the builtin. What it holds is the answer
to "how do you know?": a committed labelled corpus, a runner that scores the shipped pipeline
against it offline, and the dated reports under `reports/` every published number is generated
from.

```
corpus.py       what a case is, what a skip is, the selection rules, the explanation subset
build.py        generating the corpus from CELLAR: the only module here that may use the network
pins.py         pinning the documents each case is computed from, by digest
runner.py       scoring the committed corpus offline, through the shipped pipeline
metrics.py      scoring one transition: corpus-agnostic, so the meter can be tested on the toy
aggregate.py    pooling transitions: micro over units, macro over transitions
subset.py       choosing the pinned changes the model layer is measured over
model_run.py    explain → gate → revise → settle over that subset, from committed cassettes
model_metrics.py  what that produced, as counts: grounding, retry recovery, fallback
judge.py        the faithfulness types and the sampling rule
judgements.py   the judgement cassette, its key, its store and the replay that reads them
rubric.py       what the judge is asked, as literal text
faithfulness.py the judge agent, the one place outside `explain/` that may import pydantic-ai
worksheet.py    the human spot-review sheet, generated unticked
signoff.py      that sheet's committed result, and the digest that limits what it may claim
benchmark.py    scoring a judge against that result: the only evidence about the judge itself
prose.py        the fixed report text: the rigour table, the caveats, the known holes
metric_rows.py  the published rows, so the README and the site cannot disagree about them
report.py       the dated Markdown + JSON under reports/eval/, layered
model_report.py the model layer's own sections of it
readme_table.py the README metrics section, generated from the newest committed report
thresholds.py   committed floors; a number may rise silently, never fall
corpus_cli.py   `emendrix eval build-corpus | build-subset`: building the labelled set
benchmark_cli.py  `emendrix eval judge-benchmark`: that comparison, as a dated report
cli.py          `emendrix eval run | sample-digest | publish-readme`: scoring it, and the app
```

**Nobody here decides what changed.** The labels are the corpus's own: the Publications Office
publishes provision-level modification coordinates in each act's branch notice, and this package
scores the structural diff against them at article-or-annex granularity. `corpus.json` is
generated from those notices by `emendrix eval build-corpus`, so no hand-authored gold set exists
in this repository and none is possible.

**The reference set is incomplete in a known way.** CELLAR annotates a blanket amendment once
without enumerating the provisions it lands in, so a unit only the diff names is not automatically
a false positive: on REACH 2008 → 2009 the diff finds 40 units and the metadata 9, and the diff is
right. That transition stays in the corpus, its disagreements ship, and diff-only units are
counted as their own class instead of folded into precision. Curating them out would be the one
unrecoverable failure of this project.

**Two layers, one report.** The deterministic layers score every transition, because that costs
nothing but CPU; the model layers score a small pinned subset of changes, because each one is a
recorded exchange with a provider, committed to this repository and replayed in CI. Both go into
one dated report, in layered sections, so a regression localises to a layer rather than to "the
pipeline". Grounding and faithfulness never share a number: the first is a deterministic property
of the citation gate, the second a judgement sampled at n = 20 and withheld outright when the
judgements behind it came from a stub. Merging them would produce one impressive figure and
destroy the meaning of both.

**The fixtures are committed** rather than primed into a cache by CI, so every published number
rests on documents a reader can open: both texts of each transition, trimmed by the reproducible
rules in `eu/trims.py` and pinned by digest in the case's `inputs`. The one exception is an
amending act whose own Formex exceeds `build.MAX_INSTRUCTION_BYTES`, the CLP Regulation being
3.3 MB, and a case that loses its third signal to that cap says so in the report.
"""
