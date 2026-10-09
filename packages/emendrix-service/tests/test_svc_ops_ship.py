"""Shipping a backup: an `age` round trip, an upload to an SFTP server in this process, pruning,
and a host whose key the known-hosts file does not list refused.

The server listens on 127.0.0.1 on a port the system picks, with a host key generated for the
test and a temporary directory as its root; nothing leaves the machine.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import asyncssh
import pyrage  # type: ignore[import-untyped]  # the package ships no type information
import pytest
from typer.testing import CliRunner

from emendrix_service.cli import app
from emendrix_service.ops.retain import backup_name
from emendrix_service.ops.ship import (
    Target,
    connect,
    encrypt,
    is_custom_dump,
    parse_target,
    ship,
)
from tests.conftest import SECRET_KEY, SITE_URL

TODAY = date(2026, 10, 14)

DUMP = b"PGDMP\x01\x0e\x00" + bytes(range(256)) * 64
"""Enough of a custom-format archive to pass the check: its magic, then any bytes."""


@dataclass(frozen=True)
class Sftp:
    """A running server: its port, its root, and the files a client needs to reach it."""

    port: int
    root: Path
    client_key: Path
    known_hosts: Path

    def target(self) -> Target:
        return Target(username="backup", host="127.0.0.1", port=self.port, directory="copies")


def known_hosts_line(port: int, key: asyncssh.SSHKey) -> str:
    return f"[127.0.0.1]:{port} {key.export_public_key().decode('ascii').strip()}\n"


@pytest.fixture
async def sftp_server(tmp_path: Path) -> AsyncIterator[Sftp]:
    root = tmp_path / "root"
    (root / "copies").mkdir(parents=True)
    host_key = asyncssh.generate_private_key("ssh-ed25519")
    client = asyncssh.generate_private_key("ssh-ed25519")
    client_key = tmp_path / "id_ed25519"
    client.write_private_key(str(client_key))
    server = await asyncssh.listen(
        "127.0.0.1",
        0,
        server_host_keys=[host_key],
        authorized_client_keys=asyncssh.import_authorized_keys(
            client.export_public_key().decode("ascii")
        ),
        sftp_factory=lambda channel: asyncssh.SFTPServer(channel, chroot=bytes(root)),
        allow_scp=False,
    )
    port = server.sockets[0].getsockname()[1]
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text(known_hosts_line(port, host_key), encoding="ascii")
    try:
        yield Sftp(port=port, root=root, client_key=client_key, known_hosts=known_hosts)
    finally:
        server.close()
        await server.wait_closed()


def write_dump(tmp_path: Path) -> Path:
    dump = tmp_path / "dumps" / "app.dump"
    dump.parent.mkdir()
    dump.write_bytes(DUMP)
    return dump


def test_svc_ops_ship_targets_parse_with_and_without_a_port() -> None:
    assert parse_target("u1@backup.example.org:copies") == Target(
        username="u1", host="backup.example.org", directory="copies"
    )
    assert parse_target("u1@backup.example.org:23:emendrix/app") == Target(
        username="u1", host="backup.example.org", port=23, directory="emendrix/app"
    )
    assert parse_target("u1@backup.example.org:").directory == "."
    for wrong in ("backup.example.org:copies", "u1@backup.example.org", "@host:x", "u1@:x"):
        with pytest.raises(ValueError, match="user@host"):
            parse_target(wrong)


def test_svc_ops_ship_encrypts_so_only_the_offline_key_decrypts(tmp_path: Path) -> None:
    identity = pyrage.x25519.Identity.generate()
    source = write_dump(tmp_path)
    encrypted = tmp_path / "copy.age"
    size = encrypt(source, encrypted, str(identity.to_public()))
    assert size == encrypted.stat().st_size
    assert DUMP not in encrypted.read_bytes()
    assert pyrage.decrypt(encrypted.read_bytes(), [identity]) == DUMP
    with pytest.raises(pyrage.DecryptError):
        pyrage.decrypt(encrypted.read_bytes(), [pyrage.x25519.Identity.generate()])
    with pytest.raises(ValueError, match="age public key"):
        encrypt(source, encrypted, "ssh-ed25519 AAAA")


def test_svc_ops_ship_only_a_custom_format_archive_is_a_dump(tmp_path: Path) -> None:
    assert is_custom_dump(write_dump(tmp_path))
    plain = tmp_path / "plain.sql"
    plain.write_text("-- PostgreSQL database dump\n", encoding="ascii")
    assert not is_custom_dump(plain)


@pytest.mark.anyio
async def test_svc_ops_ship_uploads_prunes_and_leaves_nothing_behind(
    sftp_server: Sftp, tmp_path: Path
) -> None:
    copies = sftp_server.root / "copies"
    old = [date(2026, 8, 3), date(2026, 9, 7), date(2026, 9, 14), date(2026, 10, 13)]
    for day in old:
        (copies / backup_name(day)).write_bytes(b"older copy")
    (copies / "notes.txt").write_text("the operator's own file", encoding="ascii")
    (copies / (backup_name(date(2026, 10, 10)) + ".part")).write_bytes(b"an interrupted upload")
    identity = pyrage.x25519.Identity.generate()
    dump = write_dump(tmp_path)

    counts = await ship(
        dump,
        target=sftp_server.target(),
        key_path=sftp_server.client_key,
        known_hosts_path=sftp_server.known_hosts,
        recipient=str(identity.to_public()),
        today=TODAY,
    )

    shipped = copies / backup_name(TODAY)
    assert pyrage.decrypt(shipped.read_bytes(), [identity]) == DUMP
    assert counts.bytes == shipped.stat().st_size
    assert sorted(path.name for path in copies.iterdir()) == sorted(
        [
            "notes.txt",
            backup_name(date(2026, 9, 14)),
            backup_name(date(2026, 10, 13)),
            backup_name(TODAY),
        ]
    )
    assert (counts.kept, counts.pruned) == (3, 3)
    assert sorted(path.name for path in dump.parent.iterdir()) == ["app.dump"]


@pytest.mark.anyio
async def test_svc_ops_ship_a_second_run_on_one_day_replaces_the_copy(
    sftp_server: Sftp, tmp_path: Path
) -> None:
    identity = pyrage.x25519.Identity.generate()
    dump = write_dump(tmp_path)
    shipped = sftp_server.root / "copies" / backup_name(TODAY)
    shipped.write_bytes(b"an earlier run today")
    counts = await ship(
        dump,
        target=sftp_server.target(),
        key_path=sftp_server.client_key,
        known_hosts_path=sftp_server.known_hosts,
        recipient=str(identity.to_public()),
        today=TODAY,
    )
    assert pyrage.decrypt(shipped.read_bytes(), [identity]) == DUMP
    assert (counts.kept, counts.pruned) == (1, 0)


@pytest.mark.anyio
async def test_svc_ops_ship_refuses_a_host_key_the_file_does_not_list(
    sftp_server: Sftp, tmp_path: Path
) -> None:
    impostor = tmp_path / "impostor_known_hosts"
    impostor.write_text(
        known_hosts_line(sftp_server.port, asyncssh.generate_private_key("ssh-ed25519")),
        encoding="ascii",
    )
    with pytest.raises(asyncssh.HostKeyNotVerifiable):
        async with connect(sftp_server.target(), sftp_server.client_key, impostor):
            pass
    assert list((sftp_server.root / "copies").iterdir()) == []


@pytest.mark.anyio
async def test_svc_ops_ship_does_not_connect_for_a_file_that_is_not_a_dump(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "plain.sql"
    plain.write_text("-- PostgreSQL database dump\n", encoding="ascii")
    unreachable = Target(username="backup", host="127.0.0.1", port=1, directory="copies")
    with pytest.raises(ValueError, match="custom-format"):
        await ship(
            plain,
            target=unreachable,
            key_path=tmp_path / "missing",
            known_hosts_path=tmp_path / "missing",
            recipient="unused",
            today=TODAY,
        )


# --- the command ----------------------------------------------------------------------------

runner = CliRunner()


def environment(tmp_path: Path, **extra: str) -> dict[str, str]:
    values = {
        "DATABASE_URL": "postgresql+psycopg://service:service@localhost:5432/service",
        "SITE_URL": SITE_URL,
        "ALLOWED_HOSTS": "example.org",
        "SECRET_KEY": SECRET_KEY,
        **extra,
    }
    return {f"EMENDRIX_SERVICE_{name}": value for name, value in values.items()}


def backup_settings(tmp_path: Path) -> dict[str, str]:
    key = tmp_path / "id_ed25519"
    key.write_text("not read before the dump is checked", encoding="ascii")
    hosts = tmp_path / "known_hosts"
    hosts.write_text("[127.0.0.1]:1 ssh-ed25519 AAAA\n", encoding="ascii")
    return {
        "BACKUP_TARGET": "backup@127.0.0.1:1:copies",
        "BACKUP_SSH_KEY": str(key),
        "BACKUP_KNOWN_HOSTS": str(hosts),
        "BACKUP_AGE_RECIPIENT": str(pyrage.x25519.Identity.generate().to_public()),
    }


@pytest.mark.usefixtures("no_service_environment")
def test_svc_ops_ship_command_names_each_missing_setting(tmp_path: Path) -> None:
    dump = write_dump(tmp_path)
    full = backup_settings(tmp_path)
    for name in ("BACKUP_TARGET", "BACKUP_SSH_KEY", "BACKUP_KNOWN_HOSTS", "BACKUP_AGE_RECIPIENT"):
        partial = {key: value for key, value in full.items() if key != name}
        result = runner.invoke(
            app, ["backup", "ship", str(dump)], env=environment(tmp_path, **partial)
        )
        assert result.exit_code == 2
        assert result.stderr == f"emendrix-service: EMENDRIX_SERVICE_{name} is not set\n"
    wrong = {**full, "BACKUP_TARGET": "no-user-here"}
    result = runner.invoke(app, ["backup", "ship", str(dump)], env=environment(tmp_path, **wrong))
    assert result.exit_code == 2
    assert result.stderr.startswith("emendrix-service: EMENDRIX_SERVICE_BACKUP_TARGET is not valid")
    result = runner.invoke(
        app, ["backup", "ship", str(tmp_path / "absent.dump")], env=environment(tmp_path, **full)
    )
    assert result.exit_code == 2
    assert result.stderr.endswith("absent.dump is not a file\n")


@pytest.mark.usefixtures("no_service_environment")
def test_svc_ops_ship_command_ends_failed_on_a_file_that_is_not_a_dump(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plain = tmp_path / "plain.sql"
    plain.write_text("-- PostgreSQL database dump\n", encoding="ascii")
    env = environment(tmp_path, **backup_settings(tmp_path))
    result = runner.invoke(app, ["backup", "ship", str(plain)], env=env)
    assert result.exit_code == 1
    lines = [line for line in (result.stdout + capsys.readouterr().out).splitlines() if line]
    assert json.loads(lines[-1]) == {
        "emendrix_service": "backup",
        "status": "failed",
        "error": "ValueError",
    }
