"""Apple Silicon (M-series) detection and JIT memory allocation for macOS ARM64."""

import ctypes
import platform
import subprocess
import sys
from dataclasses import dataclass


def detect_apple_silicon() -> bool:
    """Return True if running on an Apple M-series chip (M1–M4).

    Uses ``platform.processor()`` and ``platform.machine()`` as the primary
    check, then falls back to ``sysctl hw.optional.arm64`` for confirmation
    when available.
    """
    if platform.system() != "Darwin":
        return False

    machine = platform.machine().lower()
    processor = platform.processor().lower()

    # Primary check: ARM64 machine on macOS
    if machine not in ("arm64", "aarch64"):
        return False

    # Processor string on Apple Silicon typically contains "apple"
    if "apple" in processor:
        return True

    # Secondary check via sysctl (available on macOS)
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.optional.arm64"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # If machine is arm64 on Darwin, treat as Apple Silicon even without sysctl
    return machine in ("arm64", "aarch64")


def _detect_chip_generation() -> str:
    """Attempt to identify the M-series generation from system information."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            brand = result.stdout.strip().lower()
            for gen in ("m4", "m3", "m2", "m1"):
                if gen in brand:
                    return gen.upper()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Fallback: try system_profiler on macOS
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout.lower()
            for gen in ("m4", "m3", "m2", "m1"):
                if f"apple {gen}" in output:
                    return gen.upper()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return "unknown"


@dataclass
class AppleSiliconInfo:
    """Detection results for Apple Silicon hardware.

    Attributes:
        is_apple_silicon: True when running on an Apple M-series chip.
        chip_generation: One of "M1", "M2", "M3", "M4", or "unknown".
        supports_map_jit: True on macOS ARM64 where MAP_JIT is available.
    """

    is_apple_silicon: bool
    chip_generation: str
    supports_map_jit: bool

    @classmethod
    def detect(cls) -> "AppleSiliconInfo":
        """Detect Apple Silicon and return an :class:`AppleSiliconInfo` instance."""
        return get_apple_silicon_info()


def get_apple_silicon_info() -> AppleSiliconInfo:
    """Return full Apple Silicon detection information."""
    is_as = detect_apple_silicon()
    chip_gen = _detect_chip_generation() if is_as else "unknown"
    # MAP_JIT is available on macOS ARM64 (and macOS x86_64 with Hardened Runtime,
    # but we only advertise it for Apple Silicon targets).
    supports_jit = is_as and platform.system() == "Darwin"
    return AppleSiliconInfo(
        is_apple_silicon=is_as,
        chip_generation=chip_gen,
        supports_map_jit=supports_jit,
    )


# ---------------------------------------------------------------------------
# mmap / munmap constants
# ---------------------------------------------------------------------------

_PROT_READ = 0x01
_PROT_WRITE = 0x02
_PROT_EXEC = 0x04

# macOS flags
_MAP_PRIVATE_MACOS = 0x0002
_MAP_ANONYMOUS_MACOS = 0x1000  # MAP_ANON on macOS
_MAP_JIT_MACOS = 0x0800        # MAP_JIT on macOS (available since 10.14)

# Linux flags
_MAP_PRIVATE_LINUX = 0x0002
_MAP_ANONYMOUS_LINUX = 0x0020

_MAP_FAILED = ctypes.c_void_p(-1).value  # (size_t)-1 cast to signed


def _load_libc() -> ctypes.CDLL:
    """Load the C standard library for the current platform."""
    try:
        return ctypes.CDLL(None)
    except OSError:
        pass
    # Explicit fallback for some Linux configurations
    try:
        return ctypes.CDLL("libc.so.6")
    except OSError as exc:
        raise RuntimeError("Could not load libc for mmap/munmap") from exc


def allocate_jit_memory(size: int) -> int:
    """Allocate executable memory suitable for JIT-compiled code.

    On macOS ARM64 (Apple Silicon) the allocation uses ``MAP_JIT`` so that
    the pages can be made executable after writing.  On all other platforms
    a standard ``mmap`` with ``PROT_READ | PROT_WRITE | PROT_EXEC`` is used.

    Args:
        size: Number of bytes to allocate.  Must be > 0.

    Returns:
        The base address of the allocated region as a Python ``int``.

    Raises:
        RuntimeError: If the allocation fails or the platform is Windows
            (use ``VirtualAlloc`` instead on Windows).
        ValueError: If *size* is not positive.
    """
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")

    system = platform.system()

    if system == "Windows":
        raise RuntimeError(
            "allocate_jit_memory is not supported on Windows; "
            "use ctypes.windll.kernel32.VirtualAlloc instead."
        )

    libc = _load_libc()
    mmap_fn = libc.mmap
    mmap_fn.argtypes = [
        ctypes.c_void_p,   # addr
        ctypes.c_size_t,   # length
        ctypes.c_int,      # prot
        ctypes.c_int,      # flags
        ctypes.c_int,      # fd
        ctypes.c_size_t,   # offset
    ]
    mmap_fn.restype = ctypes.c_void_p

    prot = _PROT_READ | _PROT_WRITE | _PROT_EXEC

    if system == "Darwin":
        flags = _MAP_PRIVATE_MACOS | _MAP_ANONYMOUS_MACOS | _MAP_JIT_MACOS
    else:
        # Linux and other POSIX systems — MAP_JIT not available/needed
        flags = _MAP_PRIVATE_LINUX | _MAP_ANONYMOUS_LINUX

    addr = mmap_fn(None, size, prot, flags, -1, 0)

    if addr is None or addr == _MAP_FAILED or addr == 0:
        raise RuntimeError(
            f"mmap failed to allocate {size} bytes of JIT memory "
            f"(system={system!r})"
        )

    return addr


def free_jit_memory(address: int, size: int) -> None:
    """Free JIT memory previously allocated by :func:`allocate_jit_memory`.

    Args:
        address: Base address returned by :func:`allocate_jit_memory`.
        size: Size in bytes that was originally requested.

    Raises:
        RuntimeError: If ``munmap`` returns a non-zero error code.
    """
    if platform.system() == "Windows":
        raise RuntimeError(
            "free_jit_memory is not supported on Windows; "
            "use ctypes.windll.kernel32.VirtualFree instead."
        )

    libc = _load_libc()
    munmap_fn = libc.munmap
    munmap_fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    munmap_fn.restype = ctypes.c_int

    ret = munmap_fn(address, size)
    if ret != 0:
        raise RuntimeError(
            f"munmap failed with return code {ret} "
            f"(address=0x{address:x}, size={size})"
        )


def get_calling_convention() -> str:
    """Return the ABI calling convention string for the current platform.

    Returns:
        ``"apple-aapcs64"`` on Apple Silicon (macOS ARM64), or
        ``"aapcs64"`` on all other ARM64 targets.
    """
    if detect_apple_silicon():
        return "apple-aapcs64"
    return "aapcs64"
"""Apple Silicon (M-series) detection and JIT memory allocation for macOS ARM64."""

import ctypes
import platform
import subprocess
import sys
from dataclasses import dataclass


def detect_apple_silicon() -> bool:
    """Return True if running on an Apple M-series chip (M1–M4).

    Uses ``platform.processor()`` and ``platform.machine()`` as the primary
    check, then falls back to ``sysctl hw.optional.arm64`` for confirmation
    when available.
    """
    if platform.system() != "Darwin":
        return False

    machine = platform.machine().lower()
    processor = platform.processor().lower()

    # Primary check: ARM64 machine on macOS
    if machine not in ("arm64", "aarch64"):
        return False

    # Processor string on Apple Silicon typically contains "apple"
    if "apple" in processor:
        return True

    # Secondary check via sysctl (available on macOS)
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.optional.arm64"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # If machine is arm64 on Darwin, treat as Apple Silicon even without sysctl
    return machine in ("arm64", "aarch64")


def _detect_chip_generation() -> str:
    """Attempt to identify the M-series generation from system information."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            brand = result.stdout.strip().lower()
            for gen in ("m4", "m3", "m2", "m1"):
                if gen in brand:
                    return gen.upper()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Fallback: try system_profiler on macOS
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout.lower()
            for gen in ("m4", "m3", "m2", "m1"):
                if f"apple {gen}" in output:
                    return gen.upper()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return "unknown"


