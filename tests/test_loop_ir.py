"""Tests for loop IR construction."""

import pytest
from uhcr.compiler.ir import Type, Opcode, Constant
from uhcr.compiler.ir_builder import IRBuilder


class TestLoopIRConstruction:
    """Test loop IR generation."""
    
    def test_loop_opcode_exists(self):
        """Test that loop opcodes are defined."""
        assert hasattr(Opcode, 'LOOP')
        assert hasattr(Opcode, 'BREAK')
        assert hasattr(Opcode, 'CONTINUE')
        assert hasattr(Opcode, 'PHI')
    
    def test_loop_header_creation(self):
        """Test creating a loop header."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_loop", [Type.I64], Type.I64)
        
        header = func.create_block("header")
        body = func.create_block("body")
        exit_block = func.create_block("exit")
        
        builder.set_block(header)
        
        # Create loop condition
        cond = builder.cmp("lt", func.arguments[0], 10)
        
        # Create loop instruction
        loop_inst = builder.loop(cond, body, exit_block)
        
        assert loop_inst.opcode == Opcode.LOOP
        assert loop_inst.type == Type.VOID
        assert len(loop_inst.args) == 3  # condition, body label, exit label
    
    def test_break_statement(self):
        """Test creating a break statement."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_break", [], Type.VOID)
        
        body = func.create_block("body")
        exit_block = func.create_block("exit")
        
        builder.set_block(body)
        
        # Create break instruction
        break_inst = builder.break_loop(exit_block)
        
        assert break_inst.opcode == Opcode.BREAK
        assert break_inst.type == Type.VOID
        assert len(break_inst.args) == 1  # target block label
    
    def test_continue_statement(self):
        """Test creating a continue statement."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_continue", [], Type.VOID)
        
        header = func.create_block("header")
        body = func.create_block("body")
        
        builder.set_block(body)
        
        # Create continue instruction
        continue_inst = builder.continue_loop(header)
        
        assert continue_inst.opcode == Opcode.CONTINUE
        assert continue_inst.type == Type.VOID
        assert len(continue_inst.args) == 1  # target block label
    
    def test_phi_node_creation(self):
        """Test creating a phi node."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_phi", [Type.I64, Type.I64], Type.I64)
        
        block1 = func.create_block("block1")
        block2 = func.create_block("block2")
        merge = func.create_block("merge")
        
        builder.set_block(merge)
        
        # Create phi node merging two values
        phi_inst = builder.phi(
            [func.arguments[0], func.arguments[1]],
            [block1, block2],
            Type.I64
        )
        
        assert phi_inst.opcode == Opcode.PHI
        assert phi_inst.type == Type.I64
        # Should have 4 args: value1, block1_label, value2, block2_label
        assert len(phi_inst.args) == 4
    
    def test_phi_node_with_instructions(self):
        """Test creating a phi node with instruction values."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_phi_inst", [Type.I64], Type.I64)
        
        block1 = func.create_block("block1")
        block2 = func.create_block("block2")
        merge = func.create_block("merge")
        
        # Create values in block1
        builder.set_block(block1)
        val1 = builder.add(func.arguments[0], 1)
        
        # Create values in block2
        builder.set_block(block2)
        val2 = builder.add(func.arguments[0], 2)
        
        # Create phi node in merge block
        builder.set_block(merge)
        phi_inst = builder.phi([val1, val2], [block1, block2], Type.I64)
        
        assert phi_inst.opcode == Opcode.PHI
        assert phi_inst.type == Type.I64
    
    def test_phi_node_requires_two_predecessors(self):
        """Test that phi node requires at least 2 predecessors."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_phi_single", [Type.I64], Type.I64)
        
        block1 = func.create_block("block1")
        merge = func.create_block("merge")
        
        builder.set_block(merge)
        
        # Should fail with only one predecessor
        with pytest.raises(AssertionError):
            builder.phi([func.arguments[0]], [block1], Type.I64)
    
    def test_simple_loop_structure(self):
        """Test building a simple loop structure."""
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("simple_loop", [Type.I64], Type.I64)
        
        # Create blocks
        header = func.create_block("header")
        body = func.create_block("body")
        exit_block = func.create_block("exit")
        
        # Header block: check condition
        builder.set_block(header)
        cond = builder.cmp("lt", func.arguments[0], 10)
        loop_inst = builder.loop(cond, body, exit_block)
        
        # Body block: increment and continue
        builder.set_block(body)
        incremented = builder.add(func.arguments[0], 1)
        continue_inst = builder.continue_loop(header)
        
        # Exit block: return
        builder.set_block(exit_block)
        builder.ret(func.arguments[0])
        
        # Verify structure
        assert len(func.blocks) == 3
        assert header.instructions[0].opcode == Opcode.CMP
        assert header.instructions[1].opcode == Opcode.LOOP
        assert body.instructions[0].opcode == Opcode.ADD
        assert body.instructions[1].opcode == Opcode.CONTINUE
        assert exit_block.instructions[0].opcode == Opcode.RET


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
