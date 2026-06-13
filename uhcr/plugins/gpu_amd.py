"""AMD GPU Plugin for UHCR.

Provides ROCm/HIP-accelerated kernels for AMD GPUs (RDNA, CDNA).
Uses the HIP runtime API (libamdhip64 / hiprtc) for kernel compilation
and execution. Falls back to Vulkan compute if HIP is unavailable.

Supported operations:
- Vector addition  (f32)
- Vector multiply  (f32)
- Matrix multiply   (f32, square NxN)
- Dot product

Usage:
    from uhcr.plugins.gpu_amd import AMDGPUPlugin
    plugin = AMDGPUPlugin()
    plugin.initialize(get_runtime())
    out = plugin.vec_add(a_tensor, b_tensor)
"""

import ctypes
import platform
import textwrap
from typing import Callable, Dict, List, Optional, Tuple

from uhcr.plugins.base import Plugin
from uhcr.compiler.ir import Type


# ── HIP kernel source (compiled at runtime via hiprtc) ───────────────────────

_HIP_VEC_ADD = textwrap.dedent("""\
    extern "C" __global__ void vec_add_f32(
            const float* a, const float* b, float* c, int n) {
        int i = blockIdx.x * blockDim.x + threadIdx.x;
        if (i < n) c[i] = a[i] + b[i];
    }
""")

_HIP_VEC_MUL = textwrap.dedent("""\
    extern "C" __global__ void vec_mul_f32(
            const float* a, const float* b, float* c, int n) {
        int i = blockIdx.x * blockDim.x + threadIdx.x;
        if (i < n) c[i] = a[i] * b[i];
    }
""")

_HIP_MATMUL = textwrap.dedent("""\
    extern "C" __global__ void matmul_f32(
            const float* a, const float* b, float* c, int n) {
        int row = blockIdx.y;
        int col = blockIdx.x;
        if (row >= n || col >= n) return;
        float acc = 0.0f;
        for (int k = 0; k < n; k++)
            acc += a[row*n + k] * b[k*n + col];
        c[row*n + col] = acc;
    }
""")

_HIP_DOT = textwrap.dedent("""\
    extern "C" __global__ void dot_f32(
            const float* a, const float* b, float* partial, int n) {
        extern __shared__ float sdata[];
        int i  = blockIdx.x * blockDim.x + threadIdx.x;
        int ti = threadIdx.x;
        sdata[ti] = (i < n) ? a[i] * b[i] : 0.0f;
        __syncthreads();
        for (int s = blockDim.x/2; s > 0; s >>= 1) {
            if (ti < s) sdata[ti] += sdata[ti + s];
            __syncthreads();
        }
        if (ti == 0) partial[blockIdx.x] = sdata[0];
    }
""")


# ── HIP driver helpers ────────────────────────────────────────────────────────

def _load_hip():
    """Load libamdhip64 (HIP runtime). Returns (hip_lib, hiprtc_lib) or (None, None)."""
    hip_names = {
        "Windows": ["amdhip64.dll"],
        "Linux":   ["libamdhip64.so", "libamdhip64.so.5"],
    }.get(platform.system(), [])

    rtc_names = {
        "Windows": ["hiprtc.dll"],
        "Linux":   ["libhiprtc.so", "libhiprtc.so.5"],
    }.get(platform.system(), [])

    hip_lib = rtc_lib = None
    for n in hip_names:
        try:
            hip_lib = ctypes.CDLL(n); break
        except Exception:
            pass

    for n in rtc_names:
        try:
            rtc_lib = ctypes.CDLL(n); break
        except Exception:
            pass

    return hip_lib, rtc_lib


