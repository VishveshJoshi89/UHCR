from typing import Dict, List, Union, Tuple, Optional

# Register definitions
RAX, RCX, RDX, RBX, RSP, RBP, RSI, RDI = range(8)
R8, R9, R10, R11, R12, R13, R14, R15 = range(8, 16)

# Vector registers
XMM0, XMM1, XMM2, XMM3, XMM4, XMM5, XMM6, XMM7 = range(8)
YMM0, YMM1, YMM2, YMM3, YMM4, YMM5, YMM6, YMM7 = range(8)
YMM8, YMM9, YMM10, YMM11, YMM12, YMM13, YMM14, YMM15 = range(8, 16)

class X86_64Assembler:
    """A low-level x86-64 machine code assembler."""
    def __init__(self):
        self.code = bytearray()
        self.labels: Dict[str, int] = {}
        self.patches: List[Tuple[str, int, int]] = []  # (label, instruction_pos, patch_pos)

    def get_bytes(self) -> bytes:
        """Returns the assembled machine code, resolving and patching all jump labels."""
        self.resolve_labels()
        return bytes(self.code)

    def label(self, name: str):
        """Declares a label at the current code offset."""
        assert name not in self.labels, f"Label {name} already defined"
        self.labels[name] = len(self.code)

    def resolve_labels(self):
        """Patches relative offsets for all jump/branch instructions."""
        for label, inst_pos, patch_pos in self.patches:
            if label not in self.labels:
                raise RuntimeError(f"Undefined label: {label}")
            target = self.labels[label]
            # Relative offset is target - (patch_pos + 4)
            offset = target - (patch_pos + 4)
            # Write 32-bit signed offset in little endian
            offset_bytes = int(offset).to_bytes(4, byteorder='little', signed=True)
            self.code[patch_pos:patch_pos+4] = offset_bytes
        self.patches.clear()

    def _write(self, data: Union[int, bytes, bytearray, List[int]]):
        if isinstance(data, int):
            self.code.append(data)
        else:
            self.code.extend(data)

    def _encode_modrm(self, mod: int, reg: int, rm: int) -> int:
        return (mod << 6) | ((reg & 7) << 3) | (rm & 7)

    def _encode_sib(self, scale: int, index: int, base: int) -> int:
        # scale: 0=1x, 1=2x, 2=4x, 3=8x
        return (scale << 6) | ((index & 7) << 3) | (base & 7)

    def _rex(self, w: bool, reg: int, rm: int, index: int = 0) -> Optional[int]:
        rex = 0x40
        if w:
            rex |= 0x08
        if reg >= 8:
            rex |= 0x04
        if index >= 8:
            rex |= 0x02
        if rm >= 8:
            rex |= 0x01
        return rex if rex != 0x40 or w else None

    def _vex3(self, w: int, reg: int, vvvv: int, l: int, pp: int, m_mmmm: int, rm: int, index: int = 0) -> bytes:
        """Encodes the 3-byte VEX prefix used for AVX/AVX2 instructions."""
        R = 0 if reg >= 8 else 1
        X = 0 if index >= 8 else 1
        B = 0 if rm >= 8 else 1
        
        b2 = (R << 7) | (X << 6) | (B << 5) | (m_mmmm & 0x1F)
        v_inv = (~vvvv) & 0x0F
        b3 = (w << 7) | (v_inv << 3) | (l << 2) | (pp & 0x03)
        return bytes([0xC4, b2, b3])

    # Core System Instructions
    def push(self, reg: int):
        """push r64"""
        rex = self._rex(False, 0, reg)
        if rex:
            self._write(rex)
        self._write(0x50 + (reg & 7))

    def pop(self, reg: int):
        """pop r64"""
        rex = self._rex(False, 0, reg)
        if rex:
            self._write(rex)
        self._write(0x58 + (reg & 7))

    def ret(self):
        """ret"""
        self._write(0xC3)

    # General Purpose Instructions
    def mov_reg_reg(self, dst: int, src: int):
        """mov r64, r64"""
        rex = self._rex(True, src, dst)
        if rex:
            self._write(rex)
        self._write(0x89)
        self._write(self._encode_modrm(3, src, dst))

    def mov_reg_imm(self, dst: int, imm: int):
        """mov r64, imm64"""
        rex = self._rex(True, 0, dst)
        if rex:
            self._write(rex)
        self._write(0xB8 + (dst & 7))
        self._write(imm.to_bytes(8, byteorder='little', signed=True))

    def mov_reg_mem(self, dst: int, base: int, offset: int = 0):
        """mov r64, [base + offset]"""
        rex = self._rex(True, dst, base)
        if rex:
            self._write(rex)
        self._write(0x8B)
        
        # SIB byte required for RSP/R12
        use_sib = (base & 7) == RSP
        
        if offset == 0 and not use_sib and (base & 7) != RBP:
            self._write(self._encode_modrm(0, dst, base))
        elif -128 <= offset <= 127:
            self._write(self._encode_modrm(1, dst, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset & 0xFF)
        else:
            self._write(self._encode_modrm(2, dst, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset.to_bytes(4, byteorder='little', signed=True))

    def mov_mem_reg(self, base: int, offset: int, src: int):
        """mov [base + offset], r64"""
        rex = self._rex(True, src, base)
        if rex:
            self._write(rex)
        self._write(0x89)
        
        use_sib = (base & 7) == RSP
        
        if offset == 0 and not use_sib and (base & 7) != RBP:
            self._write(self._encode_modrm(0, src, base))
        elif -128 <= offset <= 127:
            self._write(self._encode_modrm(1, src, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset & 0xFF)
        else:
            self._write(self._encode_modrm(2, src, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset.to_bytes(4, byteorder='little', signed=True))

    def add_reg_reg(self, dst: int, src: int):
        """add r64, r64"""
        rex = self._rex(True, src, dst)
        if rex:
            self._write(rex)
        self._write(0x01)
        self._write(self._encode_modrm(3, src, dst))

    def sub_reg_reg(self, dst: int, src: int):
        """sub r64, r64"""
        rex = self._rex(True, src, dst)
        if rex:
            self._write(rex)
        self._write(0x29)
        self._write(self._encode_modrm(3, src, dst))

    def imul_reg_reg(self, dst: int, src: int):
        """imul r64, r64"""
        rex = self._rex(True, dst, src)
        if rex:
            self._write(rex)
        self._write(0x0F)
        self._write(0xAF)
        self._write(self._encode_modrm(3, dst, src))

    # AVX Vector Floating Point Operations (256-bit YMM)
    def vmovups_load(self, dst: int, base: int, offset: int = 0):
        """vmovups ymmDst, [base + offset]"""
        vex = self._vex3(w=0, reg=dst, vvvv=0, l=1, pp=0, m_mmmm=1, rm=base)
        self._write(vex)
        self._write(0x10) # vmovups load opcode
        
        use_sib = (base & 7) == RSP
        if offset == 0 and not use_sib and (base & 7) != RBP:
            self._write(self._encode_modrm(0, dst, base))
        elif -128 <= offset <= 127:
            self._write(self._encode_modrm(1, dst, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset & 0xFF)
        else:
            self._write(self._encode_modrm(2, dst, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset.to_bytes(4, byteorder='little', signed=True))

    def vmovups_store(self, base: int, offset: int, src: int):
        """vmovups [base + offset], ymmSrc"""
        vex = self._vex3(w=0, reg=src, vvvv=0, l=1, pp=0, m_mmmm=1, rm=base)
        self._write(vex)
        self._write(0x11) # vmovups store opcode
        
        use_sib = (base & 7) == RSP
        if offset == 0 and not use_sib and (base & 7) != RBP:
            self._write(self._encode_modrm(0, src, base))
        elif -128 <= offset <= 127:
            self._write(self._encode_modrm(1, src, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset & 0xFF)
        else:
            self._write(self._encode_modrm(2, src, base))
            if use_sib:
                self._write(self._encode_sib(0, RSP, base))
            self._write(offset.to_bytes(4, byteorder='little', signed=True))

    def vaddps_ymm(self, dst: int, src1: int, src2: int):
        """vaddps ymmDst, ymmSrc1, ymmSrc2"""
        vex = self._vex3(w=0, reg=dst, vvvv=src1, l=1, pp=0, m_mmmm=1, rm=src2)
        self._write(vex)
        self._write(0x58)
        self._write(self._encode_modrm(3, dst, src2))

    def vsubps_ymm(self, dst: int, src1: int, src2: int):
        """vsubps ymmDst, ymmSrc1, ymmSrc2"""
        vex = self._vex3(w=0, reg=dst, vvvv=src1, l=1, pp=0, m_mmmm=1, rm=src2)
        self._write(vex)
        self._write(0x5C)
        self._write(self._encode_modrm(3, dst, src2))

    def vmulps_ymm(self, dst: int, src1: int, src2: int):
        """vmulps ymmDst, ymmSrc1, ymmSrc2"""
        vex = self._vex3(w=0, reg=dst, vvvv=src1, l=1, pp=0, m_mmmm=1, rm=src2)
        self._write(vex)
        self._write(0x59)
        self._write(self._encode_modrm(3, dst, src2))

    def vdivps_ymm(self, dst: int, src1: int, src2: int):
        """vdivps ymmDst, ymmSrc1, ymmSrc2"""
        vex = self._vex3(w=0, reg=dst, vvvv=src1, l=1, pp=0, m_mmmm=1, rm=src2)
        self._write(vex)
        self._write(0x5E)
        self._write(self._encode_modrm(3, dst, src2))

    def vfmadd213ps_ymm(self, dst: int, src1: int, src2: int):
        """vfmadd213ps ymmDst, ymmSrc1, ymmSrc2 (dst = src1 * dst + src2)"""
        # Map is 0x0F 0x38 -> m_mmmm = 2
        # Requires 0x66 prefix -> pp = 1
        # W must be 1 for FMA3 in some variants, we use w=1 (or w=0, but standard specifies vex.W=1 for vfmadd213ps)
        vex = self._vex3(w=1, reg=dst, vvvv=src1, l=1, pp=1, m_mmmm=2, rm=src2)
        self._write(vex)
        self._write(0xA8)
        self._write(self._encode_modrm(3, dst, src2))

    # Control Flow & Branching
    def cmp_reg_reg(self, reg1: int, reg2: int):
        """cmp r64, r64"""
        rex = self._rex(True, reg2, reg1)
        if rex:
            self._write(rex)
        self._write(0x39)
        self._write(self._encode_modrm(3, reg2, reg1))

    def cmp_reg_imm(self, reg: int, imm: int):
        """cmp r64, imm32"""
        rex = self._rex(True, 0, reg)
        if rex:
            self._write(rex)
        self._write(0x81)
        self._write(self._encode_modrm(3, 7, reg)) # 7 is opcode extension for cmp
        self._write(imm.to_bytes(4, byteorder='little', signed=True))

    def jmp(self, label: str):
        """jmp label (unconditional 32-bit relative jump)"""
        self._write(0xE9)
        patch_pos = len(self.code)
        self._write([0, 0, 0, 0]) # Placeholder bytes
        self.patches.append((label, patch_pos - 1, patch_pos))

    def je(self, label: str):
        """je label (jump if equal, 32-bit relative jump)"""
        self._write(0x0F)
        self._write(0x84)
        patch_pos = len(self.code)
        self._write([0, 0, 0, 0])
        self.patches.append((label, patch_pos - 2, patch_pos))

    def jne(self, label: str):
        """jne label (jump if not equal, 32-bit relative jump)"""
        self._write(0x0F)
        self._write(0x85)
        patch_pos = len(self.code)
        self._write([0, 0, 0, 0])
        self.patches.append((label, patch_pos - 2, patch_pos))

    def jlt(self, label: str):
        """jl label (jump if less, 32-bit relative jump)"""
        self._write(0x0F)
        self._write(0x8C)
        patch_pos = len(self.code)
        self._write([0, 0, 0, 0])
        self.patches.append((label, patch_pos - 2, patch_pos))

    def jle(self, label: str):
        """jle label (jump if less or equal, 32-bit relative jump)"""
        self._write(0x0F)
        self._write(0x8E)
        patch_pos = len(self.code)
        self._write([0, 0, 0, 0])
        self.patches.append((label, patch_pos - 2, patch_pos))

    def jgt(self, label: str):
        """jg label (jump if greater, 32-bit relative jump)"""
        self._write(0x0F)
        self._write(0x8F)
        patch_pos = len(self.code)
        self._write([0, 0, 0, 0])
        self.patches.append((label, patch_pos - 2, patch_pos))

    def jge(self, label: str):
        """jge label (jump if greater or equal, 32-bit relative jump)"""
        self._write(0x0F)
        self._write(0x8D)
        patch_pos = len(self.code)
        self._write([0, 0, 0, 0])
        self.patches.append((label, patch_pos - 2, patch_pos))

    # Helper: Epilogue and Prologue for Windows x64 ABI compatibility
    # Non-volatile registers in Windows x64: RBX, RBP, RDI, RSI, R12, R13, R14, R15, XMM6-XMM15.
    # Note: shadow space is 32 bytes.
    def write_prologue(self):
        """Writes typical Windows x64 function prologue, saving rbx and allocating stack space."""
        self.push(RBX)
        self.push(RBP)
        self.push(RSI)
        self.push(RDI)
        # Allocate 32 bytes shadow stack space + alignment (total 40 bytes)
        self.sub_reg_reg(RSP, RAX) # Wait, sub rsp, 40 is easier. Let's do sub_rsp_imm
        self._write(0x48)
        self._write(0x83)
        self._write(self._encode_modrm(3, 5, RSP)) # 5 is sub opcode extension
        self._write(40)

    def write_epilogue(self):
        """Writes Windows x64 function epilogue, restoring saved registers and stack pointer."""
        # add rsp, 40
        self._write(0x48)
        self._write(0x83)
        self._write(self._encode_modrm(3, 0, RSP)) # 0 is add opcode extension
        self._write(40)
        self.pop(RDI)
        self.pop(RSI)
        self.pop(RBP)
        self.pop(RBX)
        self.ret()
