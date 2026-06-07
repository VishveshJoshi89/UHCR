"""Tests for IR optimization passes."""
import pytest

from uhcr.compiler.ir import Type, Opcode, Constant, Function
from uhcr.compiler.ir_builder import IRBuilder
from uhcr.compiler.passes import (
    OptimizationPipeline,
    ConstantFoldingPass,
    DeadCodeEliminationPass,
    StrengthReductionPass,
    CommonSubexpressionEliminationPass,
    run_default_passes,
)


def _build_func(name, arg_types, ret_type):
    """Helper to create a function with IRBuilder."""
    builder = IRBuilder()
    builder.new_module()
    func = builder.new_function(name, arg_types, ret_type)
    entry = func.create_block("entry")
    builder.set_block(entry)
    return builder, func, entry


def _count_instructions(func):
    """Count total instructions across all blocks."""
    return sum(len(b.instructions) for b in func.blocks)


# === Constant Folding Tests ===

class TestConstantFolding:
    def test_fold_add(self):
        builder, func, entry = _build_func("test", [], Type.I32)
        # %0 = add 3, 5 → should fold to 8
        result = builder.add(3, 5)
        builder.ret(result)

        opt = ConstantFoldingPass()
        func = opt.run(func)

        # The add should be eliminated, ret should use constant 8
        assert _count_instructions(func) == 1  # only ret remains
        ret_inst = func.blocks[0].instructions[0]
        assert ret_inst.opcode == Opcode.RET
        assert isinstance(ret_inst.args[0], Constant)
        assert ret_inst.args[0].value == 8

    def test_fold_mul(self):
        builder, func, entry = _build_func("test", [], Type.I32)
        result = builder.mul(4, 7)
        builder.ret(result)

        func = ConstantFoldingPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert isinstance(ret_inst.args[0], Constant)
        assert ret_inst.args[0].value == 28

    def test_fold_chain(self):
        builder, func, entry = _build_func("test", [], Type.I32)
        # %0 = add 2, 3 → 5
        # %1 = mul %0, 4 → 20
        a = builder.add(2, 3)
        b = builder.mul(a, 4)
        builder.ret(b)

        func = ConstantFoldingPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert isinstance(ret_inst.args[0], Constant)
        assert ret_inst.args[0].value == 20

    def test_no_fold_with_arguments(self):
        builder, func, entry = _build_func("test", [Type.I32, Type.I32], Type.I32)
        # %0 = add %arg0, %arg1 → cannot fold (runtime values)
        result = builder.add(func.arguments[0], func.arguments[1])
        builder.ret(result)

        before = _count_instructions(func)
        func = ConstantFoldingPass().run(func)
        after = _count_instructions(func)
        assert before == after  # Nothing should change

    def test_fold_float(self):
        builder, func, entry = _build_func("test", [], Type.F32)
        result = builder.add(1.5, 2.5)
        builder.ret(result)

        func = ConstantFoldingPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert isinstance(ret_inst.args[0], Constant)
        assert abs(ret_inst.args[0].value - 4.0) < 0.001


# === Dead Code Elimination Tests ===

class TestDeadCodeElimination:
    def test_eliminate_unused(self):
        builder, func, entry = _build_func("test", [Type.I32, Type.I32], Type.I32)
        # %0 = add %arg0, %arg1 (used)
        # %1 = mul %arg0, 10    (DEAD — never used)
        used = builder.add(func.arguments[0], func.arguments[1])
        _dead = builder.mul(func.arguments[0], 10)
        builder.ret(used)

        before = _count_instructions(func)
        func = DeadCodeEliminationPass().run(func)
        after = _count_instructions(func)
        assert after == before - 1  # mul removed

    def test_keep_side_effects(self):
        builder, func, entry = _build_func("test", [Type.PTR], Type.VOID)
        # store has side effects — must not be eliminated
        builder.store(42, func.arguments[0], 0)
        builder.ret()

        before = _count_instructions(func)
        func = DeadCodeEliminationPass().run(func)
        after = _count_instructions(func)
        assert before == after  # Nothing removed

    def test_chain_elimination(self):
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        # %0 = add %arg0, 1 (used by %1)
        # %1 = mul %0, 2    (DEAD)
        # %2 = sub %arg0, 1 (used by ret)
        a = builder.add(func.arguments[0], 1)
        _b = builder.mul(a, 2)  # dead
        c = builder.sub(func.arguments[0], 1)
        builder.ret(c)

        func = DeadCodeEliminationPass().run(func)
        # After first pass: mul removed, then add becomes dead too
        # With iterative DCE, both should be removed
        opcodes = [inst.opcode for inst in func.blocks[0].instructions]
        assert Opcode.MUL not in opcodes
        assert Opcode.ADD not in opcodes