@dataclass
class AppleSiliconInfo:
    """Detection results for Apple Silicon hardware.

    Attributes:
        is_apple_silicon: True when running on an Apple M-series chip.
        chip_generation: One of "M1", "M2", "M3", "M4", or "unknown".
        supports_map_jit: True on macOS ARM64 where MAP_JIT is available.
    """

    is_apple_silicon: bool
    chip_generation: str
    supports_map_jit: bool

    @classmethod
    def detect(cls) -> "AppleSiliconInfo":
        """Detect Apple Silicon and return an :class:`AppleSiliconInfo` instance."""
        return get_apple_silicon_info()


def get_apple_silicon_info() -> AppleSiliconInfo:
    """Return full Apple Silicon detection information."""
    is_as = detect_apple_silicon()
    chip_gen = _detect_chip_generation() if is_as else "unknown"
    # MAP_JIT is available on macOS ARM64 (and macOS x86_64 with Hardened Runtime,
    # but we only advertise it for Apple Silicon targets).
    supports_jit = is_as and platform.system() == "Darwin"
    return AppleSiliconInfo(
        is_apple_silicon=is_as,
        chip_generation=chip_gen,
        supports_map_jit=supports_jit,
    )


# ---------------------------------------------------------------------------
# mmap / munmap constants
# ---------------------------------------------------------------------------

