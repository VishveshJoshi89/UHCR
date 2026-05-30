"""Memory-mapped I/O, LZ4 compression, batch write coalescing, and async prefetching.

Provides optimized file I/O for the UHCR storage subsystem:
- Memory-mapped reads/writes for files exceeding 1MB (MMAP_THRESHOLD)
- LZ4 compression with graceful fallback when the lz4 package is absent
- Batch write coalescing: sequential writes to the same file are merged into
  a single I/O operation on flush
- Async prefetching: background thread loads files into an in-memory cache
  so subsequent reads are served from memory

Thread-safe: the write queue and prefetch cache are protected by threading.Lock.
"""

from __future__ import annotations

import logging
import mmap
import os
import threading
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Files larger than this threshold use memory-mapped I/O
MMAP_THRESHOLD = 1024 * 1024  # 1MB

# ---------------------------------------------------------------------------
# Optional LZ4 import with graceful fallback
# ---------------------------------------------------------------------------
try:
    import lz4.frame as _lz4_frame  # type: ignore[import]
    _LZ4_AVAILABLE = True
    logger.debug("lz4 package available; LZ4 compression enabled")
except ImportError:
    _lz4_frame = None  # type: ignore[assignment]
    _LZ4_AVAILABLE = False
    logger.warning(
        "lz4 package not installed; compression disabled (data passed through as-is)"
    )


