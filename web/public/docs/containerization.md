# UHCR Containerization Guide
---
## Overview

UHCR applications can be containerized using Docker and orchestrated with Kubernetes for scalable deployment. This guide covers container optimization, multi-container architectures, and performance considerations.

---

## Docker Integration

### Basic Dockerfile

Create a production-ready UHCR container:

```dockerfile
FROM python:3.11-slim

# Install system dependencies for UHCR
RUN apt-get update && apt-get install -y \
    build-essential \
    cuda-toolkit-11-8 \
    libnuma-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV UHCR_CACHE_DIR=/opt/uhcr/cache
ENV UHCR_LOG_LEVEL=INFO

# Create UHCR directories
RUN mkdir -p /opt/uhcr/cache /app

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose ports for UHCR network subsystem
EXPOSE 8080 9090

# Run UHCR application
CMD ["python", "main.py"]
```

### Multi-stage Build

Optimize container size with multi-stage builds:

```dockerfile
# Build stage
FROM python:3.11 as builder

RUN pip install --user uhcr numpy

# Runtime stage  
FROM python:3.11-slim

# Copy built packages
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

COPY app.py .
CMD ["python", "app.py"]
```

---

## Container Optimization

### Hardware Detection in Containers

Enable proper hardware detection:

```python
import uhcr
import os

# Configure UHCR for container environment
def setup_containerized_uhcr():
    # Override CPU detection for containers
    if os.environ.get('KUBERNETES_SERVICE_HOST'):
        # Running in Kubernetes
        uhcr.config.set('backend.prefer_cpu', True)
        uhcr.config.set('memory.pool_size', '512MB')
    
    # Detect available hardware
    profile = uhcr.detect()
    
    print(f"Container CPU: {profile.cpu.brand}")
    print(f"Available cores: {profile.cpu.cores}")
    print(f"Memory: {profile.memory.total_bytes // (1024**3)}GB")
    
    return profile

# Initialize UHCR in container
profile = setup_containerized_uhcr()
```

### Resource Limits

Configure resource constraints:

```yaml
# docker-compose.yml
version: '3.8'
services:
  uhcr-app:
    build: .
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0' 
          memory: 4G
    environment:
      - UHCR_MAX_THREADS=4
      - UHCR_MEMORY_LIMIT=6G
    volumes:
      - uhcr_cache:/opt/uhcr/cache
      
volumes:
  uhcr_cache:
```

---

## Kubernetes Deployment

### Pod Specification

Deploy UHCR workloads on Kubernetes:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: uhcr-compute-pod
  labels:
    app: uhcr-compute
spec:
  containers:
  - name: uhcr-worker
    image: myregistry/uhcr-app:latest
    resources:
      requests:
        cpu: 2000m
        memory: 4Gi
      limits:
        cpu: 4000m
        memory: 8Gi
    env:
    - name: UHCR_WORKER_ID
      valueFrom:
        fieldRef:
          fieldPath: metadata.name
    - name: UHCR_LOG_LEVEL
      value: "INFO"
    volumeMounts:
    - name: uhcr-cache
      mountPath: /opt/uhcr/cache
  volumes:
  - name: uhcr-cache
    emptyDir:
      sizeLimit: 2Gi
```

### Deployment with Auto-scaling

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: uhcr-workers
spec:
  replicas: 3
  selector:
    matchLabels:
      app: uhcr-worker
  template:
    metadata:
      labels:
        app: uhcr-worker
    spec:
      containers:
      - name: uhcr-worker
        image: uhcr/worker:v1.0
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
        readinessProbe:
          httpGet:
            path: /ready  
            port: 8080
          initialDelaySeconds: 5

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: uhcr-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: uhcr-workers
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## Multi-Container Architecture

### Coordinator-Worker Pattern

```yaml
# docker-compose.yml
version: '3.8'
services:
  uhcr-coordinator:
    image: uhcr/coordinator:latest
    ports:
      - "8080:8080"
    environment:
      - UHCR_MODE=coordinator
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  uhcr-worker:
    image: uhcr/worker:latest
    deploy:
      replicas: 4
    environment:
      - UHCR_MODE=worker
      - COORDINATOR_URL=http://uhcr-coordinator:8080
      - REDIS_URL=redis://redis:6379
    depends_on:
      - uhcr-coordinator
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Service Mesh Integration

