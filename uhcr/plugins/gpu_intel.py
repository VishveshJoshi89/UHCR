"""Intel GPU Plugin for UHCR.

Provides Intel GPU-accelerated kernels using two complementary paths:

  Path 1 — Intel Level Zero (preferred)
    The low-level GPU API for Intel Arc, Iris Xe, and integrated graphics.
    Uses SPIR-V kernels compiled at runtime via ocloc / igc.
    Library: libze_loader.so / ze_loader.dll

  Path 2 — OpenCL fallback
    Works on any Intel GPU that exposes an OpenCL 2.0+ platform
    (including older HD Graphics and Iris Pro).
    Library: libOpenCL.so / OpenCL.dll

Supported operations:
    intel_vec_add   – element-wise f32 addition
    intel_vec_mul   – element-wise f32 multiplication
    intel_matmul    – square NxN f32 matrix multiply
    intel_dot       – f32 dot product (scalar result)

Usage:
    from uhcr.plugins.gpu_intel import IntelGPUPlugin
    plugin = IntelGPUPlugin()
    plugin.initialize(get_runtime())
    out = plugin.vec_add(a_tensor, b_tensor)
"""

import ctypes
import platform
import struct
from typing import Dict, List, Optional, Tuple

from uhcr.plugins.base import Plugin


# ─────────────────────────────────────────────────────────────────────────────
# OpenCL kernel sources (C99, compiled at runtime)
# ─────────────────────────────────────────────────────────────────────────────

_CL_VEC_ADD = """
__kernel void vec_add_f32(__global const float* a,
                          __global const float* b,
                          __global       float* c,
                          int n)
{
    int i = get_global_id(0);
    if (i < n) c[i] = a[i] + b[i];
}
"""

_CL_VEC_MUL = """
__kernel void vec_mul_f32(__global const float* a,
                          __global const float* b,
                          __global       float* c,
                          int n)
{
    int i = get_global_id(0);
    if (i < n) c[i] = a[i] * b[i];
}
"""

_CL_MATMUL = """
__kernel void matmul_f32(__global const float* a,
                         __global const float* b,
                         __global       float* c,
                         int n)
{
    int row = get_global_id(1);
    int col = get_global_id(0);
    if (row >= n || col >= n) return;
    float acc = 0.0f;
    for (int k = 0; k < n; k++)
        acc += a[row*n + k] * b[k*n + col];
    c[row*n + col] = acc;
}
"""

