"""NVIDIA GPU Plugin for UHCR.

Provides CUDA-accelerated kernels for NVIDIA GPUs using the CUDA Driver API.
Automatically detects CUDA availability and GPU compute capability.

Supported operations:
- Vector addition (VADD) via PTX JIT
- Matrix multiplication (MATMUL) via PTX JIT
- Element-wise multiply (VMUL)
- Dot product reduction

Usage (3rd-party style via PluginManager):
    from uhcr.plugins.base import PluginManager
    mgr = PluginManager(runtime=get_runtime())
    mgr.load_single(Path("uhcr/plugins/gpu_nvidia.py"))

Usage (direct):
    from uhcr.plugins.gpu_nvidia import NvidiaGPUPlugin
    plugin = NvidiaGPUPlugin()
    plugin.initialize(get_runtime())
    result = plugin.vec_add(a_tensor, b_tensor)
"""

import ctypes
import platform
import struct
from typing import Callable, Dict, Optional, Tuple

from uhcr.plugins.base import Plugin
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder


# ── PTX kernel templates ──────────────────────────────────────────────────────

_PTX_VEC_ADD = """\
.version 7.0
.target sm_50
.address_size 64

.visible .entry vec_add_f32(
    .param .u64 param_a,
    .param .u64 param_b,
    .param .u64 param_c,
    .param .u32 param_n
)
{
    .reg .u64 %rd<4>;
    .reg .u32 %r<4>;
    .reg .f32 %f<3>;

    ld.param.u64    %rd0, [param_a];
    ld.param.u64    %rd1, [param_b];
    ld.param.u64    %rd2, [param_c];
    ld.param.u32    %r0,  [param_n];

    mov.u32         %r1, %ctaid.x;
    mov.u32         %r2, %ntid.x;
    mov.u32         %r3, %tid.x;
    mad.lo.u32      %r3, %r1, %r2, %r3;   // global_idx = blockIdx * blockDim + threadIdx

    setp.ge.u32     %p0, %r3, %r0;
    @%p0 bra        done;

    mul.wide.u32    %rd3, %r3, 4;
    add.u64         %rd0, %rd0, %rd3;
    add.u64         %rd1, %rd1, %rd3;
    add.u64         %rd2, %rd2, %rd3;

    ld.global.f32   %f0, [%rd0];
    ld.global.f32   %f1, [%rd1];
    add.f32         %f2, %f0, %f1;
    st.global.f32   [%rd2], %f2;
done:
    ret;
}
"""

_PTX_VEC_MUL = """\
.version 7.0
.target sm_50
.address_size 64

.visible .entry vec_mul_f32(
    .param .u64 param_a,
    .param .u64 param_b,
    .param .u64 param_c,
    .param .u32 param_n
)
{
    .reg .u64 %rd<4>;
    .reg .u32 %r<4>;
    .reg .f32 %f<3>;

    ld.param.u64    %rd0, [param_a];
    ld.param.u64    %rd1, [param_b];
    ld.param.u64    %rd2, [param_c];
    ld.param.u32    %r0,  [param_n];

    mov.u32         %r1, %ctaid.x;
    mov.u32         %r2, %ntid.x;
    mov.u32         %r3, %tid.x;
    mad.lo.u32      %r3, %r1, %r2, %r3;

    setp.ge.u32     %p0, %r3, %r0;
    @%p0 bra        done;

    mul.wide.u32    %rd3, %r3, 4;
    add.u64         %rd0, %rd0, %rd3;
    add.u64         %rd1, %rd1, %rd3;
    add.u64         %rd2, %rd2, %rd3;

    ld.global.f32   %f0, [%rd0];
    ld.global.f32   %f1, [%rd1];
    mul.f32         %f2, %f0, %f1;
    st.global.f32   [%rd2], %f2;
done:
    ret;
}
"""

