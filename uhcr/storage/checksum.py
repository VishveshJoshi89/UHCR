"""CRC32 integrity verification for cached data.

Provides functions to compute, verify, pack, and unpack checksums alongside
data payloads. Uses stdlib ``zlib.crc32`` — no external dependencies required.
"""

from __future__ import annotations

import struct
import zlib


class ChecksumError(Exception):
    """Raised when a checksum verification fails.

    Attributes:
        expected: The checksum value extracted from the packed data.
        actual: The checksum computed from the data bytes.
    """

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Checksum mismatch: expected 0x{expected:08x}, got 0x{actual:08x}"
        )


def compute_checksum(data: bytes) -> int:
    """Compute the CRC32 checksum of *data*.

    Args:
        data: Arbitrary byte string to checksum.

    Returns:
        Unsigned 32-bit CRC32 integer (0 – 4 294 967 295).
    """
    return zlib.crc32(data) & 0xFFFFFFFF


def verify_checksum(data: bytes, expected: int) -> bool:
    """Verify that *data* matches *expected* checksum.

    Args:
        data: Byte string to verify.
        expected: Previously computed CRC32 value to compare against.

    Returns:
        ``True`` if the computed checksum matches *expected*, ``False`` otherwise.
    """
    return compute_checksum(data) == (expected & 0xFFFFFFFF)


def pack_with_checksum(data: bytes) -> bytes:
    """Prepend a 4-byte little-endian CRC32 checksum to *data*.

    The layout of the returned bytes is::

        [checksum: 4 bytes LE] [data: N bytes]

    Args:
        data: Payload bytes to protect.

    Returns:
        ``checksum_bytes + data`` as a single :class:`bytes` object.
    """
    checksum = compute_checksum(data)
    checksum_bytes = struct.pack("<I", checksum)
    return checksum_bytes + data


def unpack_and_verify(packed: bytes) -> bytes:
    """Extract and verify the CRC32 checksum embedded in *packed*.

    Expects the format produced by :func:`pack_with_checksum`::

        [checksum: 4 bytes LE] [data: N bytes]

    Args:
        packed: Byte string with a 4-byte little-endian checksum prefix.

    Returns:
        The data portion (everything after the first 4 bytes) if the checksum
        is valid.

    Raises:
        ValueError: If *packed* is shorter than 4 bytes.
        ChecksumError: If the computed checksum does not match the stored one.
    """
    if len(packed) < 4:
        raise ValueError(
            f"packed data too short: expected at least 4 bytes, got {len(packed)}"
        )

    (expected,) = struct.unpack("<I", packed[:4])
    data = packed[4:]
    actual = compute_checksum(data)

    if actual != expected:
        raise ChecksumError(expected=expected, actual=actual)

    return data

