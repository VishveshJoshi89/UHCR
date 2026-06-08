# Quick Start Guide

---

## Installation

Install UHCR using pip:

```bash
pip install uhcr
```

**Requirements:**
- Python 3.10 or higher
- Windows, Linux, or macOS
- (Optional) NVIDIA GPU with CUDA for GPU acceleration

---

## Your First Program

Create a file called `hello_uhcr.py`:

```python
import uhcr

# Detect hardware capabilities
profile = uhcr.detect()
print(f"Running on: {profile.cpu.brand}")
print(f"Features: {', '.join(profile.cpu.features[:5])}")

# Create a JIT-compiled function
@uhcr.jit(eager=True, verbose=True)
def add_and_multiply(a, b):
    return (a + b) * 2

# Call the function (compiles on first call)
result = add_and_multiply(10, 11)
print(f"Result: {result}")  # Output: 42
```

Run it:

```bash
python hello_uhcr.py
```

**Expected output:**
```
Running on: Intel(R) Core(TM) i7-10700K CPU @ 3.80GHz
Features: sse, sse2, sse3, ssse3, sse4_1
[uhcr.jit] Compiled 'add_and_multiply' for signature (('int',), ('int',))
Result: 42
```

---

## Working with Tensors

UHCR provides a high-level tensor API:

```python
import uhcr

# Create tensors
a = uhcr.tensor([[1.0, 2.0, 3.0],
                 [4.0, 5.0, 6.0]])

b = uhcr.tensor([[7.0, 8.0],
                 [9.0, 10.0],
                 [11.0, 12.0]])

# Matrix multiplication (automatically uses best backend)
c = a.matmul(b)

print(f"Shape: {c.shape}")
print(f"Result:\n{c.to_numpy()}")
```

**Output:**
```
Shape: (2, 2)
Result:
[[ 58.  64.]
 [139. 154.]]
```

---

## JIT Compilation Modes

### Lazy Compilation (Default)

Compiles after 3 calls (warmup period):

```python
@uhcr.jit
def compute(x, y):
    return x * y + x

compute(5, 3)   # Python execution
compute(7, 2)   # Python execution
compute(9, 4)   # Compiled! Native execution from now on
```

### Eager Compilation

Compiles on first call:

```python
@uhcr.jit(eager=True)
def compute(x, y):
    return x * y + x

compute(5, 3)   # Compiled immediately!
```

### Verbose Mode

See compilation messages:

```python
@uhcr.jit(eager=True, verbose=True)
def compute(x, y):
    return x * y + x

compute(5, 3)
# [uhcr.jit] Compiled 'compute' for signature (('int',), ('int',))
```

---

## Hardware Detection

Check what hardware UHCR detected:

```python
import uhcr

profile = uhcr.detect()

# CPU information
print(f"CPU: {profile.cpu.brand}")
print(f"Cores: {profile.cpu.cores}")
print(f"Threads: {profile.cpu.threads}")
print(f"Has AVX2: {profile.cpu.has_avx2}")
print(f"Has AVX512: {profile.cpu.has_avx512}")

# Memory information
print(f"\nRAM: {profile.memory.total_bytes / (1024**3):.1f} GB")
print(f"Type: {profile.memory.memory_type}")
print(f"Speed: {profile.memory.speed_mhz} MHz")

# GPU information
print(f"\nGPU: {profile.gpu.name}")
print(f"CUDA Available: {profile.gpu.cuda_available}")
if profile.gpu.cuda_available:
    print(f"CUDA Version: {profile.gpu.cuda_version}")

# Cache information
print(f"\nL1 Data Cache: {profile.cpu.cache_l1_data_kb} KB")
print(f"L2 Cache: {profile.cpu.cache_l2_kb} KB")
print(f"L3 Cache: {profile.cpu.cache_l3_kb} KB")
```

---

## Backend Selection

UHCR automatically selects the best backend:

