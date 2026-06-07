"""AArch64 machine code assembler — encodes ARM64 instructions to bytes.

Supports:
- Data processing (ADD, SUB, MUL, MADD)
- NEON SIMD float (FADD, FSUB, FMUL, FDIV, FMLA, FMLS for 4S and 2D)
- NEON SIMD integer (ADD, SUB, MUL for 4S, 8H, 16B)
- Memory (LDR, STR, LDP, STP)
- NEON load/store (LD1, ST1 for 4S and 2D; LD1/ST1 post-increment for 4S and 2D)
- Branches (B, B.cond, BL, RET)
- System (NOP)
"""

from typing import Dict, List, Tuple, Optional


# General-purpose registers X0-X30, SP=31, XZR=31
X0, X1, X2, X3, X4, X5, X6, X7 = range(8)
X8, X9, X10, X11, X12, X13, X14, X15 = range(8, 16)
X16, X17, X18, X19, X20, X21, X22, X23 = range(16, 24)
X24, X25, X26, X27, X28, X29, X30 = range(24, 31)
SP = 31
XZR = 31
LR = X30
FP = X29

# NEON/FP registers V0-V31
V0, V1, V2, V3, V4, V5, V6, V7 = range(8)
V8, V9, V10, V11, V12, V13, V14, V15 = range(8, 16)
V16, V17, V18, V19, V20, V21, V22, V23 = range(16, 24)
V24, V25, V26, V27, V28, V29, V30, V31 = range(24, 32)


