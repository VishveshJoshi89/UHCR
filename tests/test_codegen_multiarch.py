"""Tests for multi-ISA code generators (AArch64, RISC-V).

These tests verify instruction encoding correctness without executing
the generated code (since we may not be on the target architecture).
"""
import pytest

from uhcr.compiler.ir import Type, Opcode
from uhcr.compiler.ir_builder import IRBuilder


class TestAArch64Assembler:
    def test_import(self):
        from uhcr.compiler.aarch64.assembler import AArch64Assembler
        asm = AArch64Assembler()
        assert asm is not None

    def test_add_encoding(self):
        from uhcr.compiler.aarch64.assembler import AArch64Assembler, X0, X1, X2
        asm = AArch64Assembler()
        asm.add_reg(X0, X1, X2)
        code = asm.get_bytes()
        assert len(code) == 4  # All AArch64 instructions are 4 bytes

    def test_ret_encoding(self):
        from uhcr.compiler.aarch64.assembler import AArch64Assembler, LR
        asm = AArch64Assembler()
        asm.ret()
        code = asm.get_bytes()
        # RET X30 = 0xD65F03C0
        assert code == b'\xc0\x03\x5f\xd6'

    def test_neon_fadd(self):
        from uhcr.compiler.aarch64.assembler import AArch64Assembler, V0, V1, V2
        asm = AArch64Assembler()
        asm.fadd_4s(V0, V1, V2)
        code = asm.get_bytes()
        assert len(code) == 4

    def test_branch_and_label(self):
        from uhcr.compiler.aarch64.assembler import AArch64Assembler
        asm = AArch64Assembler()
        asm.b("target")
        asm.nop()
        asm.label("target")
        asm.nop()
        code = asm.get_bytes()
        assert len(code) == 12  # 3 instructions