# === Strength Reduction Tests ===

class TestStrengthReduction:
    def test_multiply_by_zero(self):
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        result = builder.mul(func.arguments[0], 0)
        builder.ret(result)

        func = StrengthReductionPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert ret_inst.opcode == Opcode.RET
        assert isinstance(ret_inst.args[0], Constant)
        assert ret_inst.args[0].value == 0

    def test_multiply_by_one(self):
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        result = builder.mul(func.arguments[0], 1)
        builder.ret(result)

        func = StrengthReductionPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert ret_inst.opcode == Opcode.RET
        # Should return the argument directly
        assert ret_inst.args[0] is func.arguments[0]

    def test_add_zero(self):
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        result = builder.add(func.arguments[0], 0)
        builder.ret(result)

        func = StrengthReductionPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert ret_inst.args[0] is func.arguments[0]

    def test_subtract_zero(self):
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        result = builder.sub(func.arguments[0], 0)
        builder.ret(result)

        func = StrengthReductionPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert ret_inst.args[0] is func.arguments[0]

    def test_divide_by_one(self):
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        result = builder.div(func.arguments[0], 1)
        builder.ret(result)

        func = StrengthReductionPass().run(func)
        ret_inst = func.blocks[0].instructions[0]
        assert ret_inst.args[0] is func.arguments[0]


# === Common Subexpression Elimination Tests ===

class TestCSE:
    def test_eliminate_duplicate(self):
        builder, func, entry = _build_func("test", [Type.I32, Type.I32], Type.I32)
        # %0 = add %arg0, %arg1
        # %1 = add %arg0, %arg1  ← duplicate
        # %2 = mul %0, %1
        a = builder.add(func.arguments[0], func.arguments[1])
        b = builder.add(func.arguments[0], func.arguments[1])
        c = builder.mul(a, b)
        builder.ret(c)

        before = _count_instructions(func)
        func = CommonSubexpressionEliminationPass().run(func)
        after = _count_instructions(func)
        assert after == before - 1  # One add eliminated

    def test_no_cse_for_loads(self):
        builder, func, entry = _build_func("test", [Type.PTR], Type.I32)
        # Two loads from same address — can't CSE (memory may change)
        a = builder.load(func.arguments[0], 0, Type.I32)
        b = builder.load(func.arguments[0], 0, Type.I32)
        c = builder.add(a, b)
        builder.ret(c)

        before = _count_instructions(func)
        func = CommonSubexpressionEliminationPass().run(func)
        after = _count_instructions(func)
        assert before == after  # Nothing eliminated


# === Pipeline Tests ===

class TestPipeline:
    def test_default_pipeline(self):
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        # %0 = add 2, 3       → folds to 5
        # %1 = mul %arg0, 1   → strength reduces to %arg0
        # %2 = add %1, %0     → add %arg0, 5
        a = builder.add(2, 3)
        b = builder.mul(func.arguments[0], 1)
        c = builder.add(b, a)
        builder.ret(c)

        before = _count_instructions(func)
        func = run_default_passes(func)
        after = _count_instructions(func)
        # Should be significantly reduced
        assert after < before

    def test_pipeline_stats(self):
        builder, func, entry = _build_func("test", [], Type.I32)
        builder.ret(builder.add(1, 2))

        pipeline = OptimizationPipeline()
        pipeline.add(ConstantFoldingPass())
        func = pipeline.run(func)

        assert len(pipeline.stats) > 0
        assert pipeline.stats[0]["pass"] == "constant_fold"

    def test_pipeline_repr(self):
        pipeline = OptimizationPipeline()
        pipeline.add(ConstantFoldingPass())
        pipeline.add(DeadCodeEliminationPass())
        r = repr(pipeline)
        assert "constant_fold" in r
        assert "dead_code_eliminate" in r

    def test_empty_function(self):
        """Pipeline should handle functions with no optimizable instructions."""
        builder, func, entry = _build_func("test", [Type.I32], Type.I32)
        builder.ret(func.arguments[0])

        before = _count_instructions(func)
        func = run_default_passes(func)
        after = _count_instructions(func)
        assert before == after  # Nothing to optimize