class _HIPContext:
    """Thin wrapper around the HIP Driver / hiprtc APIs."""

    BLOCK = 256

    def __init__(self, hip, rtc):
        self._hip = hip
        self._rtc = rtc
        self._prog_cache: Dict[str, ctypes.c_void_p] = {}

    # ── memory ────────────────────────────────────────────────────────────────

    def alloc(self, nbytes: int) -> int:
        ptr = ctypes.c_void_p(0)
        r = self._hip.hipMalloc(ctypes.byref(ptr), nbytes)
        if r != 0:
            raise RuntimeError(f"hipMalloc failed: {r}")
        return ptr.value

    def free(self, ptr: int):
        self._hip.hipFree(ctypes.c_void_p(ptr))

    def upload(self, host: int, dev: int, nbytes: int):
        # hipMemcpyHtoD = 1
        self._hip.hipMemcpy(ctypes.c_void_p(dev),
                             ctypes.c_void_p(host), nbytes, ctypes.c_int(1))

    def download(self, dev: int, host: int, nbytes: int):
        # hipMemcpyDtoH = 2
        self._hip.hipMemcpy(ctypes.c_void_p(host),
                             ctypes.c_void_p(dev), nbytes, ctypes.c_int(2))

    # ── compilation ───────────────────────────────────────────────────────────

    def compile_kernel(self, src: str, fn_name: str) -> ctypes.c_void_p:
        key = fn_name
        if key in self._prog_cache:
            return self._prog_cache[key]

        # hiprtcCreateProgram
        prog = ctypes.c_void_p(0)
        src_b = src.encode()
        name_b = fn_name.encode()
        self._rtc.hiprtcCreateProgram(
            ctypes.byref(prog),
            ctypes.c_char_p(src_b),
            ctypes.c_char_p(name_b),
            0, None, None
        )
        r = self._rtc.hiprtcCompileProgram(prog, 0, None)
        if r != 0:
            raise RuntimeError(f"hiprtcCompileProgram failed: {r}")

        # Get code size & code
        sz = ctypes.c_size_t(0)
        self._rtc.hiprtcGetCodeSize(prog, ctypes.byref(sz))
        code = ctypes.create_string_buffer(sz.value)
        self._rtc.hiprtcGetCode(prog, code)
        self._rtc.hiprtcDestroyProgram(ctypes.byref(prog))

        # Load module
        mod = ctypes.c_void_p(0)
        self._hip.hipModuleLoadData(ctypes.byref(mod), code)
        fn = ctypes.c_void_p(0)
        self._hip.hipModuleGetFunction(
            ctypes.byref(fn), mod, ctypes.c_char_p(fn_name.encode()))

        self._prog_cache[key] = fn
        return fn

    # ── launch ────────────────────────────────────────────────────────────────

    def launch(self, fn, grid: Tuple[int, int, int],
               block: Tuple[int, int, int], args: List, shared: int = 0):
        c_args = []
        for a in args:
            if isinstance(a, int) and a > 0xFFFFFFFF:
                c = ctypes.c_uint64(a)
            elif isinstance(a, int):
                c = ctypes.c_int(a)
            elif isinstance(a, float):
                c = ctypes.c_float(a)
            else:
                c = a
            c_args.append(ctypes.byref(c))

        arr = (ctypes.c_void_p * len(c_args))(*c_args)
        r = self._hip.hipModuleLaunchKernel(
            fn,
            *grid, *block,
            shared, None,
            arr, None
        )
        if r != 0:
            raise RuntimeError(f"hipModuleLaunchKernel failed: {r}")
        self._hip.hipDeviceSynchronize()


# ── Plugin class ──────────────────────────────────────────────────────────────

