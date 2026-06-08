import ctypes
import os
import sys
import platform
from typing import Callable, Any, Dict, List
from uhcr.backends.backend_base import Backend, register_backend
from uhcr.compiler.ir import Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function
from uhcr.hardware.platform_info import HardwareProfile

class CUDABackend(Backend):
    """NVIDIA CUDA execution path using the dynamic CUDA Driver API (nvcuda) and PTX JIT compilation."""
    def __init__(self):
        self._initialized = False
        self._lib = None
        self._ctx = None

    @property
    def name(self) -> str:
        return "cuda"

    @property
    def priority(self) -> int:
        return 15

    def supports(self, profile: HardwareProfile) -> bool:
        return profile.gpu.cuda_available

    def _init_cuda(self) -> bool:
        """Dynamically loads and initializes the CUDA driver library."""
        if self._initialized:
            return True
            
        lib_names = []
        if platform.system() == "Windows":
            lib_names = ["nvcuda.dll"]
        elif platform.system() == "Linux":
            lib_names = ["libcuda.so", "libcuda.so.1"]
        elif platform.system() == "Darwin":
            lib_names = ["libcuda.dylib"]

        for lib_name in lib_names:
            try:
                self._lib = ctypes.CDLL(lib_name)
                # cuInit(flags)
                res = self._lib.cuInit(0)
                if res != 0:
                    continue
                
                # Get device 0
                self._dev = ctypes.c_int(0)
                res = self._lib.cuDeviceGet(ctypes.byref(self._dev), 0)
                if res != 0:
                    continue

                # Create context
                self._ctx = ctypes.c_void_p(0)
                res = self._lib.cuCtxCreate(ctypes.byref(self._ctx), 0, self._dev)
                if res != 0:
                    continue
                    
                self._initialized = True
                return True
            except (OSError, AttributeError):
                continue
        return False

    def _generate_ptx(self, func: Function) -> str:
        """Generates NVIDIA PTX assembly code for the given Function IR."""
        # Simple JIT translator from our IR to GPU PTX.
        # We look at the instruction stream. Let's support vector add and matmul templates.
        
        # Analyze block instructions
        is_vector_add = False
        is_matmul = False
        
        for block in func.blocks:
            for inst in block.instructions:
                if inst.opcode == Opcode.VADD:
                    is_vector_add = True
                elif inst.opcode == Opcode.MATMUL:
                    is_matmul = True

        if is_matmul:
            # Tiled or basic matrix multiply PTX kernel template
            return f"""
.version 7.0
.target sm_50
.address_size 64

.visible .entry matmul_kernel(
    .param .u64 matmul_kernel_param_0,  // float* A
    .param .u64 matmul_kernel_param_1,  // float* B
    .param .u64 matmul_kernel_param_2,  // float* C
    .param .u32 matmul_kernel_param_3,  // int M
    .param .u32 matmul_kernel_param_4,  // int N
    .param .u32 matmul_kernel_param_5   // int K
) {{
    .reg .pred      %p<3>;
    .reg .b32       %r<15>;
    .reg .b64       %rd<20>;
    .reg .f32       %f<10>;

    // Get block and thread indices
    mov.u32         %r1, %ctaid.x;
    mov.u32         %r2, %ntid.x;
    mov.u32         %r3, %tid.x;
    mad.lo.s32      %r4, %r1, %r2, %r3; // row = blockIdx.x * blockDim.x + threadIdx.x

    mov.u32         %r5, %ctaid.y;
    mov.u32         %r6, %ntid.y;
    mov.u32         %r7, %tid.y;
    mad.lo.s32      %r8, %r5, %r6, %r7; // col = blockIdx.y * blockDim.y + threadIdx.y

    // Load parameters
    ld.param.u64    %rd1, [matmul_kernel_param_0];
    ld.param.u64    %rd2, [matmul_kernel_param_1];
    ld.param.u64    %rd3, [matmul_kernel_param_2];
    ld.param.u32    %r9, [matmul_kernel_param_3]; // M
    ld.param.u32    %r10, [matmul_kernel_param_4]; // N
    ld.param.u32    %r11, [matmul_kernel_param_5]; // K

    // Check bounds: row < M && col < N
    setp.ge.s32     %p1, %r4, %r9;
    setp.ge.s32     %p2, %r8, %r10;
    or.pred         %p0, %p1, %p2;
    @%p0 bra        L_exit;

    // Accumulator sum = 0.0
    mov.f32         %f1, 0f00000000;
    mov.u32         %r12, 0; // k = 0

L_loop:
    // val_A = A[row * K + k]
    mad.lo.s32      %r13, %r4, %r11, %r12;
    mul.wide.s32    %rd4, %r13, 4;
    add.u64         %rd5, %rd1, %rd4;
    ld.global.f32   %f2, [%rd5];

    // val_B = B[k * N + col]
    mad.lo.s32      %r14, %r12, %r10, %r8;
    mul.wide.s32    %rd6, %r14, 4;
    add.u64         %rd7, %rd2, %rd6;
    ld.global.f32   %f3, [%rd7];

    // sum += val_A * val_B
    fma.rn.f32      %f1, %f2, %f3, %f1;

    add.s32         %r12, %r12, 1;
    setp.lt.s32     %p0, %r12, %r11;
    @%p0 bra        L_loop;

    // C[row * N + col] = sum
    mad.lo.s32      %r13, %r4, %r10, %r8;
    mul.wide.s32    %rd4, %r13, 4;
    add.u64         %rd5, %rd3, %rd4;
    st.global.f32   [%rd5], %f1;

L_exit:
    ret;
}}
"""
        else:
            # Baseline element-wise vector add PTX template
            return f"""
.version 7.0
.target sm_50
.address_size 64

.visible .entry vadd_kernel(
    .param .u64 vadd_kernel_param_0, // float* x
    .param .u64 vadd_kernel_param_1, // float* y
    .param .u64 vadd_kernel_param_2, // float* z
    .param .u32 vadd_kernel_param_3  // int n
) {{
    .reg .pred      %p0;
    .reg .b32       %r<5>;
    .reg .b64       %rd<10>;
    .reg .f32       %f<4>;

    // Thread index computation
    mov.u32         %r1, %ctaid.x;
    mov.u32         %r2, %ntid.x;
    mov.u32         %r3, %tid.x;
    mad.lo.s32      %r4, %r1, %r2, %r3; // idx = blockIdx.x * blockDim.x + threadIdx.x

    ld.param.u32    %r0, [vadd_kernel_param_3]; // load n
    setp.ge.s32     %p0, %r4, %r0;             // if idx >= n, exit
    @%p0 bra        L_exit;

    // Load pointers
    ld.param.u64    %rd1, [vadd_kernel_param_0];
    ld.param.u64    %rd2, [vadd_kernel_param_1];
    ld.param.u64    %rd3, [vadd_kernel_param_2];

    // Compute addresses: base + idx * 4
    mul.wide.s32    %rd4, %r4, 4;
    add.u64         %rd5, %rd1, %rd4;
    add.u64         %rd6, %rd2, %rd4;
    add.u64         %rd7, %rd3, %rd4;

    // Load values
    ld.global.f32   %f1, [%rd5];
    ld.global.f32   %f2, [%rd6];

    // Add values
    add.f32         %f3, %f1, %f2;

    // Store value
    st.global.f32   [%rd7], %f3;

L_exit:
    ret;
}}
"""

    def compile(self, func: Function) -> Callable:
        # Safety check before CUDA compilation
        try:
            from uhcr.native import get_safety_monitor, SafetyStatus
            monitor = get_safety_monitor()
            if monitor and monitor.is_enabled():
                # Check GPU temperature
                gpu_status = monitor.check_gpu_temperature()
                if gpu_status != SafetyStatus.OK:
                    raise RuntimeError(
                        f"GPU temperature too high for compilation: {monitor.get_last_error()}"
                    )
                
                # Check for emergency stop
                if monitor.is_emergency_stopped():
                    raise RuntimeError("Emergency stop active - cannot compile CUDA kernel")
        except ImportError:
            pass
        
        # Initialize CUDA context
        if not self._init_cuda():
            raise RuntimeError("CUDA driver initialization failed")

        ptx_source = self._generate_ptx(func)
        
        # JIT Load PTX
        ptx_bytes = ptx_source.encode('utf-8') + b'\x00'
        module = ctypes.c_void_p(0)
        
        # cuModuleLoadData(&module, ptx_bytes)
        res = self._lib.cuModuleLoadData(ctypes.byref(module), ptx_bytes)
        if res != 0:
            raise RuntimeError(f"cuModuleLoadData failed with error code: {res}")

        # Get function handle
        kernel_name = b"matmul_kernel" if "matmul" in ptx_source else b"vadd_kernel"
        kernel_fn = ctypes.c_void_p(0)
        res = self._lib.cuModuleGetFunction(ctypes.byref(kernel_fn), module, kernel_name)
        if res != 0:
            raise RuntimeError(f"cuModuleGetFunction failed with error code: {res}")

        # Construct runner function wrapper
        def cuda_runner(*args):
            # Safety check before kernel launch
            try:
                from uhcr.native import get_safety_monitor, SafetyStatus
                monitor = get_safety_monitor()
                if monitor and monitor.is_enabled():
                    # Check GPU temperature before launch
                    gpu_status = monitor.check_gpu_temperature()
                    if gpu_status != SafetyStatus.OK:
                        raise RuntimeError(
                            f"GPU temperature too high for kernel launch: {monitor.get_last_error()}"
                        )
                    
                    # Start operation timer
                    monitor.start_operation(60000)  # 1 minute timeout for GPU operations
            except ImportError:
                pass
            
            try:
                from uhcr.api.tensor import Tensor
                dev_ptrs = []
                param_values = []
            
                for i, (arg, arg_def) in enumerate(zip(args, func.arguments)):
                    if arg_def.type == Type.PTR:
                        # Allocate GPU memory
                        dev_ptr = ctypes.c_void_p(0)
                        
                        if isinstance(arg, Tensor):
                            # Host Tensor
                            ctypes_type = ctypes.c_float if arg.dtype == Type.F32 else ctypes.c_double
                            host_arr = arg.buffer.as_ctypes_array(ctypes_type)
                            size_bytes = arg.buffer.size
                            
                            res = self._lib.cuMemAlloc(ctypes.byref(dev_ptr), size_bytes)
                            if res != 0:
                                raise RuntimeError(f"cuMemAlloc failed: {res}")
                                
                            # If it is not the output tensor, copy host to device
                            is_output = (i == 2) # Index 2 is the output C or z tensor
                            if not is_output:
                                res = self._lib.cuMemcpyHtoD(dev_ptr, ctypes.byref(host_arr), size_bytes)
                                if res != 0:
                                    raise RuntimeError(f"cuMemcpyHtoD failed: {res}")
                                    
                            dev_ptrs.append((dev_ptr, host_arr, size_bytes, is_output))
                            param_values.append(ctypes.c_uint64(dev_ptr.value))
                        elif isinstance(arg, int) and arg > 1000000:
                            # Raw GPU address passed directly
                            param_values.append(ctypes.c_uint64(arg))
                        else:
                            # Host ctypes array or buffer
                            size_bytes = ctypes.sizeof(arg) if hasattr(arg, '_length_') else 4096
                            res = self._lib.cuMemAlloc(ctypes.byref(dev_ptr), size_bytes)
                            if res != 0:
                                raise RuntimeError(f"cuMemAlloc failed: {res}")
                                
                            res = self._lib.cuMemcpyHtoD(dev_ptr, ctypes.byref(arg), size_bytes)
                            if res != 0:
                                raise RuntimeError(f"cuMemcpyHtoD failed: {res}")
                                
                            dev_ptrs.append((dev_ptr, arg, size_bytes, True))
                            param_values.append(ctypes.c_uint64(dev_ptr.value))
                    else:
                        # Scalar integer or float
                        if arg_def.type == Type.I32:
                            param_values.append(ctypes.c_uint32(arg))
                        elif arg_def.type == Type.F32:
                            param_values.append(ctypes.c_float(arg))

                # Build kernel parameter pointers
                param_ptrs = [ctypes.addressof(p) for p in param_values]
                # Convert list of addresses to ctypes array of void*
                void_ptr_arr = (ctypes.c_void_p * len(param_ptrs))(*param_ptrs)

                # Launch kernel:
                # cuLaunchKernel(function, gridX, gridY, gridZ, blockX, blockY, blockZ, sharedMem, stream, kernelParams, extra)
                # Use 1D grid for vadd, 2D grid for matmul
                if b"matmul_kernel" in kernel_name:
                    M, N, K = args[3], args[4], args[5]
                    # Block size: 16x16
                    block_x, block_y = 16, 16
                    grid_x = (M + block_x - 1) // block_x
                    grid_y = (N + block_y - 1) // block_y
                    res = self._lib.cuLaunchKernel(kernel_fn, grid_x, grid_y, 1, block_x, block_y, 1, 0, None, void_ptr_arr, None)
                else:
                    n = args[3]
                    # Block size: 256
                    block_x = 256
                    grid_x = (n + block_x - 1) // block_x
                    res = self._lib.cuLaunchKernel(kernel_fn, grid_x, 1, 1, block_x, 1, 1, 0, None, void_ptr_arr, None)
                    
                if res != 0:
                    raise RuntimeError(f"cuLaunchKernel failed: {res}")

                # Synchronize context
                self._lib.cuCtxSynchronize()

                # Copy device back to host for any host-allocated outputs
                for dev_ptr, host_var, size, is_output in dev_ptrs:
                    if is_output:
                        res = self._lib.cuMemcpyDtoH(ctypes.byref(host_var), dev_ptr, size)
                        if res != 0:
                            raise RuntimeError(f"cuMemcpyDtoH failed: {res}")
                    # Free device memory
                    self._lib.cuMemFree(dev_ptr)
            
            finally:
                # End operation timer
                try:
                    from uhcr.native import get_safety_monitor
                    monitor = get_safety_monitor()
                    if monitor and monitor.is_enabled():
                        monitor.end_operation()
                except ImportError:
                    pass

        return cuda_runner

register_backend(CUDABackend())
