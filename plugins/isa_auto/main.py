"""
ISA Auto-Select Plugin for UHCR
================================
Detects the current CPU ISA at runtime and wires in the best possible
kernel implementations for every benchmark category:

    Strings   — fast byte-level concat via bytearray
    Loops     — JIT-compiled increment via uhcr.jit
    Lists     — UHCR typed list_runtime
    Arrays    — AVX2 vector-add via UHCR IR (falls back to numpy add)
    MatMul    — UHCR Tensor.matmul (dispatches to AVX2/generic backend)
    Operators — JIT-compiled arithmetic expression

ISA priority ladder (highest wins):
    avx512f  → 512-bit wide SIMD path
    avx2     → 256-bit wide SIMD path   ← most modern x86 laptops/desktops
    avx      → 256-bit (no FMA)
    sse4_2   → 128-bit SIMD path
    neon     → ARM NEON path
    generic  → pure-Python fallback
"""

import ctypes
import sys
from pathlib import Path

import uhcr
from uhcr.plugins.base import Plugin
from uhcr.compiler.ir import Type
from uhcr.api.tensor import Tensor
from uhcr.runtime.memory_manager import AlignedBuffer

# ---------------------------------------------------------------------------
# Helper: detect which ISA tier we are running on
# ---------------------------------------------------------------------------

def _detect_isa_tier() -> str:
    """Return the highest ISA tier available on this CPU."""
    try:
        profile = uhcr.detect()
        features = set(profile.cpu.features)
        if any(f.startswith("avx512") for f in features):
            return "avx512"
        if "avx2" in features:
            return "avx2"
        if "avx" in features:
            return "avx"
        if "sse4_2" in features:
            return "sse4_2"
        if "neon" in features:
            return "neon"
    except Exception:
        pass
    return "generic"


# ---------------------------------------------------------------------------
# Kernel implementations per ISA tier
# ---------------------------------------------------------------------------