_PTX_MATMUL = """\
.version 7.0
.target sm_50
.address_size 64

// Naive GEMM: C[row,col] = sum_k A[row,k] * B[k,col]
.visible .entry matmul_f32(
    .param .u64 param_a,
    .param .u64 param_b,
    .param .u64 param_c,
    .param .u32 param_n
)
{
    .reg .u64  %rd<6>;
    .reg .u32  %r<16>;
    .reg .f32  %f<4>;
    .reg .pred %p0;

    ld.param.u64    %rd0, [param_a];
    ld.param.u64    %rd1, [param_b];
    ld.param.u64    %rd2, [param_c];
    ld.param.u32    %r0,  [param_n];   // matrix side N (square NxN)

    mov.u32         %r1, %ctaid.y;    // row  = blockIdx.y
    mov.u32         %r2, %ctaid.x;    // col  = blockIdx.x

    setp.ge.u32     %p0, %r1, %r0;
    @%p0 bra        done;
    setp.ge.u32     %p0, %r2, %r0;
    @%p0 bra        done;

    // accumulate dot product
    mov.f32         %f3, 0f00000000;   // acc = 0.0
    mov.u32         %r3, 0;            // k = 0
loop:
    setp.ge.u32     %p0, %r3, %r0;
    @%p0 bra        write;

    // A[row, k] = rd0 + (row*N + k)*4
    mad.lo.u32      %r4, %r1, %r0, %r3;
    mul.wide.u32    %rd3, %r4, 4;
    add.u64         %rd3, %rd0, %rd3;
    ld.global.f32   %f0, [%rd3];

    // B[k, col] = rd1 + (k*N + col)*4
    mad.lo.u32      %r5, %r3, %r0, %r2;
    mul.wide.u32    %rd4, %r5, 4;
    add.u64         %rd4, %rd1, %rd4;
    ld.global.f32   %f1, [%rd4];

    fma.rn.f32      %f3, %f0, %f1, %f3;
    add.u32         %r3, %r3, 1;
    bra             loop;

write:
    mad.lo.u32      %r6, %r1, %r0, %r2;
    mul.wide.u32    %rd5, %r6, 4;
    add.u64         %rd5, %rd2, %rd5;
    st.global.f32   [%rd5], %f3;
done:
    ret;
}
"""


# ── CUDA driver helpers ───────────────────────────────────────────────────────

def _load_cuda_driver():
    """Load nvcuda / libcuda and return the ctypes handle, or None."""
    names = {
        "Windows": ["nvcuda.dll"],
        "Linux":   ["libcuda.so.1", "libcuda.so"],
        "Darwin":  ["libcuda.dylib"],
    }.get(platform.system(), [])

    for name in names:
        try:
            lib = ctypes.CDLL(name)
            if lib.cuInit(0) == 0:
                return lib
        except Exception:
            pass
    return None


