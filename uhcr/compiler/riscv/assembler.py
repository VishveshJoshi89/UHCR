"""RISC-V machine code assembler — encodes RV64GCV instructions.

Supports:
- RV64I base integer (ADD, SUB, MUL, LD, SD, branches)
- RV64M multiply extension
- RV64V vector extension (vsetvli, vle32, vse32, vfadd, vfmul, vfmacc)
"""

from typing import Dict, List, Tuple


# Integer registers x0-x31
ZERO = 0   # x0 — hardwired zero
RA = 1     # x1 — return address
SP = 2     # x2 — stack pointer
GP = 3     # x3 — global pointer
TP = 4     # x4 — thread pointer
T0, T1, T2 = 5, 6, 7  # temporaries
S0, S1 = 8, 9  # saved (s0 = frame pointer)
A0, A1, A2, A3, A4, A5, A6, A7 = range(10, 18)  # arguments
S2, S3, S4, S5, S6, S7, S8, S9, S10, S11 = range(18, 28)  # saved
T3, T4, T5, T6 = range(28, 32)  # temporaries

FP = S0  # frame pointer alias


class RISCVAssembler:
    """Low-level RISC-V RV64GCV machine code assembler."""

    def __init__(self):
        self.code = bytearray()
        self.labels: Dict[str, int] = {}
        self.patches: List[Tuple[str, int, str]] = []

    def get_bytes(self) -> bytes:
        self._resolve_labels()
        return bytes(self.code)

    def label(self, name: str):
        self.labels[name] = len(self.code)

    def _emit(self, inst: int):
        self.code.extend(inst.to_bytes(4, "little"))

    def _resolve_labels(self):
        for label, offset, patch_type in self.patches:
            if label not in self.labels:
                raise RuntimeError(f"Undefined label: {label}")
            target = self.labels[label]
            diff = target - offset
            if patch_type == "b":
                # B-type immediate encoding
                imm = diff
                imm12 = (imm >> 12) & 1
                imm11 = (imm >> 11) & 1
                imm10_5 = (imm >> 5) & 0x3F
                imm4_1 = (imm >> 1) & 0xF
                existing = int.from_bytes(self.code[offset:offset+4], "little")
                patch = (imm12 << 31) | (imm10_5 << 25) | (imm4_1 << 8) | (imm11 << 7)
                patched = existing | patch
                self.code[offset:offset+4] = patched.to_bytes(4, "little")
            elif patch_type == "jal":
                imm = diff
                imm20 = (imm >> 20) & 1
                imm19_12 = (imm >> 12) & 0xFF
                imm11 = (imm >> 11) & 1
                imm10_1 = (imm >> 1) & 0x3FF
                existing = int.from_bytes(self.code[offset:offset+4], "little")
                patch = (imm20 << 31) | (imm10_1 << 21) | (imm11 << 20) | (imm19_12 << 12)
                patched = existing | patch
                self.code[offset:offset+4] = patched.to_bytes(4, "little")
        self.patches.clear()

    # === R-type ===

    def _r_type(self, opcode: int, rd: int, funct3: int, rs1: int, rs2: int, funct7: int):
        inst = (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode
        self._emit(inst)

    def add(self, rd: int, rs1: int, rs2: int):
        self._r_type(0b0110011, rd, 0b000, rs1, rs2, 0b0000000)

    def sub(self, rd: int, rs1: int, rs2: int):
        self._r_type(0b0110011, rd, 0b000, rs1, rs2, 0b0100000)

    def mul(self, rd: int, rs1: int, rs2: int):
        """MUL (RV64M extension)"""
        self._r_type(0b0110011, rd, 0b000, rs1, rs2, 0b0000001)

    def slli(self, rd: int, rs1: int, shamt: int):
        """SLLI rd, rs1, shamt"""
        inst = (shamt << 20) | (rs1 << 15) | (0b001 << 12) | (rd << 7) | 0b0010011
        self._emit(inst)

    # === I-type ===

    def addi(self, rd: int, rs1: int, imm: int):
        imm12 = imm & 0xFFF
        inst = (imm12 << 20) | (rs1 << 15) | (0b000 << 12) | (rd << 7) | 0b0010011
        self._emit(inst)

    def ld(self, rd: int, rs1: int, imm: int):
        """LD rd, imm(rs1) — load doubleword"""
        imm12 = imm & 0xFFF
        inst = (imm12 << 20) | (rs1 << 15) | (0b011 << 12) | (rd << 7) | 0b0000011
        self._emit(inst)

    def lw(self, rd: int, rs1: int, imm: int):
        """LW rd, imm(rs1) — load word"""
        imm12 = imm & 0xFFF
        inst = (imm12 << 20) | (rs1 << 15) | (0b010 << 12) | (rd << 7) | 0b0000011
        self._emit(inst)

    # === S-type ===

    def sd(self, rs2: int, rs1: int, imm: int):
        """SD rs2, imm(rs1) — store doubleword"""
        imm_lo = imm & 0x1F
        imm_hi = (imm >> 5) & 0x7F
        inst = (imm_hi << 25) | (rs2 << 20) | (rs1 << 15) | (0b011 << 12) | (imm_lo << 7) | 0b0100011
        self._emit(inst)

    def sw(self, rs2: int, rs1: int, imm: int):
        """SW rs2, imm(rs1) — store word"""
        imm_lo = imm & 0x1F
        imm_hi = (imm >> 5) & 0x7F
        inst = (imm_hi << 25) | (rs2 << 20) | (rs1 << 15) | (0b010 << 12) | (imm_lo << 7) | 0b0100011
        self._emit(inst)

    # === Branches ===

    def beq(self, rs1: int, rs2: int, label: str):
        offset = len(self.code)
        inst = (rs2 << 20) | (rs1 << 15) | (0b000 << 12) | 0b1100011
        self._emit(inst)
        self.patches.append((label, offset, "b"))

    def bne(self, rs1: int, rs2: int, label: str):
        offset = len(self.code)
        inst = (rs2 << 20) | (rs1 << 15) | (0b001 << 12) | 0b1100011
        self._emit(inst)
        self.patches.append((label, offset, "b"))

    def blt(self, rs1: int, rs2: int, label: str):
        offset = len(self.code)
        inst = (rs2 << 20) | (rs1 << 15) | (0b100 << 12) | 0b1100011
        self._emit(inst)
        self.patches.append((label, offset, "b"))

    def bge(self, rs1: int, rs2: int, label: str):
        offset = len(self.code)
        inst = (rs2 << 20) | (rs1 << 15) | (0b101 << 12) | 0b1100011
        self._emit(inst)
        self.patches.append((label, offset, "b"))

    def jal(self, rd: int, label: str):
        """JAL rd, label"""
        offset = len(self.code)
        inst = (rd << 7) | 0b1101111
        self._emit(inst)
        self.patches.append((label, offset, "jal"))

    def jalr(self, rd: int, rs1: int, imm: int = 0):
        """JALR rd, rs1, imm (ret = jalr x0, ra, 0)"""
        imm12 = imm & 0xFFF
        inst = (imm12 << 20) | (rs1 << 15) | (0b000 << 12) | (rd << 7) | 0b1100111
        self._emit(inst)

    def ret(self):
        """RET (alias for JALR x0, x1, 0)"""
        self.jalr(ZERO, RA, 0)

    # === RVV (Vector Extension 1.0) ===

    def vsetvli(self, rd: int, rs1: int, sew: int = 32, lmul: int = 1):
        """VSETVLI rd, rs1, vtypei — configure vector unit.

        sew: element width (8, 16, 32, 64)
        lmul: length multiplier (1, 2, 4, 8)
        """
        sew_map = {8: 0, 16: 1, 32: 2, 64: 3}
        lmul_map = {1: 0, 2: 1, 4: 2, 8: 3}
        vsew = sew_map.get(sew, 2)
        vlmul = lmul_map.get(lmul, 0)
        vtype = (vsew << 3) | vlmul
        # vsetvli: 0|imm[10:0]|rs1|111|rd|1010111
        inst = (0 << 31) | (vtype << 20) | (rs1 << 15) | (0b111 << 12) | (rd << 7) | 0b1010111
        self._emit(inst)

    def vle32(self, vd: int, rs1: int):
        """VLE32.V vd, (rs1) — vector load 32-bit elements"""
        # nf=0, mew=0, mop=00, vm=1, lumop=00000, rs1, width=110, vd, 0000111
        inst = (0b000000 << 26) | (1 << 25) | (0 << 20) | (rs1 << 15) | (0b110 << 12) | (vd << 7) | 0b0000111
        self._emit(inst)

    def vse32(self, vs3: int, rs1: int):
        """VSE32.V vs3, (rs1) — vector store 32-bit elements"""
        inst = (0b000000 << 26) | (1 << 25) | (0 << 20) | (rs1 << 15) | (0b110 << 12) | (vs3 << 7) | 0b0100111
        self._emit(inst)

    def vfadd_vv(self, vd: int, vs2: int, vs1: int):
        """VFADD.VV vd, vs2, vs1"""
        # funct6=000000|vm=1|vs2|vs1|001|vd|1010111
        inst = (0b000000 << 26) | (1 << 25) | (vs2 << 20) | (vs1 << 15) | (0b001 << 12) | (vd << 7) | 0b1010111
        self._emit(inst)

    def vfsub_vv(self, vd: int, vs2: int, vs1: int):
        """VFSUB.VV vd, vs2, vs1"""
        inst = (0b000010 << 26) | (1 << 25) | (vs2 << 20) | (vs1 << 15) | (0b001 << 12) | (vd << 7) | 0b1010111
        self._emit(inst)

    def vfmul_vv(self, vd: int, vs2: int, vs1: int):
        """VFMUL.VV vd, vs2, vs1"""
        inst = (0b100100 << 26) | (1 << 25) | (vs2 << 20) | (vs1 << 15) | (0b001 << 12) | (vd << 7) | 0b1010111
        self._emit(inst)

    def vfmacc_vv(self, vd: int, vs1: int, vs2: int):
        """VFMACC.VV vd, vs1, vs2 (vd = vd + vs1 * vs2)"""
        inst = (0b101100 << 26) | (1 << 25) | (vs2 << 20) | (vs1 << 15) | (0b001 << 12) | (vd << 7) | 0b1010111
        self._emit(inst)
