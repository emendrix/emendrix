# Explainers

Hand-written walkthroughs of how the shipped code works, for a reader who has the clone and no
other context. One file per topic, each a self-contained HTML page that opens from disk with no
network and no build step.

```
<topic-slug>.html      the page: prose, diagrams, and the file paths to read next
```

These are the opposite of `reports/` in every way that matters, and the two directories should
never be confused:

| | `reports/` | `docs/explainers/` |
|---|---|---|
| Written by | `emendrix eval run` | a person |
| Contains | measured numbers | explanation of mechanism |
| Edited afterwards | never | in place, whenever the code moves |
| Naming | dated and sha-stamped, one per run | one per topic, no date in the name |

A report is a fact about one moment and accumulates. An explainer describes the code as it stands
and is rewritten rather than duplicated, because a directory holding six stale copies of the same
walkthrough helps nobody.

## The rules a page here has to keep

**It states which revision it describes.** Every page carries the date it was written and the
short sha it was written against, in its header and nowhere else, so a reader can run
`git log <sha>..HEAD -- src/` and see for themselves how far it has drifted. A page that is stale
is still useful; a page that hides that it is stale is not.

**It is self-contained.** No CDN, no webfont URL, no remote image, no script. Everything is inline
so the page renders identically from a clone, from a checkout of an old tag, and offline. Diagrams
are hand-authored inline SVG, themed through `currentColor` and CSS custom properties, so they
read in both light and dark browsers.

**It references nothing outside the repository.** Same rule as the rest of the project: every
claim points at a file in this repository, which a reader with the clone already has. Where a page
quotes a number it names the report the number came from.

**Its numbers are quoted from a committed report, never retyped from memory.** Nothing here
measures anything. When the newest report in `reports/eval/` disagrees with a figure on a page,
the page is wrong.

**No em-dashes.** The project's prose rule applies to documentation as much as to code: a comma,
colon, semicolon or full stop does the job. Verbatim quotations of emendrix's own output are
exempt, because they are quotations.

## Why HTML and not Markdown

The rest of the project's prose is Markdown, and this directory is the one exception. These pages
carry diagrams that are the point rather than the decoration: a dependency direction, the shape of
the loop with the type on each arrow, the unit-matching pass, the two uses of the one offered
citation set. Markdown renderers strip inline SVG, and a walkthrough whose figures disappear on the
way to the reader is not a walkthrough. HTML also lets a page be opened straight from the working
tree with no toolchain, which Markdown only manages inside a forge.

## What is here

| Page | Covers | Written | Describes |
|---|---|---|---|
| [`architecture-walkthrough.html`](./architecture-walkthrough.html) | The whole system in five levels: the sealed core vocabulary, the seven-stage loop and the type on each arrow, the mechanism inside every stage, the measured evidence, and one provision traced end to end | 2026-08-09 | `162a8d7` |

**Not legal advice.** These pages describe a piece of software that computes readings of published
legal texts. They say nothing about whether any change matters to anyone, and nothing here is a
substitute for reading the official consolidated text on
[EUR-Lex](https://eur-lex.europa.eu/) or for professional legal counsel.
