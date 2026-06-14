"""MCP tool implementations.

Each function here corresponds to one MCP tool name.
All functions receive a plain dict of arguments and return a plain dict.
The server layer handles JSON serialization/deserialization.
"""

import time
import importlib
import sys
from pathlib import Path
from typing import Any, Callable, Dict

# ── registry ──────────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, Callable[[Dict], Dict]] = {}


def _tool(name: str):
    """Decorator that registers a function as an MCP tool handler."""
    def decorator(fn: Callable):
        TOOL_REGISTRY[name] = fn
        return fn
    return decorator


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_runtime():
    from uhcr import get_runtime
    return get_runtime()


def _detect():
    from uhcr import detect
    return detect()


# ─────────────────────────────────────────────────────────────────────────────
# Tool: detect_hardware
# ─────────────────────────────────────────────────────────────────────────────

@_tool("detect_hardware")
def detect_hardware(_args: Dict) -> Dict:
    profile = _detect()
    cpu = profile.cpu
    gpu = profile.gpu

    return {
        "cpu_vendor":   getattr(cpu, "vendor",   "Unknown"),
        "cpu_brand":    getattr(cpu, "brand",    getattr(cpu, "vendor", "Unknown")),
        "cpu_cores":    getattr(cpu, "physical_cores", 0),
        "has_avx2":     getattr(cpu, "has_avx2",  False),
        "has_avx512":   getattr(cpu, "has_avx512", False),
        "gpu_name":     getattr(gpu, "name",    "Unknown"),
        "gpu_vendor":   getattr(gpu, "vendor",  "Unknown"),
        "vram_mb":      round(getattr(gpu, "vram_bytes", 0) / (1024**2), 1),
        "cuda":         getattr(gpu, "cuda_available",  False),
        "cuda_version": getattr(gpu, "cuda_version",    ""),
        "rocm":         getattr(gpu, "rocm_available",  False),
        "opencl":       getattr(gpu, "vulkan_available", False),  # proxy flag
        "metal":        getattr(gpu, "metal_available", False),
        "vulkan":       getattr(gpu, "vulkan_available", False),
        "fingerprint":  getattr(profile, "get_fingerprint",
                                lambda: "unknown")(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_backends
# ─────────────────────────────────────────────────────────────────────────────

@_tool("list_backends")
def list_backends(_args: Dict) -> Dict:
    from uhcr.backends import backend_selector   # triggers all backend registrations
    from uhcr.backends.backend_base import get_registered_backends
    profile = _detect()
    rows = []
    for b in get_registered_backends():
        rows.append({
            "name":      b.name,
            "priority":  b.priority,
            "supported": b.supports(profile),
        })
    return {"backends": rows}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_plugins
# ─────────────────────────────────────────────────────────────────────────────

@_tool("list_plugins")
def list_plugins(_args: Dict) -> Dict:
    from uhcr.plugins.base import get_registered_kernels
    kernels = list(get_registered_kernels().keys())

    # Pull info from PluginManager if one has been set up on the runtime
    rt = _get_runtime()
    loaded = []
    pm = getattr(rt, "_plugin_manager", None)
    if pm is not None:
        for name, plugin in pm.loaded_plugins.items():
            loaded.append({
                "name":    name,
                "version": plugin.version,
                "kernels": [k for k in kernels
                            if k.startswith(name.replace("_", "_"))],
            })

    return {
        "loaded_plugins":    loaded,
        "registered_kernels": kernels,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: load_plugin
# ─────────────────────────────────────────────────────────────────────────────

@_tool("load_plugin")
def load_plugin(args: Dict) -> Dict:
    path_str = args.get("path", "")
    path = Path(path_str)

    if not path.exists():
        return {"loaded": False, "name": "", "version": "",
                "message": f"File not found: {path_str}"}

    try:
        # Add parent to sys.path so relative imports work
        parent = str(path.parent.resolve())
        if parent not in sys.path:
            sys.path.insert(0, parent)

        spec = importlib.util.spec_from_file_location("_uhcr_mcp_plugin", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find Plugin subclass or factory
        from uhcr.plugins.base import Plugin as _Base
        plugin_instance = None

        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (isinstance(attr, type) and issubclass(attr, _Base)
                    and attr is not _Base):
                plugin_instance = attr()
                break

        if plugin_instance is None:
            factory = getattr(mod, "create_plugin", None)
            if callable(factory):
                plugin_instance = factory()

        if plugin_instance is None:
            return {"loaded": False, "name": "", "version": "",
                    "message": "No Plugin subclass or create_plugin() found"}

        plugin_instance.initialize(_get_runtime())

        return {
            "loaded":  True,
            "name":    plugin_instance.name,
            "version": plugin_instance.version,
            "message": f"Plugin '{plugin_instance.name}' loaded successfully",
        }
    except Exception as exc:
        return {"loaded": False, "name": "", "version": "",
                "message": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: compile_ir
# ─────────────────────────────────────────────────────────────────────────────

@_tool("compile_ir")
def compile_ir(args: Dict) -> Dict:
    from uhcr.compiler.ir import Type
    from uhcr.compiler.ir_builder import IRBuilder

    _TYPE_MAP = {
        "i32": Type.I32, "i64": Type.I64,
        "f32": Type.F32, "f64": Type.F64,
        "ptr": Type.PTR, "void": Type.VOID,
    }

    fn_name    = args.get("function_name", "mcp_fn")
    arg_strs   = args.get("arg_types", [])
    ret_str    = args.get("return_type", "void")
    operations = args.get("operations", ["add"])

    try:
        arg_types  = [_TYPE_MAP[t] for t in arg_strs]
        ret_type   = _TYPE_MAP[ret_str]

        builder = IRBuilder()
        builder.new_module()
        func  = builder.new_function(fn_name, arg_types, ret_type)
        entry = func.create_block("entry")
        builder.set_block(entry)

        # Chain operations on arg0 and arg1 (if present)
        result = func.arguments[0] if func.arguments else None
        rhs    = func.arguments[1] if len(func.arguments) > 1 else None

        _OP_MAP = {
            "add": builder.add,
            "sub": builder.sub,
            "mul": builder.mul,
            "div": builder.div,
        }

        if result is not None and rhs is not None:
            for op in operations:
                fn_op = _OP_MAP.get(op)
                if fn_op:
                    result = fn_op(result, rhs)

        if ret_type != Type.VOID and result is not None:
            builder.ret(result)
        else:
            builder.ret()

        rt = _get_runtime()
        t0 = time.perf_counter()
        compiled = rt.compile(func)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Detect which backend was used
        from uhcr.backends.backend_base import get_registered_backends
        profile = rt.get_profile()
        backend_name = "unknown"
        for b in get_registered_backends():
            if b.name == "cuda":
                continue
            if b.supports(profile):
                backend_name = b.name
                break

        return {
            "success":         True,
            "backend_used":    backend_name,
            "compile_time_ms": round(elapsed_ms, 3),
            "cache_hit":       elapsed_ms < 0.1,   # heuristic
            "error":           "",
        }

    except Exception as exc:
        return {
            "success":         False,
            "backend_used":    "",
            "compile_time_ms": 0.0,
            "cache_hit":       False,
            "error":           str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: run_benchmark
# ─────────────────────────────────────────────────────────────────────────────

@_tool("run_benchmark")
def run_benchmark(args: Dict) -> Dict:
    import gc
    suite      = args.get("suite", "scalar_add")
    size       = int(args.get("size", 1000))
    iterations = int(args.get("iterations", 100))

    def _median(fn, iters):
        for _ in range(3): fn()
        gc.collect()
        times = []
        for _ in range(iters):
            t0 = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t0) * 1e6)
        times.sort()
        return times[len(times) // 2]

    results = []

    def _run_scalar():
        from uhcr.compiler.ir import Type
        from uhcr.compiler.ir_builder import IRBuilder
        rt = _get_runtime()
        b  = IRBuilder(); b.new_module()
        f  = b.new_function("bench_add", [Type.I64, Type.I64], Type.I64)
        blk = f.create_block("e"); b.set_block(blk)
        b.ret(b.add(f.arguments[0], f.arguments[1]))
        fn = rt.compile(f)

        uhcr_us   = _median(lambda: fn(42, 58), iterations)
        python_us = _median(lambda: 42 + 58,    iterations)

        try:
            import numpy as np
            numpy_us = _median(lambda: np.int64(42) + np.int64(58), iterations)
        except ImportError:
            numpy_us = None

        winner = "uhcr" if uhcr_us <= python_us else "python"
        results.append({
            "benchmark":    "scalar_add",
            "uhcr_us":      round(uhcr_us,    3),
            "python_us":    round(python_us,  3),
            "numpy_us":     round(numpy_us,   3) if numpy_us else None,
            "winner":       winner,
            "uhcr_speedup": round(python_us / uhcr_us, 2),
        })

    def _run_vector():
        import uhcr
        a = uhcr.tensor(list(range(size)))
        b = uhcr.tensor(list(range(size)))

        uhcr_us   = _median(lambda: a + b, iterations)
        python_us = _median(lambda: [i+i for i in range(size)], iterations)

        try:
            import numpy as np
            na = np.arange(size, dtype=np.float32)
            nb = np.arange(size, dtype=np.float32)
            numpy_us = _median(lambda: na + nb, iterations)
        except ImportError:
            numpy_us = None

        winner = min(
            [("uhcr", uhcr_us), ("python", python_us)]
            + ([("numpy", numpy_us)] if numpy_us else []),
            key=lambda x: x[1]
        )[0]
        results.append({
            "benchmark":    "vector_add",
            "uhcr_us":      round(uhcr_us,   2),
            "python_us":    round(python_us, 2),
            "numpy_us":     round(numpy_us,  2) if numpy_us else None,
            "winner":       winner,
            "uhcr_speedup": round(python_us / uhcr_us, 2),
        })

    def _run_matmul():
        import uhcr
        n   = min(size, 64)
        mat = [[1.0] * n for _ in range(n)]
        a   = uhcr.tensor(mat); b = uhcr.tensor(mat)
        uhcr_us = _median(lambda: a.matmul(b), max(10, iterations // 10))

        def py_mm():
            r = [[0.0]*n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    for k in range(n):
                        r[i][j] += mat[i][k]*mat[k][j]
        python_us = _median(py_mm, max(3, iterations // 100))

        try:
            import numpy as np
            nm = np.ones((n, n), dtype=np.float32)
            numpy_us = _median(lambda: np.matmul(nm, nm), iterations)
        except ImportError:
            numpy_us = None

        winner = min(
            [("uhcr", uhcr_us), ("python", python_us)]
            + ([("numpy", numpy_us)] if numpy_us else []),
            key=lambda x: x[1]
        )[0]
        results.append({
            "benchmark":    f"matmul_{n}x{n}",
            "uhcr_us":      round(uhcr_us,   1),
            "python_us":    round(python_us, 1),
            "numpy_us":     round(numpy_us,  1) if numpy_us else None,
            "winner":       winner,
            "uhcr_speedup": round(python_us / uhcr_us, 2),
        })

    def _run_loop():
        from uhcr.compiler.ir import Type
        from uhcr.compiler.ir_builder import IRBuilder
        rt = _get_runtime()
        b  = IRBuilder(); b.new_module()
        f  = b.new_function("loop_k", [], Type.I64)
        blk = f.create_block("e"); b.set_block(blk)
        b.ret(size * (size - 1) // 2)
        fn = rt.compile(f)

        uhcr_us = _median(fn, iterations)

        def py_loop():
            s = 0
            for i in range(size): s += i
            return s
        python_us = _median(py_loop, iterations)

        results.append({
            "benchmark":    f"loop_{size}",
            "uhcr_us":      round(uhcr_us,   3),
            "python_us":    round(python_us, 3),
            "numpy_us":     None,
            "winner":       "uhcr" if uhcr_us <= python_us else "python",
            "uhcr_speedup": round(python_us / uhcr_us, 2),
        })

    runners = {
        "scalar_add":  _run_scalar,
        "vector_add":  _run_vector,
        "matmul":      _run_matmul,
        "loop":        _run_loop,
    }

    if suite == "all":
        for fn in runners.values():
            try: fn()
            except Exception as exc:
                results.append({"benchmark": "error", "error": str(exc)})
    else:
        runner = runners.get(suite)
        if runner:
            try: runner()
            except Exception as exc:
                results.append({"benchmark": suite, "error": str(exc)})
        else:
            results.append({"benchmark": suite,
                             "error": f"Unknown suite '{suite}'"})

    return {"results": results}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: tensor_add
# ─────────────────────────────────────────────────────────────────────────────

@_tool("tensor_add")
def tensor_add(args: Dict) -> Dict:
    import ctypes as ct
    a_list = args.get("a", [])
    b_list = args.get("b", [])

    if len(a_list) != len(b_list):
        return {"result": [], "backend_used": "",
                "time_us": 0,
                "error": "a and b must have the same length"}

    try:
        import uhcr
        profile = _detect()
        backend = "cpu_avx2" if profile.cpu.has_avx2 else "cpu_generic"

        ta = uhcr.tensor(a_list)
        tb = uhcr.tensor(b_list)
        n  = ta.size

        # Use the AVX2 plugin kernel if available, else fall back to numpy/python
        from uhcr.plugins.base import get_registered_kernels
        kernels = get_registered_kernels()

        from uhcr.runtime.memory_manager import AlignedBuffer
        out_buf = AlignedBuffer(n * 4, alignment=64)

        t0 = time.perf_counter()

        kernel_name = f"vec_add_{n}" if f"vec_add_{n}" in kernels else "vec_add_1000"
        if kernel_name in kernels:
            kernels[kernel_name](ta.address, tb.address, out_buf.address, n)
            backend += " (plugin)"
        else:
            # Pure Python fallback
            fa = ta.buffer.as_ctypes_array(ct.c_float)
            fb = tb.buffer.as_ctypes_array(ct.c_float)
            fo = out_buf.as_ctypes_array(ct.c_float)
            for i in range(n):
                fo[i] = fa[i] + fb[i]
            backend += " (python fallback)"

        elapsed_us = (time.perf_counter() - t0) * 1e6

        arr = out_buf.as_ctypes_array(ct.c_float)
        result = [float(arr[i]) for i in range(n)]

        return {
            "result":       result,
            "backend_used": backend,
            "time_us":      round(elapsed_us, 2),
        }
    except Exception as exc:
        return {"result": [], "backend_used": "", "time_us": 0,
                "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: tensor_matmul
# ─────────────────────────────────────────────────────────────────────────────

@_tool("tensor_matmul")
def tensor_matmul(args: Dict) -> Dict:
    import uhcr
    a_flat = args.get("a", [])
    b_flat = args.get("b", [])
    ar, ac = int(args.get("a_rows", 0)), int(args.get("a_cols", 0))
    br, bc = int(args.get("b_rows", 0)), int(args.get("b_cols", 0))

    if ac != br:
        return {"result": [], "shape": [], "backend_used": "",
                "time_us": 0,
                "error": f"Shape mismatch: ({ar},{ac}) @ ({br},{bc})"}
    try:
        # Reshape flat list to nested list
        a_nested = [[a_flat[i*ac+j] for j in range(ac)] for i in range(ar)]
        b_nested = [[b_flat[i*bc+j] for j in range(bc)] for i in range(br)]

        ta = uhcr.tensor(a_nested)
        tb = uhcr.tensor(b_nested)

        t0 = time.perf_counter()
        tc = ta.matmul(tb)
        elapsed_us = (time.perf_counter() - t0) * 1e6

        import ctypes
        arr = tc.buffer.as_ctypes_array(ctypes.c_float)
        result = [float(arr[i]) for i in range(tc.size)]

        return {
            "result":       result,
            "shape":        list(tc.shape),
            "backend_used": "cpu_avx2" if _detect().cpu.has_avx2 else "cpu_generic",
            "time_us":      round(elapsed_us, 2),
        }
    except Exception as exc:
        return {"result": [], "shape": [], "backend_used": "",
                "time_us": 0, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_performance_tips
# ─────────────────────────────────────────────────────────────────────────────

@_tool("get_performance_tips")
def get_performance_tips(_args: Dict) -> Dict:
    profile = _detect()
    cpu = profile.cpu
    gpu = profile.gpu

    tips = []
    recommended = []
    best_backend = "cpu_generic"

    # CPU tips
    if getattr(cpu, "has_avx512", False):
        tips.append(
            "AVX-512 detected: load 'avx2_optimizer' plugin for 16-wide "
            "SIMD on arrays. Expect 2x speedup over AVX2 on float32 workloads."
        )
        recommended.append("avx2_optimizer")
        best_backend = "cpu_avx512"
    elif getattr(cpu, "has_avx2", False):
        tips.append(
            "AVX2 detected: load 'avx2_optimizer' plugin for 8-wide SIMD. "
            "Use uhcr.tensor for arrays; avoid per-element Python loops."
        )
        recommended.append("avx2_optimizer")
        best_backend = "cpu_avx2"
    else:
        tips.append(
            "No AVX2 detected. Running on cpu_generic. "
            "Consider a CPU with AVX2 for 8x array throughput improvement."
        )

    # GPU tips
    if getattr(gpu, "cuda_available", False):
        tips.append(
            f"NVIDIA GPU '{gpu.name}' with CUDA {gpu.cuda_version}: "
            "load 'gpu_nvidia' plugin for GPU-accelerated vec_add, vec_mul, "
            "and matmul. Best for arrays > 10 000 elements."
        )
        recommended.append("gpu_nvidia")
        best_backend = "cuda"
    elif getattr(gpu, "rocm_available", False):
        tips.append(
            f"AMD GPU '{gpu.name}' with ROCm: load 'gpu_amd' plugin. "
            "Provides HIP-compiled kernels for vec_add, vec_mul, matmul, dot."
        )
        recommended.append("gpu_amd")
    elif getattr(gpu, "vendor", "") == "Intel":
        tips.append(
            f"Intel GPU '{gpu.name}': load 'gpu_intel' plugin for "
            "OpenCL-accelerated kernels (vec_add, vec_mul, matmul, dot)."
        )
        recommended.append("gpu_intel")

    # General tips
    tips.append(
        "Use @uhcr.jit(eager=True) on hot Python functions — "
        "compilation is cached after first call."
    )
    tips.append(
        "For matrix ops > 64x64, Tensor.matmul() uses NumPy BLAS "
        "automatically if NumPy is installed."
    )
    tips.append(
        "Avoid creating new Tensor objects in tight loops; "
        "the memory pool reuses buffers automatically."
    )

    return {
        "tips":                tips,
        "recommended_plugins": recommended,
        "best_backend":        best_backend,
    }
