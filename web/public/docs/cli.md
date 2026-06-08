# UHCR Command-Line Interface

---

## Overview

The `uhcr` CLI provides commands for:

- 🔍 **Runtime Information** - Inspect hardware capabilities and backend selection
- ⚡ **Benchmarking** - Run performance tests and compare execution profiles
- 🖥️ **Server Management** - Deploy UHCR as a network service
- 📊 **Analytics** - Analyze job execution and performance metrics
- 🔬 **Monitoring** - Real-time runtime metrics and health checks

---

## Installation

The CLI is automatically installed with UHCR:

```bash
pip install uhcr
```

Verify installation:

```bash
uhcr --version
```

**Output:**

```
uhcr v1.0.1
```

---

## Global Options

Available for all commands:

```bash
uhcr [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]
```

### Global Flags

| Flag            | Description                                 |
| --------------- | ------------------------------------------- |
| `--version`     | Show UHCR version and exit                  |
| `--help`, `-h`  | Display help message                        |
| `--config PATH` | Load configuration from specified TOML file |

---

## Commands

### `uhcr info`

Display runtime and backend information including Python version, UHCR version, CPU features, and selected backend.

**Usage:**

```bash
uhcr info
```

**Output Example:**

```
UHCR Runtime
============
Python: 3.14.4
UHCR version: v1
Backend profile: x86_64
CPU features: avx2, sse4_2, fma, popcnt
CUDA available: False
Selected backend: AVX2Backend
```

**Use Cases:**

- Verify UHCR installation
- Check hardware detection
- Confirm backend selection
- Troubleshoot performance issues

---

### `uhcr benchmarks`

Run the complete UHCR benchmark suite to measure performance across different operations and backends.

**Usage:**

```bash
uhcr benchmarks [OPTIONS]
```

**Options:**

| Option             | Type | Default | Description                                          |
| ------------------ | ---- | ------- | ---------------------------------------------------- |
| `--iterations INT` | int  | 100     | Number of iterations per benchmark                   |
| `--warmup INT`     | int  | 10      | Warmup iterations before measurement                 |
| `--output PATH`    | str  | stdout  | Write results to JSON file                           |
| `--backend NAME`   | str  | auto    | Force specific backend (generic, avx2, avx512, cuda) |
| `--format FORMAT`  | str  | table   | Output format: table, json, csv                      |

**Examples:**

Basic benchmark run:

```bash
uhcr benchmarks
```

Save results to JSON:

```bash
uhcr benchmarks --output results.json --format json
```

Test specific backend:

```bash
uhcr benchmarks --backend avx2 --iterations 1000
```

**Output:**

```
UHCR Benchmarks
================
Running 100 iterations...

Simple Computation
  Average: 24.56 µs
  Min:     15.00 µs
  Max:     64.60 µs
  Throughput: 40,710 ops/sec

Tensor Creation (10K elements)
  Average: 1,263 µs
  Min:     695 µs
  Max:     4,008 µs
  Throughput: 792 tensors/sec

JIT Function Call
  Average: 112.57 µs
  Throughput: 8,883 calls/sec

Loop Performance (1K iterations)
  Average: 118.37 µs
  Operations/sec: 8,448,086
```

**Benchmark Categories:**

- Simple arithmetic operations
- Tensor creation and allocation
- JIT compilation overhead
- Loop performance
- Memory efficiency
- Backend-specific operations

---

### `uhcr serve`

Start UHCR as a network service with gRPC and HTTP endpoints for remote execution.

**Usage:**

```bash
uhcr serve [OPTIONS]
```

**Options:**

| Option               | Type | Default             | Description                     |
| -------------------- | ---- | ------------------- | ------------------------------- |
| `--host HOST`        | str  | 0.0.0.0             | Bind address for server         |
| `--grpc-port PORT`   | int  | 50051               | gRPC service port               |
| `--http-port PORT`   | int  | 8080                | HTTP REST API port              |
| `--workers INT`      | int  | 4                   | Number of worker threads        |
| `--grace-period INT` | int  | 30                  | Shutdown grace period (seconds) |
| `--redis-url URL`    | str  | None                | Redis cache URL                 |
| `--sqlite-path PATH` | str  | None                | SQLite database path            |
| `--config PATH`      | str  | ~/.uhcr/config.toml | Configuration file path         |

**Examples:**

Start server with defaults:

```bash
uhcr serve
```

Custom ports and workers:

```bash
uhcr serve --grpc-port 9090 --http-port 9091 --workers 8
```

Production deployment:

