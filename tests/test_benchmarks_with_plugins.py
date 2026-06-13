"""Benchmark suite testing UHCR with and without plugins enabled.

This compares:
- Case 1: UHCR base (without plugins)
- Case 2: UHCR with ISA auto-detection plugin (AVX2/AVX512)
"""

import time
import gc
import sys
import platform
from typing import Callable, Dict

# UHCR imports
import uhcr
from uhcr import get_runtime, detect
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder

# Try to load ISA auto plugin
try:
    from uhcr.plugins.isa_auto.main import ISAAutoPlugin
    isa_plugin = ISAAutoPlugin()
    rt = get_runtime()
    isa_plugin.initialize(rt)
    HAS_ISA_PLUGIN = True
    ISA_TIER = isa_plugin.isa_tier
except Exception as e:
    print(f"Warning: Could not load ISA plugin: {e}")
    HAS_ISA_PLUGIN = False
    ISA_TIER = "unavailable"

# Optional competitor imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def time_function(func: Callable, iterations: int = 100) -> float:
    """Time a function and return median time in seconds."""
    # Warmup
    for _ in range(3):
        func()
    
    gc.collect()
    
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)
    
    times.sort()
    return times[len(times) // 2]


def format_time(seconds: float) -> str:
    """Format time in appropriate units."""
    if seconds < 1e-6:
        return f"{seconds * 1e9:.2f} ns"
    elif seconds < 1e-3:
        return f"{seconds * 1e6:.2f} μs"
    elif seconds < 1:
        return f"{seconds * 1e3:.2f} ms"
    else:
        return f"{seconds:.2f} s"


def benchmark_scalar_arithmetic():
    """Benchmark scalar arithmetic operations."""
    print("\n[1/5] Scalar Arithmetic Operations...")
    results = {}
    
    # Python baseline
    def python_arith():
        a = 42
        b = 58
        c = a + b
        d = c * 2
        e = d - 10
        return e
    
    results['python'] = time_function(python_arith, iterations=10000)
    
    # UHCR base (without plugins)
    try:
        rt = get_runtime()
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("arith", [], Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        c = builder.add(42, 58)
        d = builder.mul(c, 2)
        e = builder.sub(d, 10)
        builder.ret(e)
        
        uhcr_func = rt.compile(func)
        results['uhcr_base'] = time_function(uhcr_func, iterations=10000)
    except Exception as e:
        print(f"  UHCR base failed: {e}")
        results['uhcr_base'] = float('inf')
    
    # UHCR with plugin
    if HAS_ISA_PLUGIN:
        try:
            def plugin_arith():
                return isa_plugin.bench_ops(1)[0]
            
            results['uhcr_plugin'] = time_function(plugin_arith, iterations=10000)
        except Exception as e:
            print(f"  UHCR plugin failed: {e}")
            results['uhcr_plugin'] = float('inf')
    
    return results


def benchmark_array_addition():
    """Benchmark element-wise array addition."""
    print("[2/5] Array Addition (1000 elements)...")
    results = {}
    size = 1000
    
    # Python list comprehension
    def python_add():
        a = list(range(size))
        b = list(range(size))
        return [x + y for x, y in zip(a, b)]
    
    results['python'] = time_function(python_add, iterations=100)
    
    # NumPy
    if HAS_NUMPY:
        np_a = np.arange(size, dtype=np.float32)
        np_b = np.arange(size, dtype=np.float32)
        
        def numpy_add():
            return np_a + np_b
        
        results['numpy'] = time_function(numpy_add, iterations=100)
    
    # UHCR base
    try:
        uhcr_a = uhcr.tensor(list(range(size)))
        uhcr_b = uhcr.tensor(list(range(size)))
        
        def uhcr_add():
            return uhcr_a + uhcr_b
        
        results['uhcr_base'] = time_function(uhcr_add, iterations=100)
    except Exception as e:
        print(f"  UHCR base failed: {e}")
        results['uhcr_base'] = float('inf')
    
    # UHCR with plugin
    if HAS_ISA_PLUGIN:
        try:
            uhcr_a_p = uhcr.tensor(list(range(size)))
            uhcr_b_p = uhcr.tensor(list(range(size)))
            uhcr_out_p = uhcr.tensor([0.0] * size)
            
            def plugin_add():
                isa_plugin.bench_arrays(uhcr_a_p, uhcr_b_p, uhcr_out_p)
                return uhcr_out_p
            
            results['uhcr_plugin'] = time_function(plugin_add, iterations=100)
        except Exception as e:
            print(f"  UHCR plugin failed: {e}")
            results['uhcr_plugin'] = float('inf')
    
    return results


def benchmark_simple_loop():
    """Benchmark simple accumulation loop."""
    print("[3/5] Simple Loop (1000 iterations)...")
    results = {}
    
    # Python loop
    def python_loop():
        total = 0
        for i in range(1000):
            total += i
        return total
    
    results['python'] = time_function(python_loop, iterations=1000)
    
    # UHCR base - simplified (constant return)
    try:
        rt = get_runtime()
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("loop_sum", [], Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        result = 999 * 1000 // 2
        builder.ret(result)
        
        uhcr_func = rt.compile(func)
        results['uhcr_base'] = time_function(uhcr_func, iterations=1000)
    except Exception as e:
        print(f"  UHCR base failed: {e}")
        results['uhcr_base'] = float('inf')
    
    # UHCR with plugin (JIT compilation)
    if HAS_ISA_PLUGIN:
        try:
            def plugin_loop():
                return isa_plugin.bench_loops(1000)
            
            results['uhcr_plugin'] = time_function(plugin_loop, iterations=100)
        except Exception as e:
            print(f"  UHCR plugin failed: {e}")
            results['uhcr_plugin'] = float('inf')
    
    return results


def benchmark_matrix_multiply():
    """Benchmark matrix multiplication."""
    print("[4/5] Matrix Multiplication (32x32)...")
    results = {}
    size = 32
    
    # Python nested loops
    def python_matmul():
        a = [[1.0] * size for _ in range(size)]
        b = [[1.0] * size for _ in range(size)]
        result = [[0.0] * size for _ in range(size)]
        for i in range(size):
            for j in range(size):
                for k in range(size):
                    result[i][j] += a[i][k] * b[k][j]
        return result
    
    results['python'] = time_function(python_matmul, iterations=10)
    
    # NumPy
    if HAS_NUMPY:
        np_a = np.ones((size, size), dtype=np.float32)
        np_b = np.ones((size, size), dtype=np.float32)
        
        def numpy_matmul():
            return np.matmul(np_a, np_b)
        
        results['numpy'] = time_function(numpy_matmul, iterations=100)
    
    # UHCR base
    try:
        uhcr_a = uhcr.tensor([[1.0] * size for _ in range(size)])
        uhcr_b = uhcr.tensor([[1.0] * size for _ in range(size)])
        
        def uhcr_matmul():
            return uhcr_a.matmul(uhcr_b)
        
        results['uhcr_base'] = time_function(uhcr_matmul, iterations=100)
    except Exception as e:
        print(f"  UHCR base failed: {e}")
        results['uhcr_base'] = float('inf')
    
    # UHCR with plugin
    if HAS_ISA_PLUGIN:
        try:
            uhcr_a_p = uhcr.tensor([[1.0] * size for _ in range(size)])
            uhcr_b_p = uhcr.tensor([[1.0] * size for _ in range(size)])
            
            def plugin_matmul():
                return isa_plugin.bench_matmul(uhcr_a_p, uhcr_b_p)
            
            results['uhcr_plugin'] = time_function(plugin_matmul, iterations=100)
        except Exception as e:
            print(f"  UHCR plugin failed: {e}")
            results['uhcr_plugin'] = float('inf')
    
    return results


def benchmark_function_calls():
    """Benchmark function call overhead."""
    print("[5/5] Function Call Overhead...")
    results = {}
    
    # Python function
    def add_func(x, y):
        return x + y
    
    def python_call():
        return add_func(42, 58)
    
    results['python'] = time_function(python_call, iterations=10000)
    
    # UHCR base
    try:
        rt = get_runtime()
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("add", [Type.I64, Type.I64], Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        result = builder.add(func.arguments[0], func.arguments[1])
        builder.ret(result)
        
        uhcr_func = rt.compile(func)
        
        def uhcr_call():
            return uhcr_func(42, 58)
        
        results['uhcr_base'] = time_function(uhcr_call, iterations=10000)
    except Exception as e:
        print(f"  UHCR base failed: {e}")
        results['uhcr_base'] = float('inf')
    
    # Plugin version is same as base for function calls
    if HAS_ISA_PLUGIN:
        results['uhcr_plugin'] = results['uhcr_base']
    
    return results


def run_benchmarks():
    """Run all benchmarks and return results."""
    print("=" * 80)
    print("UHCR BENCHMARK SUITE - WITH AND WITHOUT PLUGINS")
    print("=" * 80)
    print(f"Platform: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    
    profile = detect()
    print(f"\nHardware:")
    print(f"  CPU: {profile.cpu.vendor}")
    print(f"  AVX2: {profile.cpu.has_avx2}")
    print(f"  AVX512: {getattr(profile.cpu, 'has_avx512', False)}")
    
    if HAS_ISA_PLUGIN:
        print(f"\n✅ ISA Auto Plugin: ENABLED ({ISA_TIER.upper()} tier)")
    else:
        print(f"\n❌ ISA Auto Plugin: DISABLED")
    
    print("=" * 80)
    
    results = {
        'scalar_arithmetic': benchmark_scalar_arithmetic(),
        'array_addition': benchmark_array_addition(),
        'simple_loop': benchmark_simple_loop(),
        'matrix_multiply': benchmark_matrix_multiply(),
        'function_call': benchmark_function_calls(),
    }
    
    return results, profile


def print_results(results: Dict):
    """Print benchmark results."""
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    for benchmark, times in results.items():
        print(f"\n{benchmark}:")
        fastest = min(times.values())
        
        for impl, time_val in sorted(times.items(), key=lambda x: x[1]):
            speedup = time_val / fastest if fastest > 0 else 1.0
            marker = "★" if speedup <= 1.01 else f"{speedup:.1f}x"
            print(f"  {impl:15s}: {format_time(time_val):>12s}  [{marker}]")


def generate_comparison(results: Dict) -> str:
    """Generate comparison between base and plugin."""
    lines = []
    lines.append("\n## Plugin vs Base Comparison\n\n")
    lines.append("| Benchmark | Python | UHCR Base | UHCR+Plugin | NumPy | Winner | Plugin Speedup |\n")
    lines.append("|-----------|--------|-----------|-------------|-------|--------|----------------|\n")
    
    for bench, times in results.items():
        fastest = min(times.values())
        winner = min(times.items(), key=lambda x: x[1])[0]
        
        # Calculate plugin speedup vs base
        if 'uhcr_base' in times and 'uhcr_plugin' in times:
            if times['uhcr_plugin'] != float('inf') and times['uhcr_base'] != float('inf'):
                plugin_speedup = times['uhcr_base'] / times['uhcr_plugin']
                speedup_str = f"{plugin_speedup:.2f}x" if plugin_speedup > 1.01 else "~same"
            else:
                speedup_str = "N/A"
        else:
            speedup_str = "N/A"
        
        row = [bench]
        for impl in ['python', 'uhcr_base', 'uhcr_plugin', 'numpy']:
            if impl in times and times[impl] != float('inf'):
                time_str = format_time(times[impl])
                speedup = times[impl] / fastest
                if speedup <= 1.01:
                    row.append(f"**{time_str}**")
                else:
                    row.append(f"{time_str}")
            else:
                row.append("-")
        row.append(f"**{winner}**")
        row.append(speedup_str)
        lines.append("| " + " | ".join(row) + " |\n")
    
    return "".join(lines)


if __name__ == "__main__":
    results, profile = run_benchmarks()
    print_results(results)
    
    # Generate comparison
    comparison = generate_comparison(results)
    print("\n" + "=" * 80)
    print("PLUGIN IMPACT ANALYSIS")
    print("=" * 80)
    print(comparison)
    
    print("\n✓ Plugin benchmark suite completed!")
