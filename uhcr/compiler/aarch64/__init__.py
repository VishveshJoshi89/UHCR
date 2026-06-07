"""AArch64 (ARM64) code generation — NEON and SVE support."""

from uhcr.compiler.aarch64.assembler import AArch64Assembler
from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator
from uhcr.compiler.aarch64.target_profile import TargetProfile
from uhcr.compiler.aarch64.cross_compile import CrossCompiler, cross_compile

__all__ = [
    "AArch64Assembler",
    "AArch64CodeGenerator",
    "TargetProfile",
    "CrossCompiler",
    "cross_compile",
]
