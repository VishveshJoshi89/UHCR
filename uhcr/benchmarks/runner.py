"""UHCR Benchmark Suite — measures performance across backends.

Run: python -m uhcr.benchmarks.runner to execute all benchmarks and print results and for developers, use the individual benchmark modules in uhcr.benchmarks to run specific tests and analyze performance.
"""

import ctypes
import time
import platform
from typing import Callable, List, Tuple

import uhcr
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder
from uhcr.runtime.memory_manager import AlignedBuffer


def _time_fn(fn: Callable, args: tuple, warmup: int = 3, iterations: int = 100) -> float:
    """Time a function call, returning median time in microseconds."""
    # Warmup
    for _ in range(warmup):
        fn(*args)

    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn(*args)
        end = time.perf_counter_ns()
        times.append((end - start) / 1000.0)  # ns → μs

    times.sort()
    return times[len(times) // 2]  # median


def benchmark_scalar_add(sizes: List[int] = None) -> List[dict]:
    """Benchmark scalar integer addition (native JIT vs Python)."""
    if sizes is None:
        sizes = [1]

    results = []

    # Build native function
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("bench_add", [Type.I64, Type.I64], Type.I64)
    entry = func.create_block("entry")
    builder.set_block(entry)
    builder.ret(builder.add(func.arguments[0], func.arguments[1]))

    rt = uhcr.get_runtime()
    native_fn = rt.compile(func)

    # Python baseline
    def python_add(a, b):
        return a + b

    for _ in sizes:
        native_time = _time_fn(native_fn, (42, 58))
        python_time = _time_fn(python_add, (42, 58))
        speedup = python_time / native_time if native_time > 0 else 0

        results.append({
            "benchmark": "scalar_add",
            "native_us": round(native_time, 3),
            "python_us": round(python_time, 3),
            "speedup": round(speedup, 2),
        })

    return results


def benchmark_vector_add(sizes: List[int] = None) -> List[dict]:
    """Benchmark vector addition at different sizes."""
    if sizes is None:
        sizes = [8, 64, 256, 1024, 4096]

    results = []
    profile = uhcr.detect()

    for n in sizes:
        # Allocate aligned buffers
        byte_size = n * 4  # float32
        buf_a = AlignedBuffer(byte_size, alignment=64)
        buf_b = AlignedBuffer(byte_size, alignment=64)
        buf_c = AlignedBuffer(byte_size, alignment=64)

        arr_a = buf_a.as_ctypes_array(ctypes.c_float)
        arr_b = buf_b.as_ctypes_array(ctypes.c_float)
        for i in range(n):
            arr_a[i] = float(i)
            arr_b[i] = float(i * 2)

        # Python baseline
        def python_vadd():
            for i in range(n):
                pass  # Just loop overhead

        python_time = _time_fn(python_vadd, (), iterations=50)

        # Native via tensor API
        a_tensor = uhcr.tensor([float(i) for i in range(n)])
        b_tensor = uhcr.tensor([float(i * 2) for i in range(n)])

        def native_vadd():
            return a_tensor + b_tensor

        native_time = _time_fn(native_vadd, (), warmup=2, iterations=20)

        speedup = python_time / native_time if native_time > 0 else 0

        results.append({
            "benchmark": "vector_add",
            "size": n,
            "native_us": round(native_time, 1),
            "python_loop_us": round(python_time, 1),
            "backend": "auto",
        })

        buf_a.free()
        buf_b.free()
        buf_c.free()

    return results


def benchmark_matmul(sizes: List[int] = None) -> List[dict]:
    """Benchmark matrix multiplication at different sizes."""
    if sizes is None:
        sizes = [2, 4, 8, 16, 32]

    results = []

    for n in sizes:
        # Create random-ish matrices
        data_a = [[float((i * n + j) % 17) for j in range(n)] for i in range(n)]
        data_b = [[float((i * n + j) % 13) for j in range(n)] for i in range(n)]

        a = uhcr.tensor(data_a)
        b = uhcr.tensor(data_b)

        # Python baseline
        def python_matmul():
            result = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    s = 0.0
                    for k in range(n):
                        s += data_a[i][k] * data_b[k][j]
                    result[i][j] = s
            return result

        iters = max(5, 100 // (n * n))
        python_time = _time_fn(python_matmul, (), warmup=1, iterations=iters)

        def native_matmul():
            return a.matmul(b)

        native_time = _time_fn(native_matmul, (), warmup=2, iterations=iters)
        speedup = python_time / native_time if native_time > 0 else 0

        results.append({
            "benchmark": "matmul",
            "size": f"{n}x{n}",
            "native_us": round(native_time, 1),
            "python_us": round(python_time, 1),
            "speedup": round(speedup, 2),
        })

    return results


def benchmark_optimization_passes() -> List[dict]:
    """Benchmark the effect of optimization passes on compilation."""
    from uhcr.compiler.passes import run_default_passes

    results = []

    # Build a function with optimizable patterns
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("opt_test", [Type.I64, Type.I64], Type.I64)
    entry = func.create_block("entry")
    builder.set_block(entry)

    # Lots of constant folding opportunities
    c1 = builder.add(10, 20)  # folds to 30
    c2 = builder.mul(c1, 2)   # folds to 60
    x = builder.add(func.arguments[0], func.arguments[1])
    y = builder.mul(x, 1)     # strength reduces to x
    z = builder.add(y, 0)     # strength reduces to y (= x)
    w = builder.add(z, c2)    # add x, 60
    builder.ret(w)

    before_count = sum(len(b.instructions) for b in func.blocks)

    start = time.perf_counter_ns()
    func = run_default_passes(func)
    opt_time = (time.perf_counter_ns() - start) / 1000.0

    after_count = sum(len(b.instructions) for b in func.blocks)

    results.append({
        "benchmark": "optimization_passes",
        "before_instructions": before_count,
        "after_instructions": after_count,
        "eliminated": before_count - after_count,
        "optimization_time_us": round(opt_time, 1),
    })

    return results


def run_all():
    """Run all benchmarks and print results."""
    print("=" * 70)
    print("  UHCR BENCHMARK SUITE")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print(f"  Python: {platform.python_version()}")
    profile = uhcr.detect()
    print(f"  CPU: {profile.cpu.brand}")
    print(f"  Backend: {profile.get_fingerprint()}")
    print("=" * 70)
    print()

    # Scalar
    print("--- Scalar Addition ---")
    for r in benchmark_scalar_add():
        print(f"  Native: {r['native_us']:.3f} μs | Python: {r['python_us']:.3f} μs | Speedup: {r['speedup']}x")
    print()

    # Vector
    print("--- Vector Addition ---")
    for r in benchmark_vector_add():
        print(f"  Size {r['size']:>5}: {r['native_us']:>8.1f} μs (backend: {r['backend']})")
    print()

    # Matmul
    print("--- Matrix Multiplication ---")
    for r in benchmark_matmul():
        print(f"  {r['size']:>5}: Native {r['native_us']:>8.1f} μs | Python {r['python_us']:>8.1f} μs | Speedup: {r['speedup']}x")
    print()

    # Optimization
    print("--- Optimization Passes ---")
    for r in benchmark_optimization_passes():
        print(f"  Instructions: {r['before_instructions']} → {r['after_instructions']} ({r['eliminated']} eliminated)")
        print(f"  Optimization time: {r['optimization_time_us']:.1f} μs")
    print()

    print("=" * 70)
    print("  BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_all()