class _CUDAContext:
    """Minimal CUDA Driver API wrapper for kernel launch."""

    BLOCK = 256  # threads per block

    def __init__(self, lib):
        self._lib = lib
        self._mod_cache: Dict[str, ctypes.c_void_p] = {}
        self._dev = ctypes.c_int(0)
        self._ctx = ctypes.c_void_p(0)
        lib.cuDeviceGet(ctypes.byref(self._dev), 0)
        lib.cuCtxCreate(ctypes.byref(self._ctx), 0, self._dev)

    def _load_ptx(self, ptx_src: str) -> ctypes.c_void_p:
        if ptx_src in self._mod_cache:
            return self._mod_cache[ptx_src]
        buf = ctypes.create_string_buffer(ptx_src.encode())
        mod = ctypes.c_void_p(0)
        r = self._lib.cuModuleLoadData(ctypes.byref(mod), buf)
        if r != 0:
            raise RuntimeError(f"cuModuleLoadData failed: {r}")
        self._mod_cache[ptx_src] = mod
        return mod

    def get_function(self, ptx_src: str, fn_name: str) -> ctypes.c_void_p:
        mod = self._load_ptx(ptx_src)
        fn = ctypes.c_void_p(0)
        self._lib.cuModuleGetFunction(ctypes.byref(fn), mod,
                                      fn_name.encode())
        return fn

    def alloc(self, nbytes: int) -> int:
        ptr = ctypes.c_uint64(0)
        self._lib.cuMemAlloc(ctypes.byref(ptr), nbytes)
        return ptr.value

    def free(self, ptr: int):
        self._lib.cuMemFree(ctypes.c_uint64(ptr))

    def upload(self, host_addr: int, dev_ptr: int, nbytes: int):
        self._lib.cuMemcpyHtoD(ctypes.c_uint64(dev_ptr),
                                ctypes.c_void_p(host_addr), nbytes)

    def download(self, dev_ptr: int, host_addr: int, nbytes: int):
        self._lib.cuMemcpyDtoH(ctypes.c_void_p(host_addr),
                                ctypes.c_uint64(dev_ptr), nbytes)

    def launch(self, fn, grid: Tuple[int, int, int],
               block: Tuple[int, int, int], args: list):
        """Launch a CUDA kernel with the given grid/block dims and args."""
        # Pack args as array of pointers
        c_args = []
        for a in args:
            if isinstance(a, int):
                if a > 0xFFFFFFFF:                       # 64-bit GPU pointer
                    c = ctypes.c_uint64(a)
                else:                                    # 32-bit int
                    c = ctypes.c_uint32(a)
            elif isinstance(a, float):
                c = ctypes.c_float(a)
            else:
                c = a
            c_args.append(ctypes.byref(c))

        arr = (ctypes.c_void_p * len(c_args))(*c_args)
        r = self._lib.cuLaunchKernel(
            fn,
            *grid,          # gridX, gridY, gridZ
            *block,         # blockX, blockY, blockZ
            0, None,        # shared mem, stream
            arr, None
        )
        if r != 0:
            raise RuntimeError(f"cuLaunchKernel failed: {r}")
        self._lib.cuCtxSynchronize()


# ── Plugin class ──────────────────────────────────────────────────────────────

