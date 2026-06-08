# Multi-ISA Code Generation

## Overview

UHCR includes JIT compilation backends for three instruction set architectures:

| ISA | Module | Vector Support | Calling Convention |
|-----|--------|---------------|-------------------|
| x86_64 | `uhcr.compiler.x86_64` | AVX2 (256-bit YMM) | Win64 + SysV AMD64 |
| AArch64 | `uhcr.compiler.aarch64` | NEON (128-bit 4S) | AAPCS64 |
| RISC-V | `uhcr.compiler.riscv` | RVV 1.0 (scalable) | LP64D |

## x86_64 Backend (Native Execution)

The x86_64 backend compiles IR to native machine code and executes it directly on the host. It supports both Windows x64 and System V AMD64 calling conventions.

### Supported Instructions

- Scalar: ADD, SUB, MUL (64-bit GPR)
- Vector: VLOAD, VSTORE, VADD, VSUB, VMUL, VDIV, VFMADD (256-bit AVX2)
- Memory: LOAD, STORE with offset computation
- Control: CMP, BR, JMP, RET
- Intrinsics: MATMUL (triple-nested loop with SSE scalar math)

### Register Allocation

| Register | Usage |
|----------|-------|
| RBP | Frame pointer |
| RBX, RSI, RDI | Callee-saved (used for MATMUL loops) |
| R10, R11 | Scratch temporaries |
| YMM0-YMM5 | Vector operands |
| RCX/RDI, RDX/RSI, R8/RDX, R9/RCX | Arguments (Win64/SysV) |

## AArch64 Backend (Native & Cross-Compilation)

The AArch64 backend generates ARM64 machine code with NEON SIMD support. On ARM hosts (Apple Silicon, Graviton), this code can be executed natively. On x86 hosts, it produces correct binary output for cross-compilation.

### Apple Silicon Support (`uhcr.compiler.aarch64.apple_silicon`)

When running on macOS ARM64 (M-series processors), UHCR natively allocates executable memory using Darwin's `MAP_JIT` flag, conforming to Apple's security requirements.

```python
from uhcr.compiler.aarch64.apple_silicon import AppleSiliconInfo

info = AppleSiliconInfo.detect()
if info.is_apple_silicon:
    print(f"Running on Apple Silicon {info.chip_generation}")
    # supports_map_jit will be True on macOS ARM64
```

### Assembler (`uhcr.compiler.aarch64.assembler`)

```python
from uhcr.compiler.aarch64.assembler import AArch64Assembler, X0, X1, V0, V1, V2

asm = AArch64Assembler()
asm.add_reg(X0, X1, X0)       # ADD X0, X1, X0
asm.fadd_4s(V0, V1, V2)       # FADD V0.4S, V1.4S, V2.4S
asm.ld1_4s(V0, X0)            # LD1 {V0.4S}, [X0]
asm.ret()                      # RET
code = asm.get_bytes()
```

### Supported Instructions

**Data Processing:**
- `add_reg`, `sub_reg`, `mul_reg` — 64-bit register operations
- `add_imm`, `sub_imm` — immediate operations
- `mov_reg`, `movz` — register moves

**NEON SIMD (128-bit, 4S float arrangement):**
- `fadd_4s`, `fsub_4s`, `fmul_4s` — vector arithmetic
- `fmla_4s` — fused multiply-accumulate (Vd += Vn * Vm)
- `ld1_4s`, `st1_4s` — vector load/store

**Memory:**
- `ldr_reg`, `str_reg` — scaled offset load/store
- `stp_pre`, `ldp_post` — pair load/store (prologue/epilogue)

**Branches:**
- `b`, `b_cond` — unconditional and conditional branches
- `ret` — return via link register
- `cmp_reg` — compare (sets flags)

### Code Generator

```python
from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder

builder = IRBuilder()
builder.new_module()
func = builder.new_function("add", [Type.I64, Type.I64], Type.I64)
entry = func.create_block("entry")
builder.set_block(entry)
builder.ret(builder.add(func.arguments[0], func.arguments[1]))

codegen = AArch64CodeGenerator(func)
arm_code = codegen.compile()  # Returns AArch64 machine code bytes
```

## RISC-V Backend (Cross-Compilation)

The RISC-V backend generates RV64GCV machine code with optional Vector extension (RVV 1.0) support.

### Assembler (`uhcr.compiler.riscv.assembler`)

```python
from uhcr.compiler.riscv.assembler import RISCVAssembler, A0, A1, T0, T1, ZERO

asm = RISCVAssembler()
asm.add(A0, A1, T0)           # add a0, a1, t0
asm.vsetvli(T0, A0, sew=32)   # vsetvli t0, a0, e32, m1
asm.vle32(0, T0)              # vle32.v v0, (t0)
asm.vfadd_vv(2, 0, 1)        # vfadd.vv v2, v0, v1
asm.vse32(2, T0)              # vse32.v v2, (t0)
asm.ret()                     # ret
code = asm.get_bytes()
```

### Supported Instructions

**RV64I Base:**
- `add`, `sub`, `addi` — arithmetic
- `ld`, `sd`, `lw`, `sw` — memory
- `beq`, `bne`, `blt`, `bge` — branches
- `jal`, `jalr`, `ret` — jumps

**RV64M Extension:**
- `mul` — integer multiply
- `slli` — shift left logical

**RVV 1.0 (Vector Extension):**
- `vsetvli` — configure vector unit (SEW, LMUL)
- `vle32`, `vse32` — vector load/store (32-bit elements)
- `vfadd_vv`, `vfsub_vv`, `vfmul_vv` — vector float arithmetic
- `vfmacc_vv` — vector fused multiply-accumulate

### Code Generator

```python
from uhcr.compiler.riscv.codegen import RISCVCodeGenerator

codegen = RISCVCodeGenerator(func, has_rvv=True)
rv_code = codegen.compile()  # Returns RISC-V machine code bytes
```

## Cross-Compilation Workflow

```python
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder
from uhcr.compiler.aarch64.codegen import AArch64CodeGenerator
from uhcr.compiler.riscv.codegen import RISCVCodeGenerator

# Build IR once
builder = IRBuilder()
builder.new_module()
func = builder.new_function("compute", [Type.I64, Type.I64], Type.I64)
entry = func.create_block("entry")
builder.set_block(entry)
builder.ret(builder.add(func.arguments[0], func.arguments[1]))

# Generate for multiple targets
x86_code = uhcr.get_runtime().compile(func)  # Native execution
arm_code = AArch64CodeGenerator(func).compile()  # ARM64 bytes
rv_code = RISCVCodeGenerator(func).compile()  # RISC-V bytes

# Write to object files for deployment
with open("compute_arm64.bin", "wb") as f:
    f.write(arm_code)
with open("compute_rv64.bin", "wb") as f:
    f.write(rv_code)
```

## Adding a New ISA Target

1. Create `uhcr/compiler/<isa>/assembler.py` — instruction encoding
2. Create `uhcr/compiler/<isa>/codegen.py` — IR lowering
3. Add hardware detection in `uhcr/hardware/`
4. Create a backend in `uhcr/backends/` that uses your codegen
5. Register the backend in `uhcr/backends/backend_selector.py`

See the AArch64 and RISC-V implementations as reference.
