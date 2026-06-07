"""Dead Code Elimination Pass — removes instructions whose results are never used.

An instruction is "dead" if:
1. It produces a value (non-VOID type)
2. No other instruction references it as an operand
3. It has no side effects (not a STORE, VSTORE, RET, BR, JMP, or intrinsic)

Example:
    %0 = add i32 %arg0, %arg1   ← used by %2
    %1 = mul i32 %arg0, 10      ← DEAD (never referenced)
    %2 = sub i32 %0, 5
    ret %2
"""

from typing import Set

from uhcr.compiler.ir import (
    Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function
)
from uhcr.compiler.passes.pipeline import Pass

# Opcodes that have side effects and must never be eliminated
_SIDE_EFFECT_OPCODES = frozenset({
    Opcode.STORE, Opcode.VSTORE,
    Opcode.RET, Opcode.BR, Opcode.JMP,
    Opcode.MATMUL, Opcode.RELU,
})


class DeadCodeEliminationPass(Pass):
    """Removes instructions whose results are never used."""

    def __init__(self):
        self._eliminated_count = 0

    @property
    def name(self) -> str:
        return "dead_code_eliminate"

    @property
    def stats(self) -> dict:
        return {"eliminated": self._eliminated_count}

    def run(self, func: Function) -> Function:
        self._eliminated_count = 0

        # Iterate until no more dead code is found (handles chains)
        changed = True
        while changed:
            changed = False
            # Collect all used values
            used: Set[int] = set()  # instruction IDs that are referenced
            self._collect_uses(func, used)

            # Remove dead instructions
            for block in func.blocks:
                new_instructions = []
                for inst in block.instructions:
                    if self._is_dead(inst, used):
                        self._eliminated_count += 1
                        changed = True
                    else:
                        new_instructions.append(inst)
                block.instructions = new_instructions

        # Reassign IDs
        self._reassign_ids(func)
        return func

    def _collect_uses(self, func: Function, used: Set[int]):
        """Collect all instruction IDs that are referenced by other instructions."""
        for block in func.blocks:
            for inst in block.instructions:
                for arg in inst.args:
                    if isinstance(arg, Instruction):
                        used.add(id(arg))

    def _is_dead(self, inst: Instruction, used: Set[int]) -> bool:
        """Check if an instruction is dead (unused and no side effects)."""
        # Instructions with side effects are never dead
        if inst.opcode in _SIDE_EFFECT_OPCODES:
            return False

        # VOID-type instructions that aren't side-effecting are dead by definition
        # (but we already excluded side-effect opcodes above)
        if inst.type == Type.VOID:
            return False  # VOID instructions are typically control flow

        # If no other instruction references this one, it's dead
        return id(inst) not in used

    def _reassign_ids(self, func: Function):
        """Reassign sequential IDs to remaining instructions."""
        func._next_inst_id = 0
        for block in func.blocks:
            for inst in block.instructions:
                inst.id = func._next_inst_id
                func._next_inst_id += 1