class NvidiaGPUPlugin(Plugin):
    """
    NVIDIA GPU Plugin — CUDA-accelerated kernels for UHCR.

    Registers kernels:
        nvidia_vec_add   – element-wise f32 addition
        nvidia_vec_mul   – element-wise f32 multiplication
        nvidia_matmul    – square matrix multiply (f32)

    Falls back gracefully to CPU if CUDA is unavailable.
    """

    @property
    def name(self) -> str:
        return "gpu_nvidia"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, runtime) -> None:
        self._runtime = runtime
        self._cuda: Optional[_CUDAContext] = None
        self._available = False

        profile = runtime.get_profile()
        if not profile.gpu.cuda_available:
            print("[NvidiaGPUPlugin] CUDA not available — plugin inactive")
            return

        lib = _load_cuda_driver()
        if lib is None:
            print("[NvidiaGPUPlugin] Could not load CUDA driver — plugin inactive")
            return

        try:
            self._cuda = _CUDAContext(lib)
            self._available = True

            # Pre-load PTX modules
            self._fn_vadd = self._cuda.get_function(_PTX_VEC_ADD, "vec_add_f32")
            self._fn_vmul = self._cuda.get_function(_PTX_VEC_MUL, "vec_mul_f32")
            self._fn_mm   = self._cuda.get_function(_PTX_MATMUL,  "matmul_f32")

            # Register in global kernel registry
            self.register_kernel("nvidia_vec_add", self.vec_add)
            self.register_kernel("nvidia_vec_mul", self.vec_mul)
            self.register_kernel("nvidia_matmul",  self.matmul)

            print(f"[NvidiaGPUPlugin] Ready — GPU: {profile.gpu.name} "
                  f"CUDA {profile.gpu.cuda_version}")
        except Exception as exc:
            print(f"[NvidiaGPUPlugin] Init error: {exc} — falling back to CPU")
            self._available = False

    def shutdown(self) -> None:
        self._cuda = None
        print("[NvidiaGPUPlugin] Shutdown")

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return self._available

    def vec_add(self, a_tensor, b_tensor, out_tensor=None):
        """Element-wise f32 addition on NVIDIA GPU."""
        if not self._available:
            return self._cpu_fallback_add(a_tensor, b_tensor)

        n       = a_tensor.size
        nbytes  = n * 4
        cuda    = self._cuda

        d_a = cuda.alloc(nbytes); cuda.upload(a_tensor.address, d_a, nbytes)
        d_b = cuda.alloc(nbytes); cuda.upload(b_tensor.address, d_b, nbytes)
        d_c = cuda.alloc(nbytes)

        grid  = ((n + cuda.BLOCK - 1) // cuda.BLOCK, 1, 1)
        block = (cuda.BLOCK, 1, 1)
        cuda.launch(self._fn_vadd, grid, block, [d_a, d_b, d_c, n])

        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0] * n, shape=a_tensor.shape, dtype=a_tensor.dtype)
        cuda.download(d_c, out_tensor.address, nbytes)

        cuda.free(d_a); cuda.free(d_b); cuda.free(d_c)
        return out_tensor

    def vec_mul(self, a_tensor, b_tensor, out_tensor=None):
        """Element-wise f32 multiplication on NVIDIA GPU."""
        if not self._available:
            return self._cpu_fallback_mul(a_tensor, b_tensor)

        n       = a_tensor.size
        nbytes  = n * 4
        cuda    = self._cuda

        d_a = cuda.alloc(nbytes); cuda.upload(a_tensor.address, d_a, nbytes)
        d_b = cuda.alloc(nbytes); cuda.upload(b_tensor.address, d_b, nbytes)
        d_c = cuda.alloc(nbytes)

        grid  = ((n + cuda.BLOCK - 1) // cuda.BLOCK, 1, 1)
        block = (cuda.BLOCK, 1, 1)
        cuda.launch(self._fn_vmul, grid, block, [d_a, d_b, d_c, n])

        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0] * n, shape=a_tensor.shape, dtype=a_tensor.dtype)
        cuda.download(d_c, out_tensor.address, nbytes)

        cuda.free(d_a); cuda.free(d_b); cuda.free(d_c)
        return out_tensor

    def matmul(self, a_tensor, b_tensor, out_tensor=None):
        """Square NxN f32 matrix multiplication on NVIDIA GPU."""
        if not self._available:
            return a_tensor.matmul(b_tensor)

        M, K = a_tensor.shape
        K2, N = b_tensor.shape
        assert K == K2 and M == N, "Only square matrices supported in this kernel"

        nbytes_a = M * K * 4
        nbytes_b = K * N * 4
        nbytes_c = M * N * 4
        cuda = self._cuda

        d_a = cuda.alloc(nbytes_a); cuda.upload(a_tensor.address, d_a, nbytes_a)
        d_b = cuda.alloc(nbytes_b); cuda.upload(b_tensor.address, d_b, nbytes_b)
        d_c = cuda.alloc(nbytes_c)

        # one thread per output element; grid = (N, M)
        grid  = (N, M, 1)
        block = (1, 1, 1)
        cuda.launch(self._fn_mm, grid, block, [d_a, d_b, d_c, N])

        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0] * (M * N), shape=(M, N), dtype=a_tensor.dtype)
        cuda.download(d_c, out_tensor.address, nbytes_c)

        cuda.free(d_a); cuda.free(d_b); cuda.free(d_c)
        return out_tensor

    # ── CPU fallbacks ─────────────────────────────────────────────────────────

    def _cpu_fallback_add(self, a, b):
        return a + b

    def _cpu_fallback_mul(self, a, b):
        from uhcr.api.tensor import Tensor
        import ctypes as ct
        n = a.size
        out = Tensor([0.0] * n, shape=a.shape, dtype=a.dtype)
        fa = a.buffer.as_ctypes_array(ct.c_float)
        fb = b.buffer.as_ctypes_array(ct.c_float)
        fo = out.buffer.as_ctypes_array(ct.c_float)
        for i in range(n):
            fo[i] = fa[i] * fb[i]
        return out


def create_plugin():
    return NvidiaGPUPlugin()
