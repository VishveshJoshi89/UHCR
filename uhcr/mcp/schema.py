"""JSON Schema definitions for every MCP tool.

Each entry maps tool_name -> {description, inputSchema, outputSchema}.
AI agents use these schemas to understand what to pass and what to expect back.
"""

TOOL_SCHEMAS = {

    # ── Hardware ──────────────────────────────────────────────────────────────

    "detect_hardware": {
        "description": (
            "Detect the host hardware profile including CPU vendor, SIMD "
            "feature flags (AVX2, AVX-512), GPU name, VRAM, and available "
            "compute APIs (CUDA, ROCm, OpenCL, Metal, Vulkan)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "cpu_vendor":   {"type": "string"},
                "cpu_brand":    {"type": "string"},
                "cpu_cores":    {"type": "integer"},
                "has_avx2":     {"type": "boolean"},
                "has_avx512":   {"type": "boolean"},
                "gpu_name":     {"type": "string"},
                "gpu_vendor":   {"type": "string"},
                "vram_mb":      {"type": "number"},
                "cuda":         {"type": "boolean"},
                "cuda_version": {"type": "string"},
                "rocm":         {"type": "boolean"},
                "opencl":       {"type": "boolean"},
                "metal":        {"type": "boolean"},
                "vulkan":       {"type": "boolean"},
                "fingerprint":  {"type": "string"},
            },
        },
    },

    # ── Backends ──────────────────────────────────────────────────────────────

    "list_backends": {
        "description": (
            "List all registered UHCR execution backends in priority order. "
            "The first backend that supports the current hardware is selected "
            "automatically when compiling IR."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "backends": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":      {"type": "string"},
                            "priority":  {"type": "integer"},
                            "supported": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    },

    # ── Plugins ───────────────────────────────────────────────────────────────

    "list_plugins": {
        "description": (
            "List all plugins that are currently loaded in the UHCR runtime, "
            "together with the kernels and passes they registered."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "loaded_plugins": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":     {"type": "string"},
                            "version":  {"type": "string"},
                            "kernels":  {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "registered_kernels": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
    },

    "load_plugin": {
        "description": (
            "Dynamically load a UHCR plugin from a file path. "
            "The file must contain a class that inherits from uhcr.plugins.base.Plugin "
            "or a create_plugin() factory function."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the plugin .py file.",
                },
            },
            "required": ["path"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "loaded":   {"type": "boolean"},
                "name":     {"type": "string"},
                "version":  {"type": "string"},
                "message":  {"type": "string"},
            },
        },
    },

    # ── Compilation ───────────────────────────────────────────────────────────

    "compile_ir": {
        "description": (
            "Compile a simple UHCR IR function described as a JSON spec and "
            "return the selected backend, compile time, and a cache hit flag. "
            "Useful for testing whether a given operation will be JIT-compiled "
            "correctly on the host hardware."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {
                    "type": "string",
                    "description": "Name for the compiled function.",
                },
                "arg_types": {
                    "type": "array",
                    "items": {"type": "string",
                              "enum": ["i32","i64","f32","f64","ptr","void"]},
                    "description": "List of argument types.",
                },
                "return_type": {
                    "type": "string",
                    "enum": ["i32","i64","f32","f64","void"],
                    "description": "Return type of the function.",
                },
                "operations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "High-level op list: 'add', 'mul', 'sub', 'div'. "
                        "The compiler chains these on the arguments."
                    ),
                },
            },
            "required": ["function_name", "arg_types", "return_type"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "success":        {"type": "boolean"},
                "backend_used":   {"type": "string"},
                "compile_time_ms":{"type": "number"},
                "cache_hit":      {"type": "boolean"},
                "error":          {"type": "string"},
            },
        },
    },

    # ── Benchmarks ────────────────────────────────────────────────────────────

    "run_benchmark": {
        "description": (
            "Run one of the built-in UHCR benchmarks and return timing results. "
            "Benchmarks compare UHCR against Python and (if installed) NumPy."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "suite": {
                    "type": "string",
                    "enum": ["scalar_add", "vector_add", "matmul", "loop",
                             "all"],
                    "description": "Which benchmark suite to run.",
                },
                "size": {
                    "type": "integer",
                    "description": "Problem size (e.g. array length or matrix side). Default: 1000.",
                    "default": 1000,
                },
                "iterations": {
                    "type": "integer",
                    "description": "Number of timed iterations. Default: 100.",
                    "default": 100,
                },
            },
            "required": ["suite"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "benchmark":    {"type": "string"},
                            "uhcr_us":      {"type": "number"},
                            "python_us":    {"type": "number"},
                            "numpy_us":     {"type": "number"},
                            "winner":       {"type": "string"},
                            "uhcr_speedup": {"type": "number"},
                        },
                    },
                },
            },
        },
    },

    # ── Tensor ops ────────────────────────────────────────────────────────────

    "tensor_add": {
        "description": (
            "Create two float32 tensors from Python lists, add them "
            "element-wise using the best available UHCR backend, and return "
            "the result as a list. Useful for quick smoke-tests."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "First flat float32 array.",
                },
                "b": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Second flat float32 array (same length as a).",
                },
            },
            "required": ["a", "b"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "result":       {"type": "array", "items": {"type": "number"}},
                "backend_used": {"type": "string"},
                "time_us":      {"type": "number"},
            },
        },
    },

    "tensor_matmul": {
        "description": (
            "Perform matrix multiplication C = A @ B. "
            "Pass A and B as flat row-major float32 lists plus their shapes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "a":       {"type": "array", "items": {"type": "number"}},
                "a_rows":  {"type": "integer"},
                "a_cols":  {"type": "integer"},
                "b":       {"type": "array", "items": {"type": "number"}},
                "b_rows":  {"type": "integer"},
                "b_cols":  {"type": "integer"},
            },
            "required": ["a", "a_rows", "a_cols", "b", "b_rows", "b_cols"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "result":       {"type": "array", "items": {"type": "number"}},
                "shape":        {"type": "array",  "items": {"type": "integer"}},
                "backend_used": {"type": "string"},
                "time_us":      {"type": "number"},
            },
        },
    },

    # ── Advice ────────────────────────────────────────────────────────────────

    "get_performance_tips": {
        "description": (
            "Return human-readable performance tips tailored to the detected "
            "hardware. Tells the AI agent which plugins to load, which "
            "backends to prefer, and what operations to avoid on this machine."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "tips": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "recommended_plugins": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "best_backend": {"type": "string"},
            },
        },
    },
}
