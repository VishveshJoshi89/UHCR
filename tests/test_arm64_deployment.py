import pytest
import platform
from uhcr.compiler.aarch64.target_profile import TargetProfile
from uhcr.compiler.aarch64.cross_compile import CrossCompiler, cross_compile
from uhcr.compiler.ir import Function, Type, BasicBlock, Opcode, Instruction, Argument, Constant

def test_target_profile_default():
    profile = TargetProfile.default()
    assert profile.architecture == "aarch64"
    assert profile.baseline == "armv8.2"
    assert profile.supports_feature("neon")
    assert profile.supports_feature("fp16")
    assert not profile.apple_silicon

def test_target_profile_mobile_iot():
    profile = TargetProfile.mobile_iot()
    assert profile.baseline == "armv8.0"
    assert profile.low_memory_mode
    assert profile.thermal_constrained
    assert profile.pic_enabled

def test_target_profile_apple_silicon():
    profile = TargetProfile.apple_silicon_profile()
    assert profile.apple_silicon
    assert profile.supports_feature("neon")
    assert not profile.low_memory_mode

def test_target_profile_detect():
    profile = TargetProfile.detect()
    assert isinstance(profile, TargetProfile)
    assert profile.architecture == "aarch64"

def test_cross_compiler_init():
    profile = TargetProfile.mobile_iot()
    compiler = CrossCompiler(profile)
    assert compiler.target_profile is profile
    machine = platform.machine().lower()
    if machine not in ("arm64", "aarch64"):
        assert compiler.is_cross_compiling()

def test_cross_compile_empty_func():
    func = Function("empty_func", [], Type.VOID)
    profile = TargetProfile.default()
    compiler = CrossCompiler(profile)
    with pytest.raises(ValueError):
        compiler.compile(func)

def test_cross_compile_simple_func():
    # Build a simple IR function that returns 42
    func = Function("test_func", [], Type.I32)
    block = func.create_block("entry")
    
    # Return 42
    c42 = Constant(Type.I32, 42)
    ret = Instruction(Opcode.RET, Type.VOID, [c42])
    block.add_instruction(ret)
    
    compiler = CrossCompiler(TargetProfile.default())
    machine_code = compiler.compile(func)
    
    assert isinstance(machine_code, bytes)
    assert len(machine_code) > 0

def test_cross_compile_convenience():
    func = Function("test_func2", [], Type.I32)
    block = func.create_block("entry")
    ret = Instruction(Opcode.RET, Type.VOID, [Constant(Type.I32, 42)])
    block.add_instruction(ret)
    
    machine_code = cross_compile(func)
    assert isinstance(machine_code, bytes)
    assert len(machine_code) > 0