```python
import uhcr

# The runtime picks the best backend automatically
profile = uhcr.detect()

if profile.gpu.cuda_available:
    print("Using CUDA backend for GPU acceleration")
elif profile.cpu.has_avx512:
    print("Using AVX512 backend")
elif profile.cpu.has_avx2:
    print("Using AVX2 backend")
else:
    print("Using generic CPU backend")
```

You can also check which backends are available:

```python
from uhcr.backends.backend_selector import get_available_backends

backends = get_available_backends(profile)
for backend in backends:
    print(f"{backend.name}: priority {backend.priority}")
```

---

## Performance Tips

### 1. Use Eager Compilation for Hot Paths

```python
@uhcr.jit(eager=True)  # Compile immediately
def critical_function(x, y):
    return x * y + x
```

### 2. Reuse Tensors

```python
# Good: Reuse tensor objects
a = uhcr.tensor([1.0, 2.0, 3.0])
for i in range(1000):
    result = a.matmul(a)

# Avoid: Creating new tensors in loops
for i in range(1000):
    a = uhcr.tensor([1.0, 2.0, 3.0])  # Slow!
    result = a.matmul(a)
```

### 3. Let UHCR Choose the Backend

Don't force a specific backend unless you have a good reason. UHCR's automatic selection is usually optimal.

### 4. Profile Your Code

Use Python's built-in profiling tools:

```python
import time
import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

# Warmup
compute(10, 20)

# Benchmark
start = time.perf_counter()
for _ in range(1000000):
    compute(10, 20)
end = time.perf_counter()

print(f"Time: {(end - start) * 1000:.2f} ms")
```

---

## Common Patterns

### Pattern 1: Batch Processing

```python
import uhcr

@uhcr.jit(eager=True)
def process_item(x):
    return x * 2 + 10

# Process a batch
data = [1, 2, 3, 4, 5]
results = [process_item(x) for x in data]
```

### Pattern 2: Matrix Operations

```python
import uhcr

# Create matrices
A = uhcr.tensor([[1.0, 2.0], [3.0, 4.0]])
B = uhcr.tensor([[5.0, 6.0], [7.0, 8.0]])

# Compute: C = A @ B + A
C = A.matmul(B) + A
```

### Pattern 3: Type-Specific Functions

```python
import uhcr

@uhcr.jit(eager=True)
def process_ints(a, b):
    return a + b

@uhcr.jit(eager=True)
def process_floats(a, b):
    return a + b

# Each gets compiled separately
result1 = process_ints(10, 20)      # int version
result2 = process_floats(10.5, 20.5)  # float version
```

---

## Next Steps

Now that you've got the basics, explore more advanced features:

- **[JIT Guide](jit-guide)** — Deep dive into JIT compilation
- **[API Reference](api-reference)** — Complete API documentation
- **[Features](features)** — Explore all UHCR capabilities
- **[Plugin Guide](plugin-guide)** — Extend UHCR with custom plugins
- **[Hardware Detection](hardware-reference)** — Detailed hardware detection reference

---

## Troubleshooting

### Import Error

```
ModuleNotFoundError: No module named 'uhcr'
```

**Solution:** Make sure UHCR is installed:
```bash
pip install uhcr
```

### Compilation Warnings

If you see warnings about unsupported operations, the function will fall back to Python execution. This is normal for complex functions.

### Performance Issues

If performance is slower than expected:
1. Check that JIT compilation is actually happening (use `verbose=True`)
2. Verify hardware detection: `uhcr.detect()`
3. Make sure you're not creating tensors in tight loops
4. Profile your code to find bottlenecks

---

## Getting Help

- **GitHub Issues:** [Report bugs or request features](https://github.com/VishveshJoshi89/UHCR/issues)
- **Documentation:** [Full documentation](https://vishveshjoshi89.github.io/UHCR/)
- **Contributing:** [Contribution guide](contributing)

[View on GitHub](https://github.com/VishveshJoshi89/UHCR){: .btn .btn-primary }
