"""A tree to the bytes of one version file, and those bytes back to a tree.

The bytes are a function of the tree and the version asked for, and of nothing else: each line
is `model_dump_json()` plus `\\n`, in pre-order, gzipped at level 9 with a zero `mtime` and no
file name in the header, so two writes of one version are the same file. Dates and table rows
are not kept; a reader gets a tree whose nodes carry no dates and which holds no table entries.

Reading is never allowed to raise over a damaged file. Anything that does not decompress,
validate, match its own header or rebuild into a tree comes back as an `UnreadableVersion`
naming what was wrong.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import zlib
from dataclasses import dataclass, field

from pydantic import ValidationError

from emendrix.core import (
    ActId,
    ComparisonText,
    ProvisionLocation,
    ProvisionNode,
    ProvisionText,
    ProvisionTree,
    VersionId,
)
from emendrix.texts.model import (
    STORE_SCHEMA,
    StoredNode,
    StoredVersion,
    StoredVersionFile,
    UnreadableVersion,
)

__all__ = ["decode", "digest_of", "encode", "rebuild"]


def digest_of(comparison_text: str) -> str:
    """The deduplication key a reader can pool identical texts by."""
    return hashlib.sha256(comparison_text.encode("utf-8")).hexdigest()


def _lines(tree: ProvisionTree, version: str) -> list[str]:
    nodes: list[StoredNode] = []
    for root in tree.roots:
        _collect(root, None, nodes)
    header = StoredVersion(
        store_schema=STORE_SCHEMA,
        corpus=tree.act.corpus,
        key=tree.act.key,
        version=version,
        served_version=str(tree.version),
        language=tree.language,
        nodes=len(nodes),
        units=len(tree.roots),
    )
    return [header.model_dump_json(), *(node.model_dump_json() for node in nodes)]


def _collect(node: ProvisionNode, parent: str | None, into: list[StoredNode]) -> None:
    location = node.location.canonical
    into.append(
        StoredNode(
            location=location,
            parent=parent,
            heading=node.heading,
            text=node.text,
            comparison_text=node.comparison_text,
            digest=digest_of(node.comparison_text),
        )
    )
    for child in node.children:
        _collect(child, location, into)


def encode(tree: ProvisionTree, version: str) -> bytes:
    """The whole version file for `tree`, filed under the version that was asked for."""
    body = "".join(f"{line}\n" for line in _lines(tree, version)).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0) as out:
        out.write(body)
    return buffer.getvalue()


def decode(data: bytes, version: str) -> StoredVersionFile | UnreadableVersion:
    """Header plus nodes, or why the bytes are not a version file of `version`."""
    try:
        text = gzip.decompress(data).decode("utf-8")
    except (OSError, EOFError, zlib.error, UnicodeDecodeError) as error:
        return UnreadableVersion(version=version, detail=f"does not decompress: {error}")
    lines = text.split("\n")
    if len(lines) < 2 or lines[-1] != "":
        return UnreadableVersion(version=version, detail="does not end in a complete line")
    try:
        header = StoredVersion.model_validate_json(lines[0])
        nodes = tuple(StoredNode.model_validate_json(line) for line in lines[1:-1])
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "line"
        return UnreadableVersion(
            version=version, detail=f"a line does not validate: {where}: {first['msg']}"
        )
    problem = _inconsistency(header, nodes, version)
    if problem is not None:
        return UnreadableVersion(version=version, detail=problem)
    return StoredVersionFile(header=header, nodes=nodes)


def _inconsistency(
    header: StoredVersion, nodes: tuple[StoredNode, ...], version: str
) -> str | None:
    if header.version != version:
        return f"the header names {header.version}, not {version}"
    if header.nodes != len(nodes):
        return f"the header counts {header.nodes} nodes and {len(nodes)} follow"
    units = sum(1 for node in nodes if node.parent is None)
    if header.units != units:
        return f"the header counts {header.units} units and {units} follow"
    for node in nodes:
        if node.digest != digest_of(node.comparison_text):
            return f"the digest of {node.location} does not match its comparison text"
    return None


@dataclass
class _Open:
    """A node being rebuilt, whose children are still arriving."""

    stored: StoredNode
    location: ProvisionLocation
    children: list[ProvisionNode] = field(default_factory=list)

    def close(self) -> ProvisionNode:
        return ProvisionNode(
            location=self.location,
            heading=self.stored.heading,
            text=ProvisionText(self.stored.text),
            comparison_text=ComparisonText(self.stored.comparison_text),
            children=tuple(self.children),
        )


def rebuild(stored: StoredVersionFile) -> ProvisionTree | UnreadableVersion:
    """The tree the file was written from, less dates and table rows.

    Pre-order means a node's parent is always one of the nodes still open above it; one that is
    not is a damaged file, reported as unreadable rather than guessed at.
    """
    version = stored.header.version
    roots: list[ProvisionNode] = []
    stack: list[_Open] = []
    try:
        for node in stored.nodes:
            while stack and stack[-1].stored.location != node.parent:
                _pop(stack, roots)
            if node.parent is not None and not stack:
                return UnreadableVersion(
                    version=version,
                    detail=f"{node.location} names a parent {node.parent} not open above it",
                )
            stack.append(_Open(stored=node, location=ProvisionLocation.parse(node.location)))
        while stack:
            _pop(stack, roots)
        return ProvisionTree(
            act=ActId(corpus=stored.header.corpus, key=stored.header.key),
            version=VersionId(stored.header.served_version),
            language=stored.header.language,
            roots=tuple(roots),
        )
    except ValueError as error:
        return UnreadableVersion(version=version, detail=f"does not rebuild into a tree: {error}")


def _pop(stack: list[_Open], roots: list[ProvisionNode]) -> None:
    closed = stack.pop().close()
    (stack[-1].children if stack else roots).append(closed)