```python
# uhcr_service.py - Service mesh enabled UHCR
import uhcr
from uhcr.network import ServiceMesh

class UHCRService:
    def __init__(self):
        # Initialize service mesh
        self.mesh = ServiceMesh(
            service_name="uhcr-compute",
            registry_url=os.environ.get('SERVICE_REGISTRY'),
            metrics_port=9090
        )
        
        # Register compute endpoints
        self.mesh.register_endpoint(
            name="compute",
            handler=self.handle_compute,
            method="POST"
        )
    
    async def handle_compute(self, request):
        """Handle compute requests via service mesh"""
        
        @uhcr.jit(eager=True)
        def compute_task(data):
            # Your computation logic
            return data * 2 + 1
        
        result = compute_task(request.data)
        
        # Return response through mesh
        return {
            'result': result.tolist(),
            'worker_id': os.environ.get('UHCR_WORKER_ID'),
            'execution_time': request.execution_time
        }

# Start service
if __name__ == "__main__":
    service = UHCRService()
    service.mesh.start()
```

---

## Performance Considerations

### CPU Affinity

Set CPU affinity in containers:

```python
import uhcr
import os

def configure_cpu_affinity():
    """Configure CPU affinity for containerized UHCR"""
    
    # Get allocated CPUs from container
    cpu_quota = int(os.environ.get('UHCR_CPU_QUOTA', '0'))
    
    if cpu_quota > 0:
        # Set thread affinity
        uhcr.config.set('scheduler.cpu_affinity', True)
        uhcr.config.set('scheduler.max_threads', cpu_quota)
        
        print(f"Configured for {cpu_quota} CPU cores")

# Apply configuration
configure_cpu_affinity()
```

### Memory Management

```python
import uhcr

def setup_container_memory():
    """Optimize memory usage in containers"""
    
    # Get container memory limit
    memory_limit = os.environ.get('UHCR_MEMORY_LIMIT', '4G')
    
    # Configure UHCR memory pool
    uhcr.config.set('memory.pool_size', memory_limit)
    uhcr.config.set('memory.gc_threshold', 0.8)  # GC at 80% usage
    
    # Pre-allocate memory pool
    uhcr.memory.preallocate()

setup_container_memory()
```

### GPU Support in Containers

```dockerfile
# GPU-enabled Dockerfile
FROM nvidia/cuda:11.8-devel-ubuntu22.04

# Install UHCR with CUDA support
RUN pip install uhcr[cuda]

# Configure GPU access
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

COPY app.py .
CMD ["python", "app.py"]
```

---

## Monitoring and Observability

### Health Checks

```python
# health.py - Container health checks
from fastapi import FastAPI
import uhcr

app = FastAPI()

@app.get("/health")
async def health_check():
    """Kubernetes liveness probe"""
    try:
        # Test UHCR functionality
        @uhcr.jit(eager=True)
        def test_compute():
            return 42
        
        result = test_compute()
        return {"status": "healthy", "uhcr": "ok"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500

@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe"""
    try:
        # Check UHCR initialization
        profile = uhcr.detect()
        return {
            "status": "ready",
            "backend": profile.get_optimal_backend(),
            "workers": uhcr.get_worker_count()
        }
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}, 503

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return uhcr.metrics.export_prometheus()
```

### Logging Configuration

```python
import logging
import uhcr

def setup_container_logging():
    """Configure structured logging for containers"""
    
    logging.basicConfig(
        level=os.environ.get('UHCR_LOG_LEVEL', 'INFO'),
        format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s","worker":"%(worker_id)s"}',
        handlers=[logging.StreamHandler()]
    )
    
    # Configure UHCR logging
    uhcr.config.set('logging.structured', True)
    uhcr.config.set('logging.include_metrics', True)

setup_container_logging()
```

---

## Security Best Practices

### Secure Configuration

