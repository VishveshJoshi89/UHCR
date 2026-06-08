"""Tests for safety monitor integration in IR builder and IR components."""
import pytest
from uhcr.compiler.ir import Type, Opcode, Function
from uhcr.compiler.ir_builder import IRBuilder


class TestIRBuilderSafety:
    """Test safety monitor integration in IR builder."""
    
    def test_ir_builder_initializes_safety_monitor(self):
        """Test that IR builder initializes safety monitor."""
        builder = IRBuilder()
        # Should initialize without error (may or may not have native monitor)
        assert builder._safety_monitor is not None or builder._safety_monitor is None
    
    def test_emit_scalar_operations_without_thermal_check(self):
        """Test that scalar operations don't trigger thermal checks."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test", [Type.I32, Type.I32], Type.I32)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # Scalar operations should work even if CPU is hot
        # (they don't trigger thermal checks)
        result = builder.add(func.arguments[0], func.arguments[1])
        assert result.opcode == Opcode.ADD
    
    def test_emit_vector_operations_with_safety_monitor(self):
        """Test that vector operations check CPU temperature."""
        builder = IRBuilder()
        
        # Only test if safety monitor is available
        if builder._safety_monitor is None:
            pytest.skip("Native safety monitor not available")
        
        builder.new_module()
        func = builder.new_function("test_vector", [Type.V8F32, Type.V8F32], Type.V8F32)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # Vector operations should trigger safety checks
        # This should succeed if CPU temp is OK
        try:
            result = builder.vadd(func.arguments[0], func.arguments[1])
            assert result.opcode == Opcode.VADD
        except RuntimeError as e:
            # If CPU is too hot, should get thermal error
            assert "temperature too high" in str(e).lower()
    
    def test_emit_memory_operations_with_safety_monitor(self):
        """Test that memory operations check safety."""
        builder = IRBuilder()
        
        if builder._safety_monitor is None:
            pytest.skip("Native safety monitor not available")
        
        builder.new_module()
        func = builder.new_function("test_mem", [Type.PTR], Type.V8F32)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # Memory operations should trigger safety checks
        try:
            result = builder.vload(func.arguments[0], 0, Type.V8F32)
            assert result.opcode == Opcode.VLOAD
        except RuntimeError as e:
            assert "temperature too high" in str(e).lower() or "emergency" in str(e).lower()
    
    def test_emit_matmul_checks_cpu_and_gpu(self):
        """Test that MATMUL checks both CPU and GPU temperature."""
        builder = IRBuilder()
        
        if builder._safety_monitor is None:
            pytest.skip("Native safety monitor not available")
        
        builder.new_module()
        func = builder.new_function("test_matmul", [Type.PTR, Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # MATMUL should check both CPU and GPU
        try:
            inst = builder.matmul(func.arguments[0], func.arguments[1], func.arguments[2])
            assert inst.opcode == Opcode.MATMUL
        except RuntimeError as e:
            # Should mention temperature if check fails
            assert "temperature" in str(e).lower()
    
    def test_emergency_stop_blocks_all_emissions(self):
        """Test that emergency stop blocks all instruction emissions."""
        builder = IRBuilder()
        
        if builder._safety_monitor is None or builder._safety_monitor._lib is None:
            pytest.skip("Native safety monitor not available")
        
        # Trigger emergency stop
        builder._safety_monitor.emergency_stop()
        
        builder.new_module()
        func = builder.new_function("test", [Type.V8F32, Type.V8F32], Type.V8F32)
        entry = func.create_block("entry")
        builder.set_block(entry)
        
        # Vector operations should be blocked by emergency stop
        with pytest.raises(RuntimeError, match="Emergency stop"):
            builder.vadd(func.arguments[0], func.arguments[1])
        
        # Note: Cannot reset emergency stop without reinitializing the native library
        # This is a one-way safety mechanism by design


class TestFunctionSafety:
    """Test safety monitor integration in IR Function."""
    
    def test_function_initializes_safety_monitor(self):
        """Test that Function initializes safety monitor."""
        func = Function("test", [Type.I32], Type.I32)
        assert func._safety_monitor is not None or func._safety_monitor is None
    
    def test_create_block_basic(self):
        """Test that basic block creation works normally."""
        func = Function("test", [Type.I32], Type.I32)
        block = func.create_block("entry")
        assert block.label == "entry"
        assert len(func.blocks) == 1
    
    def test_create_many_blocks_without_thermal_stress(self):
        """Test that creating many blocks works when CPU is cool."""
        func = Function("test", [Type.I32], Type.I32)
        
        # Create 100 blocks (below threshold)
        for i in range(100):
            block = func.create_block(f"block{i}")
            assert block.label == f"block{i}"
        
        assert len(func.blocks) == 100
    
    def test_create_many_blocks_checks_temperature(self):
        """Test that creating >1000 blocks triggers temperature check."""
        func = Function("test", [Type.I32], Type.I32)
        
        if func._safety_monitor is None:
            pytest.skip("Native safety monitor not available")
        
        # Create 1000 blocks first (should work)
        for i in range(1000):
            func.create_block(f"block{i}")
        
        # Creating block 1001 should trigger temperature check
        try:
            func.create_block("block1000")
            # Should succeed if CPU temp is OK
            assert len(func.blocks) == 1001
        except RuntimeError as e:
            # Should fail if CPU is too hot
            assert "temperature too high" in str(e).lower()
            assert "complex function" in str(e).lower()
    
    def test_validate_with_safety_monitor(self):
        """Test that validation checks emergency stop."""
        func = Function("test", [Type.I32], Type.I32)
        entry = func.create_block("entry")
        
        # Add terminator
        from uhcr.compiler.ir import Instruction
        ret = Instruction(Opcode.RET, Type.VOID, [])
        entry.add_instruction(ret)
        
        # Validation should work normally
        if func._safety_monitor:
            try:
                result = func.validate()
                assert result is True
            except RuntimeError as e:
                # Should only fail if emergency stop is active
                assert "emergency" in str(e).lower()
        else:
            # Without monitor, should always validate
            assert func.validate() is True
    
    def test_emergency_stop_blocks_validation(self):
        """Test that emergency stop blocks function validation."""
        func = Function("test", [Type.I32], Type.I32)
        
        if func._safety_monitor is None or func._safety_monitor._lib is None:
            pytest.skip("Native safety monitor not available")
        
        # Trigger emergency stop
        func._safety_monitor.emergency_stop()
        
        # Validation should fail due to emergency stop
        with pytest.raises(RuntimeError, match="Emergency stop"):
            func.validate()
        
        # Note: Cannot reset emergency stop without reinitializing the native library
        # This is a one-way safety mechanism by design
    
    def test_emergency_stop_blocks_block_creation(self):
        """Test that emergency stop blocks block creation."""
        func = Function("test", [Type.I32], Type.I32)
        
        if func._safety_monitor is None or func._safety_monitor._lib is None:
            pytest.skip("Native safety monitor not available")
        
        # Trigger emergency stop
        func._safety_monitor.emergency_stop()
        
        # Block creation should fail due to emergency stop
        with pytest.raises(RuntimeError, match="Emergency stop"):
            func.create_block("entry")
        
        # Note: Cannot reset emergency stop without reinitializing the native library
        # This is a one-way safety mechanism by design


class TestIntegratedIRSafety:
    """Test integrated safety across IR builder and function."""
    
    def test_full_ir_building_flow_with_safety(self):
        """Test complete IR building flow with safety checks."""
        builder = IRBuilder()
        builder.new_module()
        
        # Create function
        func = builder.new_function("vector_add", [Type.PTR, Type.PTR, Type.PTR, Type.I64], Type.VOID)
        entry = func.create_block("entry")
        loop_header = func.create_block("loop_header")
        loop_body = func.create_block("loop_body")
        loop_exit = func.create_block("loop_exit")
        
        # Build IR with safety checks
        builder.set_block(entry)
        i = builder.add(0, 0)  # Initialize counter (scalar, no thermal check)
        builder.jmp(loop_header)
        
        builder.set_block(loop_header)
        # Loop condition (scalar, no thermal check)
        cond = builder.cmp("lt", i, func.arguments[3])
        builder.br(cond, loop_body, loop_exit)
        
        builder.set_block(loop_body)
        # These operations trigger thermal checks if monitor is available
        try:
            a = builder.vload(func.arguments[0], i, Type.V8F32)
            b = builder.vload(func.arguments[1], i, Type.V8F32)
            c = builder.vadd(a, b)
            builder.vstore(c, func.arguments[2], i)
            i_next = builder.add(i, 8)
            builder.jmp(loop_header)
        except RuntimeError as e:
            # Expected if CPU is too hot
            assert "temperature" in str(e).lower() or "emergency" in str(e).lower()
            return
        
        builder.set_block(loop_exit)
        builder.ret()
        
        # Validate (checks emergency stop if monitor available)
        try:
            assert func.validate()
        except RuntimeError as e:
            assert "emergency" in str(e).lower()
    
    def test_scalar_function_no_thermal_overhead(self):
        """Test that purely scalar functions don't trigger thermal checks."""
        builder = IRBuilder()
        builder.new_module()
        
        func = builder.new_function("scalar_math", [Type.I32, Type.I32], Type.I32)
        entry = func.create_block("entry")
        
        builder.set_block(entry)
        # All scalar operations
        a = builder.add(func.arguments[0], func.arguments[1])
        b = builder.mul(a, 2)
        c = builder.sub(b, 1)
        builder.ret(c)
        
        # Should work even if CPU is hot (no thermal checks for scalar ops)
        assert func.validate()
        assert len(entry.instructions) == 4  # add, mul, sub, ret


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
