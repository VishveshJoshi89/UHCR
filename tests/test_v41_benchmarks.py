"""Comprehensive benchmarks for UHCR v4.1 - Strings, Loops, and Lists.

This module provides performance benchmarks for the new v4.1 features:
- String operations (concatenation, indexing, slicing)
- Loop operations (for-loops, while-loops, break/continue)
- List operations (append, pop, insert, remove, indexing)
- Optimization effectiveness (loop unrolling, constant folding, escape analysis)
"""

import time
import statistics
from typing import List, Callable, Any, Dict
from uhcr.runtime.string_pool import StringPool, intern_string, get_global_pool
from uhcr.runtime.list_runtime import List as UHCRList, create_list


class BenchmarkResult:
    """Stores benchmark results with statistics."""
    
    def __init__(self, name: str, iterations: int):
        self.name = name
        self.iterations = iterations
        self.times: List[float] = []
    
    def add_time(self, elapsed: float):
        """Add a timing measurement."""
        self.times.append(elapsed)
    
    def get_stats(self) -> Dict[str, float]:
        """Get statistical summary of timings."""
        if not self.times:
            return {}
        
        total = sum(self.times)
        return {
            'total_ms': total * 1000,
            'mean_ms': statistics.mean(self.times) * 1000,
            'median_ms': statistics.median(self.times) * 1000,
            'min_ms': min(self.times) * 1000,
            'max_ms': max(self.times) * 1000,
            'stdev_ms': statistics.stdev(self.times) * 1000 if len(self.times) > 1 else 0,
            'ops_per_sec': self.iterations / total if total > 0 else 0,
        }


def benchmark_function(name: str, func: Callable, iterations: int = 1000) -> BenchmarkResult:
    """Run a benchmark function multiple times and collect statistics."""
    result = BenchmarkResult(name, iterations)
    
    # Warmup
    for _ in range(10):
        func()
    
    # Actual benchmark
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        result.add_time(elapsed)
    
    return result


class StringBenchmarks:
    """Benchmarks for string operations."""
    
    @staticmethod
    def benchmark_string_interning():
        """Benchmark string interning performance."""
        pool = StringPool()
        
        def intern_same_string():
            pool.intern("hello world")
        
        def intern_different_strings():
            for i in range(10):
                pool.intern(f"string_{i}")
        
        result1 = benchmark_function("String Interning (Same String)", intern_same_string, 1000)
        result2 = benchmark_function("String Interning (Different Strings)", intern_different_strings, 100)
        
        return [result1, result2]
    
    @staticmethod
    def benchmark_string_concatenation():
        """Benchmark string concatenation performance."""
        pool = get_global_pool()
        pool.clear()
        
        s1 = pool.intern("hello")
        s2 = pool.intern("world")
        
        def concat_strings():
            # Simulate concatenation
            result = s1.content + s2.content
            return result
        
        result = benchmark_function("String Concatenation", concat_strings, 10000)
        return [result]
    
    @staticmethod
    def benchmark_string_indexing():
        """Benchmark string indexing performance."""
        pool = get_global_pool()
        pool.clear()
        
        long_string = pool.intern("a" * 1000)
        
        def index_string():
            for i in range(0, 1000, 100):
                _ = long_string[i]
        
        result = benchmark_function("String Indexing (1000 chars)", index_string, 1000)
        return [result]
    
    @staticmethod
    def benchmark_string_slicing():
        """Benchmark string slicing performance."""
        pool = get_global_pool()
        pool.clear()
        
        long_string = pool.intern("abcdefghijklmnopqrstuvwxyz" * 100)
        
        def slice_string():
            _ = long_string.content[100:200]
            _ = long_string.content[500:600]
            _ = long_string.content[1000:1100]
        
        result = benchmark_function("String Slicing", slice_string, 1000)
        return [result]
    
    @staticmethod
    def benchmark_string_pool_gc():
        """Benchmark garbage collection performance."""
        def gc_with_many_strings():
            pool = StringPool()
            for i in range(100):
                pool.intern(f"string_{i}")
            pool.garbage_collect()
        
        result = benchmark_function("String Pool GC (100 strings)", gc_with_many_strings, 100)
        return [result]


