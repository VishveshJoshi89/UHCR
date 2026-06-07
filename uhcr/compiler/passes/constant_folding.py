"""Constant Folding Pass — evaluates constant expressions at compile time.

If both operands of an arithmetic instruction are constants, the result
is computed immediately and the instruction is replaced with the constant value.

Example:
    %0 = add i32 3, 5    →  replaced with constant 8
    %1 = mul i32 %0, 2   →  replaced with constant 16
"""

from uhcr.compiler.ir import (
    Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function
)
from uhcr.compiler.passes.pipeline import Pass


class ConstantFoldingPass(Pass):
    """Evaluates constant expressions at compile time."""

    def __init__(self):
        self._folded_count = 0

    @property
    def name(self) -> str:
        return "constant_fold"

    @property
    def stats(self) -> dict:
        return {"folded": self._folded_count}

    def run(self, func: Function) -> Function:
        self._folded_count = 0
        # Map from instruction → constant value (if folded)
        folded_values: dict = {}

        for block in func.blocks:
            new_instructions = []
            for inst in block.instructions:
                folded = self._try_fold(inst, folded_values)
                if folded is not None:
                    # This instruction was folded to a constant
                    folded_values[inst] = folded
                    self._folded_count += 1
                    # Don't emit the instruction — downstream users will
                    # resolve via folded_values
                else:
                    # Rewrite args to use folded constants where possible
                    inst.args = [self._resolve(arg, folded_values) for arg in inst.args]
                    new_instructions.append(inst)

            block.instructions = new_instructions

        # Reassign instruction IDs
        self._reassign_ids(func)
        return func

    def _try_fold(self, inst: Instruction, folded: dict):
        """Try to evaluate an instruction with constant operands.

        Returns the computed constant value, or None if not foldable.
        """
        opcode = inst.opcode

        # Only fold scalar arithmetic
        if opcode not in (Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV,
                          Opcode.FADD, Opcode.FSUB, Opcode.FMUL, Opcode.FDIV):
            return None

        if len(inst.args) != 2:
            return None

        a_val = self._get_constant_value(inst.args[0], folded)
        b_val = self._get_constant_value(inst.args[1], folded)

        if a_val is None or b_val is None:
            return None

        # Compute the result
        if opcode in (Opcode.ADD, Opcode.FADD):
            return a_val + b_val
        elif opcode in (Opcode.SUB, Opcode.FSUB):
            return a_val - b_val
        elif opcode in (Opcode.MUL, Opcode.FMUL):
            return a_val * b_val
        elif opcode in (Opcode.DIV, Opcode.FDIV):
            if b_val == 0:
                return None  # Don't fold division by zero
            return a_val / b_val if opcode == Opcode.FDIV else a_val // b_val

        return None

    def _get_constant_value(self, val: Value, folded: dict):
        """Get the constant value of a Value, if known."""
        if isinstance(val, Constant):
            return val.value
        if isinstance(val, Instruction) and val in folded:
            return folded[val]
        return None

    def _resolve(self, val: Value, folded: dict) -> Value:
        """Replace a folded instruction reference with its constant."""
        if isinstance(val, Instruction) and val in folded:
            return Constant(val.type, folded[val])
        return val

    def _reassign_ids(self, func: Function):
        """Reassign sequential IDs to remaining instructions."""
        func._next_inst_id = 0
        for block in func.blocks:
            for inst in block.instructions:
                inst.id = func._next_inst_id
                func._next_inst_id += 1
