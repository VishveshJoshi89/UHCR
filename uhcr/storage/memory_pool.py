"""Size-class memory pool with aligned buffer reuse.

Provides pre-allocated, cache-line-aligned buffers organized by size class
to reduce allocation overhead in the UHCR runtime. Buffers are reused when
released back to the pool, avoiding repeated system allocator calls.

Size classes: 64B, 256B, 1KB, 4KB, 64KB, 1MB, 16MB

Thread-safe: all operations are protected by a threading.Lock.
"""

from __future__ import annotations

import ctypes
import logging
import platform
import threading
from collections import deque
from typing import Deque, Dict, Optional

logger = logging.getLogger(__name__)

# Size classes in bytes (ascending order)
SIZE_CLASSES: tuple[int, ...] = (
    64,             # 64B
    256,            # 256B
    1024,           # 1KB
    4096,           # 4KB
    65536,          # 64KB
    1048576,        # 1MB
    16777216,       # 16MB
)

# Default alignment: 64 bytes (cache-line aligned)
DEFAULT_ALIGNMENT = 64

# Default maximum pooled memory: 512MB
DEFAULT_MAX_POOL_BYTES = 512 * 1024 * 1024


class AlignedBuffer:
    """A cache-line-aligned memory buffer for the memory pool.

    Handles platform-specific aligned allocation (Windows _aligned_malloc,
    POSIX posix_memalign) and provides methods for copying data in/out.
    """

    __slots__ = ("size", "alignment", "address", "_system", "_libc")

    def __init__(self, size: int, alignment: int = DEFAULT_ALIGNMENT) -> None:
        self.size = size
        self.alignment = alignment
        self.address: Optional[int] = None
        self._system = platform.system()
        self._libc: Optional[ctypes.CDLL] = None
        self._allocate()

    def _allocate(self) -> None:
        """Allocate aligned memory using platform-specific APIs."""
        if self._system == "Windows":
            try:
                self._libc = ctypes.cdll.msvcrt
            except Exception:
                self._libc = ctypes.CDLL("msvcrt.dll")

            self._libc._aligned_malloc.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
            self._libc._aligned_malloc.restype = ctypes.c_void_p

            self.address = self._libc._aligned_malloc(self.size, self.alignment)
            if not self.address:
                raise MemoryError(
                    f"Windows _aligned_malloc failed for size={self.size}, "
                    f"alignment={self.alignment}"
                )
        else:
            # POSIX
            try:
                self._libc = ctypes.CDLL(None)
            except Exception:
                try:
                    self._libc = ctypes.CDLL("libc.so.6")
                except Exception:
                    raise MemoryError(
                        "Could not load POSIX libc for aligned memory allocation"
                    )

            posix_memalign = self._libc.posix_memalign
            posix_memalign.argtypes = [
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_size_t,
                ctypes.c_size_t,
            ]
            posix_memalign.restype = ctypes.c_int

            ptr = ctypes.c_void_p(0)
            res = posix_memalign(ctypes.byref(ptr), self.alignment, self.size)
            if res != 0:
                raise MemoryError(
                    f"POSIX posix_memalign failed with error code: {res}"
                )
            self.address = ptr.value

    def free(self) -> None:
        """Free the underlying aligned memory."""
        if self.address is None:
            return

        if self._system == "Windows":
            assert self._libc is not None
            self._libc._aligned_free.argtypes = [ctypes.c_void_p]
            self._libc._aligned_free(self.address)
        else:
            assert self._libc is not None
            free_fn = self._libc.free
            free_fn.argtypes = [ctypes.c_void_p]
            free_fn(self.address)

        self.address = None

    def copy_from(self, src_bytes: bytes) -> None:
        """Copy raw bytes into the aligned buffer."""
        if self.address is None:
            raise RuntimeError("Buffer already freed")
        if len(src_bytes) > self.size:
            raise ValueError("Source bytes exceed buffer size")
        ctypes.memmove(self.address, src_bytes, len(src_bytes))

    def copy_to(self) -> bytes:
        """Copy the buffer contents into a Python bytes object."""
        if self.address is None:
            raise RuntimeError("Buffer already freed")
        return ctypes.string_at(self.address, self.size)

    def __enter__(self) -> "AlignedBuffer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.free()

    def __del__(self) -> None:
        try:
            self.free()
        except Exception:
            pass


