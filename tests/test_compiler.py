"""Tests for the compiler pipeline (IR, IRBuilder, codegen)."""
import platform
import ctypes
import pytest

from uhcr.compiler.ir import Type, Opcode, Function, BasicBlock, Module
from uhcr.compiler.ir_builder import IRBuilder


def test_ir_types():
    assert Type.I32.value == "i32"
    assert Type.F32.value == "f32"
    assert Type.V8F32.value == "v8f32"
    assert Type.PTR.value == "ptr"


def test_ir_builder_creates_module():
    builder = IRBuilder()
    mod = builder.new_module()
    assert isinstance(mod, Module)


def test_ir_builder_creates_function():
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("test_fn", [Type.I32, Type.I32], Type.I32)
    assert func.name == "test_fn"
    assert len(func.arguments) == 2
    assert func.return_type == Type.I32


def test_ir_builder_add():
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("add", [Type.I32, Type.I32], Type.I32)
    entry = func.create_block("entry")
    builder.set_block(entry)
    result = builder.add(func.arguments[0], func.arguments[1])
    builder.ret(result)

    assert len(func.blocks) == 1
    assert len(entry.instructions) == 2  # add + ret
    assert entry.instructions[0].opcode == Opcode.ADD


def test_ir_builder_vector_ops():
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("vadd", [Type.PTR, Type.PTR, Type.PTR], Type.VOID)
    entry = func.create_block("entry")
    builder.set_block(entry)

    va = builder.vload(func.arguments[0], 0, Type.V8F32)
    vb = builder.vload(func.arguments[1], 0, Type.V8F32)
    vc = builder.vadd(va, vb)
    builder.vstore(vc, func.arguments[2], 0)
    builder.ret()

    assert va.type == Type.V8F32
    assert vc.opcode == Opcode.VADD


def test_ir_validation():
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("valid", [Type.I32], Type.I32)
    entry = func.create_block("entry")
    builder.set_block(entry)
    builder.ret(func.arguments[0])
    assert func.validate() is True


def test_ir_repr():
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("repr_test", [Type.I32], Type.I32)
    entry = func.create_block("entry")
    builder.set_block(entry)
    builder.ret(func.arguments[0])
    text = repr(func)
    assert "repr_test" in text
    assert "entry:" in text


@pytest.mark.skipif(
    platform.machine().lower() not in ("amd64", "x86_64"),
    reason="Native codegen requires x86_64"
)
def test_native_scalar_add():
    """Test native x86_64 compilation of scalar add."""
    from uhcr.backends.cpu_avx2 import CPUAVX2Backend

    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("add", [Type.I64, Type.I64], Type.I64)
    entry = func.create_block("entry")
    builder.set_block(entry)
    builder.ret(builder.add(func.arguments[0], func.arguments[1]))

    # Only run if AVX2 is available
    profile = __import__("uhcr").detect()
    if not profile.cpu.has_avx2:
        pytest.skip("AVX2 not available")

    fn = CPUAVX2Backend().compile(func)
    assert fn(10, 32) == 42
    assert fn(0, 0) == 0
    assert fn(100, -58) == 42


@pytest.mark.skipif(
    platform.machine().lower() not in ("amd64", "x86_64"),
    reason="Native codegen requires x86_64"
)
def test_native_scalar_multiply():
    """Test native x86_64 compilation of scalar multiply."""
    from uhcr.backends.cpu_avx2 import CPUAVX2Backend

    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function("mul", [Type.I64, Type.I64], Type.I64)
    entry = func.create_block("entry")
    builder.set_block(entry)
    builder.ret(builder.mul(func.arguments[0], func.arguments[1]))

    profile = __import__("uhcr").detect()
    if not profile.cpu.has_avx2:
        pytest.skip("AVX2 not available")

    fn = CPUAVX2Backend().compile(func)
    assert fn(7, 6) == 42
    assert fn(0, 999) == 0