class IOOptimizer:
    """Optimized file I/O with mmap, LZ4 compression, batch writes, and prefetching.

    Args:
        None — all configuration is via constants or method arguments.

    Thread Safety:
        All public methods are thread-safe.

    Example::

        optimizer = IOOptimizer()

        # Compressed round-trip
        compressed = optimizer.compress(b"hello world")
        original   = optimizer.decompress(compressed)

        # Batch writes
        optimizer.queue_write("/tmp/a.bin", b"data1")
        optimizer.queue_write("/tmp/a.bin", b"data2")  # coalesced with above
        files_written = optimizer.flush_writes()

        # Prefetch
        optimizer.prefetch(["/tmp/a.bin"])
        data = optimizer.get_prefetched("/tmp/a.bin")

        optimizer.close()
    """

    def __init__(self) -> None:
        # Write queue: path -> list of data chunks (coalesced on flush)
        self._write_queue: Dict[str, List[bytes]] = defaultdict(list)
        self._write_lock = threading.Lock()

        # Prefetch cache: path -> bytes
        self._prefetch_cache: Dict[str, bytes] = {}
        self._prefetch_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Memory-mapped I/O
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> bytes:
        """Read a file, using mmap for files larger than MMAP_THRESHOLD.

        Args:
            path: Filesystem path to read.

        Returns:
            File contents as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
            OSError: On other I/O errors.
        """
        file_size = os.path.getsize(path)

        if file_size > MMAP_THRESHOLD:
            logger.debug(
                "read_file: using mmap for %s (%d bytes)", path, file_size
            )
            with open(path, "rb") as fh:
                with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    return mm.read()
        else:
            logger.debug(
                "read_file: regular read for %s (%d bytes)", path, file_size
            )
            with open(path, "rb") as fh:
                return fh.read()

    def write_file(self, path: str, data: bytes) -> None:
        """Write data to a file, using mmap for data larger than MMAP_THRESHOLD.

        For mmap writes the file is first created/truncated to the required
        size, then the data is written via a memory-mapped view.

        Args:
            path: Filesystem path to write.
            data: Bytes to write.

        Raises:
            OSError: On I/O errors.
        """
        data_size = len(data)

        if data_size > MMAP_THRESHOLD:
            logger.debug(
                "write_file: using mmap for %s (%d bytes)", path, data_size
            )
            # Pre-allocate the file to the required size
            with open(path, "wb") as fh:
                fh.seek(data_size - 1)
                fh.write(b"\x00")

            with open(path, "r+b") as fh:
                with mmap.mmap(fh.fileno(), data_size) as mm:
                    mm.write(data)
        else:
            logger.debug(
                "write_file: regular write for %s (%d bytes)", path, data_size
            )
            with open(path, "wb") as fh:
                fh.write(data)

    # ------------------------------------------------------------------
    # LZ4 compression
    # ------------------------------------------------------------------

    def compress(self, data: bytes) -> bytes:
        """Compress data with LZ4 if available, otherwise return data unchanged.

        Args:
            data: Raw bytes to compress.

        Returns:
            LZ4-compressed bytes, or the original bytes if lz4 is unavailable.
        """
        if _LZ4_AVAILABLE:
            return _lz4_frame.compress(data)  # type: ignore[union-attr]
        return data

    def decompress(self, data: bytes) -> bytes:
        """Decompress LZ4 data if available, otherwise return data unchanged.

        Args:
            data: Bytes to decompress (expected to be LZ4-compressed when
                  lz4 is available).

        Returns:
            Decompressed bytes, or the original bytes if lz4 is unavailable.
        """
        if _LZ4_AVAILABLE:
            return _lz4_frame.decompress(data)  # type: ignore[union-attr]
        return data

    # ------------------------------------------------------------------
    # Batch write coalescing
    # ------------------------------------------------------------------

    def queue_write(self, path: str, data: bytes) -> None:
        """Queue a write operation for later coalesced flushing.

        Multiple calls with the same path accumulate data chunks that are
        concatenated into a single write when :meth:`flush_writes` is called.

        Args:
            path: Filesystem path to write to.
            data: Bytes to append to the queued data for this path.
        """
        with self._write_lock:
            self._write_queue[path].append(data)
            logger.debug(
                "queue_write: queued %d bytes for %s (total chunks: %d)",
                len(data),
                path,
                len(self._write_queue[path]),
            )

    def flush_writes(self) -> int:
        """Flush all queued writes, coalescing chunks per file into one I/O op.

        Each path's accumulated data chunks are concatenated and written in a
        single call to :meth:`write_file`, reducing the number of I/O
        operations.

        Returns:
            Number of distinct files written.
        """
        with self._write_lock:
            pending = dict(self._write_queue)
            self._write_queue.clear()

        if not pending:
            return 0

        files_written = 0
        for path, chunks in pending.items():
            coalesced = b"".join(chunks)
            logger.debug(
                "flush_writes: writing %d bytes to %s (from %d chunk(s))",
                len(coalesced),
                path,
                len(chunks),
            )
            try:
                self.write_file(path, coalesced)
                files_written += 1
            except OSError:
                logger.exception("flush_writes: failed to write %s", path)

        return files_written

    def close(self) -> None:
        """Flush any pending writes and release resources.

        Safe to call multiple times.
        """
        logger.debug("IOOptimizer.close: flushing pending writes")
        self.flush_writes()

        with self._prefetch_lock:
            self._prefetch_cache.clear()

    # ------------------------------------------------------------------
    # Async prefetching
    # ------------------------------------------------------------------

    def prefetch(self, paths: List[str]) -> None:
        """Start a background thread to prefetch files into the in-memory cache.

        Files that cannot be read (e.g. do not exist) are silently skipped
        with a warning log entry.

        Args:
            paths: List of filesystem paths to prefetch.
        """
        if not paths:
            return

        thread = threading.Thread(
            target=self._prefetch_worker,
            args=(list(paths),),
            daemon=True,
            name="IOOptimizer-prefetch",
        )
        thread.start()
        logger.debug("prefetch: started background thread for %d path(s)", len(paths))

    def _prefetch_worker(self, paths: List[str]) -> None:
        """Background worker that reads files and stores them in the cache."""
        for path in paths:
            try:
                data = self.read_file(path)
                with self._prefetch_lock:
                    self._prefetch_cache[path] = data
                logger.debug("prefetch: cached %s (%d bytes)", path, len(data))
            except OSError:
                logger.warning("prefetch: could not read %s, skipping", path)

    def get_prefetched(self, path: str) -> Optional[bytes]:
        """Return prefetched data for a path if it is available in the cache.

        Args:
            path: Filesystem path to look up.

        Returns:
            Cached bytes if the path has been prefetched, otherwise ``None``.
        """
        with self._prefetch_lock:
            return self._prefetch_cache.get(path)
