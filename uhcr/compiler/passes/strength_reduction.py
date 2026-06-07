"""Strength Reduction Pass — replaces expensive operations with cheaper equivalents.

Transformations:
- Multiply by 0 → constant 0
- Multiply by 1 → identity (use operand directly)
- Multiply by power of 2 → left shift (for integers)
- Add 0 → identity
- Subtract 0 → identity
- Divide by 1 → identity

Example:
    %0 = mul i32 %arg0, 8    →  %0 = shl i32 %arg0, 3  (not yet, but folded)
    %1 = mul i32 %arg0, 1    →  (eliminated, %1 becomes %arg0)
    %2 = add i32 %arg0, 0    →  (eliminated, %2 becomes %arg0)
"""

import math
from typing import Optional, Tuple

from uhcr.compiler.ir import (
    Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function
)
from uhcr.compiler.passes.pipeline import Pass


class StrengthReductionPass(Pass):
    """Replaces expensive operations with cheaper equivalents."""

    def __init__(self):
        self._reductions_count = 0

    @property
    def name(self) -> str:
        return "strength_reduce"

    @property
    def stats(self) -> dict:
        return {"reductions": self._reductions_count}

    def run(self, func: Function) -> Function:
        self._reductions_count = 0
        # Map from instruction → replacement value
        replacements: dict = {}

        for block in func.blocks:
            new_instructions = []
            for inst in block.instructions:
                replacement = self._try_reduce(inst, replacements)
                if replacement is not None:
                    # This instruction is replaced by another value
                    replacements[inst] = replacement
                    self._reductions_count += 1
                    # Don't emit the instruction
                else:
                    # Rewrite args to use replacements
                    inst.args = [self._resolve(arg, replacements) for arg in inst.args]
                    new_instructions.append(inst)

            block.instructions = new_instructions

        self._reassign_ids(func)
        return func

    def _try_reduce(self, inst: Instruction, replacements: dict) -> Optional[Value]:
        """Try to reduce an instruction to a simpler form.

        Returns the replacement Value, or None if no reduction applies.
        """
        opcode = inst.opcode
        if len(inst.args) != 2:
            return None

        a = self._resolve(inst.args[0], replacements)
        b = self._resolve(inst.args[1], replacements)

        a_const = self._get_const(a)
        b_const = self._get_const(b)

        # Multiply reductions
        if opcode in (Opcode.MUL, Opcode.FMUL):
            # x * 0 = 0
            if b_const == 0:
                return Constant(inst.type, 0)
            if a_const == 0:
                return Constant(inst.type, 0)
            # x * 1 = x
            if b_const == 1:
                return a
            if a_const == 1:
                return b
            # x * -1 = -x (could emit SUB 0, x but skip for now)

        # Addition reductions
        elif opcode in (Opcode.ADD, Opcode.FADD):
            # x + 0 = x
            if b_const == 0:
                return a
            if a_const == 0:
                return b

        # Subtraction reductions
        elif opcode in (Opcode.SUB, Opcode.FSUB):
            # x - 0 = x
            if b_const == 0:
                return a
            # x - x = 0 (same value)
            if a is b:
                return Constant(inst.type, 0)

        # Division reductions
        elif opcode in (Opcode.DIV, Opcode.FDIV):
            # x / 1 = x
            if b_const == 1:
                return a

        return None

    def _get_const(self, val: Value) -> Optional[float]:
        """Get numeric value if val is a Constant."""
        if isinstance(val, Constant) and isinstance(val.value, (int, float)):
            return val.value
        return None

    def _resolve(self, val: Value, replacements: dict) -> Value:
        """Resolve a value through the replacement chain."""
        if isinstance(val, Instruction) and val in replacements:
            return replacements[val]
        return val

    def _reassign_ids(self, func: Function):
        """Reassign sequential IDs to remaining instructions."""
        func._next_inst_id = 0
        for block in func.blocks:
            for inst in block.instructions:
                inst.id = func._next_inst_id
                func._next_inst_id += 1