class TestAArch64CodeGen:
    def test_compile_scalar_add(self):
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("add", [Type.I64, Type.I64], Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        builder.ret(builder.add(func.arguments[0], func.arguments[1]))

        codegen = AArch64CodeGenerator(func)
        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0  # All instructions are 4 bytes

    def test_compile_vector_add(self):
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("vadd", [Type.PTR, Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        va = builder.vload(func.arguments[0], 0, Type.V4F32)
        vb = builder.vload(func.arguments[1], 0, Type.V4F32)
        vc = builder.vadd(va, vb)
        builder.vstore(vc, func.arguments[2], 0)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0


class TestAArch64PostIncrement:
    """Tests for post-increment addressing detection and emission."""

    def test_detect_sequential_vloads(self):
        """Sequential VLOADs with same base and incrementing offsets are detected."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("seq_load", [Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        # 4 sequential VLOADs: same base (arg0), offsets 0, 1, 2, 3
        v0 = builder.vload(func.arguments[0], 0, Type.V4F32)
        v1 = builder.vload(func.arguments[0], 1, Type.V4F32)
        v2 = builder.vload(func.arguments[0], 2, Type.V4F32)
        v3 = builder.vload(func.arguments[0], 3, Type.V4F32)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        sequences = codegen._detect_post_increment_pattern(entry)
        # Should detect one sequence starting at index 0 with 4 instructions
        assert len(sequences) == 1
        seq = list(sequences.values())[0]
        assert len(seq) == 4
        assert seq[0] is v0
        assert seq[1] is v1
        assert seq[2] is v2
        assert seq[3] is v3

    def test_detect_sequential_vstores(self):
        """Sequential VSTOREs with same base and incrementing offsets are detected."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("seq_store", [Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        # Load some vectors first
        v0 = builder.vload(func.arguments[0], 0, Type.V4F32)
        v1 = builder.vload(func.arguments[0], 4, Type.V4F32)
        # Sequential VSTOREs: same base (arg1), offsets 0, 1
        builder.vstore(v0, func.arguments[1], 0)
        builder.vstore(v1, func.arguments[1], 1)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        sequences = codegen._detect_post_increment_pattern(entry)
        # Should detect one VSTORE sequence (VLOADs are not sequential: 0, 4)
        assert len(sequences) == 1
        seq = list(sequences.values())[0]
        assert len(seq) == 2
        assert seq[0].opcode == Opcode.VSTORE
        assert seq[1].opcode == Opcode.VSTORE

    def test_no_detection_for_non_sequential(self):
        """Non-sequential offsets should not be detected as post-increment."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("non_seq", [Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        # Non-sequential offsets: 0, 2 (gap of 2, not 1)
        builder.vload(func.arguments[0], 0, Type.V4F32)
        builder.vload(func.arguments[0], 2, Type.V4F32)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        sequences = codegen._detect_post_increment_pattern(entry)
        assert len(sequences) == 0

    def test_no_detection_for_different_bases(self):
        """VLOADs with different base pointers should not be grouped."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("diff_base", [Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        # Same offsets but different bases
        builder.vload(func.arguments[0], 0, Type.V4F32)
        builder.vload(func.arguments[1], 1, Type.V4F32)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        sequences = codegen._detect_post_increment_pattern(entry)
        assert len(sequences) == 0

    def test_post_increment_emits_fewer_instructions(self):
        """Post-increment path should emit fewer instructions than non-sequential."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()

        # Sequential case: 3 VLOADs with offsets 0, 1, 2
        func_seq = builder.new_function("seq", [Type.PTR], Type.VOID)
        entry_seq = func_seq.create_block("entry")
        builder.set_block(entry_seq)
        builder.vload(func_seq.arguments[0], 0, Type.V4F32)
        builder.vload(func_seq.arguments[0], 1, Type.V4F32)
        builder.vload(func_seq.arguments[0], 2, Type.V4F32)
        builder.ret()

        codegen_seq = AArch64CodeGenerator(func_seq)
        code_seq = codegen_seq.compile()

        # Non-sequential case: 3 VLOADs with offsets 0, 5, 10
        func_nonsq = builder.new_function("nonsq", [Type.PTR], Type.VOID)
        entry_nonsq = func_nonsq.create_block("entry")
        builder.set_block(entry_nonsq)
        builder.vload(func_nonsq.arguments[0], 0, Type.V4F32)
        builder.vload(func_nonsq.arguments[0], 5, Type.V4F32)
        builder.vload(func_nonsq.arguments[0], 10, Type.V4F32)
        builder.ret()

        codegen_nonsq = AArch64CodeGenerator(func_nonsq)
        code_nonsq = codegen_nonsq.compile()

        # Sequential should be shorter (post-increment avoids recomputing address)
        assert len(code_seq) < len(code_nonsq)

    def test_compile_sequential_vloads_produces_valid_code(self):
        """Sequential VLOADs compile to valid 4-byte aligned AArch64 code."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("seq_load", [Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        builder.vload(func.arguments[0], 0, Type.V4F32)
        builder.vload(func.arguments[0], 1, Type.V4F32)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0

    def test_compile_sequential_vstores_produces_valid_code(self):
        """Sequential VSTOREs compile to valid 4-byte aligned AArch64 code."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("seq_store", [Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        v0 = builder.vload(func.arguments[0], 0, Type.V4F32)
        v1 = builder.vload(func.arguments[0], 1, Type.V4F32)
        builder.vstore(v0, func.arguments[1], 0)
        builder.vstore(v1, func.arguments[1], 1)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0

    def test_single_vload_uses_non_post_increment(self):
        """A single VLOAD (no sequence) should not use post-increment."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("single", [Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        builder.vload(func.arguments[0], 0, Type.V4F32)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        sequences = codegen._detect_post_increment_pattern(entry)
        assert len(sequences) == 0

        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0


class TestAArch64VFMADD:
    """Tests for VFMADD → FMLA lowering in AArch64 codegen (task 7.4)."""

    def test_fmla_2d_encoding(self):
        """fmla_2d emits correct ARM64 encoding: Q=1, U=0, sz=1 (double-precision)."""
        from uhcr.compiler.aarch64.assembler import AArch64Assembler, V0, V1, V2
        asm = AArch64Assembler()
        asm.fmla_2d(V0, V1, V2)
        code = asm.get_bytes()
        assert len(code) == 4
        word = int.from_bytes(code, "little")
        # Verify key fields:
        # bit 31 = 0, bit 30 (Q) = 1, bit 29 (U) = 0
        assert (word >> 31) & 1 == 0, "bit 31 must be 0"
        assert (word >> 30) & 1 == 1, "Q must be 1 (128-bit)"
        assert (word >> 29) & 1 == 0, "U must be 0"
        # bits 28-24 = 01110
        assert (word >> 24) & 0x1F == 0b01110, "bits 28-24 must be 01110"
        # bit 22 (sz) = 1 for double-precision
        assert (word >> 22) & 1 == 1, "sz must be 1 (double-precision)"
        # bits 15-10 = 110011 (FMLA opcode)
        assert (word >> 10) & 0x3F == 0b110011, "opcode must be 110011 (FMLA)"

    def test_fmla_4s_encoding(self):
        """fmla_4s emits correct ARM64 encoding: Q=1, U=0, sz=0 (single-precision)."""
        from uhcr.compiler.aarch64.assembler import AArch64Assembler, V0, V1, V2
        asm = AArch64Assembler()
        asm.fmla_4s(V0, V1, V2)
        code = asm.get_bytes()
        assert len(code) == 4
        word = int.from_bytes(code, "little")
        # bit 30 (Q) = 1, bit 29 (U) = 0
        assert (word >> 30) & 1 == 1, "Q must be 1 (128-bit)"
        assert (word >> 29) & 1 == 0, "U must be 0"
        # bit 22 (sz) = 0 for single-precision
        assert (word >> 22) & 1 == 0, "sz must be 0 (single-precision)"
        # bits 15-10 = 110011 (FMLA opcode)
        assert (word >> 10) & 0x3F == 0b110011, "opcode must be 110011 (FMLA)"

    def test_fmla_2d_differs_from_fmla_4s(self):
        """fmla_2d and fmla_4s produce different encodings (sz bit differs)."""
        from uhcr.compiler.aarch64.assembler import AArch64Assembler, V0, V1, V2
        asm = AArch64Assembler()
        asm.fmla_2d(V0, V1, V2)
        code_2d = asm.get_bytes()
        asm2 = AArch64Assembler()
        asm2.fmla_4s(V0, V1, V2)
        code_4s = asm2.get_bytes()
        assert code_2d != code_4s, "2D and 4S encodings must differ"

    def test_vfmadd_4s_codegen(self):
        """VFMADD on V4F32 operands lowers to fmla_4s (single-precision path)."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("fmadd_4s", [Type.PTR, Type.PTR, Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        # acc = vload(arg0, 0), a = vload(arg1, 0), b = vload(arg2, 0)
        acc = builder.vload(func.arguments[0], 0, Type.V4F32)
        a = builder.vload(func.arguments[1], 0, Type.V4F32)
        b = builder.vload(func.arguments[2], 0, Type.V4F32)
        result = builder.vfmadd(acc, a, b)
        builder.vstore(result, func.arguments[3], 0)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0

        # Verify fmla_4s encoding appears in the output (sz=0 FMLA)
        words = [int.from_bytes(code[i:i+4], "little") for i in range(0, len(code), 4)]
        fmla_4s_found = any(
            ((w >> 30) & 1 == 1) and  # Q=1
            ((w >> 29) & 1 == 0) and  # U=0
            ((w >> 22) & 1 == 0) and  # sz=0 (single)
            ((w >> 10) & 0x3F == 0b110011)  # FMLA opcode
            for w in words
        )
        assert fmla_4s_found, "Expected fmla_4s instruction in generated code"

    def test_vfmadd_2d_codegen(self):
        """VFMADD on V2F64 operands lowers to fmla_2d (double-precision path)."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("fmadd_2d", [Type.PTR, Type.PTR, Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        # Use V2F64 typed loads to trigger the 2D path
        acc = builder.vload(func.arguments[0], 0, Type.V2F64)
        a = builder.vload(func.arguments[1], 0, Type.V2F64)
        b = builder.vload(func.arguments[2], 0, Type.V2F64)
        result = builder.vfmadd(acc, a, b)
        builder.vstore(result, func.arguments[3], 0)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0

        # Verify fmla_2d encoding appears in the output (sz=1 FMLA)
        words = [int.from_bytes(code[i:i+4], "little") for i in range(0, len(code), 4)]
        fmla_2d_found = any(
            ((w >> 30) & 1 == 1) and  # Q=1
            ((w >> 29) & 1 == 0) and  # U=0
            ((w >> 22) & 1 == 1) and  # sz=1 (double)
            ((w >> 10) & 0x3F == 0b110011)  # FMLA opcode
            for w in words
        )
        assert fmla_2d_found, "Expected fmla_2d instruction in generated code"

    def test_vfmadd_2d_is_v2f64_detection(self):
        """_is_v2f64 correctly identifies V2F64 instructions for VFMADD routing."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_detect", [Type.PTR, Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        acc = builder.vload(func.arguments[0], 0, Type.V2F64)
        a = builder.vload(func.arguments[1], 0, Type.V2F64)
        b = builder.vload(func.arguments[2], 0, Type.V2F64)
        fmadd_inst = builder.vfmadd(acc, a, b)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        # The VFMADD instruction should be detected as V2F64
        assert codegen._is_v2f64(fmadd_inst), "VFMADD with V2F64 operands must be detected as 2D"

    def test_vfmadd_4s_not_v2f64(self):
        """_is_v2f64 returns False for V4F32 VFMADD instructions."""
        from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test_4s", [Type.PTR, Type.PTR, Type.PTR], Type.VOID)
        entry = func.create_block("entry")
        builder.set_block(entry)
        acc = builder.vload(func.arguments[0], 0, Type.V4F32)
        a = builder.vload(func.arguments[1], 0, Type.V4F32)
        b = builder.vload(func.arguments[2], 0, Type.V4F32)
        fmadd_inst = builder.vfmadd(acc, a, b)
        builder.ret()

        codegen = AArch64CodeGenerator(func)
        assert not codegen._is_v2f64(fmadd_inst), "VFMADD with V4F32 operands must NOT be detected as 2D"


class TestRISCVAssembler:
    def test_import(self):
        from uhcr.compiler.riscv.assembler import RISCVAssembler
        asm = RISCVAssembler()
        assert asm is not None

    def test_add_encoding(self):
        from uhcr.compiler.riscv.assembler import RISCVAssembler, A0, A1, A2
        asm = RISCVAssembler()
        asm.add(A0, A1, A2)
        code = asm.get_bytes()
        assert len(code) == 4

    def test_ret_encoding(self):
        from uhcr.compiler.riscv.assembler import RISCVAssembler
        asm = RISCVAssembler()
        asm.ret()
        code = asm.get_bytes()
        # JALR x0, x1, 0 = 0x00008067
        assert code == b'\x67\x80\x00\x00'

    def test_rvv_vsetvli(self):
        from uhcr.compiler.riscv.assembler import RISCVAssembler, T0, A0
        asm = RISCVAssembler()
        asm.vsetvli(T0, A0, sew=32, lmul=1)
        code = asm.get_bytes()
        assert len(code) == 4

    def test_rvv_vector_ops(self):
        from uhcr.compiler.riscv.assembler import RISCVAssembler, T0, T1
        asm = RISCVAssembler()
        asm.vle32(0, T0)
        asm.vle32(1, T1)
        asm.vfadd_vv(2, 0, 1)
        asm.vse32(2, T0)
        code = asm.get_bytes()
        assert len(code) == 16  # 4 instructions


class TestRISCVCodeGen:
    def test_compile_scalar_add(self):
        from uhcr.compiler.riscv.codegen import RISCVCodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("add", [Type.I64, Type.I64], Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        builder.ret(builder.add(func.arguments[0], func.arguments[1]))

        codegen = RISCVCodeGenerator(func)
        code = codegen.compile()
        assert len(code) > 0
        assert len(code) % 4 == 0

    def test_compile_with_rvv(self):
        from uhcr.compiler.riscv.codegen import RISCVCodeGenerator

        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("test", [Type.I64], Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        builder.ret(func.arguments[0])

        codegen = RISCVCodeGenerator(func, has_rvv=True)
        code = codegen.compile()
        assert len(code) > 0
