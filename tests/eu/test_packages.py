"""The one bound on reading a Formex package: how much it is allowed to expand to.

A package is a zip fetched from a remote endpoint and decompressed straight into memory. Path
traversal, the usual zip finding, has no target here, because nothing is ever extracted to
disk; members are held in memory keyed by their archive name. Size is what is left, and
"legitimate packages are small" is not a bound, so `MAX_PACKAGE_BYTES` is one.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from emendrix.eu.packages import (
    MAX_PACKAGE_BYTES,
    PackageTooLarge,
    check_package_size,
    read_package,
)
from emendrix.eu.trims import trim_formex_zip

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

MEMBERS = {"L_202401689EN.xml": b"<ACT><ARTICLE/></ACT>", "notes.txt": b"not xml"}


def _package(members: dict[str, bytes] = MEMBERS) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _declaring(blob: bytes, uncompressed: int) -> bytes:
    """Rewrite every central-directory entry to claim `uncompressed` bytes per member.

    The classic bomb in miniature, and the reason the gate is on the *declared* size: the
    archive stays a few hundred bytes while its own index claims hundreds of megabytes.
    `zipfile` reads member sizes from the central directory, so this is the number
    `ZipInfo.file_size` reports and the number `check_package_size` refuses on, without a test
    having to build a real quarter-gigabyte of anything.
    """
    out = bytearray(blob)
    start = 0
    while (found := out.find(b"PK\x01\x02", start)) != -1:
        out[found + 24 : found + 28] = uncompressed.to_bytes(4, "little")  # uncompressed size
        start = found + 4
    return bytes(out)


def test_a_package_that_declares_more_than_the_ceiling_is_refused_unread() -> None:
    """Refused before the first `read`, which is the only point at which refusing helps."""
    bomb = _declaring(_package(), MAX_PACKAGE_BYTES)
    assert len(bomb) < 1024, "the whole trick is a tiny archive claiming an enormous one"

    with pytest.raises(PackageTooLarge) as raised:
        read_package(bomb)
    assert raised.value.declared == MAX_PACKAGE_BYTES * len(MEMBERS)
    assert str(MAX_PACKAGE_BYTES) in str(raised.value), "the ceiling belongs in the message"


def test_the_trim_path_is_bounded_by_the_same_ceiling() -> None:
    """`fetch_fixtures.py` trims a response before anything else reads it, so it is first."""
    with pytest.raises(PackageTooLarge):
        trim_formex_zip(_declaring(_package(), MAX_PACKAGE_BYTES))


def test_the_ceiling_is_summed_over_members_not_applied_per_member() -> None:
    """98 members declaring 3 MB each is the same bomb as one declaring 256 MB."""
    each = MAX_PACKAGE_BYTES // 2 + 1
    with pytest.raises(PackageTooLarge):
        check_package_size(zipfile.ZipFile(io.BytesIO(_declaring(_package(), each))))


def test_an_ordinary_package_reads_exactly_as_before() -> None:
    """The guard must cost nothing on the honest path, members and order included."""
    members = read_package(_package())
    assert [member.name for member in members] == list(MEMBERS)
    assert members[0].data == MEMBERS["L_202401689EN.xml"]


def test_every_committed_package_sits_far_below_the_ceiling() -> None:
    """The evidence the number is not arbitrary, re-checked whenever a fixture is re-recorded.

    The largest real package the corpus serves is `32008R1272` at 8.9 MB over 98 members. A
    ceiling only means something against what real data actually does, so this measures the
    committed set rather than repeating the figure from a docstring.
    """
    largest = 0
    for path in sorted(FIXTURES.rglob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            largest = max(largest, sum(info.file_size for info in archive.infolist()))
    assert largest > 0, "no zip fixtures found — this test would otherwise pass vacuously"
    assert largest * 8 < MAX_PACKAGE_BYTES, f"largest committed package is {largest} bytes"
