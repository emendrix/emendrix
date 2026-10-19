"""Where the text store lives: flag > environment > `watchlist.toml`.

| Source | Form | Wins over |
|---|---|---|
| Flag | `--text-store ~/emendrix-texts` | everything |
| Environment | `EMENDRIX_TEXT_STORE=~/emendrix-texts` | the file |
| File | `[output] text_store_path = "~/emendrix-texts"` in `watchlist.toml` | — |

The same order as the output repository's (`output/config.py`), and for the same reason there
is no default: a directory holding the full text of every watched act is not a cache to appear
somewhere nobody asked for one. It lives beside the changelogs repository, never inside it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

__all__ = ["TEXT_STORE_ENV", "resolve_store_path"]

TEXT_STORE_ENV: Final = "EMENDRIX_TEXT_STORE"


def resolve_store_path(
    flag: Path | None = None,
    configured: Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """Apply the precedence above. `None` means no text store was configured at all."""
    if flag is not None:
        return flag
    from_env = (environment if environment is not None else os.environ).get(TEXT_STORE_ENV, "")
    if from_env.strip():
        return Path(from_env.strip())
    return configured
