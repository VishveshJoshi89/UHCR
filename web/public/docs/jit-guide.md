# @uhcr.jit — JIT Compilation Guide

## Overview

The `@uhcr.jit` decorator traces Python functions and compiles them to native machine code via the UHCR compiler pipeline. It provides zero-effort acceleration for arithmetic-heavy functions.

## Basic Usage

```python
import uhcr

@uhcr.jit
def add(a, b):
    return a + b

# First 2 calls execute in Python (warmup)
add(1, 2)  # Python
add(3, 4)  # Python

# 3rd call triggers compilation + executes natively
result = add(10, 32)  # Compiled! Returns 42
```

## Eager Compilation

Use `eager=True` to compile on the very first call:

```python
@uhcr.jit(eager=True)
def multiply(x, y):
    return x * y

result = multiply(7, 6)  # Compiles immediately, returns 42
```

## Verbose Mode

```python
@uhcr.jit(eager=True, verbose=True)
def compute(a, b):
    return (a + b) * 2

compute(10, 11)
# [uhcr.jit] Compiled 'compute' for signature (('int',), ('int',))
```

## Supported Operations

The JIT decorator traces these Python operations and maps them to UHCR IR:

| Python | IR Opcode | Notes |
|--------|-----------|-------|
| `a + b` | ADD/FADD | Integer or float |
| `a - b` | SUB/FSUB | Integer or float |
| `a * b` | MUL/FMUL | Integer or float |
| `a / b` | DIV/FDIV | Integer or float |

## Type Inference

Argument types are inferred from the first compilation call:

| Python Type | IR Type | Notes |
|-------------|---------|-------|
| `int` | `Type.I64` | 64-bit integer |
| `float` | `Type.F64` | 64-bit float |
| Tensor | `Type.PTR` | Pointer to aligned buffer |

## Compilation Caching

Each unique type signature is compiled once and cached:

```python
@uhcr.jit(eager=True)
def add(a, b):
    return a + b

add(1, 2)      # Compiles for (int, int) → int
add(10, 20)    # Uses cached version (same signature)
```

## Fallback Behavior

If a function can't be compiled (e.g., uses strings, objects, or complex control flow), it falls back to Python transparently:

```python
@uhcr.jit
def string_fn(s):
    return s.upper()

string_fn("hello")  # Runs in Python, returns "HELLO"
```

## API Reference

### `@uhcr.jit`

```python
@uhcr.jit
@uhcr.jit(eager=False, verbose=False)
```

**Parameters:**
- `eager` (bool): Compile on first call. Default: `False` (compile after 3 calls).
- `verbose` (bool): Print compilation messages. Default: `False`.

### JitFunction Properties

```python
@uhcr.jit(eager=True)
def fn(a, b):
    return a + b

fn.is_compiled        # bool: whether any compiled version exists
fn.python_function    # access the original Python function
fn.invalidate()       # clear compilation cache
```

## How It Works

1. **Tracing**: On compilation trigger, the decorator creates `_TracedValue` objects for each argument and executes the function. Arithmetic operations on traced values record IR instructions.

2. **IR Building**: The traced operations are captured as UHCR IR via `IRBuilder`.

3. **Optimization**: The IR passes through the optimization pipeline (constant folding, DCE, strength reduction, CSE).

4. **Compilation**: The optimized IR is compiled by the best available backend (AVX2 on x86_64).

5. **Caching**: The compiled native function is cached by type signature.

6. **Execution**: Subsequent calls with the same types execute the cached native code directly.

## Limitations

- Only scalar arithmetic is traced (no loops, branches, or array indexing yet)
- Complex control flow falls back to Python
- Object methods and attribute access are not traced
- The function must be pure (no side effects during tracing)

## Future Roadmap

- Loop tracing (for → IR loop constructs)
- Array/tensor operation tracing
- Conditional branch tracing
- GPU kernel generation from traced functions