_PROT_READ = 0x01
_PROT_WRITE = 0x02
_PROT_EXEC = 0x04

# macOS flags
_MAP_PRIVATE_MACOS = 0x0002
_MAP_ANONYMOUS_MACOS = 0x1000  # MAP_ANON on macOS
_MAP_JIT_MACOS = 0x0800        # MAP_JIT on macOS (available since 10.14)

# Linux flags
_MAP_PRIVATE_LINUX = 0x0002
_MAP_ANONYMOUS_LINUX = 0x0020

_MAP_FAILED = ctypes.c_void_p(-1).value  # (size_t)-1 cast to signed


def _load_libc() -> ctypes.CDLL:
    """Load the C standard library for the current platform."""
    try:
        return ctypes.CDLL(None)
    except OSError:
        pass
    # Explicit fallback for some Linux configurations
    try:
        return ctypes.CDLL("libc.so.6")
    except OSError as exc:
        raise RuntimeError("Could not load libc for mmap/munmap") from exc


def allocate_jit_memory(size: int) -> int:
    """Allocate executable memory suitable for JIT-compiled code.

    On macOS ARM64 (Apple Silicon) the allocation uses ``MAP_JIT`` so that
    the pages can be made executable after writing.  On all other platforms
    a standard ``mmap`` with ``PROT_READ | PROT_WRITE | PROT_EXEC`` is used.

    Args:
        size: Number of bytes to allocate.  Must be > 0.

    Returns:
        The base address of the allocated region as a Python ``int``.

    Raises:
        RuntimeError: If the allocation fails or the platform is Windows
            (use ``VirtualAlloc`` instead on Windows).
        ValueError: If *size* is not positive.
    """
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")

    system = platform.system()

    if system == "Windows":
        raise RuntimeError(
            "allocate_jit_memory is not supported on Windows; "
            "use ctypes.windll.kernel32.VirtualAlloc instead."
        )

    libc = _load_libc()
    mmap_fn = libc.mmap
    mmap_fn.argtypes = [
        ctypes.c_void_p,   # addr
        ctypes.c_size_t,   # length
        ctypes.c_int,      # prot
        ctypes.c_int,      # flags
        ctypes.c_int,      # fd
        ctypes.c_size_t,   # offset
    ]
    mmap_fn.restype = ctypes.c_void_p

    prot = _PROT_READ | _PROT_WRITE | _PROT_EXEC

    if system == "Darwin":
        flags = _MAP_PRIVATE_MACOS | _MAP_ANONYMOUS_MACOS | _MAP_JIT_MACOS
    else:
        # Linux and other POSIX systems — MAP_JIT not available/needed
        flags = _MAP_PRIVATE_LINUX | _MAP_ANONYMOUS_LINUX

    addr = mmap_fn(None, size, prot, flags, -1, 0)

    if addr is None or addr == _MAP_FAILED or addr == 0:
        raise RuntimeError(
            f"mmap failed to allocate {size} bytes of JIT memory "
            f"(system={system!r})"
        )

    return addr


def free_jit_memory(address: int, size: int) -> None:
    """Free JIT memory previously allocated by :func:`allocate_jit_memory`.

    Args:
        address: Base address returned by :func:`allocate_jit_memory`.
        size: Size in bytes that was originally requested.

    Raises:
        RuntimeError: If ``munmap`` returns a non-zero error code.
    """
    if platform.system() == "Windows":
        raise RuntimeError(
            "free_jit_memory is not supported on Windows; "
            "use ctypes.windll.kernel32.VirtualFree instead."
        )

    libc = _load_libc()
    munmap_fn = libc.munmap
    munmap_fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    munmap_fn.restype = ctypes.c_int

    ret = munmap_fn(address, size)
    if ret != 0:
        raise RuntimeError(
            f"munmap failed with return code {ret} "
            f"(address=0x{address:x}, size={size})"
        )


def get_calling_convention() -> str:
    """Return the ABI calling convention string for the current platform.

    Returns:
        ``"apple-aapcs64"`` on Apple Silicon (macOS ARM64), or
        ``"aapcs64"`` on all other ARM64 targets.
    """
    if detect_apple_silicon():
        return "apple-aapcs64"
    return "aapcs64"
