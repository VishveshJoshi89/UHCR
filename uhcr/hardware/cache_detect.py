"""CPU cache topology detection module."""

import platform
from dataclasses import dataclass
from typing import Optional


@dataclass
class CacheLevel:
    """Describes a single cache level.

    Attributes:
        level: Cache level (1, 2, or 3).
        type: Cache type - "data", "instruction", or "unified".
        size_kb: Total cache size in kilobytes.
        line_size_bytes: Cache line size in bytes.
        associativity: Number of ways (set-associative).
        sets: Number of sets.
    """
    level: int
    type: str
    size_kb: int
    line_size_bytes: int
    associativity: int
    sets: int


@dataclass
class CacheTopology:
    """Complete CPU cache topology.

    Attributes:
        l1_data: L1 data cache descriptor.
        l1_instruction: L1 instruction cache descriptor.
        l2: L2 unified cache descriptor.
        l3: L3 unified cache descriptor.
    """
    l1_data: CacheLevel
    l1_instruction: CacheLevel
    l2: CacheLevel
    l3: CacheLevel


# Mapping from CPUID cache type field to string
_CACHE_TYPE_MAP = {
    1: "data",
    2: "instruction",
    3: "unified",
}


def parse_cpuid_cache_descriptor(eax: int, ebx: int, ecx: int) -> CacheLevel:
    """Parse CPUID leaf 4 register values into a CacheLevel.

    This is a pure function that extracts cache parameters from raw CPUID
    register values returned by leaf 4 (Deterministic Cache Parameters).

    Extracts:
        - cache_type from EAX[4:0] (1=data, 2=instruction, 3=unified)
        - cache_level from EAX[7:5]
        - ways from EBX[31:22] + 1
        - partitions from EBX[21:12] + 1
        - line_size from EBX[11:0] + 1
        - sets from ECX + 1
        - size_kb = (ways * partitions * line_size * sets) / 1024

    Args:
        eax: Value of EAX register from CPUID leaf 4.
        ebx: Value of EBX register from CPUID leaf 4.
        ecx: Value of ECX register from CPUID leaf 4.

    Returns:
        A CacheLevel instance describing the cache.
    """
    cache_type_raw = eax & 0x1F
    cache_level = (eax >> 5) & 0x7

    ways = ((ebx >> 22) & 0x3FF) + 1
    partitions = ((ebx >> 12) & 0x3FF) + 1
    line_size = (ebx & 0xFFF) + 1
    sets = ecx + 1

    size_kb = (ways * partitions * line_size * sets) // 1024

    cache_type = _CACHE_TYPE_MAP.get(cache_type_raw, "unknown")

    return CacheLevel(
        level=cache_level,
        type=cache_type,
        size_kb=size_kb,
        line_size_bytes=line_size,
        associativity=ways,
        sets=sets,
    )


def detect_cache_fallback() -> CacheTopology:
    """Provide sensible default cache values for non-x86 platforms.

    Returns a CacheTopology with conservative defaults typical of modern
    processors when CPUID-based detection is not available.

    Returns:
        CacheTopology with default values:
            - L1 data: 32 KB, 64-byte lines, 8-way
            - L1 instruction: 32 KB, 64-byte lines, 8-way
            - L2: 256 KB, 64-byte lines, 8-way
            - L3: 0 KB (not present), 64-byte lines, 0-way
    """
    l1_data = CacheLevel(
        level=1,
        type="data",
        size_kb=32,
        line_size_bytes=64,
        associativity=8,
        sets=(32 * 1024) // (64 * 8),  # 64 sets
    )
    l1_instruction = CacheLevel(
        level=1,
        type="instruction",
        size_kb=32,
        line_size_bytes=64,
        associativity=8,
        sets=(32 * 1024) // (64 * 8),  # 64 sets
    )
    l2 = CacheLevel(
        level=2,
        type="unified",
        size_kb=256,
        line_size_bytes=64,
        associativity=8,
        sets=(256 * 1024) // (64 * 8),  # 512 sets
    )
    l3 = CacheLevel(
        level=3,
        type="unified",
        size_kb=0,
        line_size_bytes=64,
        associativity=0,
        sets=0,
    )
    return CacheTopology(
        l1_data=l1_data,
        l1_instruction=l1_instruction,
        l2=l2,
        l3=l3,
    )


def detect_cache() -> CacheTopology:
    """Detect CPU cache topology using CPUID (x86) or fallback.

    On x86_64 platforms, iterates CPUID leaf 4 subleaves to enumerate all
    cache levels. On non-x86 platforms or if CPUID fails, returns sensible
    defaults via detect_cache_fallback().

    Returns:
        CacheTopology describing the detected (or default) cache hierarchy.
    """
    arch = platform.machine().lower()
    if arch not in ("amd64", "x86_64"):
        return detect_cache_fallback()

    try:
        from uhcr.hardware.cpuid import run_cpuid

        l1_data: Optional[CacheLevel] = None
        l1_instruction: Optional[CacheLevel] = None
        l2: Optional[CacheLevel] = None
        l3: Optional[CacheLevel] = None

        for subleaf in range(32):  # Iterate subleaves until type == 0
            eax, ebx, ecx, _edx = run_cpuid(4, subleaf)
            cache_type_raw = eax & 0x1F
            if cache_type_raw == 0:
                break  # No more cache levels

            cache = parse_cpuid_cache_descriptor(eax, ebx, ecx)
            cache_level = (eax >> 5) & 0x7

            if cache_level == 1:
                if cache_type_raw == 1:  # Data
                    l1_data = cache
                elif cache_type_raw == 2:  # Instruction
                    l1_instruction = cache
            elif cache_level == 2:
                l2 = cache
            elif cache_level == 3:
                l3 = cache

        # Fill in any missing levels with fallback values
        fallback = detect_cache_fallback()
        return CacheTopology(
            l1_data=l1_data if l1_data is not None else fallback.l1_data,
            l1_instruction=l1_instruction if l1_instruction is not None else fallback.l1_instruction,
            l2=l2 if l2 is not None else fallback.l2,
            l3=l3 if l3 is not None else fallback.l3,
        )

    except Exception:
        return detect_cache_fallback()
