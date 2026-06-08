# UHCR Native Safety Layer

C++ safety layer to prevent hardware damage from unsafe Python execution.

## Safety Features

### 1. Memory Safety
- Bounds checking on all memory operations
- Guard pages to detect buffer overflows
- Address sanitization
- Stack overflow protection

### 2. CPU Protection
- Temperature monitoring
- Frequency throttling detection
- Core usage limits
- SIMD instruction validation

### 3. GPU Protection
- VRAM overflow prevention
- Thermal throttling detection
- Power limit enforcement
- Command buffer validation

### 4. Resource Limits
- Memory allocation caps
- Execution time limits
- Thread count limits
- File descriptor limits

## Build

```bash
# Windows (MSVC)
cl /EHsc /std:c++17 /O2 safety_monitor.cpp /link /OUT:safety_monitor.dll

# Linux/macOS (GCC/Clang)
g++ -std=c++17 -O2 -shared -fPIC safety_monitor.cpp -o safety_monitor.so

# Build all
python build_native.py
```

## Integration

The Python code automatically loads the native safety layer via ctypes:

```python
from uhcr.native import SafetyMonitor

monitor = SafetyMonitor()
monitor.enable()

# All operations are now protected
```

## Architecture

```
Python Layer (uhcr.runtime)
         ↓
C++ Safety Monitor
         ↓
   Hardware Access
```

Every hardware operation passes through the C++ safety monitor which validates:
- Memory bounds
- Resource limits
- Thermal state
- Power constraints

If any safety violation is detected, the operation is aborted before reaching hardware.
