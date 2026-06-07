"""Common Subexpression Elimination (CSE) — reuses previously computed values.

If two instructions compute the same operation on the same operands,
the second one is eliminated and its uses are redirected to the first.

Example:
    %0 = add i32 %arg0, %arg1
    %1 = add i32 %arg0, %arg1   ← DUPLICATE of %0
    %2 = mul i32 %0, %1         → becomes mul i32 %0, %0

CSE uses a value-numbering approach: instructions are keyed by
(opcode, type, operand_ids) to detect duplicates.
"""

from typing import Dict, Optional, Tuple

from uhcr.compiler.ir import (
    Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function
)
from uhcr.compiler.passes.pipeline import Pass

# Opcodes that should NOT be CSE'd (side effects or non-deterministic)
_NO_CSE_OPCODES = frozenset({
    Opcode.STORE, Opcode.VSTORE,
    Opcode.LOAD, Opcode.VLOAD,  # Loads can't be CSE'd (memory may change)
    Opcode.RET, Opcode.BR, Opcode.JMP,
    Opcode.MATMUL, Opcode.RELU,
    Opcode.CMP,  # Comparisons set flags, context-dependent
})


class CommonSubexpressionEliminationPass(Pass):
    """Eliminates redundant computations by reusing previously computed values."""

    def __init__(self):
        self._eliminated_count = 0

    @property
    def name(self) -> str:
        return "cse"

    @property
    def stats(self) -> dict:
        return {"eliminated": self._eliminated_count}

    def run(self, func: Function) -> Function:
        self._eliminated_count = 0
        # Map from expression key → first instruction that computed it
        expr_map: Dict[Tuple, Instruction] = {}
        # Map from eliminated instruction → replacement instruction
        replacements: Dict[int, Instruction] = {}  # id(inst) → replacement

        for block in func.blocks:
            new_instructions = []
            for inst in block.instructions:
                # First, rewrite args to use replacements from earlier CSE
                inst.args = [self._resolve(arg, replacements) for arg in inst.args]

                # Check if this instruction can be CSE'd
                if inst.opcode in _NO_CSE_OPCODES or inst.type == Type.VOID:
                    new_instructions.append(inst)
                    continue

                # Compute expression key
                key = self._expr_key(inst)
                if key is None:
                    new_instructions.append(inst)
                    continue

                if key in expr_map:
                    # Duplicate found — eliminate this instruction
                    replacements[id(inst)] = expr_map[key]
                    self._eliminated_count += 1
                else:
                    # First occurrence — record it
                    expr_map[key] = inst
                    new_instructions.append(inst)

            block.instructions = new_instructions

        self._reassign_ids(func)
        return func

    def _expr_key(self, inst: Instruction) -> Optional[Tuple]:
        """Compute a hashable key representing this expression.

        Returns None if the instruction can't be keyed (e.g., has non-hashable args).
        """
        arg_keys = []
        for arg in inst.args:
            key = self._value_key(arg)
            if key is None:
                return None
            arg_keys.append(key)

        return (inst.opcode, inst.type, tuple(arg_keys))

    def _value_key(self, val: Value) -> Optional:
        """Get a hashable identifier for a value."""
        if isinstance(val, Constant):
            return ("const", val.type, val.value)
        elif isinstance(val, Argument):
            return ("arg", val.name)
        elif isinstance(val, Instruction):
            return ("inst", id(val))
        return None

    def _resolve(self, val: Value, replacements: Dict[int, Instruction]) -> Value:
        """Replace an eliminated instruction reference with its canonical version."""
        if isinstance(val, Instruction) and id(val) in replacements:
            return replacements[id(val)]
        return val

    def _reassign_ids(self, func: Function):
        """Reassign sequential IDs to remaining instructions."""
        func._next_inst_id = 0
        for block in func.blocks:
            for inst in block.instructions:
                inst.id = func._next_inst_id
                func._next_inst_id += 1
