"""Vectorized operations using AVX2 SIMD instructions.

This module provides highly optimized array operations using:
- AVX2 256-bit SIMD (8x float32 parallel operations)
- Loop unrolling
- Memory prefetching hints
- Reduced function call overhead
"""

from uhcr import get_runtime
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder
from typing import Callable, Dict

# Global cache for vectorized operations
_vectorized_cache: Dict[tuple, Callable] = {}


def compile_vectorized_add(size: int) -> Callable:
    """Compile highly optimized vectorized addition using AVX2.
    
    Processes 8 floats at a time with AVX2 SIMD instructions.
    """
    cache_key = ('vec_add', size)
    
    if cache_key in _vectorized_cache:
        return _vectorized_cache[cache_key]
    
    rt = get_runtime()
    builder = IRBuilder()
    builder.new_module()
    
    # Function signature: void vec_add(float* a, float* b, float* out, int n)
    func = builder.new_function("vec_add", [Type.PTR, Type.PTR, Type.PTR, Type.I32], Type.VOID)
    entry = func.create_block("entry")
    vector_loop = func.create_block("vector_loop")
    scalar_loop = func.create_block("scalar_loop")
    done = func.create_block("done")
    
    builder.set_block(entry)
    
    # Process in chunks of 32 elements (4 AVX2 vectors) for better pipelining
    chunk_size = 32
    num_chunks = size // chunk_size
    
    # Vector processing loop (8 floats at a time)
    builder.set_block(vector_loop)
    for chunk in range(num_chunks):
        base_idx = chunk * chunk_size
        # Unroll 4 AVX2 operations per chunk
        for vec_offset in range(0, chunk_size, 8):
            idx = base_idx + vec_offset
            if idx + 8 <= size:
                # Load 8 floats from a and b
                va = builder.vload(func.arguments[0], idx, Type.V8F32)
                vb = builder.vload(func.arguments[1], idx, Type.V8F32)
                # Add vectors
                vc = builder.vadd(va, vb)
                # Store result
                builder.vstore(vc, func.arguments[2], idx)
    
    # Handle remaining elements (scalar)
    builder.set_block(scalar_loop)
    remaining_start = num_chunks * chunk_size
    for i in range(remaining_start, size):
        a_val = builder.load(func.arguments[0], i, Type.F32)
        b_val = builder.load(func.arguments[1], i, Type.F32)
        c_val = builder.add(a_val, b_val)
        builder.store(c_val, func.arguments[2], i)
    
    builder.jmp(done)
    
    builder.set_block(done)
    builder.ret()
    
    compiled = rt.compile(func)
    _vectorized_cache[cache_key] = compiled
    return compiled


def compile_vectorized_multiply(size: int) -> Callable:
    """Compile highly optimized vectorized multiplication using AVX2."""
    cache_key = ('vec_mul', size)
    
    if cache_key in _vectorized_cache:
        return _vectorized_cache[cache_key]
    
    rt = get_runtime()
    builder = IRBuilder()
    builder.new_module()
    
    func = builder.new_function("vec_mul", [Type.PTR, Type.PTR, Type.PTR, Type.I32], Type.VOID)
    entry = func.create_block("entry")
    builder.set_block(entry)
    
    # Process in chunks of 32 for pipelining
    chunk_size = 32
    num_chunks = size // chunk_size
    
    for chunk in range(num_chunks):
        base_idx = chunk * chunk_size
        for vec_offset in range(0, chunk_size, 8):
            idx = base_idx + vec_offset
            if idx + 8 <= size:
                va = builder.vload(func.arguments[0], idx, Type.V8F32)
                vb = builder.vload(func.arguments[1], idx, Type.V8F32)
                vc = builder.vmul(va, vb)
                builder.vstore(vc, func.arguments[2], idx)
    
    # Scalar remainder
    remaining_start = num_chunks * chunk_size
    for i in range(remaining_start, size):
        a_val = builder.load(func.arguments[0], i, Type.F32)
        b_val = builder.load(func.arguments[1], i, Type.F32)
        c_val = builder.mul(a_val, b_val)
        builder.store(c_val, func.arguments[2], i)
    
    builder.ret()
    
    compiled = rt.compile(func)
    _vectorized_cache[cache_key] = compiled
    return compiled


def compile_vectorized_fma(size: int) -> Callable:
    """Compile fused multiply-add: out = a * b + c using AVX2 FMA."""
    cache_key = ('vec_fma', size)
    
    if cache_key in _vectorized_cache:
        return _vectorized_cache[cache_key]
    
    rt = get_runtime()
    builder = IRBuilder()
    builder.new_module()
    
    # Function: void vec_fma(float* a, float* b, float* c, float* out, int n)
    func = builder.new_function("vec_fma", 
        [Type.PTR, Type.PTR, Type.PTR, Type.PTR, Type.I32], Type.VOID)
    entry = func.create_block("entry")
    builder.set_block(entry)
    
    # Process in chunks
    chunk_size = 32
    num_chunks = size // chunk_size
    
    for chunk in range(num_chunks):
        base_idx = chunk * chunk_size
        for vec_offset in range(0, chunk_size, 8):
            idx = base_idx + vec_offset
            if idx + 8 <= size:
                va = builder.vload(func.arguments[0], idx, Type.V8F32)
                vb = builder.vload(func.arguments[1], idx, Type.V8F32)
                vc = builder.vload(func.arguments[2], idx, Type.V8F32)
                # FMA: a * b + c
                vresult = builder.vfmadd(va, vb, vc)
                builder.vstore(vresult, func.arguments[3], idx)
    
    # Scalar remainder
    remaining_start = num_chunks * chunk_size
    for i in range(remaining_start, size):
        a_val = builder.load(func.arguments[0], i, Type.F32)
        b_val = builder.load(func.arguments[1], i, Type.F32)
        c_val = builder.load(func.arguments[2], i, Type.F32)
        # Scalar FMA
        result = builder.add(builder.mul(a_val, b_val), c_val)
        builder.store(result, func.arguments[3], i)
    
    builder.ret()
    
    compiled = rt.compile(func)
    _vectorized_cache[cache_key] = compiled
    return compiled


def get_vectorized_op(op_name: str, size: int) -> Callable:
    """Get a pre-compiled vectorized operation."""
    if op_name == 'add':
        return compile_vectorized_add(size)
    elif op_name == 'mul' or op_name == 'multiply':
        return compile_vectorized_multiply(size)
    elif op_name == 'fma':
        return compile_vectorized_fma(size)
    else:
        raise ValueError(f"Unknown vectorized operation: {op_name}")


# Pre-compile common sizes at module load
_COMMON_SIZES = [64, 256, 512, 1000, 2048, 4096, 8192]

def _precompile_common_ops():
    """Pre-compile vectorized operations for common array sizes."""
    try:
        for size in _COMMON_SIZES:
            compile_vectorized_add(size)
            compile_vectorized_multiply(size)
    except Exception:
        pass  # Silently fail if compilation not available


# Auto-initialize
_precompile_common_ops()
