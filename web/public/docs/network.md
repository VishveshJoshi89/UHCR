# Network Subsystem

The Network Subsystem (`uhcr.network`) enables distributed execution of UHCR computations across multiple machines in UHCR.

## Overview

The network layer provides:
- **Dual-protocol coordination** (gRPC for performance, REST for compatibility)
- **Job scheduling and tracking** across distributed workers
- **Health monitoring** and automatic failover
- **Performance telemetry** collection and aggregation
- **Worker orchestration** with hardware-aware routing

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Client Application                    │
│              uhcr.submit(), uhcr.status()               │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
    ┌───▼────────┐          ┌────▼──────┐
    │ REST API   │          │ gRPC      │
    │ (HTTP)     │          │ Service   │
    └───┬────────┘          └────┬──────┘
        │                        │
        └────────────┬───────────┘
                     │
        ┌────────────▼────────────┐
        │  Protocol Server        │
        │  (Coordinator)          │
        └────────────┬────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
    ┌───▼──────────┐      ┌──────▼────┐
    │ Worker Node  │      │ Worker    │
    │ (Hardware A) │      │ Node      │
    │              │      │ (Hardware │
    │ Job Manager  │      │ B)        │
    │ Executor     │      │           │
    └──────────────┘      └───────────┘
```

## Components

### Protocol Server (`protocol_server.py`)

Central coordinator managing both gRPC and REST endpoints.

```python
from uhcr.network.protocol_server import ProtocolServer

server = ProtocolServer(
    grpc_port=50051,
    rest_port=8080,
    max_workers=10
)
server.start()
```

**Features:**
- Unified gRPC and REST interface
- Connection pooling and load balancing
- Request routing to appropriate workers
- Graceful shutdown with connection draining

### REST API Server (`rest_api.py`)

HTTP endpoints for job submission and status queries.

```python
# Submit a job
POST /api/v1/jobs
{
  "code": "def compute(a, b): return a + b",
  "args": [10, 20],
  "hardware_hint": "avx2"
}

# Query job status
GET /api/v1/jobs/{job_id}

# Get metrics
GET /api/v1/metrics
```

**Endpoints:**
- `POST /api/v1/jobs` — Submit a new job
- `GET /api/v1/jobs/{job_id}` — Query job status
- `GET /api/v1/jobs` — List all jobs
- `DELETE /api/v1/jobs/{job_id}` — Cancel a job
- `GET /api/v1/metrics` — Retrieve performance metrics
- `GET /api/v1/health` — Health check

### gRPC Service (`grpc_service.py`)

High-performance RPC for distributed compute with streaming support.

```python
from uhcr.network.grpc_service import UHCRServicer

class UHCRImpl(UHCRServicer):
    def SubmitJob(self, request, context):
        # Handle job submission
        pass
    
    def GetJobStatus(self, request, context):
        # Return job status
        pass
    
    def StreamMetrics(self, request, context):
        # Stream metrics to client
        pass
```

**Services:**
- `SubmitJob` — Submit a computation job
- `GetJobStatus` — Query job execution status
- `CancelJob` — Cancel a running job
- `StreamMetrics` — Stream performance metrics
- `RegisterWorker` — Register a new worker node

### Job Manager (`job_manager.py`)

Handles task execution state and lifecycle.

```python
from uhcr.network.job_manager import JobManager

manager = JobManager()
job_id = manager.submit_job(code, args, hardware_hint)
status = manager.get_status(job_id)
result = manager.get_result(job_id)
```

**States:**
- `queued` — Waiting for worker availability
- `running` — Currently executing
- `completed` — Finished successfully
- `failed` — Execution error
- `cancelled` — User-initiated cancellation
- `timeout` — Exceeded time limit

### Coordinator Node (`coordinator.py`)

Routes jobs to appropriate workers based on hardware constraints.

```python
from uhcr.network.coordinator import CoordinatorNode

coordinator = CoordinatorNode(
    listen_addr='0.0.0.0',
    listen_port=50051
)
coordinator.register_worker(worker_profile)
coordinator.route_job(job, available_workers)
```

**Responsibilities:**
- Worker registration and health tracking
- Job routing based on hardware profiles
- Load balancing across workers
- Failover and retry logic

### Worker Node (`worker.py`)

Connects to coordinator, registers hardware profile, and executes jobs.

```python
from uhcr.network.worker import WorkerNode

worker = WorkerNode(
    coordinator_addr='localhost:50051',
    num_threads=8
)
worker.start()
```

**Responsibilities:**
- Register with coordinator
- Receive job assignments
- Execute jobs using local UHCR runtime
- Report results and metrics
- Maintain heartbeat with coordinator

### Health Check (`health_check.py`)

Liveness and readiness probes for distributed health monitoring.

```python
from uhcr.network.health_check import HealthChecker

checker = HealthChecker()
is_alive = checker.is_alive(worker_addr)
is_ready = checker.is_ready(worker_addr)
```

**Checks:**
- Liveness probe (TCP connection)
- Readiness probe (can accept jobs)
- Resource availability (CPU, memory)
- Network connectivity

### Metrics Collector (`metrics_collector.py`)

Aggregates performance telemetry across the cluster.

```python
from uhcr.network.metrics_collector import MetricsCollector

collector = MetricsCollector()
collector.record_job_metrics(job_id, duration, memory, throughput)
stats = collector.get_aggregate_stats()
```

**Metrics:**
- Job execution duration
- Memory usage
- Throughput (jobs/sec)
- Error rates
- Worker utilization

## Usage Patterns

### Starting a Distributed Server

```bash
uhcr serve --grpc-port 50051 --rest-port 8080 --workers 4
```

### Submitting a Remote Job

```bash
uhcr submit --server localhost:50051 \
  --code "def compute(a, b): return a + b" \
  --args 10 20
```

### Monitoring Job Status

```bash
uhcr status --server localhost:50051 --job-id job_123
```

### Real-time Monitoring

```bash
uhcr monitor --server localhost:50051 --interval 1
```

### Collecting Analytics

```bash
uhcr analytics --server localhost:50051 --duration 3600
```

## Configuration

Network components can be configured via environment variables:

```bash
export UHCR_GRPC_PORT=50051
export UHCR_REST_PORT=8080
export UHCR_MAX_WORKERS=10
export UHCR_WORKER_TIMEOUT=30
export UHCR_JOB_TIMEOUT=300
```

Or programmatically:

```python
from uhcr.network.protocol_server import ProtocolServer

server = ProtocolServer(
    grpc_port=50051,
    rest_port=8080,
    max_workers=10,
    worker_timeout=30,
    job_timeout=300
)
```

## Performance Considerations

- **gRPC**: Use for high-throughput, low-latency communication
- **REST**: Use for compatibility with HTTP clients and load balancers
- **Job Manager**: Implement job queue with priority levels for fairness
- **Coordinator**: Use consistent hashing for worker selection
- **Metrics**: Aggregate metrics asynchronously to avoid blocking job execution

## See Also

- [Architecture](architecture) — System design overview
- [Storage Subsystem](storage) — Caching and persistence
- [CLI Guide](cli-guide) — Command-line interface
