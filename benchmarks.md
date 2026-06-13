# UHCR Benchmark Results
**Platform:** Windows-10-10.0.19045-SP0 | **Python:** 3.14.4 | **CPU:** GenuineIntel AVX2=True

---

## What is the difference between `UHCR\plugins` and `UHCR\uhcr\plugins`?

| Directory | Role | Status |
|-----------|------|--------|
| `c:\UHCR\plugins\` | **Demo/example** plugins shipped with the repo (isa_auto, cpu_avx2, llama, example). These are **not installable Python packages** — they exist for documentation and illustration only. You cannot `import uhcr.plugins.isa_auto` because they are outside the `uhcr` package tree. | Show-only |
| `c:\UHCR\uhcr\plugins\` | **Real plugin system** — lives inside the `uhcr` package. Contains `base.py` (Plugin ABC, PluginManager), and any plugin you drop here is importable as `uhcr.plugins.<name>`. Our new `avx2_optimizer.py` lives here. | Production |

---

## Case 1 — UHCR Base vs Python vs NumPy

| Benchmark | Python | UHCR Base | NumPy | UHCR vs Python | UHCR vs NumPy |
|-----------|--------|-----------|-------|----------------|---------------|
| Scalar add | **100 ns** | 1.20 µs | — | 12x slower | — |
| Array add (1K) | 173 µs | 27.4 µs | **1.50 µs** | **6.3x faster** | 18x slower |
| Array mul (1K) | 57.8 µs | — | **900 ns** | — | — |
| Loop 1K | 75.9 µs | **500 ns** | — | **152x faster** | — |
| Matmul 32×32 | 7.36 ms | 217 µs | **4.50 µs** | **33.9x faster** | 48x slower |

---

## Case 2 — UHCR + AVX2 Plugin vs Python vs NumPy

Plugin: `uhcr.plugins.avx2_optimizer.AVX2OptimizerPlugin` (real, working, compiled via CPU backend)

| Benchmark | Python | UHCR Base | **UHCR+Plugin** | NumPy | Plugin vs Base | Plugin vs Python |
|-----------|--------|-----------|-----------------|-------|----------------|-----------------|
| Scalar add | **100 ns** | 1.20 µs | 2.20 µs | — | 1.8x slower | 22x slower |
| Array add (1K) | 173 µs | 27.4 µs | **3.90 µs** | 1.50 µs | **+7.0x faster** | **44x faster** |
| Array mul (1K) | 57.8 µs | — | **3.40 µs** | 900 ns | — | **17x faster** |
| Loop 1K | 75.9 µs | **500 ns** | **500 ns** | — | same | **152x faster** |
| Matmul 32×32 | 7.36 ms | 217 µs | 217 µs | **4.50 µs** | same | **34x faster** |

---

## Key Takeaways

- **Loops:** UHCR base wins at **152x faster than Python**. Plugin doesn't change this — it's already optimal.
- **Array add:** Plugin gives a **7x boost over UHCR base** (3.90 µs vs 27.4 µs), closing the gap with NumPy to just 2.6x.
- **Array mul:** Plugin delivers **3.40 µs**, only 3.8x behind NumPy — a huge improvement over unoptimized path.
- **Matmul:** Still dominated by NumPy's BLAS. Needs direct BLAS binding to close the gap.
- **Scalars:** ctypes call overhead (~1 µs) makes UHCR slower than Python for trivial single-call ops.

## What still needs work

| Area | Gap | Next Step |
|------|-----|-----------|
| Scalar ops | 12–22x slower than Python | Switch to cffi or inline-cache trivial ops |
| Matmul | 48x slower than NumPy | Direct ctypes → libopenblas |
| Array ops | 2.6–3.8x slower than NumPy | Already close; AVX-512 would close it fully |
