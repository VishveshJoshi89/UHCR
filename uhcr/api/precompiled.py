"""Pre-compiled common operations for zero compilation overhead."""

from uhcr import get_runtime
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder
from typing import Dict, Callable

# Global cache of pre-compiled operations
_precompiled_ops: Dict[str, Callable] = {}

def _precompile_scalar_ops():
    """Pre-compile common scalar operations."""
    rt = get_runtime()
    
    # Scalar add: i64 + i64
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("add_i64", [Type.I64, Type.I64], Type.I64)
    entry = func.create_block("entry")
    builder.set_block(entry)
    result = builder.add(func.arguments[0], func.arguments[1])
    builder.ret(result)
    _precompiled_ops['add_i64'] = rt.compile(func)
    
    # Scalar multiply: i64 * i64
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("mul_i64", [Type.I64, Type.I64], Type.I64)
    entry = func.create_block("entry")
    builder.set_block(entry)
    result = builder.mul(func.arguments[0], func.arguments[1])
    builder.ret(result)
    _precompiled_ops['mul_i64'] = rt.compile(func)
    
    # Scalar sub: i64 - i64
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("sub_i64", [Type.I64, Type.I64], Type.I64)
    entry = func.create_block("entry")
    builder.set_block(entry)
    result = builder.sub(func.arguments[0], func.arguments[1])
    builder.ret(result)
    _precompiled_ops['sub_i64'] = rt.compile(func)


def _precompile_array_ops():
    """Pre-compile common array operations at different sizes."""
    rt = get_runtime()
    
    # Pre-compile vector add for common sizes
    for size in [64, 256, 1000, 4096]:
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function(f"vadd_{size}", [Type.PTR, Type.PTR, Type.PTR, Type.I32], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # Unrolled loop for performance
        unroll = min(8, size)
        for i in range(0, size, unroll):
            for j in range(unroll):
                if i + j < size:
                    a = builder.load(func.arguments[0], i + j, Type.F32)
                    b = builder.load(func.arguments[1], i + j, Type.F32)
                    c = builder.add(a, b)
                    builder.store(c, func.arguments[2], i + j)
        
        builder.ret()
        _precompiled_ops[f'vadd_{size}'] = rt.compile(func)


def get_precompiled_op(name: str) -> Callable:
    """Get a pre-compiled operation."""
    return _precompiled_ops.get(name)


def initialize_precompiled_ops():
    """Initialize all pre-compiled operations. Call once at module load."""
    try:
        _precompile_scalar_ops()
        _precompile_array_ops()
    except Exception as e:
        # If precompilation fails, operations will compile on-demand
        print(f"Warning: Precompilation failed: {e}")


# Auto-initialize on import
initialize_precompiled_ops()
