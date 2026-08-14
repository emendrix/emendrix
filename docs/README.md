# Documentation

Reference material for emendrix, split by question. [`../README.md`](../README.md) is the
operator's entry point: install it, run it, configure it, deploy it. Everything here is the
methodology behind what it prints.

| File | Answers |
|---|---|
| [`architecture.md`](./architecture.md) | How the code is layered, what the `CorpusAdapter` seam is, how the structural diff works, and why a graph framework assembles a near-linear pipeline |
| [`pipeline.md`](./pipeline.md) | Each stage of `WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT` in loop order, the model's narrow mandate, the citation gate, and how to run the whole thing |
| [`evaluation.md`](./evaluation.md) | Three-way corroboration, the labelled corpus, what each published number means and what it does not, the judge, and the hand reviews behind the sign-offs |
| [`output-format.md`](./output-format.md) | The output git repository, the Markdown shape, the versioned JSON schema, and every cap that can truncate a quote |
| [`site.md`](./site.md) | What `emendrix site build` writes: the pages, the Atom feeds, the search index and the discovery files |
| [`limitations.md`](./limitations.md) | The failure modes, and where the release's own limitations are enumerated |
| [`roadmap.md`](./roadmap.md) | What did not fit inside the v0.1 caps |
| [`explainers/`](./explainers/) | Hand-written HTML walkthroughs of the shipped code, each one stating the revision it describes |

The published metrics table lives in [`../README.md`](../README.md), generated from the newest
committed report by `uv run emendrix eval publish-readme`. There is one of it, in one place, and
nothing here retypes a number from it.

**Not legal advice.** emendrix produces engineering assistance: a machine-computed description of
textual differences between published versions of legal acts. Nothing in this directory, and
nothing the tool emits, is a substitute for reading the official consolidated text on
[EUR-Lex](https://eur-lex.europa.eu/) or for professional legal counsel.