```python
# secure_config.py
import uhcr
import os
from cryptography.fernet import Fernet

class SecureUHCRConfig:
    def __init__(self):
        # Load encryption key from secret
        key = os.environ.get('UHCR_ENCRYPTION_KEY')
        self.cipher = Fernet(key.encode()) if key else None
    
    def decrypt_config(self, encrypted_value):
        """Decrypt sensitive configuration values"""
        if self.cipher:
            return self.cipher.decrypt(encrypted_value.encode()).decode()
        return encrypted_value
    
    def setup_secure_uhcr(self):
        """Configure UHCR with encrypted settings"""
        
        # Decrypt database credentials
        db_url = self.decrypt_config(
            os.environ.get('UHCR_DB_URL_ENCRYPTED')
        )
        
        uhcr.config.set('storage.database_url', db_url)
        uhcr.config.set('security.enable_tls', True)

# Usage in container
config = SecureUHCRConfig()
config.setup_secure_uhcr()
```

### Network Security

```yaml
# Network policies for Kubernetes
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: uhcr-network-policy
spec:
  podSelector:
    matchLabels:
      app: uhcr-worker
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: uhcr-coordinator
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

---

## Troubleshooting

### Common Container Issues

```python
# diagnostics.py
import uhcr
import psutil
import os

def container_diagnostics():
    """Diagnose UHCR issues in containers"""
    
    print("=== UHCR Container Diagnostics ===")
    
    # System info
    print(f"Python version: {sys.version}")
    print(f"UHCR version: {uhcr.__version__}")
    print(f"Container ID: {os.environ.get('HOSTNAME', 'unknown')}")
    
    # Resource usage
    memory = psutil.virtual_memory()
    print(f"Memory usage: {memory.percent}%")
    print(f"Available memory: {memory.available / (1024**3):.2f}GB")
    
    # UHCR status
    try:
        profile = uhcr.detect()
        print(f"UHCR backend: {profile.get_optimal_backend()}")
        print(f"Worker threads: {uhcr.get_worker_count()}")
    except Exception as e:
        print(f"UHCR initialization error: {e}")
    
    # Network connectivity
    if 'COORDINATOR_URL' in os.environ:
        import requests
        try:
            response = requests.get(f"{os.environ['COORDINATOR_URL']}/health")
            print(f"Coordinator status: {response.status_code}")
        except Exception as e:
            print(f"Coordinator unreachable: {e}")

if __name__ == "__main__":
    container_diagnostics()
```

### Performance Debugging

```bash
#!/bin/bash
# debug_container.sh - Container performance debugging

echo "=== Container Resource Limits ==="
cat /sys/fs/cgroup/memory/memory.limit_in_bytes
cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us

echo "=== UHCR Process Info ==="
ps aux | grep python
top -b -n 1 | grep python

echo "=== Network Connectivity ==="
netstat -tuln | grep LISTEN

echo "=== UHCR Logs ==="
tail -n 50 /var/log/uhcr/worker.log
```

---

## Examples

### Complete Container Application

```python
# main.py - Complete containerized UHCR application
import asyncio
import uhcr
from fastapi import FastAPI, BackgroundTasks
import uvicorn

app = FastAPI(title="UHCR Compute Service")

# Global UHCR setup
@app.on_event("startup")
async def startup():
    # Initialize UHCR for container environment
    uhcr.config.load_from_env()
    profile = uhcr.detect()
    
    print(f"UHCR initialized with {profile.cpu.cores} cores")

@app.post("/compute")
async def compute_endpoint(data: dict, background_tasks: BackgroundTasks):
    """Compute endpoint with UHCR JIT compilation"""
    
    @uhcr.jit(eager=True)
    def matrix_multiply(a, b):
        return uhcr.tensor(a).matmul(uhcr.tensor(b))
    
    # Background task for result processing
    background_tasks.add_task(log_computation, data)
    
    # Perform computation
    result = matrix_multiply(data['matrix_a'], data['matrix_b'])
    
    return {
        'result': result.to_numpy().tolist(),
        'shape': result.shape,
        'backend': uhcr.get_active_backend()
    }

async def log_computation(data):
    """Log computation for monitoring"""
    print(f"Processed computation: {data.get('id', 'unknown')}")

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080,
        workers=int(os.environ.get('UHCR_WORKERS', 1))
    )
```

This containerization guide provides comprehensive coverage of deploying UHCR applications in container environments, from basic Docker setups to advanced Kubernetes orchestration with security and monitoring best practices.

[Next: Plugins →](plugins){: .btn .btn-primary }
[Back to Guides →](guides){: .btn }
