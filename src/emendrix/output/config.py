"""Where the output repository lives: flag > environment > `watchlist.toml`.

Three sources, one order, stated once so `emendrix run` and `emendrix explain` cannot disagree
about it:

| Source | Form | Wins over |
|---|---|---|
| Flag | `--output-repo ~/regulatory-changelog` | everything |
| Environment | `EMENDRIX_OUTPUT_REPO=~/regulatory-changelog` | the file |
| File | `[output] repo_path = "~/regulatory-changelog"` in `watchlist.toml` | — |

**There is no default, and that is deliberate.** Every other path this project picks by itself
(the response cache, the watch state) is disposable and lives under a per-user directory; a git
repository the tool commits into is neither. With nothing configured, `run` and `explain` print
their report and write no files: silence, rather than a repository appearing somewhere the user
did not ask for one.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

__all__ = ["OUTPUT_REPO_ENV", "resolve_repo_path"]

OUTPUT_REPO_ENV: Final = "EMENDRIX_OUTPUT_REPO"


def resolve_repo_path(
    flag: Path | None = None,
    configured: Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """Apply the precedence above. `None` means no output repository was configured at all."""
    if flag is not None:
        return flag
    from_env = (environment if environment is not None else os.environ).get(OUTPUT_REPO_ENV, "")
    if from_env.strip():
        return Path(from_env.strip())
    return configured