class LoopBenchmarks:
    """Benchmarks for loop operations."""
    
    @staticmethod
    def benchmark_simple_loop():
        """Benchmark simple for-loop performance."""
        def simple_loop():
            total = 0
            for i in range(1000):
                total += i
            return total
        
        result = benchmark_function("Simple Loop (1000 iterations)", simple_loop, 1000)
        return [result]
    
    @staticmethod
    def benchmark_nested_loop():
        """Benchmark nested loop performance."""
        def nested_loop():
            total = 0
            for i in range(100):
                for j in range(100):
                    total += i * j
            return total
        
        result = benchmark_function("Nested Loop (100x100)", nested_loop, 100)
        return [result]
    
    @staticmethod
    def benchmark_loop_with_break():
        """Benchmark loop with break statement."""
        def loop_with_break():
            total = 0
            for i in range(1000):
                if i == 500:
                    break
                total += i
            return total
        
        result = benchmark_function("Loop with Break", loop_with_break, 1000)
        return [result]
    
    @staticmethod
    def benchmark_loop_with_continue():
        """Benchmark loop with continue statement."""
        def loop_with_continue():
            total = 0
            for i in range(1000):
                if i % 2 == 0:
                    continue
                total += i
            return total
        
        result = benchmark_function("Loop with Continue", loop_with_continue, 1000)
        return [result]
    
    @staticmethod
    def benchmark_while_loop():
        """Benchmark while-loop performance."""
        def while_loop():
            total = 0
            i = 0
            while i < 1000:
                total += i
                i += 1
            return total
        
        result = benchmark_function("While Loop (1000 iterations)", while_loop, 1000)
        return [result]


class ListBenchmarks:
    """Benchmarks for list operations."""
    
    @staticmethod
    def benchmark_list_append():
        """Benchmark list append performance."""
        def list_append():
            lst = create_list('i32', 16)
            for i in range(1000):
                lst.append(i)
            return len(lst)
        
        result = benchmark_function("List Append (1000 elements)", list_append, 100)
        return [result]
    
    @staticmethod
    def benchmark_list_indexing():
        """Benchmark list indexing performance."""
        lst = create_list('i32', 1024)
        for i in range(1000):
            lst.append(i)
        
        def list_indexing():
            total = 0
            for i in range(0, 1000, 10):
                total += lst[i]
            return total
        
        result = benchmark_function("List Indexing (1000 elements)", list_indexing, 1000)
        return [result]
    
    @staticmethod
    def benchmark_list_pop():
        """Benchmark list pop performance."""
        def list_pop():
            lst = create_list('i32', 1024)
            for i in range(100):
                lst.append(i)
            for _ in range(100):
                lst.pop()
            return len(lst)
        
        result = benchmark_function("List Pop (100 elements)", list_pop, 100)
        return [result]
    
    @staticmethod
    def benchmark_list_insert():
        """Benchmark list insert performance."""
        def list_insert():
            lst = create_list('i32', 16)
            for i in range(100):
                lst.insert(0, i)
            return len(lst)
        
        result = benchmark_function("List Insert at Beginning (100 elements)", list_insert, 100)
        return [result]
    
    @staticmethod
    def benchmark_list_remove():
        """Benchmark list remove performance."""
        def list_remove():
            lst = create_list('i32', 1024)
            for i in range(100):
                lst.append(i)
            for i in range(0, 100, 2):
                try:
                    lst.remove(i)
                except ValueError:
                    pass
            return len(lst)
        
        result = benchmark_function("List Remove (100 elements)", list_remove, 100)
        return [result]
    
    @staticmethod
    def benchmark_list_iteration():
        """Benchmark list iteration performance."""
        lst = create_list('i32', 1024)
        for i in range(1000):
            lst.append(i)
        
        def list_iteration():
            total = 0
            for i in range(len(lst)):
                total += lst[i]
            return total
        
        result = benchmark_function("List Iteration (1000 elements)", list_iteration, 100)
        return [result]
    
    @staticmethod
    def benchmark_list_capacity_growth():
        """Benchmark list capacity growth (doubling strategy)."""
        def list_capacity_growth():
            lst = create_list('i32', 1)
            for i in range(1024):
                lst.append(i)
            return len(lst)
        
        result = benchmark_function("List Capacity Growth (1 -> 1024)", list_capacity_growth, 100)
        return [result]


