"""RISC-V code generator — lowers UHCR IR to RV64GCV machine code.

Supports RISC-V LP64D calling convention:
- Arguments: a0-a7 (x10-x17)
- Return: a0 (x10)
- Callee-saved: s0-s11 (x8-x9, x18-x27)
- Frame pointer: s0 (x8), Return address: ra (x1)
"""

from typing import Dict, Union

from uhcr.compiler.ir import Type, Opcode, Value, Constant, Argument, Instruction, Function
from uhcr.compiler.riscv.assembler import (
    RISCVAssembler,
    ZERO, RA, SP, FP, T0, T1, T2, T3,
    A0, A1, A2, A3, A4, A5, A6, A7,
    S0, S1,
)


_ARG_REGS = [A0, A1, A2, A3, A4, A5, A6, A7]


class RISCVCodeGenerator:
    """Generates RISC-V RV64GCV machine code from UHCR IR."""

    def __init__(self, func: Function, has_rvv: bool = False):
        self.func = func
        self.has_rvv = has_rvv
        self.asm = RISCVAssembler()
        self.stack_offsets: Dict[Union[Instruction, Argument], int] = {}
        self.stack_size = 0
        self._plan_stack()

    def _plan_stack(self):
        """Plan stack frame layout."""
        offset = 16  # After saved ra + s0

        for arg in self.func.arguments:
            self.stack_offsets[arg] = offset
            offset += 8

        for block in self.func.blocks:
            for inst in block.instructions:
                if inst.type != Type.VOID:
                    self.stack_offsets[inst] = offset
                    offset += 8

        self.stack_size = (offset + 15) & ~15

    def compile(self) -> bytes:
        """Full compilation."""
        self.asm = RISCVAssembler()

        # Prologue
        self.asm.addi(SP, SP, -self.stack_size)
        self.asm.sd(RA, SP, self.stack_size - 8)
        self.asm.sd(FP, SP, self.stack_size - 16)
        self.asm.addi(FP, SP, self.stack_size)

        # Store arguments
        for i, arg in enumerate(self.func.arguments):
            if i < len(_ARG_REGS):
                offset = self.stack_offsets[arg]
                self.asm.sd(_ARG_REGS[i], SP, offset)

        # Compile blocks
        for block in self.func.blocks:
            self.asm.label(block.label)
            last_cmp_cond = None

            for inst in block.instructions:
                opcode = inst.opcode

                if opcode in (Opcode.ADD, Opcode.SUB, Opcode.MUL):
                    self._load_scalar(inst.args[0], T0)
                    self._load_scalar(inst.args[1], T1)
                    if opcode == Opcode.ADD:
                        self.asm.add(T2, T0, T1)
                    elif opcode == Opcode.SUB:
                        self.asm.sub(T2, T0, T1)
                    elif opcode == Opcode.MUL:
                        self.asm.mul(T2, T0, T1)
                    self._store_scalar(inst, T2)

                elif opcode == Opcode.VADD and self.has_rvv:
                    # RVV vector add
                    self._load_scalar(inst.args[0], T0)  # ptr to vec a
                    self._load_scalar(inst.args[1], T1)  # ptr to vec b
                    # vsetvli, vle32, vfadd, vse32
                    self.asm.vsetvli(T2, ZERO, sew=32, lmul=1)
                    self.asm.vle32(0, T0)   # v0 = load from T0
                    self.asm.vle32(1, T1)   # v1 = load from T1
                    self.asm.vfadd_vv(2, 0, 1)  # v2 = v0 + v1
                    self._store_scalar(inst, T2)

                elif opcode == Opcode.CMP:
                    last_cmp_cond = inst.args[0].value if isinstance(inst.args[0], Constant) else "eq"
                    self._load_scalar(inst.args[1], T0)
                    self._load_scalar(inst.args[2], T1)

                elif opcode == Opcode.BR:
                    true_lbl = inst.args[1].value
                    false_lbl = inst.args[2].value
                    if last_cmp_cond == "eq":
                        self.asm.beq(T0, T1, true_lbl)
                    elif last_cmp_cond == "ne":
                        self.asm.bne(T0, T1, true_lbl)
                    elif last_cmp_cond == "lt":
                        self.asm.blt(T0, T1, true_lbl)
                    elif last_cmp_cond == "ge":
                        self.asm.bge(T0, T1, true_lbl)
                    else:
                        self.asm.bne(T0, T1, true_lbl)
                    self.asm.jal(ZERO, false_lbl)

                elif opcode == Opcode.JMP:
                    self.asm.jal(ZERO, inst.args[0].value)

                elif opcode == Opcode.STRLEN:
                    # STRLEN dst, string_ptr
                    self._load_scalar(inst.args[0], A0)  # string_ptr in A0
                    # Call runtime strlen function
                    # Result in A0
                    self._store_scalar(inst, A0)
                    
                elif opcode == Opcode.STRCAT:
                    # STRCAT dst, str1, str2
                    self._load_scalar(inst.args[0], A0)  # str1
                    self._load_scalar(inst.args[1], A1)  # str2
                    # Call runtime strcat function
                    # Result in A0
                    self._store_scalar(inst, A0)
                    
                elif opcode == Opcode.STRINDEX:
                    # STRINDEX dst, string_ptr, index
                    self._load_scalar(inst.args[0], A0)  # string_ptr
                    self._load_scalar(inst.args[1], A1)  # index
                    # Call runtime strindex function
                    # Result in A0 (i32 character code)
                    self._store_scalar(inst, A0)
                    
                elif opcode == Opcode.STRSLICE:
                    # STRSLICE dst, string_ptr, start, end
                    self._load_scalar(inst.args[0], A0)  # string_ptr
                    self._load_scalar(inst.args[1], A1)  # start
                    self._load_scalar(inst.args[2], A2)  # end
                    # Call runtime strslice function
                    # Result in A0 (string pointer)
                    self._store_scalar(inst, A0)
                    
                elif opcode == Opcode.STREQ:
                    # STREQ dst, str1, str2
                    self._load_scalar(inst.args[0], A0)  # str1
                    self._load_scalar(inst.args[1], A1)  # str2
                    # Call runtime streq function
                    # Result in A0 (i32 boolean)
                    self._store_scalar(inst, A0)
                    
                elif opcode == Opcode.STRHASH:
                    # STRHASH dst, string_ptr
                    self._load_scalar(inst.args[0], A0)  # string_ptr
                    # Call runtime strhash function
                    # Result in A0 (i64 hash)
                    self._store_scalar(inst, A0)

                elif opcode == Opcode.LOOP:
                    # LOOP cond, body_label, exit_label
                    self._load_scalar(inst.args[0], A0)  # condition
                    body_label = inst.args[1].value
                    exit_label = inst.args[2].value
                    # Test if condition is true
                    self.asm.bne(A0, ZERO, body_label)
                    self.asm.jal(ZERO, exit_label)
                    
                elif opcode == Opcode.BREAK:
                    # BREAK target_label
                    target_label = inst.args[0].value
                    self.asm.jal(ZERO, target_label)
                    
                elif opcode == Opcode.CONTINUE:
                    # CONTINUE target_label
                    target_label = inst.args[0].value
                    self.asm.jal(ZERO, target_label)
                    
                elif opcode == Opcode.PHI:
                    # PHI node: merge values from multiple predecessors
                    # For now, use the first value (simplified)
                    first_value = inst.args[0]
                    self._load_scalar(first_value, A0)
                    self._store_scalar(inst, A0)

                elif opcode == Opcode.RET:
                    if inst.args:
                        self._load_scalar(inst.args[0], A0)
                    # Epilogue
                    self.asm.ld(RA, SP, self.stack_size - 8)
                    self.asm.ld(FP, SP, self.stack_size - 16)
                    self.asm.addi(SP, SP, self.stack_size)
                    self.asm.ret()

        return self.asm.get_bytes()

    def _load_scalar(self, val: Value, reg: int):
        if isinstance(val, Constant):
            imm = int(val.value) if isinstance(val.value, (int, float)) else 0
            self.asm.addi(reg, ZERO, imm & 0x7FF)  # 12-bit signed immediate
        elif isinstance(val, (Instruction, Argument)):
            offset = self.stack_offsets[val]
            self.asm.ld(reg, SP, offset)

    def _store_scalar(self, inst: Instruction, reg: int):
        offset = self.stack_offsets[inst]
        self.asm.sd(reg, SP, offset)
