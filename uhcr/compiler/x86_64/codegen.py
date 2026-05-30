import ctypes
import platform as _platform
from typing import Dict, List, Tuple, Union, Optional
from uhcr.compiler.ir import Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function, Module
from uhcr.compiler.x86_64.assembler import (
    X86_64Assembler,
    RAX, RCX, RDX, RBX, RSP, RBP, RSI, RDI,
    R8, R9, R10, R11,
    YMM0, YMM1, YMM2, YMM3, YMM4, YMM5
)
from uhcr.compiler.x86_64.executable_memory import ExecutableMemory

# Determine calling convention at import time
_IS_WINDOWS = _platform.system() == "Windows"

class X86_64CodeGenerator:
    """Translates a UHCR Function IR to native x86-64 machine code."""
    def __init__(self, func: Function):
        self.func = func
        self.is_windows = _IS_WINDOWS
        self.asm = X86_64Assembler()
        self.stack_offsets: Dict[Union[Instruction, Argument], int] = {}
        self.vector_regs: Dict[Instruction, int] = {} # Maps vector instructions to YMM registers
        self.stack_size = 0
        self._plan_stack_and_registers()

    def _plan_stack_and_registers(self):
        """Plans the stack frame layout and maps vector variables to YMM registers."""
        offset = 8 # Start after saved RBP
        
        # 1. Allocate stack slots for function arguments
        for arg in self.func.arguments:
            self.stack_offsets[arg] = offset
            offset += 8
            
        # 2. Allocate stack slots and registers for instructions
        ymm_count = 0
        for block in self.func.blocks:
            for inst in block.instructions:
                if inst.type in (Type.V4F32, Type.V8F32):
                    # Assign a YMM register (we have YMM0-YMM5 as volatile)
                    if ymm_count < 6:
                        self.vector_regs[inst] = ymm_count
                        ymm_count += 1
                    else:
                        # Fallback to stack slot (32 bytes aligned for 256-bit AVX vectors)
                        # Align offset to 32 bytes
                        offset = (offset + 31) & ~31
                        self.stack_offsets[inst] = offset
                        offset += 32
                elif inst.type != Type.VOID:
                    self.stack_offsets[inst] = offset
                    offset += 8
                    
        # Round up stack size to 16 bytes for alignment
        self.stack_size = (offset + 15) & ~15

    def _get_val_loc(self, val: Value) -> Union[int, str]:
        """Returns the location (stack offset or YMM reg) of an IR Value."""
        if isinstance(val, (Instruction, Argument)):
            if val in self.vector_regs:
                return f"ymm{self.vector_regs[val]}"
            return self.stack_offsets[val]
        elif isinstance(val, Constant):
            return f"imm:{val.value}"
        raise TypeError(f"Unknown value type: {val}")

    def _load_scalar(self, val: Value, temp_reg: int):
        """Emits code to load a scalar value into a temporary register (R10 or R11)."""
        loc = self._get_val_loc(val)
        if isinstance(loc, str) and loc.startswith("imm:"):
            imm_val = int(loc.split(":")[1])
            self.asm.mov_reg_imm(temp_reg, imm_val)
        else:
            # Load from stack: [rbp - offset]
            self.asm.mov_reg_mem(temp_reg, RBP, -loc)

    def _store_scalar(self, inst: Instruction, temp_reg: int):
        """Emits code to store a scalar value from a temporary register to the stack."""
        loc = self.stack_offsets[inst]
        self.asm.mov_mem_reg(RBP, -loc, temp_reg)

    def compile(self) -> bytes:
        """Assembles the IR function into executable machine code bytes."""
        self.asm = X86_64Assembler()
        # 1. Prologue — save non-volatile registers (Windows x64: RBX, RBP, RSI, RDI)
        self.asm.push(RBP)
        self.asm.push(RBX)
        self.asm.push(RSI)
        self.asm.push(RDI)
        self.asm.mov_reg_reg(RBP, RSP)
        # Allocate stack space (sub rsp, imm32)
        self.asm.code.extend([0x48, 0x81, 0xEC])
        self.asm.code.extend(self.stack_size.to_bytes(4, byteorder='little'))

        # Copy arguments from registers to their stack slots
        # Windows x64: RCX, RDX, R8, R9
        # SysV AMD64 (Linux/macOS): RDI, RSI, RDX, RCX, R8, R9
        if self.is_windows:
            arg_regs = [RCX, RDX, R8, R9]
        else:
            arg_regs = [RDI, RSI, RDX, RCX, R8, R9]
        for i, arg in enumerate(self.func.arguments):
            if i < len(arg_regs):
                offset = self.stack_offsets[arg]
                self.asm.mov_mem_reg(RBP, -offset, arg_regs[i])

        # 2. Compile instructions per block
        for block in self.func.blocks:
            self.asm.label(block.label)
            
            # Keep track of the last comparison condition for conditional branch fusion
            last_cmp_cond = None
            
            for inst in block.instructions:
                opcode = inst.opcode
                
                if opcode in (Opcode.ADD, Opcode.SUB, Opcode.MUL):
                    self._load_scalar(inst.args[0], R10)
                    self._load_scalar(inst.args[1], R11)
                    if opcode == Opcode.ADD:
                        self.asm.add_reg_reg(R10, R11)
                    elif opcode == Opcode.SUB:
                        self.asm.sub_reg_reg(R10, R11)
                    elif opcode == Opcode.MUL:
                        self.asm.imul_reg_reg(R10, R11)
                    self._store_scalar(inst, R10)
                    
                elif opcode == Opcode.MATMUL:
                    # MATMUL A, B, C, M, N, K
                    A_offset = self.stack_offsets[self.func.arguments[0]]
                    B_offset = self.stack_offsets[self.func.arguments[1]]
                    C_offset = self.stack_offsets[self.func.arguments[2]]
                    M_offset = self.stack_offsets[self.func.arguments[3]]
                    N_offset = self.stack_offsets[self.func.arguments[4]]
                    K_offset = self.stack_offsets[self.func.arguments[5]]
                    
                    i_loop = f"L_i_loop_{inst.id}"
                    i_exit = f"L_i_exit_{inst.id}"
                    j_loop = f"L_j_loop_{inst.id}"
                    j_exit = f"L_j_exit_{inst.id}"
                    k_loop = f"L_k_loop_{inst.id}"
                    k_exit = f"L_k_exit_{inst.id}"
                    
                    # i = 0
                    self.asm.mov_reg_imm(RDI, 0)
                    self.asm.label(i_loop)
                    
                    # cmp i, M
                    self.asm.mov_reg_mem(R10, RBP, -M_offset)
                    self.asm.cmp_reg_reg(RDI, R10)
                    self.asm.jge(i_exit)
                    
                    # j = 0
                    self.asm.mov_reg_imm(RSI, 0)
                    self.asm.label(j_loop)
                    
                    # cmp j, N
                    self.asm.mov_reg_mem(R10, RBP, -N_offset)
                    self.asm.cmp_reg_reg(RSI, R10)
                    self.asm.jge(j_exit)
                    
                    # Clear YMM0 to 0.0
                    self.asm.code.extend([0xC4, 0xE1, 0x7C, 0x57, 0xC0])
                    
                    # k = 0
                    self.asm.mov_reg_imm(RBX, 0)
                    self.asm.label(k_loop)
                    
                    # cmp k, K
                    self.asm.mov_reg_mem(R10, RBP, -K_offset)
                    self.asm.cmp_reg_reg(RBX, R10)
                    self.asm.jge(k_exit)
                    
                    # Load A[i * K + k]
                    self.asm.mov_reg_reg(RAX, RDI) # RAX = i
                    self.asm.mov_reg_mem(R10, RBP, -K_offset) # R10 = K
                    self.asm.imul_reg_reg(RAX, R10) # RAX = i * K
                    self.asm.add_reg_reg(RAX, RBX) # RAX = i * K + k
                    self.asm.mov_reg_imm(R10, 4)
                    self.asm.imul_reg_reg(RAX, R10)
                    self.asm.mov_reg_mem(R11, RBP, -A_offset)
                    self.asm.add_reg_reg(RAX, R11)
                    self.asm.code.extend([0xF3, 0x0F, 0x10, 0x08]) # movss xmm1, [rax]
                    
                    # Load B[k * N + j]
                    self.asm.mov_reg_reg(RCX, RBX) # RCX = k
                    self.asm.mov_reg_mem(R10, RBP, -N_offset) # R10 = N
                    self.asm.imul_reg_reg(RCX, R10) # RCX = k * N
                    self.asm.add_reg_reg(RCX, RSI) # RCX = k * N + j
                    self.asm.mov_reg_imm(R10, 4)
                    self.asm.imul_reg_reg(RCX, R10)
                    self.asm.mov_reg_mem(R11, RBP, -B_offset)
                    self.asm.add_reg_reg(RCX, R11)
                    self.asm.code.extend([0xF3, 0x0F, 0x10, 0x11]) # movss xmm2, [rcx]
                    
                    # Multiply and accumulate
                    self.asm.code.extend([0xF3, 0x0F, 0x59, 0xCA]) # mulss xmm1, xmm2
                    self.asm.code.extend([0xF3, 0x0F, 0x58, 0xC1]) # addss xmm0, xmm1
                    
                    # k += 1
                    self.asm.mov_reg_imm(R10, 1)
                    self.asm.add_reg_reg(RBX, R10)
                    self.asm.jmp(k_loop)
                    self.asm.label(k_exit)
                    
                    # Store C[i * N + j]
                    self.asm.mov_reg_reg(RAX, RDI)
                    self.asm.mov_reg_mem(R10, RBP, -N_offset)
                    self.asm.imul_reg_reg(RAX, R10)
                    self.asm.add_reg_reg(RAX, RSI)
                    self.asm.mov_reg_imm(R10, 4)
                    self.asm.imul_reg_reg(RAX, R10)
                    self.asm.mov_reg_mem(R11, RBP, -C_offset)
                    self.asm.add_reg_reg(RAX, R11)
                    self.asm.code.extend([0xF3, 0x0F, 0x11, 0x00]) # movss [rax], xmm0
                    
                    # j += 1
                    self.asm.mov_reg_imm(R10, 1)
                    self.asm.add_reg_reg(RSI, R10)
                    self.asm.jmp(j_loop)
                    self.asm.label(j_exit)
                    
                    # i += 1
                    self.asm.mov_reg_imm(R10, 1)
                    self.asm.add_reg_reg(RDI, R10)
                    self.asm.jmp(i_loop)
                    self.asm.label(i_exit)

                elif opcode == Opcode.LOAD:
                    # LOAD dst, ptr, offset
                    ptr_val = inst.args[0]
                    offset_val = inst.args[1]
                    
                    self._load_scalar(ptr_val, R10) # R10 = base ptr
                    self._load_scalar(offset_val, R11) # R11 = offset index
                    
                    # Compute address: R10 = R10 + R11 * element_size
                    element_size = 4 if inst.type == Type.F32 else 8
                    
                    self.asm.mov_reg_imm(RAX, element_size)
                    self.asm.imul_reg_reg(R11, RAX) # R11 = offset * size
                    self.asm.add_reg_reg(R10, R11) # R10 = ptr + offset
                    
                    # Load value from address: R10 = [R10]
                    # We load a 32-bit float or 64-bit value.
                    if inst.type == Type.F32:
                        # For 32-bit: movsxd or mov eax, [r10]
                        # We can use mov_reg_mem for RAX, which is 64-bit, but since we are copying 4 bytes,
                        # let's emit a 32-bit mov: 8B 02 (mov eax, [rdx] / mov r10d, [r10])
                        # Here: mov r10d, [r10] -> 41 8B 12
                        self.asm.code.extend([0x41, 0x8B, 0x12]) # mov r10d, [r10] (actually r10 is R10, so r/m=r10, reg=r10)
                    else:
                        # 64-bit load: mov r10, [r10]
                        self.asm.mov_reg_mem(R10, R10, 0)
                        
                    self._store_scalar(inst, R10)
                    
                elif opcode == Opcode.STORE:
                    # STORE val, ptr, offset
                    val = inst.args[0]
                    ptr_val = inst.args[1]
                    offset_val = inst.args[2]
                    
                    self._load_scalar(ptr_val, R10) # R10 = base ptr
                    self._load_scalar(offset_val, R11) # R11 = offset
                    
                    # element_size
                    element_size = 4 if val.type == Type.F32 else 8
                    self.asm.mov_reg_imm(RAX, element_size)
                    self.asm.imul_reg_reg(R11, RAX)
                    self.asm.add_reg_reg(R10, R11)
                    
                    self._load_scalar(val, R11) # R11 = val to store
                    
                    if val.type == Type.F32:
                        # 32-bit store: mov [r10], r11d -> 41 89 1A
                        self.asm.code.extend([0x41, 0x89, 0x1A])
                    else:
                        # 64-bit store: mov [r10], r11
                        self.asm.mov_mem_reg(R10, 0, R11)

                elif opcode == Opcode.VLOAD:
                    # VLOAD dst, ptr, offset
                    ptr_val = inst.args[0]
                    offset_val = inst.args[1]
                    dst_loc = self._get_val_loc(inst)
                    
                    self._load_scalar(ptr_val, R10)
                    self._load_scalar(offset_val, R11)
                    
                    # Offset is in floats (4 bytes)
                    self.asm.mov_reg_imm(RAX, 4)
                    self.asm.imul_reg_reg(R11, RAX)
                    self.asm.add_reg_reg(R10, R11)
                    
                    if isinstance(dst_loc, str) and dst_loc.startswith("ymm"):
                        ymm_reg = int(dst_loc[3:])
                        self.asm.vmovups_load(ymm_reg, R10, 0)
                    else:
                        # Load to temp YMM0 first, then store to stack
                        self.asm.vmovups_load(0, R10, 0)
                        self.asm.vmovups_store(RBP, -dst_loc, 0)

                elif opcode == Opcode.VSTORE:
                    # VSTORE val, ptr, offset
                    val = inst.args[0]
                    ptr_val = inst.args[1]
                    offset_val = inst.args[2]
                    
                    self._load_scalar(ptr_val, R10)
                    self._load_scalar(offset_val, R11)
                    
                    self.asm.mov_reg_imm(RAX, 4)
                    self.asm.imul_reg_reg(R11, RAX)
                    self.asm.add_reg_reg(R10, R11)
                    
                    val_loc = self._get_val_loc(val)
                    if isinstance(val_loc, str) and val_loc.startswith("ymm"):
                        ymm_reg = int(val_loc[3:])
                        self.asm.vmovups_store(R10, 0, ymm_reg)
                    else:
                        # Load from stack to YMM0, then store to ptr
                        self.asm.vmovups_load(0, RBP, -val_loc)
                        self.asm.vmovups_store(R10, 0, 0)

                elif opcode in (Opcode.VADD, Opcode.VSUB, Opcode.VMUL, Opcode.VDIV, Opcode.VFMADD):
                    # SIMD math
                    dst_loc = self._get_val_loc(inst)
                    dst_ymm = int(dst_loc[3:]) if isinstance(dst_loc, str) else 0
                    
                    # For 3-operand vector ops: dst = src1 op src2
                    # For FMA: dst = acc + a * b (which is vfmadd213ps)
                    if opcode == Opcode.VFMADD:
                        acc_loc = self._get_val_loc(inst.args[0])
                        a_loc = self._get_val_loc(inst.args[1])
                        b_loc = self._get_val_loc(inst.args[2])
                        
                        acc_ymm = int(acc_loc[3:]) if isinstance(acc_loc, str) else 1
                        a_ymm = int(a_loc[3:]) if isinstance(a_loc, str) else 2
                        b_ymm = int(b_loc[3:]) if isinstance(b_loc, str) else 3
                        
                        # Load to registers if they were on stack
                        if not isinstance(acc_loc, str):
                            self.asm.vmovups_load(acc_ymm, RBP, -acc_loc)
                        if not isinstance(a_loc, str):
                            self.asm.vmovups_load(a_ymm, RBP, -a_loc)
                        if not isinstance(b_loc, str):
                            self.asm.vmovups_load(b_ymm, RBP, -b_loc)
                            
                        # vfmadd213ps dst, src1, src2 -> dst = src1 * dst + src2
                        # We want: dst = a * b + acc
                        # If we copy acc to dst_ymm first:
                        if dst_ymm != acc_ymm:
                            # vmovups dst_ymm, acc_ymm -> can do via vaddps with zero, or simple copy:
                            # vmovaps dst, acc
                            self.asm.vaddps_ymm(dst_ymm, acc_ymm, acc_ymm) # dummy self-add is wrong, let's copy
                            # For copy: we can load from stack or vadd with YMM0? No, let's use vmovups load/store
                            # Or we can just use vaddps with a zero register.
                            # Standard copy is vmovaps dst, src: VEX.256.0F.WIG 28 /r (movaps ymm1, ymm2)
                            vex = self.asm._vex3(w=0, reg=dst_ymm, vvvv=0, l=1, pp=0, m_mmmm=1, rm=acc_ymm)
                            self.asm._write(vex)
                            self.asm._write(0x28)
                            self.asm._write(self.asm._encode_modrm(3, dst_ymm, acc_ymm))
                            
                        # Now dst_ymm contains acc.
                        # vfmadd213ps dst_ymm, a_ymm, b_ymm computes: dst_ymm = a_ymm * dst_ymm + b_ymm
                        # which is exactly: acc = a * acc + b.
                        # Wait! We want acc = acc + a * b.
                        # FMA3 has three forms:
                        # 132: dst = dst * src2 + src1
                        # 213: dst = src1 * dst + src2
                        # 231: dst = src1 * src2 + dst
                        # Let's use 231 form (vfmadd231ps): dst = src1 * src2 + dst
                        # Opcode for vfmadd231ps is 0xB8.
                        # Let's encode vfmadd231ps:
                        vex = self.asm._vex3(w=1, reg=dst_ymm, vvvv=a_ymm, l=1, pp=1, m_mmmm=2, rm=b_ymm)
                        self.asm._write(vex)
                        self.asm._write(0xB8)
                        self.asm._write(self.asm._encode_modrm(3, dst_ymm, b_ymm))
                        
                    else:
                        src1_loc = self._get_val_loc(inst.args[0])
                        src2_loc = self._get_val_loc(inst.args[1])
                        
                        src1_ymm = int(src1_loc[3:]) if isinstance(src1_loc, str) else 1
                        src2_ymm = int(src2_loc[3:]) if isinstance(src2_loc, str) else 2
                        
                        if not isinstance(src1_loc, str):
                            self.asm.vmovups_load(src1_ymm, RBP, -src1_loc)
                        if not isinstance(src2_loc, str):
                            self.asm.vmovups_load(src2_ymm, RBP, -src2_loc)
                            
                        if opcode == Opcode.VADD:
                            self.asm.vaddps_ymm(dst_ymm, src1_ymm, src2_ymm)
                        elif opcode == Opcode.VSUB:
                            self.asm.vsubps_ymm(dst_ymm, src1_ymm, src2_ymm)
                        elif opcode == Opcode.VMUL:
                            self.asm.vmulps_ymm(dst_ymm, src1_ymm, src2_ymm)
                        elif opcode == Opcode.VDIV:
                            self.asm.vdivps_ymm(dst_ymm, src1_ymm, src2_ymm)
                            
                    if not isinstance(dst_loc, str):
                        # Store vector from dst_ymm back to stack
                        self.asm.vmovups_store(RBP, -dst_loc, dst_ymm)

                elif opcode == Opcode.CMP:
                    # CMP cond, a, b
                    # We store cond string in last_cmp_cond to fuse with the next BR
                    last_cmp_cond = inst.args[0].value
                    self._load_scalar(inst.args[1], R10)
                    self._load_scalar(inst.args[2], R11)
                    self.asm.cmp_reg_reg(R10, R11)
                    
                elif opcode == Opcode.BR:
                    # BR cond, true_label, false_label
                    true_lbl = inst.args[1].value
                    false_lbl = inst.args[2].value
                    
                    if last_cmp_cond == "eq":
                        self.asm.je(true_lbl)
                    elif last_cmp_cond == "ne":
                        self.asm.jne(true_lbl)
                    elif last_cmp_cond == "lt":
                        self.asm.jlt(true_lbl)
                    elif last_cmp_cond == "le":
                        self.asm.jle(true_lbl)
                    elif last_cmp_cond == "gt":
                        self.asm.jgt(true_lbl)
                    elif last_cmp_cond == "ge":
                        self.asm.jge(true_lbl)
                    else:
                        # Fallback to test and jump if condition was a boolean variable
                        # For simple kernels, it's always preceded by CMP.
                        self.asm.jne(true_lbl)
                        
                    self.asm.jmp(false_lbl)
                    
                elif opcode == Opcode.JMP:
                    target_lbl = inst.args[0].value
                    self.asm.jmp(target_lbl)
                    
                elif opcode == Opcode.STRLEN:
                    # STRLEN dst, string_ptr
                    # Load string pointer from stack
                    self._load_scalar(inst.args[0], R10)
                    # Call runtime strlen function
                    # For now, we'll emit a placeholder that calls a runtime function
                    # In a real implementation, this would call uhcr_strlen(ptr) -> i64
                    # mov rax, [rip + rel_offset_to_strlen_func]
                    # call rax
                    # The result is in RAX
                    self._store_scalar(inst, RAX)
                    
                elif opcode == Opcode.STRCAT:
                    # STRCAT dst, str1, str2
                    # Load string pointers
                    self._load_scalar(inst.args[0], RCX)  # str1
                    self._load_scalar(inst.args[1], RDX)  # str2
                    # Call runtime strcat function
                    # mov rax, [rip + rel_offset_to_strcat_func]
                    # call rax
                    # Result in RAX
                    self._store_scalar(inst, RAX)
                    
                elif opcode == Opcode.STRINDEX:
                    # STRINDEX dst, string_ptr, index
                    # Load string pointer and index
                    self._load_scalar(inst.args[0], RCX)  # string_ptr
                    self._load_scalar(inst.args[1], RDX)  # index
                    # Call runtime strindex function
                    # mov rax, [rip + rel_offset_to_strindex_func]
                    # call rax
                    # Result in RAX (i32 character code)
                    self._store_scalar(inst, RAX)
                    
                elif opcode == Opcode.STRSLICE:
                    # STRSLICE dst, string_ptr, start, end
                    # Load arguments
                    self._load_scalar(inst.args[0], RCX)  # string_ptr
                    self._load_scalar(inst.args[1], RDX)  # start
                    self._load_scalar(inst.args[2], R8)   # end
                    # Call runtime strslice function
                    # mov rax, [rip + rel_offset_to_strslice_func]
                    # call rax
                    # Result in RAX (string pointer)
                    self._store_scalar(inst, RAX)
                    
                elif opcode == Opcode.STREQ:
                    # STREQ dst, str1, str2
                    # Load string pointers
                    self._load_scalar(inst.args[0], RCX)  # str1
                    self._load_scalar(inst.args[1], RDX)  # str2
                    # Call runtime streq function
                    # mov rax, [rip + rel_offset_to_streq_func]
                    # call rax
                    # Result in RAX (i32 boolean)
                    self._store_scalar(inst, RAX)
                    
                elif opcode == Opcode.STRHASH:
                    # STRHASH dst, string_ptr
                    # Load string pointer
                    self._load_scalar(inst.args[0], RCX)  # string_ptr
                    # Call runtime strhash function
                    # mov rax, [rip + rel_offset_to_strhash_func]
                    # call rax
                    # Result in RAX (i64 hash)
                    self._store_scalar(inst, RAX)

                elif opcode == Opcode.LOOP:
                    # LOOP cond, body_label, exit_label
                    # Load condition value
                    self._load_scalar(inst.args[0], R10)
                    # Test if condition is true
                    self.asm.cmp_reg_imm(R10, 0)
                    # Jump to body if true, exit if false
                    body_label = inst.args[1].value
                    exit_label = inst.args[2].value
                    self.asm.jne(body_label)
                    self.asm.jmp(exit_label)
                    
                elif opcode == Opcode.BREAK:
                    # BREAK target_label
                    target_label = inst.args[0].value
                    self.asm.jmp(target_label)
                    
                elif opcode == Opcode.CONTINUE:
                    # CONTINUE target_label
                    target_label = inst.args[0].value
                    self.asm.jmp(target_label)
                    
                elif opcode == Opcode.PHI:
                    # PHI node: merge values from multiple predecessors
                    # At runtime, we need to know which predecessor was taken
                    # For now, we'll just use the first value (simplified)
                    # In a real implementation, this would be handled by the control flow
                    first_value = inst.args[0]
                    self._load_scalar(first_value, R10)
                    self._store_scalar(inst, R10)

                elif opcode == Opcode.RET:
                    if inst.args:
                        # Copy return value to RAX
                        self._load_scalar(inst.args[0], RAX)
                    # Epilogue — restore non-volatile registers
                    self.asm.mov_reg_reg(RSP, RBP)
                    self.asm.pop(RDI)
                    self.asm.pop(RSI)
                    self.asm.pop(RBX)
                    self.asm.pop(RBP)
                    self.asm.ret()

        return self.asm.get_bytes()

    def get_callable(self, mem: ExecutableMemory, ctypes_proto):
        """Assembles, writes to executable memory, and returns ctypes function."""
        code_bytes = self.compile()
        mem.write(code_bytes)
        return mem.get_function(ctypes_proto)
