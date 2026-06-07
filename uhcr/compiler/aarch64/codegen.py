"""AArch64 code generator — lowers UHCR IR to ARM64 machine code.

Supports AAPCS64 calling convention:
- Arguments: X0-X7 (integer), V0-V7 (SIMD/FP)
- Return: X0 (integer), V0 (SIMD/FP)
- Callee-saved: X19-X28, V8-V15
- Frame pointer: X29, Link register: X30

On Apple Silicon (M-series), the Apple AAPCS64 variant is used and
2D vector loads/stores use the explicit 2D arrangement encoding.
"""

import ctypes
import logging
import platform
from typing import Dict, List, Callable, Union

from uhcr.compiler.ir import Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function
from uhcr.compiler.aarch64.assembler import (
    AArch64Assembler,
    X0, X1, X2, X3, X4, X5, X6, X7,
    X8, X9, X10, X11, X19, X20, X29, X30, SP, XZR, LR, FP,
    V0, V1, V2, V3, V4, V5,
    COND_EQ, COND_NE, COND_LT, COND_LE, COND_GT, COND_GE,
)
from uhcr.compiler.aarch64.apple_silicon import AppleSiliconInfo

_log = logging.getLogger(__name__)


# AAPCS64 argument registers
_ARG_REGS = [X0, X1, X2, X3, X4, X5, X6, X7]
_TEMP_REGS = [X9, X10, X11]  # Scratch registers


