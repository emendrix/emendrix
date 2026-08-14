"""The watchlist: which acts this installation cares about, and the filter that finds them.

```toml
# watchlist.toml
[[acts]]
celex   = "32024R1689"
name    = "AI Act"
domain  = "Digital"                    # groups the act on the published site
aliases = ["Artificial Intelligence Act"]   # other names a search should find it under

[output]
repo_path = "~/regulatory-changelog"   # where the committed changelog lives
```

`name`, `domain` and `aliases` are labels for output only: identity is the CELEX, exactly as
everywhere else in the system (`core.ActId`). The published site groups and searches by them, and
nothing in the system ever resolves an act through any of them. A file naming an act twice, or
naming something that is not a CELEX, is refused at load time with the line's own value in the
message: this is the one input a person writes by hand, so it is the one place worth being
strict.

## Why the index is a separate object

The `ingestion` channel carries ~3,000 notifications a day and a watchlist hit is rare: the AI
Act's consolidation was 46 entries out of 3,819 on 2026-08-05. So matching has to be string work.
`WatchIndex` builds two dictionaries once per poll, and every entry after that costs a
`partition`, a `dict` lookup and, only for the two identifier families that can name an act, a
regex.

An act surfaces under **two** identifier forms and both must match: the act's own CELEX
`32024R1689` when its work record is updated, and the consolidated form `02024R1689-20260727` /
`2024R1689/20260727` when a new version is built, which is the form that carries the news. The
consolidated form drops the sector digit, so it is matched on the act code (`2024R1689`) and the
plain CELEX on the whole identifier. Reading either is `eu/identifiers.py`'s job, and it is the
one module that knows every identifier family the feed can carry, so a second regex here would be
a second answer to the same question.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from emendrix.core import ActId
from emendrix.eu.feed_atom import FeedEntry, FeedIdentifier
from emendrix.eu.identifiers import Celex, ConsolidatedId, act_id, parse_identifier

__all__ = [
    "EXAMPLE_PATH",
    "OutputConfig",
    "WatchIndex",
    "WatchMatch",
    "WatchedAct",
    "Watchlist",
    "load_watchlist",
]

EXAMPLE_PATH = Path("watchlist.example.toml")
"""The shipped example, holding the four acts the eval corpus is built from."""


class WatchedAct(BaseModel):
    """One act on the watchlist."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    celex: str = Field(description="CELEX of the act as published, e.g. 32024R1689.")
    name: str | None = Field(default=None, description="Label for output; never identity.")
    domain: str | None = Field(
        default=None, description="Site grouping label, e.g. 'Data & privacy'; never identity."
    )
    aliases: tuple[str, ...] = Field(
        default=(), description="Other names the site's search should find this act under."
    )

    @field_validator("celex")
    @classmethod
    def _valid_celex(cls, value: str) -> str:
        return Celex.parse(value).value

    @property
    def act(self) -> ActId:
        return act_id(Celex.parse(self.celex), display_name=self.name)

    @property
    def act_code(self) -> str:
        """`2024R1689` — how the consolidated forms of this act name it."""
        return Celex.parse(self.celex).act_code


class OutputConfig(BaseModel):
    """The `[output]` table: where the changelog git repository lives.

    It rides in `watchlist.toml` because that is the one file a person writes by hand, and a
    second config file for one path would be a worse answer than a second table in this one.
    The precedence between this value, `EMENDRIX_OUTPUT_REPO` and `--output-repo` is
    `output/config.py`'s to state; this is only the file end of it. `None` means no output
    repository is configured, and nothing is written.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repo_path: Path | None = Field(
        default=None, description="Path to the changelog git repository; created if absent."
    )


class Watchlist(BaseModel):
    """Every act being watched, in the order the file lists them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    acts: tuple[WatchedAct, ...] = ()
    output: OutputConfig = OutputConfig()

    @model_validator(mode="after")
    def _no_duplicates(self) -> Self:
        seen = [entry.celex for entry in self.acts]
        repeated = sorted({value for value in seen if seen.count(value) > 1})
        if repeated:
            raise ValueError(f"watchlist names the same act twice: {', '.join(repeated)}")
        return self


class WatchMatch(BaseModel):
    """A feed identifier that names a watched act, and the version it announced.

    `version` is `None` when the identifier named the act itself rather than one of its
    consolidations — the work record was touched, and which version that implies is a question
    for the act's tree notice, not for the feed.
    """

    model_config = ConfigDict(frozen=True)

    watched: WatchedAct
    identifier: str
    version: str | None = None


class WatchIndex:
    """The cheap filter: identifiers in, watched acts out. Built once per poll."""

    def __init__(self, watchlist: Watchlist) -> None:
        self.watchlist = watchlist
        self._by_celex = {entry.celex: entry for entry in watchlist.acts}
        self._by_act_code = {entry.act_code: entry for entry in watchlist.acts}

    def match(self, identifier: FeedIdentifier) -> WatchMatch | None:
        """One identifier → the act it names, if that act is watched."""
        if not identifier.readable:
            return None
        parsed = parse_identifier(identifier.value)
        if isinstance(parsed, ConsolidatedId):
            watched = self._by_act_code.get(parsed.act_code)
            if watched is None:
                return None
            return WatchMatch(watched=watched, identifier=str(identifier), version=parsed.value)
        if isinstance(parsed, Celex):
            watched = self._by_celex.get(parsed.value)
            if watched is None:
                return None
            return WatchMatch(watched=watched, identifier=str(identifier))
        return None

    def match_entry(self, entry: FeedEntry) -> WatchMatch | None:
        """The first watched act an entry names, preferring an identifier that names a version.

        One entry carries the same work under several identifiers — `consolidation:`,
        `celex:` and `eli:` for a consolidation — so the consolidated form is preferred: it is
        the one that says *which* version was built.
        """
        fallback: WatchMatch | None = None
        for identifier in entry.readable_identifiers:
            found = self.match(identifier)
            if found is None:
                continue
            if found.version is not None:
                return found
            fallback = fallback if fallback is not None else found
        return fallback


def load_watchlist(path: Path) -> Watchlist:
    """Read and validate `watchlist.toml`. A missing file is an error, not an empty list."""
    if not path.is_file():
        raise FileNotFoundError(
            f"no watchlist at {path}: copy {EXAMPLE_PATH} and name the acts to watch"
        )
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path} is not valid TOML: {error}") from error
    return Watchlist.model_validate(payload)