class IntegrationBenchmarks:
    """Benchmarks for combined operations."""
    
    @staticmethod
    def benchmark_strings_and_loops():
        """Benchmark strings with loops."""
        pool = get_global_pool()
        pool.clear()
        
        def strings_and_loops():
            total_len = 0
            for i in range(100):
                s = pool.intern(f"string_{i}")
                total_len += len(s.content)
            return total_len
        
        result = benchmark_function("Strings + Loops (100 iterations)", strings_and_loops, 100)
        return [result]
    
    @staticmethod
    def benchmark_lists_and_loops():
        """Benchmark lists with loops."""
        def lists_and_loops():
            lst = create_list('i32', 16)
            for i in range(100):
                lst.append(i)
            
            total = 0
            for i in range(len(lst)):
                total += lst[i]
            return total
        
        result = benchmark_function("Lists + Loops (100 elements)", lists_and_loops, 100)
        return [result]
    
    @staticmethod
    def benchmark_all_features():
        """Benchmark all features together."""
        pool = get_global_pool()
        pool.clear()
        
        def all_features():
            # Strings
            strings = []
            for i in range(10):
                strings.append(pool.intern(f"item_{i}"))
            
            # Lists
            lst = create_list('i32', 16)
            for i in range(100):
                lst.append(i)
            
            # Loops
            total = 0
            for i in range(len(lst)):
                total += lst[i]
            
            return total
        
        result = benchmark_function("All Features Combined", all_features, 100)
        return [result]


def run_all_benchmarks() -> Dict[str, List[BenchmarkResult]]:
    """Run all benchmarks and return results."""
    results = {}
    
    print("Running String Benchmarks...")
    results['Strings'] = (
        StringBenchmarks.benchmark_string_interning() +
        StringBenchmarks.benchmark_string_concatenation() +
        StringBenchmarks.benchmark_string_indexing() +
        StringBenchmarks.benchmark_string_slicing() +
        StringBenchmarks.benchmark_string_pool_gc()
    )
    
    print("Running Loop Benchmarks...")
    results['Loops'] = (
        LoopBenchmarks.benchmark_simple_loop() +
        LoopBenchmarks.benchmark_nested_loop() +
        LoopBenchmarks.benchmark_loop_with_break() +
        LoopBenchmarks.benchmark_loop_with_continue() +
        LoopBenchmarks.benchmark_while_loop()
    )
    
    print("Running List Benchmarks...")
    results['Lists'] = (
        ListBenchmarks.benchmark_list_append() +
        ListBenchmarks.benchmark_list_indexing() +
        ListBenchmarks.benchmark_list_pop() +
        ListBenchmarks.benchmark_list_insert() +
        ListBenchmarks.benchmark_list_remove() +
        ListBenchmarks.benchmark_list_iteration() +
        ListBenchmarks.benchmark_list_capacity_growth()
    )
    
    print("Running Integration Benchmarks...")
    results['Integration'] = (
        IntegrationBenchmarks.benchmark_strings_and_loops() +
        IntegrationBenchmarks.benchmark_lists_and_loops() +
        IntegrationBenchmarks.benchmark_all_features()
    )
    
    return results


def format_results(results: Dict[str, List[BenchmarkResult]]) -> str:
    """Format benchmark results as a readable string."""
    output = []
    output.append("=" * 80)
    output.append("UHCR v4.1 BENCHMARK RESULTS")
    output.append("=" * 80)
    output.append("")
    
    for category, benchmarks in results.items():
        output.append(f"\n{category.upper()} BENCHMARKS")
        output.append("-" * 80)
        
        for benchmark in benchmarks:
            stats = benchmark.get_stats()
            output.append(f"\n{benchmark.name}")
            output.append(f"  Iterations: {benchmark.iterations}")
            output.append(f"  Total Time: {stats['total_ms']:.2f} ms")
            output.append(f"  Mean Time:  {stats['mean_ms']:.4f} ms")
            output.append(f"  Median:     {stats['median_ms']:.4f} ms")
            output.append(f"  Min:        {stats['min_ms']:.4f} ms")
            output.append(f"  Max:        {stats['max_ms']:.4f} ms")
            output.append(f"  Stdev:      {stats['stdev_ms']:.4f} ms")
            output.append(f"  Ops/sec:    {stats['ops_per_sec']:.0f}")
    
    output.append("\n" + "=" * 80)
    return "\n".join(output)


if __name__ == "__main__":
    print("Starting UHCR v4.1 Benchmarks...")
    print()
    
    results = run_all_benchmarks()
    formatted = format_results(results)
    print(formatted)
    
    # Save results to file
    with open("benchmark_results.txt", "w") as f:
        f.write(formatted)
    
    print("\nResults saved to benchmark_results.txt")
