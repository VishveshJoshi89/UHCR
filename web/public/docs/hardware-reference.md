# Hardware Detection Reference

> RAM speed/type and CPU cache line size/associativity fields are stable as of this release.

## Overview

UHCR's hardware detection system probes the host machine at runtime to build a complete `HardwareProfile`. This profile drives backend selection, SIMD dispatch, memory alignment, and cache-aware optimization decisions throughout the compiler and runtime.

Detection runs automatically on first call to `uhcr.detect()` and the result is cached for the lifetime of the process. The system covers:

- **CPU** — vendor, brand, core/thread topology, instruction set extensions, and cache hierarchy
- **Memory** — total/available RAM, NUMA topology, page size, speed, and DDR generation
- **GPU** — name, vendor, VRAM, and accelerated runtime availability (CUDA, Vulkan, ROCm, Metal)

All detection gracefully degrades: if a subsystem cannot be queried (permissions, unsupported platform), sensible defaults are returned rather than raising exceptions.

---

## MemoryCapabilities

Detected by `uhcr.hardware.memory_detect.detect_memory()`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `total_bytes` | `int` | `0` | Total physical RAM in bytes |
| `available_bytes` | `int` | `0` | Available (free) RAM in bytes |
| `numa_nodes` | `int` | `1` | Number of NUMA nodes |
| `page_size` | `int` | `4096` | OS page size in bytes |
| `speed_mhz` | `int` | `0` | RAM clock speed in MHz |
| `memory_type` | `str` | `"Unknown"` | DDR generation: DDR3, DDR4, DDR5, or Unknown |



If speed or type cannot be determined, the fields return `0` and `"Unknown"` respectively.

---

## CPUCapabilities

Detected by `uhcr.hardware.cpuid.detect_cpu()` with cache topology populated from `uhcr.hardware.cache_detect.detect_cache()`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vendor` | `str` | `"Unknown"` | CPU vendor string (e.g. "GenuineIntel", "AuthenticAMD") |
| `brand` | `str` | `"Unknown"` | Full CPU brand string |
| `cores` | `int` | `1` | Physical core count |
| `threads` | `int` | `1` | Logical thread count (includes SMT/HyperThreading) |
| `features` | `List[str]` | `[]` | Detected instruction set extensions (sse, avx2, avx512f, etc.) |
| `cache_l1_data_kb` | `int` | `0` | L1 data cache size in KB |
| `cache_l1_inst_kb` | `int` | `0` | L1 instruction cache size in KB |
| `cache_l2_kb` | `int` | `0` | L2 cache size in KB |
| `cache_l3_kb` | `int` | `0` | L3 cache size in KB |
| `cache_l1_line_size` | `int` | `0` | L1 cache line size in bytes |
| `cache_l1_associativity` | `int` | `0` | L1 set associativity (number of ways) |
| `cache_l2_line_size` | `int` | `0` | L2 cache line size in bytes |
| `cache_l2_associativity` | `int` | `0` | L2 set associativity (number of ways) |
| `cache_l3_line_size` | `int` | `0` | L3 cache line size in bytes |
| `cache_l3_associativity` | `int` | `0` | L3 set associativity (number of ways) |

### Feature helper properties

| Property | Returns `True` when |
|----------|---------------------|
| `has_sse` | `"sse"` in features |
| `has_avx` | `"avx"` in features |
| `has_avx2` | `"avx2"` in features |
| `has_avx512` | any `"avx512*"` in features |
| `has_fma` | `"fma"` in features |

### Cache detection details

On x86_64 platforms, cache topology is detected via CPUID leaf 4 (Deterministic Cache Parameters). Each subleaf describes one cache level, providing:

- **line_size_bytes** — extracted from `EBX[11:0] + 1`
- **associativity** — extracted from `(EBX >> 22) & 0x3FF + 1` (number of ways)
- **sets** — extracted from `ECX + 1`
- **size** — computed as `ways × partitions × line_size × sets`


---

## GPUCapabilities

Detected by `uhcr.hardware.gpu_detect.detect_gpu()`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `"Unknown"` | GPU model name |
| `vram_bytes` | `int` | `0` | Video RAM in bytes |
| `driver_version` | `str` | `"Unknown"` | GPU driver version string |
| `cuda_available` | `bool` | `False` | NVIDIA CUDA runtime detected |
| `cuda_version` | `str` | `"Unknown"` | CUDA driver version (e.g. "12.2") |
| `vulkan_available` | `bool` | `False` | Vulkan runtime detected |

---

## Code Examples

### Basic hardware detection

```python
import uhcr

# Detect hardware (result is cached after first call)
profile = uhcr.detect()

# Access CPU information
print(f"CPU: {profile.cpu.brand}")
print(f"Cores: {profile.cpu.cores}, Threads: {profile.cpu.threads}")
print(f"Features: {', '.join(profile.cpu.features)}")

# Access cache topology
print(f"L1 Data: {profile.cpu.cache_l1_data_kb} KB, "
      f"line={profile.cpu.cache_l1_line_size}B, "
      f"{profile.cpu.cache_l1_associativity}-way")
print(f"L2: {profile.cpu.cache_l2_kb} KB, "
      f"line={profile.cpu.cache_l2_line_size}B, "
      f"{profile.cpu.cache_l2_associativity}-way")
print(f"L3: {profile.cpu.cache_l3_kb} KB, "
      f"line={profile.cpu.cache_l3_line_size}B, "
      f"{profile.cpu.cache_l3_associativity}-way")

# Access memory information
print(f"RAM: {profile.memory.total_bytes / (1024**3):.1f} GB")
print(f"Speed: {profile.memory.speed_mhz} MHz")
print(f"Type: {profile.memory.memory_type}")

# Access GPU information
print(f"GPU: {profile.gpu.name} ({profile.gpu.vendor})")
print(f"CUDA: {profile.gpu.cuda_available}")
```

### Fingerprint and JSON serialization

```python
import uhcr
import json

profile = uhcr.detect()

# Get a capability fingerprint for backend targeting
fingerprint = profile.get_fingerprint()
print(f"Fingerprint: {fingerprint}")
# Example output: "Windows-AMD64-avx2-cuda_12.2+vulkan"

# Serialize to JSON (includes all RAM and cache fields)
json_str = profile.to_json()
print(json_str)

# Parse back for programmatic access
data = json.loads(json_str)
print(f"RAM speed: {data['memory']['speed_mhz']} MHz")
print(f"L2 line size: {data['cpu']['cache_l2_line_size']} bytes")
print(f"L2 associativity: {data['cpu']['cache_l2_associativity']}-way")
```

### Formatted table output

```python
import uhcr

profile = uhcr.detect()

# Print a formatted table (same output as `uhcr hw` CLI command)
print(profile.format_table())
```

---

## Notes

- The `speed_mhz`, `memory_type`, `cache_l1_line_size`, `cache_l1_associativity`, `cache_l2_line_size`, `cache_l2_associativity`, `cache_l3_line_size`, and `cache_l3_associativity` fields are new in v3.0.0.
- RAM speed and type detection may require elevated privileges on some platforms (e.g. `dmidecode` on Linux typically needs root).
- Cache detection uses CPUID leaf 4 on x86_64 and returns conservative fallback values on other architectures.
- All detection functions are designed to never raise exceptions to user code — failures result in default values.
