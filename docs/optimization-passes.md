---
layout: default
title: Optimization Passes
nav_order: 3
parent: Reference
---

# IR Optimization Passes

## Overview

UHCR includes a pipeline of optimization passes that transform IR functions before backend compilation. Passes run automatically when `UHCRRuntime.compile()` is called (can be disabled with `runtime.optimize = False`).

## Default Pipeline

The default pipeline runs these passes in order, iterating to a fixed point:

```
Constant Folding → Strength Reduction → DCE → CSE → DCE
```

## Using the Pipeline

### Automatic (via Runtime)

```python
import uhcr

rt = uhcr.get_runtime()
rt.optimize = True  # Default: enabled

# All compile() calls run optimization automatically
fn = rt.compile(ir_function)
```

### Manual

```python
from uhcr.compiler.passes import run_default_passes, OptimizationPipeline
from uhcr.compiler.passes import ConstantFoldingPass, DeadCodeEliminationPass

# Use default pipeline
optimized = run_default_passes(func)

# Or build a custom pipeline
pipeline = OptimizationPipeline()
pipeline.add(ConstantFoldingPass())
pipeline.add(DeadCodeEliminationPass())
optimized = pipeline.run(func)
```

## Pass Descriptions

### Constant Folding

Evaluates expressions with constant operands at compile time.

**Before:**
```
%0 = add i32 3, 5
%1 = mul i32 %0, 2
ret %1
```

**After:**
```
ret i32 16
```

**Rules:**
- Both operands must be compile-time constants
- Supports ADD, SUB, MUL, DIV (integer and float)
- Chains: if `%0` folds to a constant, `%1` using `%0` can also fold
- Division by zero is never folded (preserved for runtime error)

### Dead Code Elimination (DCE)

Removes instructions whose results are never used by any other instruction.

**Before:**
```
%0 = add i32 %arg0, %arg1   ← used by ret
%1 = mul i32 %arg0, 10      ← DEAD (never referenced)
ret %0
```

**After:**
```
%0 = add i32 %arg0, %arg1
ret %0
```

**Rules:**
- Instructions with side effects are never eliminated (STORE, VSTORE, RET, BR, JMP, MATMUL, RELU)
- Iterative: removing one dead instruction may make others dead
- VOID-type instructions are preserved (they're typically control flow)

### Strength Reduction

Replaces expensive operations with cheaper equivalents.

| Pattern | Replacement | Reason |
|---------|-------------|--------|
| `x * 0` | `0` | Multiplication identity |
| `x * 1` | `x` | Multiplication identity |
| `x + 0` | `x` | Addition identity |
| `x - 0` | `x` | Subtraction identity |
| `x / 1` | `x` | Division identity |
| `x - x` | `0` | Self-subtraction |

### Common Subexpression Elimination (CSE)

Detects duplicate computations and reuses the first result.

**Before:**
```
%0 = add i32 %arg0, %arg1
%1 = add i32 %arg0, %arg1   ← duplicate of %0
%2 = mul i32 %0, %1
ret %2
```

**After:**
```
%0 = add i32 %arg0, %arg1
%1 = mul i32 %0, %0          ← reuses %0
ret %1
```

**Rules:**
- Uses value numbering: `(opcode, type, operand_ids)` as key
- Memory operations (LOAD, VLOAD) are never CSE'd (memory may change between loads)
- Side-effect instructions are never CSE'd
- Only works within a single basic block (no cross-block CSE yet)

## Pipeline Configuration

### Fixed-Point Iteration

The pipeline runs all passes repeatedly until no pass changes anything (max 3 iterations):

```python
pipeline = OptimizationPipeline()
pipeline.add(ConstantFoldingPass())
pipeline.add(DeadCodeEliminationPass())

# Runs up to 3 full iterations
optimized = pipeline.run(func, max_iterations=3)
```

### Statistics

```python
pipeline.run(func)
for stat in pipeline.stats:
    print(f"{stat['pass']}: {stat['before']} → {stat['after']} instructions")
```

## Writing Custom Passes

```python
from uhcr.compiler.passes.pipeline import Pass
from uhcr.compiler.ir import Function

class MyPass(Pass):
    @property
    def name(self) -> str:
        return "my_custom_pass"

    def run(self, func: Function) -> Function:
        # Transform func.blocks[*].instructions
        # Return the modified function
        return func

# Register via plugin system
from uhcr.plugins import Plugin

class MyPlugin(Plugin):
    def initialize(self, runtime):
        self.register_pass("my_pass", MyPass().run)
```

## Performance Impact

From benchmarks on a typical function with redundant operations:

```
Before optimization: 7 instructions
After optimization:  3 instructions (57% reduction)
Optimization time:   ~230 μs (one-time cost, amortized by caching)
```

The optimization pipeline adds negligible overhead since results are cached — the passes only run once per unique function.