class _Kernels:
    """Namespace holding all benchmark kernels for a specific ISA tier."""

    def __init__(self, isa: str, runtime):
        self.isa = isa
        self._runtime = runtime
        self._jit_loop = None
        self._jit_ops = None
        self._vadd_fn = None
        self._setup(runtime)

    # ------------------------------------------------------------------ setup

    def _setup(self, runtime):
        # ---- JIT: loop increment (same for all ISAs — JIT handles it) ------
        @uhcr.jit(eager=True)
        def _loop_inc(n):
            return n + 1

        self._jit_loop = _loop_inc

        # ---- JIT: arithmetic operators  (a*b) + (a-b) ----------------------
        @uhcr.jit(eager=True)
        def _ops(a, b):
            return (a * b) + (a - b)

        self._jit_ops = _ops

        # ---- Vector add: build UHCR IR for AVX2/AVX512 wide SIMD -----------
        if self.isa in ("avx2", "avx512", "avx"):
            self._vadd_fn = self._build_ir_vadd(runtime)
        # SSE4 / NEON / generic → numpy-backed fallback (see bench_arrays)

    def _build_ir_vadd(self, runtime):
        """Compile a UHCR-IR vector-add function (8 floats at a time, AVX2).
        Compiled via CPU backend directly — bypasses CUDA routing.
        """
        try:
            from uhcr.compiler.ir_builder import IRBuilder
            from uhcr.compiler.passes import run_default_passes
            from uhcr.backends.backend_base import get_registered_backends

            b = IRBuilder()
            b.new_module()
            # Signature: (src_a: PTR, src_b: PTR, dst: PTR, n: I32, idx_ptr: PTR) -> VOID
            f = b.new_function(
                "isa_vadd",
                [Type.PTR, Type.PTR, Type.PTR, Type.I32, Type.PTR],
                Type.VOID,
            )
            en  = f.create_block("entry")
            lc  = f.create_block("loop_cond")
            lb  = f.create_block("loop_body")
            ex  = f.create_block("exit")

            # entry: idx = 0; goto loop_cond
            b.set_block(en)
            b.store(0, f.arguments[4], 0)
            b.jmp(lc)

            # loop_cond: if idx < n goto body else exit
            b.set_block(lc)
            idx = b.load(f.arguments[4], 0, Type.I32)
            b.br(b.cmp("lt", idx, f.arguments[3]), lb, ex)

            # loop_body: dst[idx:idx+8] = src_a[idx:idx+8] + src_b[idx:idx+8]
            b.set_block(lb)
            va = b.vload(f.arguments[0], idx, Type.V8F32)
            vb = b.vload(f.arguments[1], idx, Type.V8F32)
            vc = b.vadd(va, vb)
            b.vstore(vc, f.arguments[2], idx)
            b.store(b.add(idx, 8), f.arguments[4], 0)
            b.jmp(lc)

            b.set_block(ex)
            b.ret()

            # Compile via CPU backend only (skip CUDA)
            profile = runtime.get_profile()
            f = run_default_passes(f)
            for backend in get_registered_backends():
                if backend.name == "cuda":
                    continue
                if backend.supports(profile):
                    return backend.compile(f)

            return None
        except Exception:
            return None  # fall back to numpy

    # ---------------------------------------------------------------- kernels

    def string(self, s1: str, s2: str, n: int) -> str:
        """Fast string concatenation via bytearray (ISA-aware byte ops)."""
        if self.isa in ("avx2", "avx512", "avx", "sse4_2"):
            # bytearray avoids Python str immutability overhead
            parts = bytearray()
            enc1 = s1.encode()
            enc2 = s2.encode()
            for _ in range(n):
                parts.extend(enc1)
                parts.extend(enc2)
            return parts.decode()
        # generic / neon — standard join
        return "".join(s1 + s2 for _ in range(n))

    def loops(self, n: int):
        """JIT-compiled increment loop."""
        return [self._jit_loop(i) for i in range(n)]

    def lists(self, n: int):
        """UHCR typed list (i32) construction."""
        from uhcr.runtime.list_runtime import create_list
        lst = create_list("i32", n)
        for i in range(n):
            lst.append(i)
        return lst

    def arrays(self, x: Tensor, y: Tensor, out: Tensor):
        """Element-wise float32 add via UHCR IR (AVX2) or numpy fallback."""
        if self._vadd_fn is not None:
            with AlignedBuffer(4, alignment=64) as idx_buf:
                self._vadd_fn(
                    x.address, y.address, out.address, x.size, idx_buf.address
                )
        else:
            # SSE4 / NEON / generic: use numpy for correctness
            import numpy as np
            a_np = x.to_numpy().flatten()
            b_np = y.to_numpy().flatten()
            r    = a_np + b_np
            ctypes.memmove(
                out.buffer.address, r.ctypes.data, r.nbytes
            )

    def matmul(self, A: Tensor, B: Tensor) -> Tensor:
        """Hardware-dispatched matrix multiplication."""
        return A.matmul(B)

    def operators(self, n: int):
        """JIT-compiled (a*b)+(a-b) operators."""
        return [self._jit_ops(i, 2) for i in range(n)]


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

class ISAAutoPlugin(Plugin):
    """
    UHCR ISA Auto-Select Plugin  (3rd-party style — lives in plugins/).

    On initialize() this plugin:
      1. Detects the current CPU ISA tier (AVX-512 > AVX2 > AVX > SSE4.2 > NEON > generic).
      2. Compiles hardware-optimal kernels for every benchmark category.
      3. Registers a isa_vadd kernel in the global UHCR kernel registry.
      4. Exposes a bench_* method family for the benchmark runner.
    """

    @property
    def name(self) -> str:
        return "isa_auto"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, runtime) -> None:
        self._isa = _detect_isa_tier()
        self._kernels = _Kernels(self._isa, runtime)

        # Register the vector-add kernel globally so other code can look it up
        if self._kernels._vadd_fn is not None:
            self.register_kernel("isa_vadd", self._kernels._vadd_fn)

        print(
            f"[ISAAutoPlugin] Initialized v{self.version} — "
            f"ISA tier: {self._isa.upper()}"
        )

    def shutdown(self) -> None:
        print("[ISAAutoPlugin] Shutdown")

    # ---------------------------------------------------------------- proxy API

    @property
    def isa_tier(self) -> str:
        return getattr(self, "_isa", "unknown")

    def bench_string(self, s1: str, s2: str, n: int) -> str:
        return self._kernels.string(s1, s2, n)

    def bench_loops(self, n: int):
        return self._kernels.loops(n)

    def bench_lists(self, n: int):
        return self._kernels.lists(n)

    def bench_arrays(self, x: Tensor, y: Tensor, out: Tensor):
        return self._kernels.arrays(x, y, out)

    def bench_matmul(self, A: Tensor, B: Tensor) -> Tensor:
        return self._kernels.matmul(A, B)

    def bench_ops(self, n: int):
        return self._kernels.operators(n)