class MemoryPool:
    """Size-class memory pool with aligned buffer reuse.

    Organizes pre-allocated buffers into size classes for fast allocation
    and reuse. When a buffer is requested, the smallest size class that
    fits the request is selected. Released buffers are returned to their
    size class's free list for reuse.

    Args:
        max_pool_bytes: Maximum total bytes the pool will hold. Defaults to 512MB.
        alignment: Buffer alignment in bytes. Defaults to 64 (cache-line).

    Thread Safety:
        All public methods are protected by a threading.Lock.

    Example:
        pool = MemoryPool()
        buf = pool.allocate(100)   # Returns a 256B-class buffer
        pool.release(buf)          # Returns buffer to pool for reuse
        pool.release_all()         # Frees all pooled memory
    """

    def __init__(
        self,
        max_pool_bytes: int = DEFAULT_MAX_POOL_BYTES,
        alignment: int = DEFAULT_ALIGNMENT,
    ) -> None:
        self._max_pool_bytes = max_pool_bytes
        self._alignment = alignment
        self._lock = threading.Lock()

        # Free lists: size_class -> deque of available AlignedBuffers
        self._free_lists: Dict[int, Deque[AlignedBuffer]] = {
            sc: deque() for sc in SIZE_CLASSES
        }

        # Track current pooled memory usage (bytes held in free lists)
        self._pooled_bytes: int = 0

        # Metrics
        self._pool_hits: int = 0
        self._pool_misses: int = 0

    @property
    def max_pool_bytes(self) -> int:
        """Maximum total bytes the pool will hold."""
        return self._max_pool_bytes

    @property
    def pooled_bytes(self) -> int:
        """Current bytes held in the pool's free lists."""
        with self._lock:
            return self._pooled_bytes

    @property
    def pool_hits(self) -> int:
        """Number of allocations served from the pool."""
        with self._lock:
            return self._pool_hits

    @property
    def pool_misses(self) -> int:
        """Number of allocations that required a fresh system allocation."""
        with self._lock:
            return self._pool_misses

    @staticmethod
    def _find_size_class(size: int) -> Optional[int]:
        """Find the smallest size class that can satisfy the requested size.

        Returns None if the request exceeds the largest size class.
        """
        for sc in SIZE_CLASSES:
            if size <= sc:
                return sc
        return None

    def allocate(self, size: int) -> AlignedBuffer:
        """Allocate an aligned buffer of at least `size` bytes.

        Finds the smallest size class that fits the request. If a buffer
        is available in that class's free list, it is reused. Otherwise,
        a new buffer is allocated from the system.

        Args:
            size: Minimum number of bytes needed.

        Returns:
            An AlignedBuffer with capacity >= size.

        Raises:
            ValueError: If size <= 0.
            MemoryError: If system allocation fails.
        """
        if size <= 0:
            raise ValueError(f"Allocation size must be positive, got {size}")
        
        # Safety check before allocation
        try:
            from uhcr.native import get_safety_monitor, SafetyStatus
            monitor = get_safety_monitor()
            if monitor and monitor.is_enabled():
                # Check memory limits
                current_usage = monitor.get_memory_usage()
                if current_usage + size > 16 * 1024 * 1024 * 1024:  # 16GB limit
                    raise MemoryError(
                        f"Memory allocation would exceed safety limit. "
                        f"Current: {current_usage/1024**3:.2f}GB, Requested: {size/1024**3:.2f}GB"
                    )
                
                # Validate allocation
                status = monitor.validate_memory(0, size, False)
                if status != SafetyStatus.OK:
                    raise MemoryError(f"Memory safety check failed: {monitor.get_last_error()}")
        except ImportError:
            pass

        size_class = self._find_size_class(size)

        # If request exceeds largest size class, allocate exact size from system
        if size_class is None:
            logger.info(
                "Allocation of %d bytes exceeds largest size class (%d), "
                "using system allocator",
                size,
                SIZE_CLASSES[-1],
            )
            self._increment_pool_misses()
            return AlignedBuffer(size, self._alignment)

        with self._lock:
            free_list = self._free_lists[size_class]
            if free_list:
                # Reuse a pooled buffer
                buf = free_list.pop()
                self._pooled_bytes -= size_class
                self._pool_hits += 1
                return buf

            # Pool miss: allocate fresh from system
            self._pool_misses += 1

        logger.debug(
            "Pool miss for size class %d (requested %d bytes), "
            "allocating from system",
            size_class,
            size,
        )
        return AlignedBuffer(size_class, self._alignment)

    def release(self, buffer: AlignedBuffer) -> None:
        """Return a buffer to the pool for reuse.

        If the buffer's size matches a known size class and the pool has
        capacity, the buffer is added to the appropriate free list.
        Otherwise, the buffer is freed immediately.

        Args:
            buffer: The AlignedBuffer to release back to the pool.
        """
        if buffer.address is None:
            # Buffer already freed, nothing to do
            return

        size_class = self._find_size_class(buffer.size)

        # If buffer doesn't fit a size class, or its size doesn't match
        # a size class exactly (e.g. oversized allocation), free it
        if size_class is None or buffer.size != size_class:
            buffer.free()
            return

        with self._lock:
            # Check if adding this buffer would exceed pool capacity
            if self._pooled_bytes + size_class > self._max_pool_bytes:
                # Pool is full, free the buffer instead
                buffer.free()
                return

            self._free_lists[size_class].append(buffer)
            self._pooled_bytes += size_class

    def release_all(self) -> None:
        """Free all pooled memory and reset the pool.

        Frees every buffer in every size class's free list and resets
        the pooled byte counter to zero.
        """
        with self._lock:
            for size_class in SIZE_CLASSES:
                free_list = self._free_lists[size_class]
                while free_list:
                    buf = free_list.pop()
                    buf.free()
            self._pooled_bytes = 0

    def stats(self) -> Dict[str, object]:
        """Return pool statistics.

        Returns:
            Dictionary with pool metrics including hits, misses, pooled bytes,
            and per-class buffer counts.
        """
        with self._lock:
            class_counts = {
                sc: len(self._free_lists[sc]) for sc in SIZE_CLASSES
            }
            return {
                "max_pool_bytes": self._max_pool_bytes,
                "pooled_bytes": self._pooled_bytes,
                "pool_hits": self._pool_hits,
                "pool_misses": self._pool_misses,
                "alignment": self._alignment,
                "class_counts": class_counts,
            }

    def _increment_pool_misses(self) -> None:
        """Thread-safe increment of pool miss counter."""
        with self._lock:
            self._pool_misses += 1