class AArch64Assembler:
    """Low-level AArch64 machine code assembler."""

    def __init__(self):
        self.code = bytearray()
        self.labels: Dict[str, int] = {}
        self.patches: List[Tuple[str, int, str]] = []  # (label, offset, type)

    def get_bytes(self) -> bytes:
        """Returns assembled machine code with resolved labels."""
        self._resolve_labels()
        return bytes(self.code)

    def label(self, name: str):
        """Declare a label at the current offset."""
        self.labels[name] = len(self.code)

    def _emit(self, inst: int):
        """Emit a 32-bit instruction in little-endian."""
        self.code.extend(inst.to_bytes(4, "little"))

    def _resolve_labels(self):
        """Patch branch offsets."""
        for label, offset, patch_type in self.patches:
            if label not in self.labels:
                raise RuntimeError(f"Undefined label: {label}")
            target = self.labels[label]
            if patch_type == "b":
                # B imm26: offset in instructions (4-byte units)
                imm26 = ((target - offset) >> 2) & 0x03FFFFFF
                existing = int.from_bytes(self.code[offset:offset+4], "little")
                patched = existing | imm26
                self.code[offset:offset+4] = patched.to_bytes(4, "little")
            elif patch_type == "bcond":
                imm19 = ((target - offset) >> 2) & 0x7FFFF
                existing = int.from_bytes(self.code[offset:offset+4], "little")
                patched = existing | (imm19 << 5)
                self.code[offset:offset+4] = patched.to_bytes(4, "little")
        self.patches.clear()

    # === Data Processing (Register) ===

    def add_reg(self, rd: int, rn: int, rm: int, sf: int = 1):
        """ADD Xd, Xn, Xm (sf=1 for 64-bit, sf=0 for 32-bit)"""
        inst = (sf << 31) | (0b0001011000 << 21) | (rm << 16) | (0 << 10) | (rn << 5) | rd
        self._emit(inst)

    def sub_reg(self, rd: int, rn: int, rm: int, sf: int = 1):
        """SUB Xd, Xn, Xm"""
        inst = (sf << 31) | (0b1001011000 << 21) | (rm << 16) | (0 << 10) | (rn << 5) | rd
        self._emit(inst)

    def mul_reg(self, rd: int, rn: int, rm: int, sf: int = 1):
        """MUL Xd, Xn, Xm (alias for MADD Xd, Xn, Xm, XZR)"""
        # MADD: sf|00|11011|000|Rm|0|Ra(=XZR)|Rn|Rd
        inst = (sf << 31) | (0b0011011000 << 21) | (rm << 16) | (0 << 15) | (XZR << 10) | (rn << 5) | rd
        self._emit(inst)

    def add_imm(self, rd: int, rn: int, imm12: int, sf: int = 1):
        """ADD Xd, Xn, #imm12"""
        inst = (sf << 31) | (0b00100010 << 23) | (0 << 22) | ((imm12 & 0xFFF) << 10) | (rn << 5) | rd
        self._emit(inst)

    def sub_imm(self, rd: int, rn: int, imm12: int, sf: int = 1):
        """SUB Xd, Xn, #imm12"""
        inst = (sf << 31) | (0b10100010 << 23) | (0 << 22) | ((imm12 & 0xFFF) << 10) | (rn << 5) | rd
        self._emit(inst)

    def mov_reg(self, rd: int, rm: int, sf: int = 1):
        """MOV Xd, Xm (alias for ORR Xd, XZR, Xm)"""
        inst = (sf << 31) | (0b0101010000 << 21) | (rm << 16) | (0 << 10) | (XZR << 5) | rd
        self._emit(inst)

    def movz(self, rd: int, imm16: int, shift: int = 0, sf: int = 1):
        """MOVZ Xd, #imm16, LSL #shift"""
        hw = shift // 16
        inst = (sf << 31) | (0b10100101 << 23) | (hw << 21) | ((imm16 & 0xFFFF) << 5) | rd
        self._emit(inst)

    # === Memory ===

    def ldr_reg(self, rt: int, rn: int, offset: int = 0, sf: int = 1):
        """LDR Xt, [Xn, #offset] (unsigned offset, scaled by 8 for 64-bit)"""
        size = 3 if sf else 2  # 11 for 64-bit, 10 for 32-bit
        scale = 8 if sf else 4
        imm12 = (offset // scale) & 0xFFF
        inst = (size << 30) | (0b11100101 << 22) | (imm12 << 10) | (rn << 5) | rt
        self._emit(inst)

    def str_reg(self, rt: int, rn: int, offset: int = 0, sf: int = 1):
        """STR Xt, [Xn, #offset]"""
        size = 3 if sf else 2
        scale = 8 if sf else 4
        imm12 = (offset // scale) & 0xFFF
        inst = (size << 30) | (0b11100100 << 22) | (imm12 << 10) | (rn << 5) | rt
        self._emit(inst)

    def stp_pre(self, rt1: int, rt2: int, rn: int, imm7: int):
        """STP Xt1, Xt2, [Xn, #imm7]! (pre-index)"""
        opc = 0b10  # 64-bit
        imm7_enc = (imm7 // 8) & 0x7F
        inst = (opc << 30) | (0b10100110 << 22) | (imm7_enc << 15) | (rt2 << 10) | (rn << 5) | rt1
        self._emit(inst)

    def ldp_post(self, rt1: int, rt2: int, rn: int, imm7: int):
        """LDP Xt1, Xt2, [Xn], #imm7 (post-index)"""
        opc = 0b10
        imm7_enc = (imm7 // 8) & 0x7F
        inst = (opc << 30) | (0b10100011 << 22) | (imm7_enc << 15) | (rt2 << 10) | (rn << 5) | rt1
        self._emit(inst)

    # === NEON SIMD (128-bit, 4S arrangement) ===

    def fadd_4s(self, vd: int, vn: int, vm: int):
        """FADD Vd.4S, Vn.4S, Vm.4S"""
        # 0|1|0|01110|0|0|1|Vm|110101|Vn|Vd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110001 << 21) | (vm << 16) | (0b110101 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fsub_4s(self, vd: int, vn: int, vm: int):
        """FSUB Vd.4S, Vn.4S, Vm.4S"""
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110101 << 21) | (vm << 16) | (0b110101 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fmul_4s(self, vd: int, vn: int, vm: int):
        """FMUL Vd.4S, Vn.4S, Vm.4S"""
        inst = (0 << 31) | (1 << 30) | (1 << 29) | (0b01110001 << 21) | (vm << 16) | (0b110111 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fdiv_4s(self, vd: int, vn: int, vm: int):
        """FDIV Vd.4S, Vn.4S, Vm.4S"""
        # 0|1|1|01110|0|0|1|Vm|111111|Vn|Vd  (Q=1, U=1, size=00)
        inst = (0 << 31) | (1 << 30) | (1 << 29) | (0b01110001 << 21) | (vm << 16) | (0b111111 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fmla_4s(self, vd: int, vn: int, vm: int):
        """FMLA Vd.4S, Vn.4S, Vm.4S (Vd += Vn * Vm)"""
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110001 << 21) | (vm << 16) | (0b110011 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fmls_4s(self, vd: int, vn: int, vm: int):
        """FMLS Vd.4S, Vn.4S, Vm.4S (Vd -= Vn * Vm)"""
        # 0|1|0|01110|1|0|1|Vm|110011|Vn|Vd  (Q=1, U=0, size=10)
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110101 << 21) | (vm << 16) | (0b110011 << 10) | (vn << 5) | vd
        self._emit(inst)

    # === NEON SIMD (128-bit, integer operations) ===

    def add_4s(self, vd: int, vn: int, vm: int):
        """ADD Vd.4S, Vn.4S, Vm.4S (integer add, 32-bit lanes)"""
        # Q=1|U=0|01110|size=10|1|Rm|opcode=10000|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110 << 24) | (0b10 << 22) | (1 << 21) | (vm << 16) | (0b100001 << 10) | (vn << 5) | vd
        self._emit(inst)

    def sub_4s(self, vd: int, vn: int, vm: int):
        """SUB Vd.4S, Vn.4S, Vm.4S (integer subtract, 32-bit lanes)"""
        # Q=1|U=1|01110|size=10|1|Rm|opcode=10000|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (1 << 29) | (0b01110 << 24) | (0b10 << 22) | (1 << 21) | (vm << 16) | (0b100001 << 10) | (vn << 5) | vd
        self._emit(inst)

    def mul_4s(self, vd: int, vn: int, vm: int):
        """MUL Vd.4S, Vn.4S, Vm.4S (integer multiply, 32-bit lanes)"""
        # Q=1|U=0|01110|size=10|1|Rm|opcode=10011|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110 << 24) | (0b10 << 22) | (1 << 21) | (vm << 16) | (0b100111 << 10) | (vn << 5) | vd
        self._emit(inst)

    def add_8h(self, vd: int, vn: int, vm: int):
        """ADD Vd.8H, Vn.8H, Vm.8H (integer add, 16-bit lanes)"""
        # Q=1|U=0|01110|size=01|1|Rm|opcode=10000|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110 << 24) | (0b01 << 22) | (1 << 21) | (vm << 16) | (0b100001 << 10) | (vn << 5) | vd
        self._emit(inst)

    def sub_8h(self, vd: int, vn: int, vm: int):
        """SUB Vd.8H, Vn.8H, Vm.8H (integer subtract, 16-bit lanes)"""
        # Q=1|U=1|01110|size=01|1|Rm|opcode=10000|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (1 << 29) | (0b01110 << 24) | (0b01 << 22) | (1 << 21) | (vm << 16) | (0b100001 << 10) | (vn << 5) | vd
        self._emit(inst)

    def mul_8h(self, vd: int, vn: int, vm: int):
        """MUL Vd.8H, Vn.8H, Vm.8H (integer multiply, 16-bit lanes)"""
        # Q=1|U=0|01110|size=01|1|Rm|opcode=10011|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110 << 24) | (0b01 << 22) | (1 << 21) | (vm << 16) | (0b100111 << 10) | (vn << 5) | vd
        self._emit(inst)

    def add_16b(self, vd: int, vn: int, vm: int):
        """ADD Vd.16B, Vn.16B, Vm.16B (integer add, 8-bit lanes)"""
        # Q=1|U=0|01110|size=00|1|Rm|opcode=10000|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110 << 24) | (0b00 << 22) | (1 << 21) | (vm << 16) | (0b100001 << 10) | (vn << 5) | vd
        self._emit(inst)

    def sub_16b(self, vd: int, vn: int, vm: int):
        """SUB Vd.16B, Vn.16B, Vm.16B (integer subtract, 8-bit lanes)"""
        # Q=1|U=1|01110|size=00|1|Rm|opcode=10000|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (1 << 29) | (0b01110 << 24) | (0b00 << 22) | (1 << 21) | (vm << 16) | (0b100001 << 10) | (vn << 5) | vd
        self._emit(inst)

    def mul_16b(self, vd: int, vn: int, vm: int):
        """MUL Vd.16B, Vn.16B, Vm.16B (integer multiply, 8-bit lanes)"""
        # Q=1|U=0|01110|size=00|1|Rm|opcode=10011|1|Rn|Rd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110 << 24) | (0b00 << 22) | (1 << 21) | (vm << 16) | (0b100111 << 10) | (vn << 5) | vd
        self._emit(inst)

    # === NEON SIMD (128-bit, 2D arrangement — double-precision) ===

    def fadd_2d(self, vd: int, vn: int, vm: int):
        """FADD Vd.2D, Vn.2D, Vm.2D"""
        # 0|1|0|01110|01|1|Vm|110101|Vn|Vd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110011 << 21) | (vm << 16) | (0b110101 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fsub_2d(self, vd: int, vn: int, vm: int):
        """FSUB Vd.2D, Vn.2D, Vm.2D"""
        # 0|1|0|01110|11|1|Vm|110101|Vn|Vd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110111 << 21) | (vm << 16) | (0b110101 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fmul_2d(self, vd: int, vn: int, vm: int):
        """FMUL Vd.2D, Vn.2D, Vm.2D"""
        # 0|1|1|01110|01|1|Vm|110111|Vn|Vd
        inst = (0 << 31) | (1 << 30) | (1 << 29) | (0b01110011 << 21) | (vm << 16) | (0b110111 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fdiv_2d(self, vd: int, vn: int, vm: int):
        """FDIV Vd.2D, Vn.2D, Vm.2D"""
        # 0|1|1|01110|01|1|Vm|111111|Vn|Vd
        inst = (0 << 31) | (1 << 30) | (1 << 29) | (0b01110011 << 21) | (vm << 16) | (0b111111 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fmla_2d(self, vd: int, vn: int, vm: int):
        """FMLA Vd.2D, Vn.2D, Vm.2D (Vd += Vn * Vm)"""
        # 0|1|0|01110|01|1|Vm|110011|Vn|Vd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110011 << 21) | (vm << 16) | (0b110011 << 10) | (vn << 5) | vd
        self._emit(inst)

    def fmls_2d(self, vd: int, vn: int, vm: int):
        """FMLS Vd.2D, Vn.2D, Vm.2D (Vd -= Vn * Vm)"""
        # 0|1|0|01110|11|1|Vm|110011|Vn|Vd
        inst = (0 << 31) | (1 << 30) | (0 << 29) | (0b01110111 << 21) | (vm << 16) | (0b110011 << 10) | (vn << 5) | vd
        self._emit(inst)

    # === NEON SIMD (128-bit, load/store) ===

    def ld1_4s(self, vt: int, rn: int):
        """LD1 {Vt.4S}, [Xn]"""
        # 0|1|001100|0|1|0|00000|1010|10|Rn|Rt
        inst = (0 << 31) | (1 << 30) | (0b001100010 << 21) | (0 << 16) | (0b101010 << 10) | (rn << 5) | vt
        self._emit(inst)

    def st1_4s(self, vt: int, rn: int):
        """ST1 {Vt.4S}, [Xn]"""
        inst = (0 << 31) | (1 << 30) | (0b001100000 << 21) | (0 << 16) | (0b101010 << 10) | (rn << 5) | vt
        self._emit(inst)

    def ld1_2d(self, vt: int, rn: int):
        """LD1 {Vt.2D}, [Xn] (128-bit load, 2x64-bit double-precision arrangement)"""
        # 0|Q=1|001100010|0|00000|opcode+size=101011|Rn|Rt
        inst = (0 << 31) | (1 << 30) | (0b001100010 << 21) | (0 << 16) | (0b101011 << 10) | (rn << 5) | vt
        self._emit(inst)

    def st1_2d(self, vt: int, rn: int):
        """ST1 {Vt.2D}, [Xn] (128-bit store, 2x64-bit double-precision arrangement)"""
        # 0|Q=1|001100000|0|00000|opcode+size=101011|Rn|Rt
        inst = (0 << 31) | (1 << 30) | (0b001100000 << 21) | (0 << 16) | (0b101011 << 10) | (rn << 5) | vt
        self._emit(inst)

    def ld1_4s_post(self, vt: int, rn: int):
        """LD1 {Vt.4S}, [Xn], #16 (post-increment by 16 bytes for 4x32-bit)"""
        # 0|Q=1|001100110|0|Rm=11111|opcode+size=101010|Rn|Rt
        inst = (0 << 31) | (1 << 30) | (0b001100110 << 21) | (0b11111 << 16) | (0b101010 << 10) | (rn << 5) | vt
        self._emit(inst)

    def st1_4s_post(self, vt: int, rn: int):
        """ST1 {Vt.4S}, [Xn], #16 (post-increment by 16 bytes for 4x32-bit)"""
        # 0|Q=1|001100100|0|Rm=11111|opcode+size=101010|Rn|Rt
        inst = (0 << 31) | (1 << 30) | (0b001100100 << 21) | (0b11111 << 16) | (0b101010 << 10) | (rn << 5) | vt
        self._emit(inst)

    def ld1_2d_post(self, vt: int, rn: int):
        """LD1 {Vt.2D}, [Xn], #16 (post-increment by 16 bytes for 2x64-bit)"""
        # 0|Q=1|001100110|0|Rm=11111|opcode+size=101011|Rn|Rt
        inst = (0 << 31) | (1 << 30) | (0b001100110 << 21) | (0b11111 << 16) | (0b101011 << 10) | (rn << 5) | vt
        self._emit(inst)

    def st1_2d_post(self, vt: int, rn: int):
        """ST1 {Vt.2D}, [Xn], #16 (post-increment by 16 bytes for 2x64-bit)"""
        # 0|Q=1|001100100|0|Rm=11111|opcode+size=101011|Rn|Rt
        inst = (0 << 31) | (1 << 30) | (0b001100100 << 21) | (0b11111 << 16) | (0b101011 << 10) | (rn << 5) | vt
        self._emit(inst)

    # === Branches ===

    def ret(self, rn: int = LR):
        """RET {Xn} (default: X30/LR)"""
        inst = 0xD65F0000 | (rn << 5)
        self._emit(inst)

    def b(self, label: str):
        """B label (unconditional branch)"""
        offset = len(self.code)
        self._emit(0x14000000)  # B with imm26=0 (patched later)
        self.patches.append((label, offset, "b"))

    def b_cond(self, cond: int, label: str):
        """B.cond label (conditional branch)"""
        offset = len(self.code)
        inst = 0x54000000 | cond  # B.cond with imm19=0
        self._emit(inst)
        self.patches.append((label, offset, "bcond"))

    def cmp_reg(self, rn: int, rm: int, sf: int = 1):
        """CMP Xn, Xm (alias for SUBS XZR, Xn, Xm)"""
        inst = (sf << 31) | (0b1101011000 << 21) | (rm << 16) | (0 << 10) | (rn << 5) | XZR
        self._emit(inst)

    def nop(self):
        """NOP"""
        self._emit(0xD503201F)


# Branch condition codes
COND_EQ = 0b0000
COND_NE = 0b0001
COND_LT = 0b1011
COND_LE = 0b1101
COND_GT = 0b1100
COND_GE = 0b1010