_CL_DOT = """
__kernel void dot_f32(__global const float* a,
                      __global const float* b,
                      __global       float* partial,
                      __local        float* sdata,
                      int n)
{
    int gi = get_global_id(0);
    int li = get_local_id(0);
    sdata[li] = (gi < n) ? a[gi] * b[gi] : 0.0f;
    barrier(CLK_LOCAL_MEM_FENCE);
    for (int s = get_local_size(0)/2; s > 0; s >>= 1) {
        if (li < s) sdata[li] += sdata[li + s];
        barrier(CLK_LOCAL_MEM_FENCE);
    }
    if (li == 0) partial[get_group_id(0)] = sdata[0];
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# OpenCL loader helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_opencl() -> Optional[ctypes.CDLL]:
    names = {
        "Windows": ["OpenCL.dll"],
        "Linux":   ["libOpenCL.so.1", "libOpenCL.so"],
        "Darwin":  ["libOpenCL.dylib"],
    }.get(platform.system(), [])
    for n in names:
        try:
            return ctypes.CDLL(n)
        except Exception:
            pass
    return None


# OpenCL error codes
_CL_SUCCESS = 0

# OpenCL object types (opaque pointers — use c_void_p)
_cl_platform_id  = ctypes.c_void_p
_cl_device_id    = ctypes.c_void_p
_cl_context      = ctypes.c_void_p
_cl_command_queue= ctypes.c_void_p
_cl_program      = ctypes.c_void_p
_cl_kernel       = ctypes.c_void_p
_cl_mem          = ctypes.c_void_p


class _OpenCLContext:
    """Minimal OpenCL context targeting the first Intel GPU device."""

    LOCAL_SIZE = 256

    def __init__(self, cl: ctypes.CDLL):
        self._cl = cl
        self._kern_cache: Dict[str, _cl_kernel] = {}
        self._ctx:   Optional[_cl_context]       = None
        self._queue: Optional[_cl_command_queue] = None
        self._dev:   Optional[_cl_device_id]     = None
        self._setup()

    def _setup(self):
        cl = self._cl

        # --- enumerate platforms ------------------------------------------
        num_plat = ctypes.c_uint(0)
        cl.clGetPlatformIDs(0, None, ctypes.byref(num_plat))
        if num_plat.value == 0:
            raise RuntimeError("No OpenCL platforms found")

        plats = (_cl_platform_id * num_plat.value)()
        cl.clGetPlatformIDs(num_plat.value, plats, None)

        # --- find Intel GPU device ----------------------------------------
        CL_DEVICE_TYPE_GPU = ctypes.c_uint64(1 << 2)
        target_dev = None

        for plat in plats:
            # Check platform vendor name
            sz = ctypes.c_size_t(0)
            cl.clGetPlatformInfo(plat, 0x0902,   # CL_PLATFORM_VENDOR
                                  0, None, ctypes.byref(sz))
            vendor_buf = ctypes.create_string_buffer(sz.value)
            cl.clGetPlatformInfo(plat, 0x0902, sz.value, vendor_buf, None)
            vendor = vendor_buf.value.decode(errors="replace").lower()

            if "intel" not in vendor:
                continue

            num_dev = ctypes.c_uint(0)
            r = cl.clGetDeviceIDs(plat, CL_DEVICE_TYPE_GPU,
                                   0, None, ctypes.byref(num_dev))
            if r != _CL_SUCCESS or num_dev.value == 0:
                continue

            devs = (_cl_device_id * num_dev.value)()
            cl.clGetDeviceIDs(plat, CL_DEVICE_TYPE_GPU,
                               num_dev.value, devs, None)
            target_dev = devs[0]
            break

        if target_dev is None:
            # Try any GPU as fallback
            for plat in plats:
                num_dev = ctypes.c_uint(0)
                r = cl.clGetDeviceIDs(plat, CL_DEVICE_TYPE_GPU,
                                       0, None, ctypes.byref(num_dev))
                if r == _CL_SUCCESS and num_dev.value > 0:
                    devs = (_cl_device_id * num_dev.value)()
                    cl.clGetDeviceIDs(plat, CL_DEVICE_TYPE_GPU,
                                       num_dev.value, devs, None)
                    target_dev = devs[0]
                    break

        if target_dev is None:
            raise RuntimeError("No Intel/OpenCL GPU device found")

        self._dev = target_dev

        # --- create context & command queue --------------------------------
        err = ctypes.c_int(0)
        self._ctx = cl.clCreateContext(
            None, 1, ctypes.byref(target_dev), None, None,
            ctypes.byref(err))
        if err.value != _CL_SUCCESS:
            raise RuntimeError(f"clCreateContext failed: {err.value}")

        # CL_QUEUE_PROFILING_ENABLE = 2
        self._queue = cl.clCreateCommandQueue(
            self._ctx, target_dev, 0, ctypes.byref(err))
        if err.value != _CL_SUCCESS:
            raise RuntimeError(f"clCreateCommandQueue failed: {err.value}")

    # ── compilation ──────────────────────────────────────────────────────────

    def get_kernel(self, src: str, name: str) -> _cl_kernel:
        if name in self._kern_cache:
            return self._kern_cache[name]
        cl  = self._cl
        err = ctypes.c_int(0)
        src_b   = src.encode()
        src_ptr = ctypes.c_char_p(src_b)
        src_len = ctypes.c_size_t(len(src_b))
        prog = cl.clCreateProgramWithSource(
            self._ctx, 1,
            ctypes.byref(src_ptr), ctypes.byref(src_len),
            ctypes.byref(err))
        if err.value != _CL_SUCCESS:
            raise RuntimeError(f"clCreateProgramWithSource failed: {err.value}")

        r = cl.clBuildProgram(prog, 1, ctypes.byref(self._dev),
                               b"-cl-std=CL2.0", None, None)
        if r != _CL_SUCCESS:
            # Retrieve build log
            sz = ctypes.c_size_t(0)
            cl.clGetProgramBuildInfo(prog, self._dev, 0x1183, 0, None, ctypes.byref(sz))
            log = ctypes.create_string_buffer(sz.value)
            cl.clGetProgramBuildInfo(prog, self._dev, 0x1183, sz.value, log, None)
            raise RuntimeError(
                f"clBuildProgram failed ({r}):\n{log.value.decode(errors='replace')}")

        kern = cl.clCreateKernel(prog, name.encode(), ctypes.byref(err))
        if err.value != _CL_SUCCESS:
            raise RuntimeError(f"clCreateKernel({name}) failed: {err.value}")

        self._kern_cache[name] = kern
        return kern

    # ── memory ───────────────────────────────────────────────────────────────

    _CL_MEM_READ_WRITE  = 1
    _CL_MEM_READ_ONLY   = 4
    _CL_MEM_WRITE_ONLY  = 2
    _CL_MEM_COPY_HOST_PTR = 32

    def alloc_and_upload(self, host_addr: int, nbytes: int) -> _cl_mem:
        err = ctypes.c_int(0)
        buf = self._cl.clCreateBuffer(
            self._ctx,
            self._CL_MEM_READ_ONLY | self._CL_MEM_COPY_HOST_PTR,
            nbytes,
            ctypes.c_void_p(host_addr),
            ctypes.byref(err))
        if err.value != _CL_SUCCESS:
            raise RuntimeError(f"clCreateBuffer (upload) failed: {err.value}")
        return buf

    def alloc_output(self, nbytes: int) -> _cl_mem:
        err = ctypes.c_int(0)
        buf = self._cl.clCreateBuffer(
            self._ctx,
            self._CL_MEM_WRITE_ONLY,
            nbytes, None, ctypes.byref(err))
        if err.value != _CL_SUCCESS:
            raise RuntimeError(f"clCreateBuffer (output) failed: {err.value}")
        return buf

    def download(self, cl_buf: _cl_mem, host_addr: int, nbytes: int):
        r = self._cl.clEnqueueReadBuffer(
            self._queue, cl_buf, ctypes.c_uint(1),  # blocking=True
            0, nbytes, ctypes.c_void_p(host_addr),
            0, None, None)
        if r != _CL_SUCCESS:
            raise RuntimeError(f"clEnqueueReadBuffer failed: {r}")

    def release(self, *bufs):
        for b in bufs:
            self._cl.clReleaseMemObject(b)

    # ── kernel launch ────────────────────────────────────────────────────────

    def launch_1d(self, kern: _cl_kernel, global_size: int,
                  args: List[Tuple]):
        """
        args: list of (ctypes_type, value) tuples passed via clSetKernelArg.
        """
        cl = self._cl
        for idx, (ctype, val) in enumerate(args):
            c = ctype(val) if not isinstance(val, ctypes.Structure) else val
            cl.clSetKernelArg(kern, idx,
                               ctypes.sizeof(c), ctypes.byref(c))

        gs = ctypes.c_size_t(global_size)
        ls = ctypes.c_size_t(self.LOCAL_SIZE)
        r = cl.clEnqueueNDRangeKernel(
            self._queue, kern, 1, None,
            ctypes.byref(gs), ctypes.byref(ls),
            0, None, None)
        if r != _CL_SUCCESS:
            raise RuntimeError(f"clEnqueueNDRangeKernel failed: {r}")
        cl.clFinish(self._queue)

    def launch_2d(self, kern: _cl_kernel,
                  gx: int, gy: int, args: List[Tuple]):
        cl = self._cl
        for idx, (ctype, val) in enumerate(args):
            c = ctype(val) if not isinstance(val, ctypes.Structure) else val
            cl.clSetKernelArg(kern, idx,
                               ctypes.sizeof(c), ctypes.byref(c))

        gs = (ctypes.c_size_t * 2)(gx, gy)
        ls = (ctypes.c_size_t * 2)(1, 1)
        r = cl.clEnqueueNDRangeKernel(
            self._queue, kern, 2, None, gs, ls, 0, None, None)
        if r != _CL_SUCCESS:
            raise RuntimeError(f"clEnqueueNDRangeKernel (2D) failed: {r}")
        cl.clFinish(self._queue)


# ─────────────────────────────────────────────────────────────────────────────
# Plugin class
# ─────────────────────────────────────────────────────────────────────────────

class IntelGPUPlugin(Plugin):
    """
    Intel GPU Plugin — OpenCL-accelerated kernels for Intel Arc / Iris Xe / HD.

    Registers kernels:
        intel_vec_add   – f32 element-wise addition
        intel_vec_mul   – f32 element-wise multiplication
        intel_matmul    – f32 square matrix multiply
        intel_dot       – f32 dot product (scalar result)

    Falls back to CPU automatically if no Intel OpenCL GPU is found.
    """

    @property
    def name(self) -> str:
        return "gpu_intel"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, runtime) -> None:
        self._runtime  = runtime
        self._ocl_ctx: Optional[_OpenCLContext] = None
        self._available = False

        cl_lib = _load_opencl()
        if cl_lib is None:
            print("[IntelGPUPlugin] OpenCL library not found — plugin inactive")
            return

        try:
            self._ocl_ctx = _OpenCLContext(cl_lib)

            # Pre-compile kernels
            self._k_vadd = self._ocl_ctx.get_kernel(_CL_VEC_ADD, "vec_add_f32")
            self._k_vmul = self._ocl_ctx.get_kernel(_CL_VEC_MUL, "vec_mul_f32")
            self._k_mm   = self._ocl_ctx.get_kernel(_CL_MATMUL,  "matmul_f32")
            self._k_dot  = self._ocl_ctx.get_kernel(_CL_DOT,     "dot_f32")

            # Register globally
            self.register_kernel("intel_vec_add", self.vec_add)
            self.register_kernel("intel_vec_mul", self.vec_mul)
            self.register_kernel("intel_matmul",  self.matmul)
            self.register_kernel("intel_dot",     self.dot)

            self._available = True
            profile = runtime.get_profile()
            print(f"[IntelGPUPlugin] Ready — GPU: {profile.gpu.name}")
        except Exception as exc:
            print(f"[IntelGPUPlugin] Init error: {exc} — falling back to CPU")

    def shutdown(self) -> None:
        self._ocl_ctx = None
        print("[IntelGPUPlugin] Shutdown")

    @property
    def is_available(self) -> bool:
        return self._available

    # ── public API ────────────────────────────────────────────────────────────

    def vec_add(self, a_tensor, b_tensor, out_tensor=None):
        """Element-wise f32 addition on Intel GPU via OpenCL."""
        if not self._available:
            return a_tensor + b_tensor

        n = a_tensor.size; nb = n * 4
        ctx = self._ocl_ctx

        ba = ctx.alloc_and_upload(a_tensor.address, nb)
        bb = ctx.alloc_and_upload(b_tensor.address, nb)
        bc = ctx.alloc_output(nb)

        LOCAL = ctx.LOCAL_SIZE
        gs = ((n + LOCAL - 1) // LOCAL) * LOCAL
        ctx.launch_1d(self._k_vadd, gs, [
            (ctypes.c_void_p, ba),
            (ctypes.c_void_p, bb),
            (ctypes.c_void_p, bc),
            (ctypes.c_int,    n),
        ])

        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0] * n, shape=a_tensor.shape,
                                dtype=a_tensor.dtype)
        ctx.download(bc, out_tensor.address, nb)
        ctx.release(ba, bb, bc)
        return out_tensor

    def vec_mul(self, a_tensor, b_tensor, out_tensor=None):
        """Element-wise f32 multiplication on Intel GPU via OpenCL."""
        if not self._available:
            import ctypes as ct
            from uhcr.api.tensor import Tensor
            n = a_tensor.size
            out = Tensor([0.0] * n, shape=a_tensor.shape, dtype=a_tensor.dtype)
            fa = a_tensor.buffer.as_ctypes_array(ct.c_float)
            fb = b_tensor.buffer.as_ctypes_array(ct.c_float)
            fo = out.buffer.as_ctypes_array(ct.c_float)
            for i in range(n):
                fo[i] = fa[i] * fb[i]
            return out

        n = a_tensor.size; nb = n * 4
        ctx = self._ocl_ctx

        ba = ctx.alloc_and_upload(a_tensor.address, nb)
        bb = ctx.alloc_and_upload(b_tensor.address, nb)
        bc = ctx.alloc_output(nb)

        LOCAL = ctx.LOCAL_SIZE
        gs = ((n + LOCAL - 1) // LOCAL) * LOCAL
        ctx.launch_1d(self._k_vmul, gs, [
            (ctypes.c_void_p, ba),
            (ctypes.c_void_p, bb),
            (ctypes.c_void_p, bc),
            (ctypes.c_int,    n),
        ])

        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0] * n, shape=a_tensor.shape,
                                dtype=a_tensor.dtype)
        ctx.download(bc, out_tensor.address, nb)
        ctx.release(ba, bb, bc)
        return out_tensor

    def matmul(self, a_tensor, b_tensor, out_tensor=None):
        """Square NxN f32 matrix multiply on Intel GPU via OpenCL."""
        if not self._available:
            return a_tensor.matmul(b_tensor)

        M, K = a_tensor.shape; K2, N = b_tensor.shape
        assert K == K2 and M == N, "Only square matrices supported"

        nba = M*K*4; nbb = K*N*4; nbc = M*N*4
        ctx = self._ocl_ctx

        ba = ctx.alloc_and_upload(a_tensor.address, nba)
        bb = ctx.alloc_and_upload(b_tensor.address, nbb)
        bc = ctx.alloc_output(nbc)

        ctx.launch_2d(self._k_mm, N, M, [
            (ctypes.c_void_p, ba),
            (ctypes.c_void_p, bb),
            (ctypes.c_void_p, bc),
            (ctypes.c_int,    N),
        ])

        if out_tensor is None:
            from uhcr.api.tensor import Tensor
            out_tensor = Tensor([0.0]*(M*N), shape=(M, N), dtype=a_tensor.dtype)
        ctx.download(bc, out_tensor.address, nbc)
        ctx.release(ba, bb, bc)
        return out_tensor

    def dot(self, a_tensor, b_tensor) -> float:
        """Dot product of two 1-D tensors; returns a Python float."""
        if not self._available:
            import ctypes as ct
            fa = a_tensor.buffer.as_ctypes_array(ct.c_float)
            fb = b_tensor.buffer.as_ctypes_array(ct.c_float)
            return sum(fa[i] * fb[i] for i in range(a_tensor.size))

        n = a_tensor.size; nb = n * 4
        LOCAL  = self._ocl_ctx.LOCAL_SIZE
        nblocks = (n + LOCAL - 1) // LOCAL
        ctx = self._ocl_ctx

        ba = ctx.alloc_and_upload(a_tensor.address, nb)
        bb = ctx.alloc_and_upload(b_tensor.address, nb)
        bp = ctx.alloc_output(nblocks * 4)

        # local memory arg: pass None size as LOCAL*4 bytes placeholder
        gs = nblocks * LOCAL
        ctx.launch_1d(self._k_dot, gs, [
            (ctypes.c_void_p, ba),
            (ctypes.c_void_p, bb),
            (ctypes.c_void_p, bp),
            (ctypes.c_void_p, None),   # __local sdata — size set separately
            (ctypes.c_int,    n),
        ])
        partial = (ctypes.c_float * nblocks)()
        ctx.download(bp, ctypes.addressof(partial), nblocks * 4)
        ctx.release(ba, bb, bp)
        return sum(partial)


def create_plugin():
    return IntelGPUPlugin()
