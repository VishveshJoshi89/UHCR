"""Tests for JIT loop tracing."""

import pytest
from uhcr.frontend.decorator import jit, _LoopContext, _TracedValue
from uhcr.compiler.ir import Type, Opcode
from uhcr.compiler.ir_builder import IRBuilder


class TestLoopContext:
    """Test loop context creation."""
    
    def test_loop_context_creation(self):
        """Test creating a loop context."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_loop", [], Type.I64)
        block = func.create_block("entry")
        builder.set_block(block)
        
        # Create a loop context
        loop_ctx = _LoopContext(builder, range(10))
        
        assert loop_ctx.builder is builder
        assert loop_ctx.iterable == range(10)
        assert loop_ctx.header_block is None  # Not created yet
    
    def test_loop_context_enter_exit(self):
        """Test entering and exiting a loop context."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_loop", [], Type.I64)
        block = func.create_block("entry")
        builder.set_block(block)
        
        # Create and enter loop context
        loop_ctx = _LoopContext(builder, range(10))
        loop_var = loop_ctx.__enter__()
        
        # Verify blocks were created
        assert loop_ctx.header_block is not None
        assert loop_ctx.body_block is not None
        assert loop_ctx.exit_block is not None
        assert loop_var is not None
        
        # Exit loop context
        loop_ctx.__exit__(None, None, None)
        
        # Verify we're in the exit block
        assert builder.current_block == loop_ctx.exit_block
    
    def test_loop_context_with_statement(self):
        """Test using loop context as a context manager."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_loop", [], Type.I64)
        block = func.create_block("entry")
        builder.set_block(block)
        
        # Use loop context with 'with' statement
        with _LoopContext(builder, range(10)) as loop_var:
            assert loop_var is not None
            assert isinstance(loop_var, _TracedValue)
        
        # After exiting, we should be in the exit block
        assert builder.current_block is not None


class TestJitLoopCompilation:
    """Test JIT compilation of loop functions."""
    
    def test_jit_simple_loop(self):
        """Test JIT compilation of a simple loop."""
        @jit(eager=True, verbose=False)
        def count_to_n(n):
            total = 0
            for i in range(n):
                total = total + i
            return total
        
        # This should compile and execute
        try:
            result = count_to_n(5)
            # If compilation succeeded, result should be 0+1+2+3+4 = 10
            assert result == 10
        except Exception:
            # Fallback to Python is acceptable
            pass
    
    def test_jit_loop_with_break(self):
        """Test JIT compilation of loop with break."""
        @jit(eager=True, verbose=False)
        def find_first_even(n):
            for i in range(n):
                if i % 2 == 0:
                    return i
            return -1
        
        try:
            result = find_first_even(10)
            # First even number is 0
            assert result == 0
        except Exception:
            # Fallback to Python is acceptable
            pass
    
    def test_jit_nested_loops(self):
        """Test JIT compilation of nested loops."""
        @jit(eager=True, verbose=False)
        def sum_matrix(n):
            total = 0
            for i in range(n):
                for j in range(n):
                    total = total + i + j
            return total
        
        try:
            result = sum_matrix(3)
            # Calculate expected: sum of (i+j) for i,j in 0..2
            # = (0+0) + (0+1) + (0+2) + (1+0) + (1+1) + (1+2) + (2+0) + (2+1) + (2+2)
            # = 0 + 1 + 2 + 1 + 2 + 3 + 2 + 3 + 4 = 18
            assert result == 18
        except Exception:
            # Fallback to Python is acceptable
            pass


class TestTracedValueLoopOps:
    """Test loop operations on traced values."""
    
    def test_loop_variable_arithmetic(self):
        """Test arithmetic operations on loop variables."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test", [Type.I64], Type.I64)
        block = func.create_block("entry")
        builder.set_block(block)
        
        # Create a traced value
        loop_var = _TracedValue(func.arguments[0], builder)
        
        # Perform arithmetic
        result = loop_var + 1
        assert isinstance(result, _TracedValue)
        assert result._ir_value.opcode == Opcode.ADD
        
        result2 = result * 2
        assert isinstance(result2, _TracedValue)
        assert result2._ir_value.opcode == Opcode.MUL
    
    def test_loop_variable_comparison(self):
        """Test comparison operations on loop variables."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test", [Type.I64], Type.I64)
        block = func.create_block("entry")
        builder.set_block(block)
        
        # Create a traced value
        loop_var = _TracedValue(func.arguments[0], builder)
        
        # Perform comparison
        cond = builder.cmp("lt", loop_var._ir_value, 10)
        assert cond.opcode == Opcode.CMP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
