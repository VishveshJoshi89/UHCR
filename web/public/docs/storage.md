# Storage Subsystem

The Storage Subsystem (`uhcr.storage`) provides high-performance caching, persistence, and memory management for UHCR 

## Overview

The storage layer is designed to:
- **Cache compiled kernels** for fast reuse across multiple invocations
- **Persist execution metadata** for auditing and recovery
- **Optimize memory allocation** with pre-allocated pools
- **Accelerate I/O operations** with batching and compression
- **Verify data integrity** with checksums

## Components

### Memory Pool Manager (`memory_pool.py`)

Manages a pre-allocated pool of aligned buffers to reduce allocation overhead.

```python
from uhcr.storage.memory_pool import MemoryPool

pool = MemoryPool(buffer_size=1024*1024, num_buffers=100)
buf = pool.acquire()
# ... use buffer ...
pool.release(buf)
```

**Features:**
- Pre-allocated `AlignedBuffer` instances (64-byte alignment)
- Fragmentation tracking and defragmentation
- Thread-safe acquire/release operations
- Automatic cleanup on context exit

### Redis Cache Layer (`redis_cache.py`)

High-speed distributed caching for compiled code and intermediate results.

```python
from uhcr.storage.redis_cache import RedisCache

cache = RedisCache(host='localhost', port=6379, db=0)
cache.set('kernel_hash', compiled_binary, ttl=3600)
binary = cache.get('kernel_hash')
```

**Features:**
- Key-value storage with TTL support
- Automatic serialization/deserialization
- Connection pooling
- Cluster support for distributed deployments

### SQLite Persistence (`sqlite_backend.py`)

Durable storage for job execution metrics, histories, and server state.

```python
from uhcr.storage.sqlite_backend import SQLiteStore

store = SQLiteStore(db_path='uhcr.db')
store.record_job(job_id, status, duration, result)
history = store.get_job_history(limit=100)
```

**Features:**
- Job execution tracking (queued, running, completed, failed)
- Performance metrics (duration, memory, throughput)
- Query interface for analytics
- Automatic schema initialization

### I/O Optimizer (`io_optimizer.py`)

Combines memory-mapped I/O, LZ4 compression, and batched writes for fast disk/network transfers.

```python
from uhcr.storage.io_optimizer import IOOptimizer

optimizer = IOOptimizer(batch_size=1000, compression='lz4')
optimizer.write_batch(data_list)
result = optimizer.read_mmap(file_path)
```

**Features:**
- Memory-mapped file I/O for zero-copy reads
- LZ4 compression for bandwidth optimization
- Batched writes to reduce syscall overhead
- Async I/O support with asyncio

### Checksum Validator (`checksum.py`)

SHA256-based integrity verification for cached kernels and data.

```python
from uhcr.storage.checksum import ChecksumValidator

validator = ChecksumValidator()
checksum = validator.compute(data)
is_valid = validator.verify(data, checksum)
```

**Features:**
- SHA256 hashing for integrity verification
- Streaming hash computation for large files
- Checksum caching to avoid recomputation
- Mismatch detection and reporting

## Usage Patterns

### Caching Compiled Kernels

```python
import uhcr
from uhcr.storage.redis_cache import RedisCache
from uhcr.storage.checksum import ChecksumValidator

cache = RedisCache()
validator = ChecksumValidator()

@uhcr.jit
def compute(a, b):
    return a + b

# First call: compile and cache
result1 = compute(10, 20)

# Second call: retrieve from cache
result2 = compute(10, 20)  # Fast!
```

### Persisting Job History

```python
from uhcr.storage.sqlite_backend import SQLiteStore

store = SQLiteStore('jobs.db')

# Record job execution
store.record_job(
    job_id='job_123',
    status='completed',
    duration=1.23,
    result={'output': [1, 2, 3]}
)

# Query history
history = store.get_job_history(limit=50)
for job in history:
    print(f"{job['job_id']}: {job['status']} ({job['duration']}s)")
```

### Optimized Batch I/O

```python
from uhcr.storage.io_optimizer import IOOptimizer

optimizer = IOOptimizer(batch_size=5000, compression='lz4')

# Write large dataset efficiently
data = [{'id': i, 'value': i*2} for i in range(100000)]
optimizer.write_batch(data, output_file='data.bin')

# Read with zero-copy memory mapping
result = optimizer.read_mmap('data.bin')
```

## Configuration

Storage components can be configured via environment variables or programmatically:

```python
import os
from uhcr.storage.redis_cache import RedisCache

# Via environment
os.environ['UHCR_REDIS_HOST'] = 'redis.example.com'
os.environ['UHCR_REDIS_PORT'] = '6379'

# Via constructor
cache = RedisCache(
    host='redis.example.com',
    port=6379,
    db=0,
    password='secret'
)
```

## Performance Considerations

- **Memory Pool**: Pre-allocate based on expected workload to minimize allocation latency
- **Redis Cache**: Use TTL to prevent unbounded memory growth; consider cluster mode for HA
- **SQLite**: Index frequently-queried columns (job_id, status, timestamp)
- **I/O Optimizer**: Tune batch_size based on data size and network latency
- **Checksums**: Cache computed checksums to avoid recomputation on repeated verifications

## See Also

- [Architecture](architecture) — System design overview
- [API Reference](api-reference) — Complete API documentation