```bash
uhcr serve \
  --host 10.0.0.1 \
  --workers 16 \
  --grace-period 60 \
  --redis-url redis://localhost:6379/0 \
  --sqlite-path /var/lib/uhcr/data.db
```

**Service Endpoints:**

**gRPC (port 50051):**

- `ExecuteFunction` - Execute JIT-compiled function
- `CompileIR` - Compile IR module
- `GetCapabilities` - Query hardware capabilities

**HTTP REST API (port 8080):**

- `GET /health` - Health check endpoint
- `POST /execute` - Execute function
- `GET /metrics` - Prometheus-compatible metrics
- `GET /api/v1/status` - Runtime status

**Health Check:**

```bash
curl http://localhost:8080/health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "v1",
  "uptime_seconds": 3600,
  "active_workers": 4
}
```

---

### `uhcr monitor`

Real-time monitoring of UHCR runtime metrics including CPU usage, memory, active jobs, and performance statistics.

**Usage:**

```bash
uhcr monitor [OPTIONS]
```

**Options:**

| Option              | Type | Default | Description                        |
| ------------------- | ---- | ------- | ---------------------------------- |
| `--interval INT`    | int  | 2       | Update interval in seconds         |
| `--json`            | flag | False   | Output in JSON format              |
| `--metrics METRICS` | str  | all     | Comma-separated metrics to display |

**Examples:**

Basic monitoring:

```bash
uhcr monitor
```

JSON output with 5-second interval:

```bash
uhcr monitor --interval 5 --json
```

Specific metrics:

```bash
uhcr monitor --metrics cpu,memory,jobs
```

**Output:**

```
UHCR Monitor (updating every 2s)
=================================

CPU Usage:        23.4%
Memory Used:      1.2 GB / 16.0 GB (7.5%)
Active Jobs:      3
Completed Jobs:   127
Failed Jobs:      0

Backend:          AVX2Backend
Cache Hit Rate:   94.2%
Avg Job Time:     45.2 ms

Press Ctrl+C to exit
```

**JSON Output:**

```json
{
  "timestamp": "2026-06-08T10:30:45Z",
  "cpu_usage_percent": 23.4,
  "memory_used_gb": 1.2,
  "memory_total_gb": 16.0,
  "active_jobs": 3,
  "completed_jobs": 127,
  "failed_jobs": 0,
  "backend": "AVX2Backend",
  "cache_hit_rate": 0.942,
  "avg_job_time_ms": 45.2
}
```

**Available Metrics:**

- `cpu` - CPU usage percentage
- `memory` - Memory usage
- `jobs` - Job statistics
- `backend` - Backend information
- `cache` - Cache performance
- `network` - Network metrics (if server running)
- `all` - All metrics (default)

---

### `uhcr analytics`

Analyze job execution history, compare performance profiles, and generate performance reports.

**Usage:**

```bash
uhcr analytics JOB_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description               |
| -------- | -------- | ------------------------- |
| `JOB_ID` | Yes      | Job identifier to analyze |

**Options:**

| Option              | Type | Default | Description                      |
| ------------------- | ---- | ------- | -------------------------------- |
| `--compare JOB_ID`  | str  | None    | Compare with another job         |
| `--format FORMAT`   | str  | table   | Output format: table, json, html |
| `--output PATH`     | str  | stdout  | Write report to file             |
| `--metrics METRICS` | str  | all     | Specific metrics to include      |

**Examples:**

Analyze single job:

```bash
uhcr analytics job-12345
```

Compare two jobs:

```bash
uhcr analytics job-12345 --compare job-67890
```

Generate HTML report:

```bash
uhcr analytics job-12345 --format html --output report.html
```

**Output:**

```
Job Analytics: job-12345
========================

Execution Time:     142.3 ms
Backend Used:       AVX2Backend
CPU Time:           138.1 ms
Memory Peak:        45.2 MB
Cache Hits:         234 / 250 (93.6%)
Compilation Time:   8.2 ms
Execution Count:    1,000

Top Operations:
  matmul:     45.2 ms (31.8%)
  add:        32.1 ms (22.6%)
  relu:       18.4 ms (12.9%)

Optimization Passes Applied:
  ✓ Constant Folding
  ✓ Dead Code Elimination
  ✓ Common Subexpression Elimination
  ✓ Strength Reduction
```

**Comparison Output:**

```
Job Comparison
==============

                    job-12345    job-67890    Difference
