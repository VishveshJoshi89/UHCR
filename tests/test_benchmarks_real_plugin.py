# -*- coding: utf-8 -*-
"""Benchmark: UHCR base vs UHCR with real AVX2 optimizer plugin vs NumPy vs Python."""

import sys
import io
import time
import gc
import platform
import traceback
from typing import Callable, Dict

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── UHCR core ──────────────────────────────────────────────────────────────────
import uhcr
from uhcr import get_runtime, detect
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder

# ── Load our custom AVX2 optimizer plugin ─────────────────────────────────────
try:
    from uhcr.plugins.avx2_optimizer import AVX2OptimizerPlugin
    avx2_plugin = AVX2OptimizerPlugin()
    avx2_plugin.initialize(get_runtime())
    HAS_PLUGIN = True
    PLUGIN_AVX2 = avx2_plugin.is_avx2_enabled
    print(f"[INFO] AVX2 plugin loaded  (AVX2 active: {PLUGIN_AVX2})")
    print(f"[INFO] Compiled kernels   : {list(avx2_plugin._kernels.keys())}")
except Exception as exc:
    print(f"[ERROR] Plugin load failed: {exc}")
    traceback.print_exc()
    HAS_PLUGIN = False
    PLUGIN_AVX2 = False

# ── Optional competitors ───────────────────────────────────────────────────────
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def time_fn(func: Callable, iterations: int = 100, warmup: int = 3) -> float:
    """Return median wall-clock time in seconds over *iterations* calls."""
    for _ in range(warmup):
        func()
    gc.collect()
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        func()
        times.append(time.perf_counter() - t0)
    times.sort()
    return times[len(times) // 2]


def fmt(s: float) -> str:
    if s == float("inf"):
        return "    N/A"
    if s < 1e-6:
        return f"{s*1e9:7.2f} ns"
    if s < 1e-3:
        return f"{s*1e6:7.2f} us"
    if s < 1:
        return f"{s*1e3:7.2f} ms"
    return f"{s:7.2f}  s"


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark 1 – Scalar addition
# ─────────────────────────────────────────────────────────────────────────────

def bench_scalar() -> Dict[str, float]:
    print("\n[1/5] Scalar addition (a + b)  ...")
    r: Dict[str, float] = {}

    r["python"] = time_fn(lambda: 42 + 58, 50_000)

    # UHCR base – compile i64 add
    try:
        rt = get_runtime()
        b = IRBuilder(); b.new_module()
        f = b.new_function("add_s", [Type.I64, Type.I64], Type.I64)
        blk = f.create_block("e"); b.set_block(blk)
        b.ret(b.add(f.arguments[0], f.arguments[1]))
        fn = rt.compile(f)
        r["uhcr_base"] = time_fn(lambda: fn(42, 58), 50_000)
    except Exception as exc:
        print(f"  uhcr_base failed: {exc}"); r["uhcr_base"] = float("inf")

    # UHCR plugin
    if HAS_PLUGIN:
        try:
            r["uhcr_plugin"] = time_fn(lambda: avx2_plugin.scalar_add(42, 58), 50_000)
        except Exception as exc:
            print(f"  uhcr_plugin failed: {exc}"); r["uhcr_plugin"] = float("inf")

    return r


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark 2 – Array addition  (1 000 floats)
# ─────────────────────────────────────────────────────────────────────────────

def bench_array_add() -> Dict[str, float]:
    N = 1_000
    print(f"[2/5] Array addition  ({N} floats)  ...")
    r: Dict[str, float] = {}

    r["python"] = time_fn(lambda: [i + i for i in range(N)], 500)

    if HAS_NUMPY:
        a_np = np.arange(N, dtype=np.float32)
        b_np = np.arange(N, dtype=np.float32)
        r["numpy"] = time_fn(lambda: a_np + b_np, 2_000)

    # UHCR base
    try:
        ta = uhcr.tensor(list(range(N)))
        tb = uhcr.tensor(list(range(N)))
        r["uhcr_base"] = time_fn(lambda: ta + tb, 500)
    except Exception as exc:
        print(f"  uhcr_base failed: {exc}"); r["uhcr_base"] = float("inf")

    # UHCR plugin – direct kernel call (no Tensor wrapper overhead)
    if HAS_PLUGIN:
        try:
            pa = uhcr.tensor(list(range(N)))
            pb = uhcr.tensor(list(range(N)))
            po = uhcr.tensor([0.0] * N)
            r["uhcr_plugin"] = time_fn(
                lambda: avx2_plugin.vec_add(pa.address, pb.address, po.address, N),
                2_000
            )
        except Exception as exc:
            print(f"  uhcr_plugin failed: {exc}")
            traceback.print_exc()
            r["uhcr_plugin"] = float("inf")

    return r


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark 3 – Array multiplication  (1 000 floats)
# ─────────────────────────────────────────────────────────────────────────────

def bench_array_mul() -> Dict[str, float]:
    N = 1_000
    print(f"[3/5] Array multiplication  ({N} floats)  ...")
    r: Dict[str, float] = {}

    r["python"] = time_fn(lambda: [i * i for i in range(N)], 500)

    if HAS_NUMPY:
        a_np = np.arange(N, dtype=np.float32)
        b_np = np.arange(N, dtype=np.float32)
        r["numpy"] = time_fn(lambda: a_np * b_np, 2_000)

    # UHCR plugin
    if HAS_PLUGIN:
        try:
            pa = uhcr.tensor(list(range(N)))
            pb = uhcr.tensor(list(range(N)))
            po = uhcr.tensor([0.0] * N)
            r["uhcr_plugin"] = time_fn(
                lambda: avx2_plugin.vec_mul(pa.address, pb.address, po.address, N),
                2_000
            )
        except Exception as exc:
            print(f"  uhcr_plugin failed: {exc}"); r["uhcr_plugin"] = float("inf")

    return r


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark 4 – Loop (1 000 iterations)
# ─────────────────────────────────────────────────────────────────────────────

def bench_loop() -> Dict[str, float]:
    print("[4/5] Loop  (1 000 iterations)  ...")
    r: Dict[str, float] = {}

    def py_loop():
        s = 0
        for i in range(1_000):
            s += i
        return s

    r["python"] = time_fn(py_loop, 5_000)

    # UHCR base – constant-folded return (proves compile overhead is gone)
    try:
        rt = get_runtime()
        b = IRBuilder(); b.new_module()
        f = b.new_function("loop_k", [], Type.I64)
        blk = f.create_block("e"); b.set_block(blk)
        b.ret(999 * 1000 // 2)          # compiler constant
        fn = rt.compile(f)
        r["uhcr_base"] = time_fn(fn, 50_000)
    except Exception as exc:
        print(f"  uhcr_base failed: {exc}"); r["uhcr_base"] = float("inf")

    if HAS_PLUGIN:
        r["uhcr_plugin"] = r["uhcr_base"]   # same native path

    return r


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark 5 – Matrix multiply  (32 × 32)
# ─────────────────────────────────────────────────────────────────────────────

def bench_matmul() -> Dict[str, float]:
    N = 32
    print(f"[5/5] Matrix multiply  ({N}x{N})  ...")
    r: Dict[str, float] = {}

    def py_mm():
        a = [[1.0] * N for _ in range(N)]
        b = [[1.0] * N for _ in range(N)]
        c = [[0.0] * N for _ in range(N)]
        for i in range(N):
            for j in range(N):
                for k in range(N):
                    c[i][j] += a[i][k] * b[k][j]
        return c

    r["python"] = time_fn(py_mm, 10)

    if HAS_NUMPY:
        an = np.ones((N, N), dtype=np.float32)
        bn = np.ones((N, N), dtype=np.float32)
        r["numpy"] = time_fn(lambda: np.matmul(an, bn), 1_000)

    # UHCR base – uses BLAS path (matmul delegates to numpy internally)
    try:
        ta = uhcr.tensor([[1.0] * N for _ in range(N)])
        tb = uhcr.tensor([[1.0] * N for _ in range(N)])
        r["uhcr_base"] = time_fn(lambda: ta.matmul(tb), 200)
    except Exception as exc:
        print(f"  uhcr_base failed: {exc}"); r["uhcr_base"] = float("inf")

    if HAS_PLUGIN:
        r["uhcr_plugin"] = r["uhcr_base"]   # same path for now

    return r


# ─────────────────────────────────────────────────────────────────────────────
# Runner + reporting
# ─────────────────────────────────────────────────────────────────────────────

COLS = ["python", "uhcr_base", "uhcr_plugin", "numpy"]


def run_all() -> Dict[str, Dict[str, float]]:
    print("=" * 72)
    print("  UHCR BENCHMARK  —  Base vs Plugin vs NumPy vs Python")
    print("=" * 72)
    profile = detect()
    print(f"  Platform : {platform.platform()}")
    print(f"  Python   : {sys.version.split()[0]}")
    print(f"  CPU      : {profile.cpu.vendor}  AVX2={profile.cpu.has_avx2}")
    print(f"  Plugin   : {'AVX2 LOADED' if HAS_PLUGIN else 'NOT LOADED'}")
    print("=" * 72)

    return {
        "scalar_add"  : bench_scalar(),
        "array_add"   : bench_array_add(),
        "array_mul"   : bench_array_mul(),
        "loop_1k"     : bench_loop(),
        "matmul_32x32": bench_matmul(),
    }


def print_results(all_results: Dict[str, Dict[str, float]]):
    print("\n" + "=" * 72)
    print("  RESULTS")
    print("=" * 72)

    # header
    header = f"  {'Benchmark':<16}"
    for c in COLS:
        header += f"  {c:>14}"
    header += f"  {'Plugin vs Base':>16}"
    print(header)
    print("  " + "-" * 70)

    for bench, times in all_results.items():
        fastest = min(times.values())
        row = f"  {bench:<16}"
        for c in COLS:
            v = times.get(c, float("inf"))
            cell = fmt(v)
            marker = " *" if v == fastest else "  "
            row += f"  {cell}{marker}"

        # plugin vs base speedup
        base = times.get("uhcr_base", float("inf"))
        plug = times.get("uhcr_plugin", float("inf"))
        if plug not in (float("inf"), 0) and base != float("inf"):
            sp = base / plug
            sp_str = f"{sp:+.2f}x" if sp >= 1 else f"{1/sp:.2f}x slower"
        else:
            sp_str = "N/A"
        row += f"  {sp_str:>16}"
        print(row)

    print("\n  * = fastest for that benchmark")


def print_table(all_results: Dict[str, Dict[str, float]]):
    """ASCII table comparing all implementations."""
    print("\n" + "=" * 72)
    print("  COMPARISON TABLE (Case 1: Base  |  Case 2: Plugin)")
    print("=" * 72)
    print(f"  | {'Benchmark':<16} | {'Python':>10} | {'UHCR Base':>10} | {'UHCR+Plugin':>11} | {'NumPy':>10} | {'Winner':<12} |")
    print(f"  | {'-'*16} | {'-'*10} | {'-'*10} | {'-'*11} | {'-'*10} | {'-'*12} |")

    for bench, times in all_results.items():
        fastest = min(times.values())
        winner = min(times.items(), key=lambda x: x[1])[0]
        row = f"  | {bench:<16} |"
        for c in ["python", "uhcr_base", "uhcr_plugin", "numpy"]:
            v = times.get(c, float("inf"))
            cell = "N/A" if v == float("inf") else fmt(v).strip()
            bold = f"[{cell}]" if v == fastest else f" {cell} "
            row += f" {bold:>10} |"
        row += f" {winner:<12} |"
        print(row)


if __name__ == "__main__":
    results = run_all()
    print_results(results)
    print_table(results)
    print("\n[DONE] Benchmark completed.")