class AMDGPUPlugin(Plugin):
    """
    AMD GPU Plugin — ROCm/HIP-accelerated kernels for UHCR.

    Registers kernels:
        amd_vec_add   – f32 element-wise addition
        amd_vec_mul   – f32 element-wise multiplication
        amd_matmul    – f32 square matrix multiply
        amd_dot       – f32 dot product (scalar result)

    Gracefully falls back to CPU if HIP is unavailable.
    """

    @property
    def name(self) -> str:
        return "gpu_amd"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, runtime) -> None:
        self._runtime = runtime
        self._hip_ctx: Optional[_HIPContext] = None
        self._available = False

        profile = runtime.get_profile()
        if not profile.gpu.rocm_available:
            print("[AMDGPUPlugin] ROCm not available — plugin inactive")
            return

        hip, rtc = _load_hip()
        if hip is None or rtc is None:
            print("[AMDGPUPlugin] Could not load HIP/hiprtc — plugin inactive")
            return

        try:
            # Init HIP device 0
            hip.hipInit(0)
            self._hip_ctx = _HIPContext(hip, rtc)

            # Pre-compile all kernels
            self._fn_vadd = self._hip_ctx.compile_kernel(_HIP_VEC_ADD, "vec_add_f32")
            self._fn_vmul = self._hip_ctx.compile_kernel(_HIP_VEC_MUL, "vec_mul_f32")
            self._fn_mm   = self._hip_ctx.compile_kernel(_HIP_MATMUL,  "matmul_f32")
            self._fn_dot  = self._hip_ctx.compile_kernel(_HIP_DOT,     "dot_f32")

            # Register in global kernel registry
            self.register_kernel("amd_vec_add", self.vec_add)
            self.register_kernel("amd_vec_mul", self.vec_mul)
            self.register_kernel("amd_matmul",  self.matmul)
            self.register_kernel("amd_dot",     self.dot)

            self._available = True
            print(f"[AMDGPUPlugin] Ready — GPU: {profile.gpu.name}")
        except Exception as exc:
            print(f"[AMDGPUPlugin] Init error: {exc} — falling back to CPU")

    def shutdown(self) -> None:
        self._hip_ctx = None
        print("[AMDGPUPlugin] Shutdown")

    @property
    def is_available(self) -> bool:
        return self._available

    # ── public API ────────────────────────────────────────────────────────────

    def vec_add(self, a_tensor, b_tensor, out_tensor=None):
        if not self._available:
            return a_tensor + b_tensor
        n = a_tensor.size; nb = n * 4
        ctx = self._hip_ctx
        da = ctx.alloc(nb); ctx.upload(a_tensor.address, da, nb)
        db = ctx.alloc(nb); ctx.upload(b_tensor.address, db, nb)
        dc = ctx.alloc(nb)
        g = ((n + ctx.BLOCK - 1) // ctx.BLOCK, 1, 1)
        ctx.launch(self._fn_vadd, g, (ctx.BLOCK, 1, 1), [da, db, dc, n])
        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0] * n, shape=a_tensor.shape, dtype=a_tensor.dtype)
        ctx.download(dc, out_tensor.address, nb)
        ctx.free(da); ctx.free(db); ctx.free(dc)
        return out_tensor

    def vec_mul(self, a_tensor, b_tensor, out_tensor=None):
        if not self._available:
            import ctypes as ct
            from uhcr.api.tensor import Tensor
            n = a_tensor.size
            out = Tensor([0.0] * n, shape=a_tensor.shape, dtype=a_tensor.dtype)
            fa = a_tensor.buffer.as_ctypes_array(ct.c_float)
            fb = b_tensor.buffer.as_ctypes_array(ct.c_float)
            fo = out.buffer.as_ctypes_array(ct.c_float)
            for i in range(n): fo[i] = fa[i] * fb[i]
            return out
        n = a_tensor.size; nb = n * 4
        ctx = self._hip_ctx
        da = ctx.alloc(nb); ctx.upload(a_tensor.address, da, nb)
        db = ctx.alloc(nb); ctx.upload(b_tensor.address, db, nb)
        dc = ctx.alloc(nb)
        g = ((n + ctx.BLOCK - 1) // ctx.BLOCK, 1, 1)
        ctx.launch(self._fn_vmul, g, (ctx.BLOCK, 1, 1), [da, db, dc, n])
        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0] * n, shape=a_tensor.shape, dtype=a_tensor.dtype)
        ctx.download(dc, out_tensor.address, nb)
        ctx.free(da); ctx.free(db); ctx.free(dc)
        return out_tensor

    def matmul(self, a_tensor, b_tensor, out_tensor=None):
        if not self._available:
            return a_tensor.matmul(b_tensor)
        M, K = a_tensor.shape; K2, N = b_tensor.shape
        assert K == K2 and M == N
        nba = M*K*4; nbb = K*N*4; nbc = M*N*4
        ctx = self._hip_ctx
        da = ctx.alloc(nba); ctx.upload(a_tensor.address, da, nba)
        db = ctx.alloc(nbb); ctx.upload(b_tensor.address, db, nbb)
        dc = ctx.alloc(nbc)
        ctx.launch(self._fn_mm, (N, M, 1), (1, 1, 1), [da, db, dc, N])
        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0]*(M*N), shape=(M,N), dtype=a_tensor.dtype)
        ctx.download(dc, out_tensor.address, nbc)
        ctx.free(da); ctx.free(db); ctx.free(dc)
        return out_tensor

    def dot(self, a_tensor, b_tensor) -> float:
        """Compute dot product of two 1-D tensors, returns a Python float."""
        if not self._available:
            import ctypes as ct
            fa = a_tensor.buffer.as_ctypes_array(ct.c_float)
            fb = b_tensor.buffer.as_ctypes_array(ct.c_float)
            return sum(fa[i] * fb[i] for i in range(a_tensor.size))
        n = a_tensor.size; nb = n * 4
        BLOCK = self._hip_ctx.BLOCK
        num_blocks = (n + BLOCK - 1) // BLOCK
        ctx = self._hip_ctx
        da = ctx.alloc(nb); ctx.upload(a_tensor.address, da, nb)
        db = ctx.alloc(nb); ctx.upload(b_tensor.address, db, nb)
        dp = ctx.alloc(num_blocks * 4)
        ctx.launch(self._fn_dot, (num_blocks, 1, 1), (BLOCK, 1, 1),
                   [da, db, dp, n], shared=BLOCK * 4)
        partial = (ctypes.c_float * num_blocks)()
        ctx.download(dp, ctypes.addressof(partial), num_blocks * 4)
        ctx.free(da); ctx.free(db); ctx.free(dp)
        return sum(partial)


def create_plugin():
    return AMDGPUPlugin()