class AArch64CodeGenerator:
    """Generates AArch64 machine code from UHCR IR."""

    def __init__(self, func: Function):
        self.func = func
        self.asm = AArch64Assembler()
        self.stack_offsets: Dict[Union[Instruction, Argument], int] = {}
        self.stack_size = 0
        self._post_increment_sets: Dict[int, List[Instruction]] = {}
        self._apple_silicon = AppleSiliconInfo.detect()
        if self._apple_silicon.is_apple_silicon:
            _log.debug("Apple Silicon detected: enabling M-series optimizations")
        self._plan_stack()

    @property
    def apple_silicon_info(self) -> "AppleSiliconInfo":
        """Return the Apple Silicon detection result for this code generator."""
        return self._apple_silicon

    def _plan_stack(self):
        """Plan stack frame layout for arguments and temporaries."""
        offset = 16  # After saved FP+LR

        for arg in self.func.arguments:
            self.stack_offsets[arg] = offset
            offset += 8

        for block in self.func.blocks:
            for inst in block.instructions:
                if inst.type != Type.VOID:
                    self.stack_offsets[inst] = offset
                    offset += 8

        # Align to 16 bytes
        self.stack_size = (offset + 15) & ~15

    def _detect_post_increment_pattern(self, block: BasicBlock) -> Dict[int, List[Instruction]]:
        """Detect sequential VLOAD/VSTORE patterns suitable for post-increment addressing.

        Scans a basic block for consecutive VLOAD or VSTORE instructions that share
        the same base pointer and have offsets incrementing by 1 each time.

        Returns a dict mapping the index of the first instruction in each sequence
        to the list of instructions in that sequence (length >= 2).
        """
        sequences: Dict[int, List[Instruction]] = {}
        instructions = block.instructions
        i = 0
        while i < len(instructions):
            inst = instructions[i]
            if inst.opcode == Opcode.VLOAD:
                # VLOAD args: [ptr, offset]
                base = inst.args[0]
                offset_val = inst.args[1]
                if isinstance(offset_val, Constant):
                    current_offset = int(offset_val.value)
                    seq = [inst]
                    j = i + 1
                    while j < len(instructions):
                        next_inst = instructions[j]
                        if next_inst.opcode != Opcode.VLOAD:
                            break
                        next_base = next_inst.args[0]
                        next_offset_val = next_inst.args[1]
                        if next_base is not base:
                            break
                        if not isinstance(next_offset_val, Constant):
                            break
                        next_offset = int(next_offset_val.value)
                        if next_offset != current_offset + 1:
                            break
                        seq.append(next_inst)
                        current_offset = next_offset
                        j += 1
                    if len(seq) >= 2:
                        sequences[i] = seq
                        i = j
                        continue
            elif inst.opcode == Opcode.VSTORE:
                # VSTORE args: [data, ptr, offset]
                base = inst.args[1]
                offset_val = inst.args[2]
                if isinstance(offset_val, Constant):
                    current_offset = int(offset_val.value)
                    seq = [inst]
                    j = i + 1
                    while j < len(instructions):
                        next_inst = instructions[j]
                        if next_inst.opcode != Opcode.VSTORE:
                            break
                        next_base = next_inst.args[1]
                        next_offset_val = next_inst.args[2]
                        if next_base is not base:
                            break
                        if not isinstance(next_offset_val, Constant):
                            break
                        next_offset = int(next_offset_val.value)
                        if next_offset != current_offset + 1:
                            break
                        seq.append(next_inst)
                        current_offset = next_offset
                        j += 1
                    if len(seq) >= 2:
                        sequences[i] = seq
                        i = j
                        continue
            i += 1
        return sequences

    def _is_post_increment_continuation(self, inst: Instruction, block_sequences: Dict[int, List[Instruction]]) -> bool:
        """Check if an instruction is a non-first element in a post-increment sequence."""
        for start_idx, seq in block_sequences.items():
            if inst in seq[1:]:
                return True
        return False

    def _is_post_increment_first(self, inst: Instruction, block_sequences: Dict[int, List[Instruction]]) -> bool:
        """Check if an instruction is the first element in a post-increment sequence."""
        for start_idx, seq in block_sequences.items():
            if inst is seq[0]:
                return True
        return False

    def compile(self) -> bytes:
        """Full compilation: prologue + body + epilogue."""
        self.asm = AArch64Assembler()

        # Prologue
        self.asm.stp_pre(FP, LR, SP, -self.stack_size)
        self.asm.add_imm(FP, SP, 0)

        # Store arguments from registers to stack
        for i, arg in enumerate(self.func.arguments):
            if i < len(_ARG_REGS):
                offset = self.stack_offsets[arg]
                self.asm.str_reg(_ARG_REGS[i], SP, offset)

        # Compile blocks
        for block in self.func.blocks:
            self.asm.label(block.label)
            last_cmp_cond = None
            block_sequences = self._detect_post_increment_pattern(block)

            for inst in block.instructions:
                opcode = inst.opcode

                if opcode in (Opcode.ADD, Opcode.SUB, Opcode.MUL):
                    self._load_scalar(inst.args[0], X9)
                    self._load_scalar(inst.args[1], X10)
                    if opcode == Opcode.ADD:
                        self.asm.add_reg(X11, X9, X10)
                    elif opcode == Opcode.SUB:
                        self.asm.sub_reg(X11, X9, X10)
                    elif opcode == Opcode.MUL:
                        self.asm.mul_reg(X11, X9, X10)
                    self._store_scalar(inst, X11)

                elif opcode in (Opcode.VADD, Opcode.VSUB, Opcode.VMUL):
                    if self._is_integer_vector(inst):
                        # NEON integer vector operations
                        int_type = self._get_integer_vector_type(inst)
                        self._load_vector(inst.args[0], V0)
                        self._load_vector(inst.args[1], V1)
                        if int_type == Type.V4I32:
                            if opcode == Opcode.VADD:
                                self.asm.add_4s(V2, V0, V1)
                            elif opcode == Opcode.VSUB:
                                self.asm.sub_4s(V2, V0, V1)
                            elif opcode == Opcode.VMUL:
                                self.asm.mul_4s(V2, V0, V1)
                        elif int_type == Type.V8I16:
                            if opcode == Opcode.VADD:
                                self.asm.add_8h(V2, V0, V1)
                            elif opcode == Opcode.VSUB:
                                self.asm.sub_8h(V2, V0, V1)
                            elif opcode == Opcode.VMUL:
                                self.asm.mul_8h(V2, V0, V1)
                        elif int_type == Type.V16I8:
                            if opcode == Opcode.VADD:
                                self.asm.add_16b(V2, V0, V1)
                            elif opcode == Opcode.VSUB:
                                self.asm.sub_16b(V2, V0, V1)
                            elif opcode == Opcode.VMUL:
                                self.asm.mul_16b(V2, V0, V1)
                        self._store_vector(inst, V2)
                    elif self._is_v2f64(inst):
                        # NEON 2D (double-precision) operations
                        self._load_vector_2d(inst.args[0], V0)
                        self._load_vector_2d(inst.args[1], V1)
                        if opcode == Opcode.VADD:
                            self.asm.fadd_2d(V2, V0, V1)
                        elif opcode == Opcode.VSUB:
                            self.asm.fsub_2d(V2, V0, V1)
                        elif opcode == Opcode.VMUL:
                            self.asm.fmul_2d(V2, V0, V1)
                        self._store_vector_2d(inst, V2)
                    else:
                        # NEON 4S (single-precision) operations
                        self._load_vector(inst.args[0], V0)
                        self._load_vector(inst.args[1], V1)
                        if opcode == Opcode.VADD:
                            self.asm.fadd_4s(V2, V0, V1)
                        elif opcode == Opcode.VSUB:
                            self.asm.fsub_4s(V2, V0, V1)
                        elif opcode == Opcode.VMUL:
                            self.asm.fmul_4s(V2, V0, V1)
                        self._store_vector(inst, V2)

                elif opcode == Opcode.VDIV:
                    if self._is_v2f64(inst):
                        # NEON 2D (double-precision) divide
                        self._load_vector_2d(inst.args[0], V0)
                        self._load_vector_2d(inst.args[1], V1)
                        self.asm.fdiv_2d(V2, V0, V1)
                        self._store_vector_2d(inst, V2)
                    else:
                        # NEON 4S (single-precision) divide
                        self._load_vector(inst.args[0], V0)
                        self._load_vector(inst.args[1], V1)
                        self.asm.fdiv_4s(V2, V0, V1)
                        self._store_vector(inst, V2)

                elif opcode == Opcode.VFMADD:
                    if self._is_v2f64(inst):
                        # NEON 2D (double-precision) fused multiply-add
                        self._load_vector_2d(inst.args[0], V0)  # acc
                        self._load_vector_2d(inst.args[1], V1)  # a
                        self._load_vector_2d(inst.args[2], V2)  # b
                        # FMLA: V0 += V1 * V2
                        self.asm.fmla_2d(V0, V1, V2)
                        self._store_vector_2d(inst, V0)
                    else:
                        # NEON 4S (single-precision) fused multiply-add
                        self._load_vector(inst.args[0], V0)  # acc
                        self._load_vector(inst.args[1], V1)  # a
                        self._load_vector(inst.args[2], V2)  # b
                        # FMLA: V0 += V1 * V2
                        self.asm.fmla_4s(V0, V1, V2)
                        self._store_vector(inst, V0)

                elif opcode == Opcode.VLOAD:
                    if self._is_post_increment_continuation(inst, block_sequences):
                        # Use post-increment: address register X9 already points
                        # to the next element from the previous post-increment op
                        if self._is_v2f64(inst):
                            self.asm.ld1_2d_post(V0, X9)
                        else:
                            self.asm.ld1_4s_post(V0, X9)
                        self._store_vector(inst, V0)
                    elif self._is_post_increment_first(inst, block_sequences):
                        # First in a post-increment sequence: compute base address,
                        # then use post-increment load
                        self._load_scalar(inst.args[0], X9)  # ptr
                        self._load_scalar(inst.args[1], X10)  # offset
                        # Compute address: X9 = X9 + X10 * 16 (offset in vector units)
                        self.asm.movz(X11, 16, sf=1)
                        self.asm.mul_reg(X10, X10, X11)
                        self.asm.add_reg(X9, X9, X10)
                        if self._is_v2f64(inst):
                            self.asm.ld1_2d_post(V0, X9)
                        else:
                            self.asm.ld1_4s_post(V0, X9)
                        self._store_vector(inst, V0)
                    else:
                        # Non-sequential access: compute address each time
                        self._load_scalar(inst.args[0], X9)  # ptr
                        self._load_scalar(inst.args[1], X10)  # offset
                        # Compute address: X9 = X9 + X10 * 4
                        self.asm.movz(X11, 4, sf=1)
                        self.asm.mul_reg(X10, X10, X11)
                        self.asm.add_reg(X9, X9, X10)
                        self.asm.ld1_4s(V0, X9)
                        self._store_vector(inst, V0)

                elif opcode == Opcode.VSTORE:
                    if self._is_post_increment_continuation(inst, block_sequences):
                        # Use post-increment: address register X9 already points
                        # to the next element from the previous post-increment op
                        self._load_vector(inst.args[0], V0)
                        if self._is_v2f64(inst):
                            self.asm.st1_2d_post(V0, X9)
                        else:
                            self.asm.st1_4s_post(V0, X9)
                    elif self._is_post_increment_first(inst, block_sequences):
                        # First in a post-increment sequence: compute base address,
                        # then use post-increment store
                        self._load_vector(inst.args[0], V0)
                        self._load_scalar(inst.args[1], X9)  # ptr
                        self._load_scalar(inst.args[2], X10)  # offset
                        # Compute address: X9 = X9 + X10 * 16 (offset in vector units)
                        self.asm.movz(X11, 16, sf=1)
                        self.asm.mul_reg(X10, X10, X11)
                        self.asm.add_reg(X9, X9, X10)
                        if self._is_v2f64(inst):
                            self.asm.st1_2d_post(V0, X9)
                        else:
                            self.asm.st1_4s_post(V0, X9)
                    else:
                        # Non-sequential access: compute address each time
                        self._load_vector(inst.args[0], V0)
                        self._load_scalar(inst.args[1], X9)  # ptr
                        self._load_scalar(inst.args[2], X10)  # offset
                        self.asm.movz(X11, 4, sf=1)
                        self.asm.mul_reg(X10, X10, X11)
                        self.asm.add_reg(X9, X9, X10)
                        self.asm.st1_4s(V0, X9)

                elif opcode == Opcode.CMP:
                    last_cmp_cond = inst.args[0].value if isinstance(inst.args[0], Constant) else "eq"
                    self._load_scalar(inst.args[1], X9)
                    self._load_scalar(inst.args[2], X10)
                    self.asm.cmp_reg(X9, X10)

                elif opcode == Opcode.BR:
                    true_lbl = inst.args[1].value
                    false_lbl = inst.args[2].value
                    cond_map = {
                        "eq": COND_EQ, "ne": COND_NE,
                        "lt": COND_LT, "le": COND_LE,
                        "gt": COND_GT, "ge": COND_GE,
                    }
                    cond = cond_map.get(last_cmp_cond, COND_NE)
                    self.asm.b_cond(cond, true_lbl)
                    self.asm.b(false_lbl)

                elif opcode == Opcode.JMP:
                    self.asm.b(inst.args[0].value)

                elif opcode == Opcode.STRLEN:
                    # STRLEN dst, string_ptr
                    self._load_scalar(inst.args[0], X0)  # string_ptr in X0
                    # Call runtime strlen function
                    # Result in X0
                    self._store_scalar(inst, X0)
                    
                elif opcode == Opcode.STRCAT:
                    # STRCAT dst, str1, str2
                    self._load_scalar(inst.args[0], X0)  # str1
                    self._load_scalar(inst.args[1], X1)  # str2
                    # Call runtime strcat function
                    # Result in X0
                    self._store_scalar(inst, X0)
                    
                elif opcode == Opcode.STRINDEX:
                    # STRINDEX dst, string_ptr, index
                    self._load_scalar(inst.args[0], X0)  # string_ptr
                    self._load_scalar(inst.args[1], X1)  # index
                    # Call runtime strindex function
                    # Result in X0 (i32 character code)
                    self._store_scalar(inst, X0)
                    
                elif opcode == Opcode.STRSLICE:
                    # STRSLICE dst, string_ptr, start, end
                    self._load_scalar(inst.args[0], X0)  # string_ptr
                    self._load_scalar(inst.args[1], X1)  # start
                    self._load_scalar(inst.args[2], X2)  # end
                    # Call runtime strslice function
                    # Result in X0 (string pointer)
                    self._store_scalar(inst, X0)
                    
                elif opcode == Opcode.STREQ:
                    # STREQ dst, str1, str2
                    self._load_scalar(inst.args[0], X0)  # str1
                    self._load_scalar(inst.args[1], X1)  # str2
                    # Call runtime streq function
                    # Result in X0 (i32 boolean)
                    self._store_scalar(inst, X0)
                    
                elif opcode == Opcode.STRHASH:
                    # STRHASH dst, string_ptr
                    self._load_scalar(inst.args[0], X0)  # string_ptr
                    # Call runtime strhash function
                    # Result in X0 (i64 hash)
                    self._store_scalar(inst, X0)

                elif opcode == Opcode.LOOP:
                    # LOOP cond, body_label, exit_label
                    self._load_scalar(inst.args[0], X0)  # condition
                    body_label = inst.args[1].value
                    exit_label = inst.args[2].value
                    # Test if condition is true
                    self.asm.cmp_reg_imm(X0, 0)
                    # Jump to body if true, exit if false
                    self.asm.b_cond(body_label, COND_NE)
                    self.asm.b(exit_label)
                    
                elif opcode == Opcode.BREAK:
                    # BREAK target_label
                    target_label = inst.args[0].value
                    self.asm.b(target_label)
                    
                elif opcode == Opcode.CONTINUE:
                    # CONTINUE target_label
                    target_label = inst.args[0].value
                    self.asm.b(target_label)
                    
                elif opcode == Opcode.PHI:
                    # PHI node: merge values from multiple predecessors
                    # For now, use the first value (simplified)
                    first_value = inst.args[0]
                    self._load_scalar(first_value, X0)
                    self._store_scalar(inst, X0)

                elif opcode == Opcode.RET:
                    if inst.args:
                        self._load_scalar(inst.args[0], X0)
                    # Epilogue
                    self.asm.ldp_post(FP, LR, SP, self.stack_size)
                    self.asm.ret()

        return self.asm.get_bytes()

    def _load_scalar(self, val: Value, reg: int):
        """Load a scalar value into a register."""
        if isinstance(val, Constant):
            imm = int(val.value) if isinstance(val.value, (int, float)) else 0
            if 0 <= imm <= 0xFFFF:
                self.asm.movz(reg, imm & 0xFFFF)
            else:
                # For larger immediates, use movz + movk (simplified: just low 16 bits)
                self.asm.movz(reg, imm & 0xFFFF)
        elif isinstance(val, (Instruction, Argument)):
            offset = self.stack_offsets[val]
            self.asm.ldr_reg(reg, SP, offset)

    def _store_scalar(self, inst: Instruction, reg: int):
        """Store a register value to the instruction's stack slot."""
        offset = self.stack_offsets[inst]
        self.asm.str_reg(reg, SP, offset)

    def _load_vector(self, val: Value, vreg: int):
        """Load a vector value — for now uses stack slot address."""
        if isinstance(val, (Instruction, Argument)):
            offset = self.stack_offsets.get(val)
            if offset is not None:
                self.asm.add_imm(X9, SP, offset)
                self.asm.ld1_4s(vreg, X9)

    def _store_vector(self, inst: Instruction, vreg: int):
        """Store a vector register to the instruction's stack slot."""
        offset = self.stack_offsets.get(inst)
        if offset is not None:
            self.asm.add_imm(X9, SP, offset)
            self.asm.st1_4s(vreg, X9)

    def _is_v2f64(self, inst: Instruction) -> bool:
        """Check if an instruction operates on 2D (double-precision) vectors."""
        # Check the instruction's own type first
        if inst.type == Type.V2F64:
            return True
        # Check if any operand is typed as V2F64
        for arg in inst.args:
            if isinstance(arg, (Instruction, Argument)) and arg.type == Type.V2F64:
                return True
        return False

    def _is_integer_vector(self, inst: Instruction) -> bool:
        """Check if an instruction operates on integer vectors."""
        integer_vector_types = (Type.V4I32, Type.V8I16, Type.V16I8)
        # Check the instruction's own type first
        if inst.type in integer_vector_types:
            return True
        # Check if any operand is typed as an integer vector
        for arg in inst.args:
            if isinstance(arg, (Instruction, Argument)) and arg.type in integer_vector_types:
                return True
        return False

    def _get_integer_vector_type(self, inst: Instruction) -> Type:
        """Get the specific integer vector type for an instruction."""
        integer_vector_types = (Type.V4I32, Type.V8I16, Type.V16I8)
        # Check the instruction's own type first
        if inst.type in integer_vector_types:
            return inst.type
        # Check operands
        for arg in inst.args:
            if isinstance(arg, (Instruction, Argument)) and arg.type in integer_vector_types:
                return arg.type
        # Default to V4I32 (4x int32)
        return Type.V4I32

    def _load_vector_2d(self, val: Value, vreg: int):
        """Load a 2D (double-precision) vector value from stack slot.

        On Apple Silicon the explicit 2D arrangement encoding (ld1_2d) is used;
        on other AArch64 targets the 4S encoding is used (same 128-bit load).
        """
        if isinstance(val, (Instruction, Argument)):
            offset = self.stack_offsets.get(val)
            if offset is not None:
                self.asm.add_imm(X9, SP, offset)
                if self._apple_silicon.is_apple_silicon:
                    self.asm.ld1_2d(vreg, X9)
                else:
                    self.asm.ld1_4s(vreg, X9)  # LD1 with 128-bit load (same encoding for 2D)

    def _store_vector_2d(self, inst: Instruction, vreg: int):
        """Store a 2D (double-precision) vector register to the instruction's stack slot.

        On Apple Silicon the explicit 2D arrangement encoding (st1_2d) is used;
        on other AArch64 targets the 4S encoding is used (same 128-bit store).
        """
        offset = self.stack_offsets.get(inst)
        if offset is not None:
            self.asm.add_imm(X9, SP, offset)
            if self._apple_silicon.is_apple_silicon:
                self.asm.st1_2d(vreg, X9)
            else:
                self.asm.st1_4s(vreg, X9)  # ST1 with 128-bit store (same encoding for 2D)
