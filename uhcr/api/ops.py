import ctypes
from uhcr import get_runtime
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder
from uhcr.runtime.memory_manager import AlignedBuffer
from uhcr.api.tensor import Tensor

def dispatch_vadd(x: Tensor, y: Tensor, out: Tensor):
    """Compiles and executes an element-wise vector addition using the best available backend."""
    rt = get_runtime()
    
    # Check if we can run via CUDA
    if rt.get_profile().gpu.cuda_available:
        # CUDA backend handles element-wise operations directly via its PTX vadd template
        builder = IRBuilder()
        builder.new_module()
        # CUDA expects: float* x, float* y, float* z, int n
        func = builder.new_function("cuda_vadd", [Type.PTR, Type.PTR, Type.PTR, Type.I32], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # Emit dummy vector add so the backend detects it as vector add
        vx = builder.vload(func.arguments[0], 0, Type.V8F32)
        vy = builder.vload(func.arguments[1], 0, Type.V8F32)
        vz = builder.vadd(vx, vy)
        builder.vstore(vz, func.arguments[2], 0)
        builder.ret()
        
        fn = rt.compile(func)
        # CUDA runner expects Tensor objects for proper GPU memory management
        fn(x, y, out, x.size)
        return

    # CPU path: we use a vector loop. To avoid phi nodes, we pass an index pointer!
    builder = IRBuilder()
    builder.new_module()
    
    # Arguments: float* x, float* y, float* out, int n, int* idx_ptr
    func = builder.new_function("cpu_vadd", [Type.PTR, Type.PTR, Type.PTR, Type.I32, Type.PTR], Type.VOID)
    
    entry = func.create_block("entry")
    loop_cond = func.create_block("loop_cond")
    loop_body = func.create_block("loop_body")
    exit_blk = func.create_block("exit")
    
    # entry:
    builder.set_block(entry)
    # Initialize index to 0: store 0, idx_ptr, 0
    builder.store(0, func.arguments[4], 0)
    builder.jmp(loop_cond)
    
    # loop_cond:
    builder.set_block(loop_cond)
    # load index: %idx = load idx_ptr, 0
    idx = builder.load(func.arguments[4], 0, Type.I32)
    # cond = %idx < %n
    n = func.arguments[3]
    cond = builder.cmp("lt", idx, n)
    builder.br(cond, loop_body, exit_blk)
    
    # loop_body:
    builder.set_block(loop_body)
    # Determine step size: if AVX2 is supported, we load 8 floats (V8F32)
    use_avx2 = rt.get_profile().cpu.has_avx2
    step = 8 if use_avx2 else 1
    
    if use_avx2:
        vx = builder.vload(func.arguments[0], idx, Type.V8F32)
        vy = builder.vload(func.arguments[1], idx, Type.V8F32)
        vz = builder.vadd(vx, vy)
        builder.vstore(vz, func.arguments[2], idx)
    else:
        # Scalar fallback
        vx = builder.load(func.arguments[0], idx, Type.F32)
        vy = builder.load(func.arguments[1], idx, Type.F32)
        vz = builder.add(vx, vy)
        builder.store(vz, func.arguments[2], idx)
        
    # Increment index: %idx_next = %idx + step
    idx_next = builder.add(idx, step)
    # store index: store %idx_next, idx_ptr, 0
    builder.store(idx_next, func.arguments[4], 0)
    builder.jmp(loop_cond)
    
    # exit:
    builder.set_block(exit_blk)
    builder.ret()
    
    # Compile
    fn = rt.compile(func)
    
    # Allocate temporary index variable on host
    with AlignedBuffer(4, alignment=64) as idx_buf:
        # Cast address to pass to runner
        fn(x.address, y.address, out.address, x.size, idx_buf.address)

def dispatch_matmul(A: Tensor, B: Tensor, C: Tensor):
    """Compiles and executes matrix multiplication using the best available backend."""
    import ctypes
    
    M, K = A.shape
    K2, N = B.shape
    
    # Try CUDA path first (only if truly available and functional)
    try:
        rt = get_runtime()
        if rt.get_profile().gpu.cuda_available:
            builder = IRBuilder()
            builder.new_module()
            func = builder.new_function("cuda_matmul", [Type.PTR, Type.PTR, Type.PTR, Type.I32, Type.I32, Type.I32], Type.VOID)
            entry = func.create_block("entry")
            builder.set_block(entry)
            builder.matmul(func.arguments[0], func.arguments[1], func.arguments[2])
            builder.ret()
            
            from uhcr.backends.cuda_backend import CUDABackend
            cuda = CUDABackend()
            if cuda._init_cuda():
                fn = cuda.compile(func)
                fn(A, B, C, M, N, K)
                return
    except Exception:
        pass
    
    # CPU path — pure Python matmul (safe, no native codegen)
    float_size = ctypes.sizeof(ctypes.c_float)
    ptr_a = A.address
    ptr_b = B.address
    ptr_c = C.address
    
    for i in range(M):
        for j in range(N):
            acc = 0.0
            for k in range(K):
                a_val = ctypes.c_float.from_address(ptr_a + (i * K + k) * float_size).value
                b_val = ctypes.c_float.from_address(ptr_b + (k * N + j) * float_size).value
                acc += a_val * b_val
            ctypes.c_float.from_address(ptr_c + (i * N + j) * float_size).value = acc
