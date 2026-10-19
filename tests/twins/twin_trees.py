"""Small generic trees for the twin tests: numbered placeholder words, not legal text."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from emendrix.core import ActId, ProvisionNode, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.output import OutputRepo, diff_only_entry
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

ALPHA = ActId(corpus="toy", key="alpha")
BETA = ActId(corpus="toy", key="beta")


def words(count: int, start: int = 0, stem: str = "w") -> list[str]:
    """`count` distinct placeholder words, `w000`, `w001`, ..."""
    return [f"{stem}{index:03d}" for index in range(start, start + count)]


def text(count: int, start: int = 0, *, change: dict[int, str] | None = None) -> str:
    """`count` words from `start`, with the words at the given offsets replaced."""
    chosen = words(count, start)
    for offset, word in (change or {}).items():
        chosen[offset] = word
    return " ".join(chosen)


def node(
    location: str, body: str, *children: ProvisionNode, heading: str | None = None
) -> ProvisionNode:
    """A node whose text is its own words followed by its children's, as a parser builds it."""
    whole = " ".join([body, *(str(child.text) for child in children)]).strip()
    return ProvisionNode.from_plain_text(location, whole, heading=heading, children=children)


def tree(act: ActId, version: str, *roots: ProvisionNode) -> ProvisionTree:
    return ProvisionTree(act=act, version=VersionId(version), language="ENG", roots=roots)


def changelog_repo(path: Path) -> OutputRepo:
    """A changelog repository emendrix created, holding one toy event and its indexes."""
    adapter = ToyCorpusAdapter(observed_on=date(2026, 8, 6))
    before, after = adapter.fetch_version(HOUSE_RULES, V1), adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    repo = OutputRepo.open(path)
    entry = diff_only_entry(compute_delta(before, after), detected_on=date(2026, 8, 6))
    assert repo.write(entry).committed
    return repo


def git_log(path: Path) -> list[str]:
    """Every commit subject, newest first."""
    listed = subprocess.run(
        ["git", "log", "--format=%s"], cwd=path, capture_output=True, text=True, check=True
    )
    return listed.stdout.splitlines()