Execution Time:     142.3 ms     165.8 ms     -14.2% ✓
Memory Peak:        45.2 MB      52.3 MB      -13.6% ✓
Cache Hit Rate:     93.6%        87.2%        +6.4%  ✓
Backend:            AVX2         Generic      -
```

---

### `uhcr mcp`

Start the UHCR Model Context Protocol (MCP) server for AI agent integration. Enables AI assistants to query documentation, search code examples, and get API references.

**Usage:**

```bash
uhcr mcp [OPTIONS]
```

**Options:**

| Option              | Type | Default   | Description                                     |
| ------------------- | ---- | --------- | ----------------------------------------------- |
| `--docs-path PATH`  | str  | ./docs    | Documentation directory path                    |
| `--host HOST`       | str  | localhost | MCP server bind address                         |
| `--port PORT`       | int  | 3000      | MCP server port                                 |
| `--log-level LEVEL` | str  | INFO      | Logging level (DEBUG, INFO, WARN, ERROR)        |
| `--cache`           | flag | False     | Enable documentation caching                    |
| `--stdio`           | flag | False     | Use stdio transport (for direct AI integration) |

**Examples:**

Start MCP server:

```bash
uhcr mcp --docs-path docs/
```

Start with caching enabled:

```bash
uhcr mcp --docs-path docs/ --cache --log-level DEBUG
```

Start in stdio mode (for Claude Desktop/Kiro):

```bash
uhcr mcp --stdio
```

**Available MCP Tools:**

The MCP server exposes these tools to AI agents:

1. **`search_docs`** - Search documentation by keywords

   ```json
   {
     "query": "jit compilation",
     "category": "guides",
     "max_results": 5
   }
   ```

2. **`get_code_examples`** - Extract code examples

   ```json
   {
     "topic": "tensor operations",
     "language": "python"
   }
   ```

3. **`get_api_reference`** - Get API documentation

   ```json
   {
     "api_name": "uhcr.tensor"
   }
   ```

4. **`get_navigation_structure`** - Get docs hierarchy

   ```json
   {}
   ```

5. **`get_quick_reference`** - Get cheat sheets
   ```json
   {
     "category": "jit"
   }
   ```

**AI Assistant Configuration:**

For Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "uhcr",
      "args": ["mcp", "--stdio", "--docs-path", "/path/to/UHCR/docs"],
      "env": {}
    }
  }
}
```

For Kiro, add to `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "uhcr",
      "args": ["mcp", "--stdio"],
      "autoApprove": ["search_docs", "get_code_examples"],
      "disabled": false
    }
  }
}
```

**Testing MCP Server:**

```bash
# Start server
uhcr mcp --docs-path docs/ --log-level DEBUG

# In another terminal, test with curl (if using HTTP mode)
curl http://localhost:3000/tools/search_docs \
  -d '{"query": "tensor", "max_results": 3}'
```

**Use Cases:**

- Enable AI assistants to search UHCR documentation
- Provide code examples to AI coding assistants
- Allow AI agents to understand UHCR API
- Support AI-powered documentation navigation
- Enable conversational documentation queries

---

## Configuration File

UHCR can be configured via TOML file at `~/.uhcr/config.toml`.

**Location Priority:**

1. Path specified with `--config`
2. `~/.uhcr/config.toml` (default)
3. Built-in defaults

**Example Configuration:**

```toml
[server]
host = "0.0.0.0"
grpc_port = 50051
http_port = 8080
workers = 4
grace_period = 30

# Optional: Redis cache
redis_url = "redis://localhost:6379/0"

# Optional: SQLite persistence
sqlite_path = "/var/lib/uhcr/data.db"

[benchmarks]
iterations = 100
warmup = 10
output_format = "json"

[monitoring]
update_interval = 2
metrics = ["cpu", "memory", "jobs"]

[runtime]
default_backend = "avx2"  # auto, generic, avx2, avx512, cuda
cache_size_mb = 512
enable_profiling = true
```

**Configuration Keys:**

### `[server]`

- `host` - Bind address (default: "0.0.0.0")
- `grpc_port` - gRPC port (default: 50051)
- `http_port` - HTTP port (default: 8080)
- `workers` - Worker threads (default: 4)
- `grace_period` - Shutdown timeout (default: 30)
- `redis_url` - Redis cache connection
- `sqlite_path` - SQLite database location

### `[benchmarks]`

- `iterations` - Benchmark iterations (default: 100)
- `warmup` - Warmup iterations (default: 10)
- `output_format` - Format: table, json, csv

### `[monitoring]`

- `update_interval` - Monitor refresh rate (default: 2)
- `metrics` - Metrics to track

### `[runtime]`

- `default_backend` - Backend selection
- `cache_size_mb` - JIT cache size
- `enable_profiling` - Enable performance profiling

