"""Shipping a backup: encrypt a dump to an `age` recipient, upload it over SFTP, prune old copies.

The second of the two modules that connect out. The dump is made and checked with
`pg_restore --list` by the database's own image before this runs, because a `pg_dump` of
another major version than the server's refuses to run. Here it is only checked to open as a
custom-format archive does, so an empty file or a captured error message is never shipped as a
backup; `pg_restore --list` is the check that it is whole.

Only the public half of the `age` key is ever here. The private half stays offline with the
operator, so nothing this service runs can decrypt a backup, and a stolen copy, or the storage
host itself, discloses nothing.

The host's key is pinned by a known-hosts file and nothing else: no agent, no OpenSSH client
configuration and no host key learned on first use. A host presenting a key the file does not
list is refused before a byte is sent. A copy is written under a temporary name and renamed
when complete, so an interrupted upload never leaves a partial file under a name prune keeps.
"""

from __future__ import annotations

import posixpath
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import asyncssh
import pyrage  # type: ignore[import-untyped]  # the package ships no type information
from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.ops.retain import PARTIAL, backup_name, dated, prunable

__all__ = [
    "DUMP_MAGIC",
    "ShipCounts",
    "Target",
    "connect",
    "encrypt",
    "is_custom_dump",
    "parse_target",
    "prune",
    "ship",
    "upload",
]

DUMP_MAGIC: Final = b"PGDMP"
"""The first bytes of every archive `pg_dump -Fc` writes."""

TIMEOUT: Final = 60.0
"""Seconds the connection and the login may each take."""


class Target(BaseModel):
    """Where copies go: a login on an SFTP host, and a directory there."""

    model_config = ConfigDict(frozen=True)

    username: str = Field(description="The login name.")
    host: str = Field(description="The host name.")
    port: int = Field(default=22, ge=1, le=65535, description="The SSH port.")
    directory: str = Field(description="The directory copies go to; `.` is the login's own.")


class ShipCounts(BaseModel):
    """What one shipment did."""

    model_config = ConfigDict(frozen=True)

    bytes: int = Field(description="The size of the encrypted copy uploaded.")
    kept: int = Field(description="Copies on the host after pruning, this one included.")
    pruned: int = Field(description="Copies pruned.")


def parse_target(text: str) -> Target:
    """`user@host:directory` or `user@host:port:directory`; raises `ValueError` otherwise."""
    username, at, rest = text.partition("@")
    host, colon, path = rest.partition(":")
    if not at or not username or not colon or not host:
        raise ValueError("must be user@host:directory or user@host:port:directory")
    port = 22
    first, second_colon, remainder = path.partition(":")
    if second_colon and first.isdigit():
        port, path = int(first), remainder
    return Target(username=username, host=host, port=port, directory=path or ".")


def is_custom_dump(path: Path) -> bool:
    """Whether `path` starts as a `pg_dump -Fc` archive does."""
    with path.open("rb") as stream:
        return stream.read(len(DUMP_MAGIC)) == DUMP_MAGIC


def encrypt(src: Path, dst: Path, recipient: str) -> int:
    """Encrypt `src` to the `age` public key `recipient` into `dst`, streamed; its size.

    Raises `ValueError` when `recipient` is not an `age` public key.
    """
    try:
        key = pyrage.x25519.Recipient.from_str(recipient.strip())
    except pyrage.RecipientError as error:
        raise ValueError("the age recipient is not an age public key") from error
    with src.open("rb") as reader, dst.open("wb") as writer:
        pyrage.encrypt_io(reader, writer, [key])
    return dst.stat().st_size


@asynccontextmanager
async def connect(
    target: Target, key_path: Path, known_hosts_path: Path
) -> AsyncIterator[asyncssh.SFTPClient]:
    """An SFTP session on the target host, its host key checked against `known_hosts_path`."""
    async with (
        asyncssh.connect(
            target.host,
            port=target.port,
            username=target.username,
            client_keys=[str(key_path)],
            known_hosts=str(known_hosts_path),
            config=None,
            agent_path=None,
            preferred_auth="publickey",
            connect_timeout=TIMEOUT,
            login_timeout=TIMEOUT,
        ) as connection,
        connection.start_sftp_client() as sftp,
    ):
        yield sftp


async def upload(sftp: asyncssh.SFTPClient, local: Path, directory: str, name: str) -> None:
    """Put `local` at `directory/name`, replacing a copy of the same name only when complete."""
    final = posixpath.join(directory, name)
    partial = final + PARTIAL
    try:
        await sftp.put(str(local), partial)
        if await sftp.exists(final):
            await sftp.remove(final)
        await sftp.rename(partial, final)
    except BaseException:
        # Best effort: a partial left behind is pruned on a later day.
        with suppress(asyncssh.Error, OSError):
            await sftp.remove(partial)
        raise


async def prune(sftp: asyncssh.SFTPClient, directory: str, today: date) -> tuple[int, int]:
    """Delete what `retain.prunable` names in `directory`; (copies kept, files pruned)."""
    names = [str(name) for name in await sftp.listdir(directory)]
    doomed = prunable(names, today)
    for name in doomed:
        await sftp.remove(posixpath.join(directory, name))
    copies = sum(1 for name in names if dated(name) is not None)
    return copies - sum(1 for name in doomed if dated(name) is not None), len(doomed)


async def ship(
    dump: Path,
    *,
    target: Target,
    key_path: Path,
    known_hosts_path: Path,
    recipient: str,
    today: date,
) -> ShipCounts:
    """Encrypt `dump` into a temporary directory, upload it as today's copy, and prune.

    The dump's own directory may be read-only to this process, and the encrypted copy is gone
    when this returns, whatever happened. Raises `ValueError` when `dump` is not a custom-format
    archive or the recipient is not a key; a connection, login or transfer failure propagates as
    asyncssh raised it.
    """
    if not is_custom_dump(dump):
        raise ValueError("the dump is not a pg_dump custom-format archive")
    name = backup_name(today)
    with TemporaryDirectory(prefix="emendrix-backup-") as scratch:
        encrypted = Path(scratch) / name
        size = encrypt(dump, encrypted, recipient)
        async with connect(target, key_path, known_hosts_path) as sftp:
            await upload(sftp, encrypted, target.directory, name)
            kept, pruned = await prune(sftp, target.directory, today)
    return ShipCounts(bytes=size, kept=kept, pruned=pruned)
