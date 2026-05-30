"""Storage optimizer — Redis hot cache, SQLite persistence, memory pooling, and I/O optimization.

The storage subsystem provides a multi-tier caching and persistence layer for UHCR
It coordinates four components:

- RedisCache: Hot cache for compiled artifacts and intermediate results
- SQLiteStore: Local persistence for job history, configuration, and metrics
- MemoryPool: Pre-allocated aligned buffer reuse to reduce allocation overhead
- IOOptimizer: Memory-mapped I/O, LZ4 compression, prefetching, and batch writes
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uhcr.storage.redis_cache import RedisCache
    from uhcr.storage.sqlite_store import SQLiteStore
    from uhcr.storage.memory_pool import MemoryPool
    from uhcr.storage.io_optimizer import IOOptimizer

logger = logging.getLogger(__name__)


class StorageOptimizer:
    """Facade coordinating all storage subsystems.

    The StorageOptimizer is the main entry point for storage operations in UHCR.
    It manages the lifecycle of Redis cache, SQLite store, memory pool, and I/O
    optimizer, providing a unified interface for the rest of the runtime.

    Usage:
        optimizer = StorageOptimizer()
        await optimizer.initialize()
        # ... use optimizer.redis_cache, optimizer.sqlite_store, etc.
        await optimizer.shutdown()
    """

    def __init__(self) -> None:
        self._redis_cache: Optional[RedisCache] = None
        self._sqlite_store: Optional[SQLiteStore] = None
        self._memory_pool: Optional[MemoryPool] = None
        self._io_optimizer: Optional[IOOptimizer] = None
        self._initialized: bool = False

    @property
    def redis_cache(self) -> Optional[RedisCache]:
        """The Redis hot cache instance, or None if not initialized."""
        return self._redis_cache

    @property
    def sqlite_store(self) -> Optional[SQLiteStore]:
        """The SQLite persistence store instance, or None if not initialized."""
        return self._sqlite_store

    @property
    def memory_pool(self) -> Optional[MemoryPool]:
        """The memory pool instance, or None if not initialized."""
        return self._memory_pool

    @property
    def io_optimizer(self) -> Optional[IOOptimizer]:
        """The I/O optimizer instance, or None if not initialized."""
        return self._io_optimizer

    @property
    def initialized(self) -> bool:
        """Whether the storage optimizer has been initialized."""
        return self._initialized

    async def initialize(self) -> None:
        """Initialize all storage subsystems.

        Creates and configures the Redis cache, SQLite store, memory pool,
        and I/O optimizer. Subsystems that fail to initialize (e.g. Redis
        unavailable) will fall back gracefully with a warning log.
        """
        if self._initialized:
            logger.warning("StorageOptimizer already initialized")
            return

        logger.info("Initializing storage optimizer")

        # Initialize memory pool (no external dependencies)
        try:
            from uhcr.storage.memory_pool import MemoryPool
            self._memory_pool = MemoryPool()
            logger.info("Memory pool initialized")
        except Exception as e:
            logger.error("Failed to initialize memory pool: %s", e)

        # Initialize SQLite store
        try:
            from uhcr.storage.sqlite_store import SQLiteStore
            self._sqlite_store = SQLiteStore()
            logger.info("SQLite store initialized")
        except Exception as e:
            logger.error("Failed to initialize SQLite store: %s", e)

        # Initialize Redis cache (may fall back to in-memory)
        try:
            from uhcr.storage.redis_cache import RedisCache
            self._redis_cache = RedisCache()
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.warning("Failed to initialize Redis cache: %s", e)

        # Initialize I/O optimizer
        try:
            from uhcr.storage.io_optimizer import IOOptimizer
            self._io_optimizer = IOOptimizer()
            logger.info("I/O optimizer initialized")
        except Exception as e:
            logger.error("Failed to initialize I/O optimizer: %s", e)

        self._initialized = True
        logger.info("Storage optimizer initialization complete")

    async def shutdown(self) -> None:
        """Shut down all storage subsystems and release resources.

        Gracefully closes connections, flushes pending writes, and returns
        pooled memory to the system.
        """
        if not self._initialized:
            return

        logger.info("Shutting down storage optimizer")

        if self._redis_cache is not None:
            try:
                await self._redis_cache.close()
            except Exception as e:
                logger.error("Error closing Redis cache: %s", e)
            self._redis_cache = None

        if self._sqlite_store is not None:
            try:
                self._sqlite_store.close()
            except Exception as e:
                logger.error("Error closing SQLite store: %s", e)
            self._sqlite_store = None

        if self._memory_pool is not None:
            try:
                self._memory_pool.release_all()
            except Exception as e:
                logger.error("Error releasing memory pool: %s", e)
            self._memory_pool = None

        if self._io_optimizer is not None:
            try:
                self._io_optimizer.close()
            except Exception as e:
                logger.error("Error closing I/O optimizer: %s", e)
            self._io_optimizer = None

        self._initialized = False
        logger.info("Storage optimizer shutdown complete")