---

## Environment Variables

UHCR respects the following environment variables:

| Variable         | Description                  | Default         |
| ---------------- | ---------------------------- | --------------- |
| `UHCR_HOME`      | UHCR configuration directory | `~/.uhcr`       |
| `UHCR_BACKEND`   | Force backend selection      | auto            |
| `UHCR_CACHE_DIR` | JIT cache directory          | `~/.uhcr/cache` |
| `UHCR_LOG_LEVEL` | Logging level                | INFO            |
| `UHCR_WORKERS`   | Default worker count         | 4               |
| `UHCR_GRPC_PORT` | Default gRPC port            | 50051           |
| `UHCR_HTTP_PORT` | Default HTTP port            | 8080            |

**Example:**

```bash
export UHCR_BACKEND=avx2
export UHCR_LOG_LEVEL=DEBUG
uhcr serve
```

---

## Exit Codes

| Code | Meaning                       |
| ---- | ----------------------------- |
| 0    | Success                       |
| 1    | General error                 |
| 2    | Invalid arguments             |
| 3    | Configuration error           |
| 4    | Backend initialization failed |
| 5    | Network error (server mode)   |
| 130  | Interrupted (Ctrl+C)          |

---

## Examples

### Development Workflow

```bash
# Check system capabilities
uhcr info

# Run benchmarks to establish baseline
uhcr benchmarks --output baseline.json

# Start development server
uhcr serve --workers 2

# Monitor performance
uhcr monitor --interval 1
```

### AI Assistant Integration

```bash
# Start MCP server for AI agents
uhcr mcp --docs-path docs/ --cache

# Or use stdio mode for direct integration
uhcr mcp --stdio --docs-path docs/
```

**Claude Desktop Integration:**

```json
{
  "mcpServers": {
    "uhcr-docs": {
      "command": "uhcr",
      "args": ["mcp", "--stdio", "--docs-path", "/path/to/UHCR/docs"]
    }
  }
}
```

### Production Deployment

```bash
# Create configuration
cat > ~/.uhcr/config.toml << EOF
[server]
host = "10.0.0.1"
grpc_port = 50051
http_port = 8080
workers = 16
grace_period = 60
redis_url = "redis://redis-server:6379/0"
sqlite_path = "/var/lib/uhcr/data.db"
EOF

# Start server
uhcr serve --config ~/.uhcr/config.toml

# Health check
curl http://10.0.0.1:8080/health

# Monitor in separate terminal
uhcr monitor --json > metrics.log
```

### Performance Analysis

```bash
# Run benchmarks with different backends
uhcr benchmarks --backend generic --output generic.json
uhcr benchmarks --backend avx2 --output avx2.json
uhcr benchmarks --backend avx512 --output avx512.json

# Compare results
diff generic.json avx2.json

# Analyze specific job
uhcr analytics job-abc123 --output report.html --format html
```

---

## Troubleshooting

### Command Not Found

**Problem:** `uhcr: command not found`

**Solution:**

```bash
# Reinstall UHCR
pip install --upgrade uhcr

# Verify installation
python -c "import uhcr; print(uhcr.__version__)"

# Check PATH
echo $PATH | grep -o ~/.local/bin
```

### Server Won't Start

**Problem:** Port already in use

**Solution:**

```bash
# Check port usage
lsof -i :50051
lsof -i :8080

# Use different ports
uhcr serve --grpc-port 50052 --http-port 8081
```

### Performance Issues

**Problem:** Slow execution

**Solution:**

```bash
# Check backend selection
uhcr info

# Force better backend
export UHCR_BACKEND=avx2
uhcr benchmarks

# Monitor resource usage
uhcr monitor
```

---

## See Also

- [Quick Start Guide](quickstart) - Getting started with UHCR
- [API Reference](api-reference) - Python API documentation
- [Benchmarks](benchmarks) - Performance metrics
- [Network Subsystem](network) - Distributed execution
- [Containerization](containerization) - Docker/K8s deployment
- [AI Agent Integration](ai-integration) - MCP server details

---

## Feedback

Have questions or suggestions about the CLI?

- 🐛 **Report a bug**: [GitHub Issues](https://github.com/VishveshJoshi89/UHCR/issues)
- 💬 **Start a discussion**: [GitHub Discussions](https://github.com/VishveshJoshi89/UHCR/discussions)
- 📖 **Improve docs**: Submit a pull request

---

**Last Updated:** June 8, 2026  
**UHCR Version:** v1  
**CLI Version:** v1.0.1
