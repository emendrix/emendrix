"""`emendrix.output` — the artifacts the loop exists to produce.

WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT ends in a typed document
(`graph/report.py`). This package turns that document into the two things a person and a
program actually consume, and commits both into a git repository:

1. **A Markdown changelog per act**, newest entry first, committed and diffable. This is the
   primary artifact of the project: your regulatory dependencies get the review workflow your
   code dependencies already have.
2. **Structured JSON** of the same content, versioned from the first byte because other tools
   read it.

Nothing here reads a clock, reaches a network, calls a model or knows whose corpus it is
rendering: the observation date arrives on the entry, citations were rendered by the adapter at
emit time, and the whole package renders the toy corpus exactly as it renders law. That makes the
output byte-stable, which is a requirement rather than an aesthetic preference: a changelog is
reviewed as a git diff, so a re-run that changes only ordering or a timestamp is a bug.

Layout:

- `disclaimer.py`: the not-legal-advice line, in both artifacts' shapes, on every output.
- `json_out.py`: `ChangelogEntry`, the versioned JSON document and the renderer's input.
- `markdown.py`: one amendment event, with the four properties its format forces.
- `changelog.py`: the `CHANGELOG.md` file: header, entry markers, newest version first.
- `git.py`: the git command line, scoped so it cannot touch anything but that repository.
- `repo.py`: the writer: open-or-init, write, commit, never push, idempotent.
- `config.py`: where the repository lives: flag > environment > `watchlist.toml`.
"""

from emendrix.output.changelog import MARKER, changelog_text, header_for, split_entries
from emendrix.output.config import OUTPUT_REPO_ENV, resolve_repo_path
from emendrix.output.disclaimer import MARKDOWN_DISCLAIMER
from emendrix.output.git import AUTHOR_EMAIL, AUTHOR_NAME, GitError
from emendrix.output.json_out import (
    DIFF_ONLY_NOTE,
    SCHEMA_VERSION,
    ChangelogEntry,
    EntryCounts,
    diff_only_entry,
    entries_for,
)
from emendrix.output.markdown import (
    QUOTE_CHAR_CAP,
    TRUNCATION_MARKER,
    render_entry,
    render_standalone,
)
from emendrix.output.repo import (
    MARKER_FILE,
    ForeignRepository,
    NestedRepository,
    OutputRepo,
    WriteResult,
)

__all__ = [
    "AUTHOR_EMAIL",
    "AUTHOR_NAME",
    "DIFF_ONLY_NOTE",
    "MARKDOWN_DISCLAIMER",
    "MARKER",
    "MARKER_FILE",
    "OUTPUT_REPO_ENV",
    "QUOTE_CHAR_CAP",
    "SCHEMA_VERSION",
    "TRUNCATION_MARKER",
    "ChangelogEntry",
    "EntryCounts",
    "ForeignRepository",
    "GitError",
    "NestedRepository",
    "OutputRepo",
    "WriteResult",
    "changelog_text",
    "diff_only_entry",
    "entries_for",
    "header_for",
    "render_entry",
    "render_standalone",
    "resolve_repo_path",
    "split_entries",
]
