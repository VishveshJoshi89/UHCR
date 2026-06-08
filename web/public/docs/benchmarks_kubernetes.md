

# UHCR Kubernetes Benchmarks

This page follows the same benchmark style as the Docker benchmark page, but runs the workload inside Docker Desktop Kubernetes on this device.

The final benchmark was executed as a Kubernetes `Job` on the `docker-desktop` context. The pod completed successfully and saved its result JSON to `/tmp/k8s_benchmark_uhcr-benchmark-gfnnz.json` inside the pod.

## Executive Summary

Docker Desktop Kubernetes is working on this device and UHCR benchmarks now run inside a real Kubernetes pod.

The strongest Kubernetes result is matrix multiplication:

- UHCR + Plugin: **5.20x faster** than Python
- UHCR built-in backend: **4.06x faster** than Python

String concatenation also improved with the built-in backend at **1.64x faster**. Loop and list workloads were mixed, which matches the Docker benchmark pattern where UHCR is strongest on compute-heavy operations.

## Environment

| Item | Value |
|------|-------|
| Host | Windows 10 10.0.19045 |
| Docker Desktop | Running |
| Docker engine | 29.5.2 |
| Kubernetes mode | Docker Desktop `kind` |
| Kubernetes version | 1.34.3 |
| kubectl context | `docker-desktop` |
| Node | `desktop-control-plane` |
| Pod | `uhcr-benchmark-gfnnz` |
| Pod OS | Linux 6.6.114.1 WSL2 |
| Pod Python | 3.11.15 |
| Architecture | x86_64 |
| Benchmark script | `benchmark_k8s.py` |

## How The Test Was Run

Docker Desktop Kubernetes uses a kind/containerd runtime. The local Docker image `uhcr-benchmark:latest` built successfully, but the pod could not see it with `imagePullPolicy: Never`, so the benchmark job now uses a Kubernetes-native source bundle:

1. Package the repository into `uhcr-src.tar.gz`.
2. Create a ConfigMap named `uhcr-source-bundle`.
3. Run `k8s-deployment.yaml` as a Kubernetes `Job`.
4. The pod unpacks the source, installs NumPy and UHCR, then runs `benchmark_k8s.py`.

Commands used:

```powershell
tar --exclude=.git --exclude=.vs --exclude=uhcr.egg-info --exclude=uhcr-src.tar.gz -czf uhcr-src.tar.gz .
kubectl create configmap uhcr-source-bundle --from-file=uhcr-src.tar.gz
kubectl apply -f k8s-deployment.yaml
kubectl wait --for=condition=complete job/uhcr-benchmark --timeout=300s
kubectl logs job/uhcr-benchmark
```

## Kubernetes Job Configuration

The benchmark runs as a one-shot `Job`, which is the correct Kubernetes workload type for a command that exits after one benchmark run.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: uhcr-benchmark
spec:
  backoffLimit: 0
  template:
    spec:
      containers:
      - name: uhcr-benchmark
        image: python:3.11-slim
        workingDir: /workspace
        command: ["/bin/sh", "-c"]
        args:
        - mkdir -p /workspace && tar -xzf /src/uhcr-src.tar.gz -C /workspace && cd /workspace && python -m pip install --no-cache-dir numpy && python -m pip install --no-cache-dir -e . && python benchmark_k8s.py
        resources:
          requests:
            cpu: "1"
            memory: "2Gi"
          limits:
            cpu: "2"
            memory: "4Gi"
      restartPolicy: Never
```

## Benchmark Results

### Workloads

| Workload | Size |
|----------|------|
| String concatenation | 5 million iterations |
| Loop sum | 10 million integers |
| Matrix multiplication | 500x500 |
| List comprehension | 10 million elements |

### Kubernetes Pod Results

| Workload | Python (ms) | UHCR + Plugin (ms) | UHCR (ms) | Plugin Speedup | UHCR Speedup |
|----------|-------------|--------------------|-----------|----------------|--------------|
| String concat (5M) | 4017.90 | 3096.40 | 2450.06 | 1.30x | 1.64x |
| Loop sum (10M) | 336.22 | 302.29 | 371.01 | 1.11x | 0.91x |
| Matrix (500x500) | 51.78 | 9.97 | 12.77 | 5.20x | 4.06x |
| List comp (10M) | 1885.90 | 1865.11 | 2110.62 | 1.01x | 0.89x |

## Comparison With Docker Benchmark

| Workload | Docker UHCR Speedup | Kubernetes UHCR Speedup | Notes |
|----------|---------------------|-------------------------|-------|
| String concat (5M) | 1.77x | 1.64x | Docker slightly ahead |
| Loop sum (10M) | 1.10x | 0.91x | Kubernetes built-in backend slower here |
| Matrix (500x500) | 3.48x | 4.06x | Kubernetes stronger for built-in matrix backend |
| List comp (10M) | 0.94x | 0.89x | Both environments slower than Python |

## Analysis

### Matrix Multiplication

Matrix multiplication is the strongest Kubernetes result:

- Python: 51.78ms
- UHCR + Plugin: 9.97ms, or 5.20x faster
- UHCR built-in backend: 12.77ms, or 4.06x faster

This confirms the same core finding from the Docker benchmark: UHCR performs best on compute-heavy numeric workloads.

### String Concatenation

String concatenation also improved:

- UHCR + Plugin: 1.30x faster
- UHCR built-in backend: 1.64x faster

The built-in backend performed better than the plugin for this workload.

### Loop And List Workloads

Loop and list results were mixed:

- Loop sum was faster with the plugin, but slower with the built-in backend.
- List comprehension was almost neutral with the plugin and slower with the built-in backend.

These workloads are less compute-heavy and more sensitive to Python runtime behavior, memory pressure, and scheduler noise.

## Notes From The Run

- Docker Desktop Kubernetes had to be enabled before the test. Its status changed to `running` after cluster reset/provisioning.
- The first `Deployment` manifest failed because deployments do not support `restartPolicy: Never`; the benchmark manifest was corrected to use a `Job`.
- The local image path failed with `ErrImageNeverPull`, so the final benchmark uses a ConfigMap source bundle with `python:3.11-slim`.
- The script originally misdetected Docker Desktop Kubernetes as non-Kubernetes because kind/containerd pods do not always expose `/.dockerenv`; detection was updated to use Kubernetes service account/env metadata.
- The pod printed `/bin/sh: 1: lspci: not found`; this did not stop the benchmark.

## Recommendations

Use Docker Desktop Kubernetes for UHCR when:

1. You want to verify Kubernetes manifests locally before production.
2. You need repeatable pod-level benchmark behavior.
3. You want Kubernetes resource limits around UHCR workloads.
4. You are testing batch-style jobs that should run once and exit.

Use Docker or host execution when:

1. You need the fastest local development loop.
2. You only need a single benchmark run.
3. You do not need Kubernetes scheduling, pod metadata, or resource limits.

## Conclusion

UHCR now has a real Docker Desktop Kubernetes benchmark path on this device. The Kubernetes pod results show strong acceleration for matrix multiplication and useful acceleration for string concatenation, while scalar loop and list workloads remain mixed.

For production-style UHCR workloads, Kubernetes is most valuable when paired with compute-heavy tasks and batch/job orchestration.
