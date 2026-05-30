"""Redis hot cache for compiled artifacts and intermediate results.

Provides an async Redis client with configurable TTL, LZ4 compression,
and automatic fallback to an in-memory dict when Redis is unavailable.

Key format:
    uhcr:compiled:{structural_hash} — LZ4-compressed compiled artifact bytes
    uhcr:result:{job_id} — LZ4-compressed computation result bytes
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Dict, Optional, Tuple

# Try importing redis (async)
try:
    import redis.asyncio as aioredis

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

# Try importing lz4 for compression
try:
    import lz4.frame

    _LZ4_AVAILABLE = True
except ImportError:
    _LZ4_AVAILABLE = False

logger = logging.getLogger(__name__)


class RedisCache:
    """Async Redis cache with TTL, LZ4 compression, and in-memory fallback.

    The cache stores compiled artifacts and computation results keyed by
    structural hash or job ID. Keys are formatted as:
        - ``uhcr:compiled:{hash}`` for compiled artifacts
        - ``uhcr:result:{job_id}`` for computation results

    If the ``redis`` package is not installed or the Redis server is
    unreachable, the cache falls back to a thread-safe in-memory dict
    with TTL tracking.

    Args:
        redis_url: Redis connection URL. If not provided, reads from the
            ``UHCR_REDIS_URL`` environment variable. Falls back to
            in-memory mode if neither is set or connection fails.
        default_ttl: Default time-to-live in seconds for cached entries.
            Defaults to 86400 (24 hours).
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = 86400,
    ) -> None:
        self._default_ttl = default_ttl
        self._redis_client: Optional[object] = None
        self._using_fallback = False

        # In-memory fallback storage: key -> (data, expiry_timestamp)
        self._memory_store: Dict[str, Tuple[bytes, float]] = {}
        self._memory_lock = threading.Lock()

        # Resolve Redis URL
        url = redis_url or os.environ.get("UHCR_REDIS_URL")

        if not _REDIS_AVAILABLE:
            logger.warning(
                "redis package not installed; using in-memory cache fallback"
            )
            self._using_fallback = True
            return

        if not url:
            logger.warning(
                "No Redis URL configured (UHCR_REDIS_URL not set); "
                "using in-memory cache fallback"
            )
            self._using_fallback = True
            return

        # Attempt to create the Redis client
        try:
            self._redis_client = aioredis.from_url(
                url, decode_responses=False
            )
        except Exception as exc:
            logger.warning(
                "Failed to create Redis client (%s); "
                "using in-memory cache fallback",
                exc,
            )
            self._using_fallback = True

    @property
    def using_fallback(self) -> bool:
        """Whether the cache is using the in-memory fallback."""
        return self._using_fallback

    @property
    def default_ttl(self) -> int:
        """The default TTL in seconds for cached entries."""
        return self._default_ttl

    # ------------------------------------------------------------------
    # Compression helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compress(data: bytes) -> bytes:
        """Compress data using LZ4 if available."""
        if _LZ4_AVAILABLE:
            return lz4.frame.compress(data)
        return data

    @staticmethod
    def _decompress(data: bytes) -> bytes:
        """Decompress data using LZ4 if available."""
        if _LZ4_AVAILABLE:
            return lz4.frame.decompress(data)
        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[bytes]:
        """Retrieve cached data by key.

        Args:
            key: The cache key (e.g. ``uhcr:compiled:{hash}``).

        Returns:
            The decompressed cached bytes, or ``None`` if not found or expired.
        """
        if self._using_fallback:
            return self._fallback_get(key)

        try:
            raw = await self._redis_client.get(key)  # type: ignore[union-attr]
            if raw is None:
                return None
            return self._decompress(raw)
        except Exception as exc:
            logger.warning(
                "Redis GET failed for key %s (%s); switching to fallback",
                key,
                exc,
            )
            self._switch_to_fallback()
            return self._fallback_get(key)

    async def put(
        self, key: str, data: bytes, ttl: Optional[int] = None
    ) -> None:
        """Store data in the cache with a TTL.

        Args:
            key: The cache key (e.g. ``uhcr:compiled:{hash}``).
            data: The raw bytes to cache.
            ttl: Time-to-live in seconds. Uses the default TTL if not specified.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        compressed = self._compress(data)

        if self._using_fallback:
            self._fallback_put(key, compressed, effective_ttl)
            return

        try:
            await self._redis_client.set(  # type: ignore[union-attr]
                key, compressed, ex=effective_ttl
            )
        except Exception as exc:
            logger.warning(
                "Redis SET failed for key %s (%s); switching to fallback",
                key,
                exc,
            )
            self._switch_to_fallback()
            self._fallback_put(key, compressed, effective_ttl)

    async def invalidate(self, key: str) -> None:
        """Remove a cache entry.

        Args:
            key: The cache key to invalidate.
        """
        if self._using_fallback:
            self._fallback_invalidate(key)
            return

        try:
            await self._redis_client.delete(key)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning(
                "Redis DELETE failed for key %s (%s); switching to fallback",
                key,
                exc,
            )
            self._switch_to_fallback()
            self._fallback_invalidate(key)

    async def close(self) -> None:
        """Close the Redis connection and release resources."""
        if self._redis_client is not None:
            try:
                await self._redis_client.aclose()  # type: ignore[union-attr]
            except Exception as exc:
                logger.warning("Error closing Redis connection: %s", exc)
            finally:
                self._redis_client = None

    # ------------------------------------------------------------------
    # In-memory fallback (thread-safe)
    # ------------------------------------------------------------------

    def _switch_to_fallback(self) -> None:
        """Switch from Redis to in-memory fallback mode."""
        if not self._using_fallback:
            logger.warning(
                "Redis unavailable; switching to in-memory cache fallback"
            )
            self._using_fallback = True

    def _fallback_get(self, key: str) -> Optional[bytes]:
        """Get a value from the in-memory store, respecting TTL."""
        with self._memory_lock:
            entry = self._memory_store.get(key)
            if entry is None:
                return None
            data, expiry = entry
            if time.time() > expiry:
                del self._memory_store[key]
                return None
            return self._decompress(data)

    def _fallback_put(self, key: str, compressed_data: bytes, ttl: int) -> None:
        """Put a value into the in-memory store with TTL tracking."""
        expiry = time.time() + ttl
        with self._memory_lock:
            self._memory_store[key] = (compressed_data, expiry)

    def _fallback_invalidate(self, key: str) -> None:
        """Remove a key from the in-memory store."""
        with self._memory_lock:
            self._memory_store.pop(key, None)
