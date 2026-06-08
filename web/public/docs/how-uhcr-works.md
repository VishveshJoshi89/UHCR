# Architecture Overview

UHCR is a hardware-aware compute runtime that compiles Python functions to optimized native machine code at runtime. The system consists of several interconnected subsystems:

```
┌─────────────────────────────────────────────────────────┐
│                   Python Application                    │
│              @uhcr.jit decorated functions              │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │      UHCR Frontend        │
        │   - Function tracing      │
        │   - Type inference        │
        │   - Call interception     │
        └─────────────┬─────────────┘
                      │
        ┌─────────────┴─────────────┐
        │     IR Generator          │
        │   - AST analysis          │
        │   - IR construction       │
        │   - Control flow          │
        └─────────────┬─────────────┘
                      │
        ┌─────────────┴─────────────┐
        │   Optimization Pipeline   │
        │   - Constant folding      │
        │   - Dead code elimination │
        │   - Strength reduction    │
        └─────────────┬─────────────┘
                      │
        ┌─────────────┴─────────────┐
        │    Backend Selector       │
        │   - Hardware detection    │
        │   - Capability matching   │
        │   - Priority resolution   │
        └─────────────┬─────────────┘
                      │
     ┌────────────────┼────────────────┐
     │                │                │
┌────▼────┐    ┌─────▼─────┐    ┌────▼────┐
│CPU-AVX2 │    │CUDA-PTX   │    │Generic  │
│Backend  │    │Backend    │    │Backend  │
└────┬────┘    └─────┬─────┘    └────┬────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
        ┌────────────▼─────────────┐
        │    Runtime System        │
        │   - Memory management    │
        │   - Thread scheduling    │
        │   - Function cache       │
        └─────────────┬────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   Native Execution        │
        │   - Machine code          │
        │   - Hardware acceleration │
        │   - Result handling       │
        └───────────────────────────┘
```

---

## Compilation Pipeline

### Phase 1: Function Interception

When a `@uhcr.jit` decorated function is called:

```python
# Original function call
@uhcr.jit(eager=True)
def compute(a, b):
    return a + b * 2

result = compute(10, 5)  # This triggers compilation
```

UHCR intercepts the call through a wrapper:

```python
# uhcr/frontend/decorator.py
class JitFunction:
    def __init__(self, python_func, config):
        self.python_func = python_func
        self.config = config
        self.compiled_versions = {}  # Cache by signature
        self.call_count = 0
    
    def __call__(self, *args, **kwargs):
        self.call_count += 1
        
        # Determine if compilation is needed
        if self.should_compile():
            return self._compile_and_execute(*args, **kwargs)
        else:
            # Run in Python for warmup
            return self.python_func(*args, **kwargs)
    
    def should_compile(self):
        if self.config.eager:
            return self.call_count >= 1
        else:
            return self.call_count >= 3  # Default warmup
```

### Phase 2: Function Tracing

UHCR traces the Python function execution to capture operations:

```python
# uhcr/frontend/tracing.py
class FunctionTracer:
    def __init__(self):
        self.traced_operations = []
        self.variables = {}
    
    def trace_function(self, func, args):
        """Trace function execution with special value objects"""
        
        # Create traced values for arguments
        traced_args = []
        for i, arg in enumerate(args):
            traced_arg = TracedValue(
                type=self._infer_type(arg),
                name=f"arg_{i}",
                value=arg
            )
            traced_args.append(traced_arg)
        
        # Execute function with traced values
        try:
            # Monkey patch arithmetic operations
            original_add = float.__add__
            float.__add__ = self._traced_add
            
            result = func(*traced_args)
            
            # Restore original operations
            float.__add__ = original_add
            
        except Exception as e:
            raise TracingError(f"Failed to trace function: {e}")
        
        return self.traced_operations, result
    
    def _traced_add(self, other):
        """Traced addition operation"""
        
        # Record the operation
        op = TracedOperation(
            opcode='ADD',
            operands=[self, other],
            result_type=self._infer_result_type(self, other)
        )
        
        self.traced_operations.append(op)
        
        # Return traced result
        result = TracedValue(
            type=op.result_type,
            name=f"tmp_{len(self.traced_operations)}",
            operation=op
        )
        
        return result
```

### Phase 3: IR Generation

Traced operations are converted to UHCR's intermediate representation:

```python
# uhcr/compiler/ir_builder.py
class IRBuilder:
    def __init__(self):
        self.module = None
        self.current_function = None
        self.current_block = None
        self.value_map = {}
    
    def build_from_trace(self, traced_ops, func_name, arg_types):
        """Build IR from traced operations"""
        
        self.module = Module()
        
        # Create function signature
        return_type = self._infer_return_type(traced_ops)
        self.current_function = self.module.create_function(
            func_name, arg_types, return_type
        )
        
        # Create entry block
        self.current_block = self.current_function.create_block("entry")
        
        # Map function arguments
        for i, arg_type in enumerate(arg_types):
            arg_value = self.current_function.get_argument(i)
            self.value_map[f"arg_{i}"] = arg_value
        
        # Generate IR for each traced operation
        for op in traced_ops:
            ir_value = self._generate_ir_for_operation(op)
            if op.result_name:
                self.value_map[op.result_name] = ir_value
        
        return self.module
    
    def _generate_ir_for_operation(self, op):
        """Generate IR instruction for traced operation"""
        
        if op.opcode == 'ADD':
            left = self.value_map[op.operands[0].name]
            right = self.value_map[op.operands[1].name]
            
            if op.result_type.is_float():
                return self.fadd(left, right)
            else:
                return self.add(left, right)
        
        elif op.opcode == 'MUL':
            left = self.value_map[op.operands[0].name]
            right = self.value_map[op.operands[1].name]
            
            if op.result_type.is_float():
                return self.fmul(left, right)
            else:
                return self.mul(left, right)
        
        # ... handle other operations
```

### Phase 4: Optimization

The IR passes through multiple optimization phases:

```python
# uhcr/compiler/optimization.py
class OptimizationPipeline:
    def __init__(self, passes=None):
        self.passes = passes or [
            'constant-folding',
            'dead-code-elimination', 
            'strength-reduction',
            'common-subexpression-elimination',
            'loop-optimization'
        ]
    
    def run(self, module):
        """Run optimization pipeline on IR module"""
        
        for pass_name in self.passes:
            pass_instance = self._get_pass(pass_name)
            module = pass_instance.run(module)
        
        return module

class ConstantFoldingPass:
    def run(self, module):
        """Fold constant expressions at compile time"""
        
        modified = True
        while modified:
            modified = False
            
            for function in module.functions:
                for block in function.blocks:
                    for instruction in list(block.instructions):
                        if self._can_fold(instruction):
                            folded = self._fold_instruction(instruction)
                            block.replace_instruction(instruction, folded)
                            modified = True
        
        return module
    
    def _can_fold(self, instruction):
        """Check if instruction can be constant folded"""
        
        if instruction.opcode in ['ADD', 'SUB', 'MUL', 'DIV']:
            return all(op.is_constant() for op in instruction.operands)
        
        return False
    
    def _fold_instruction(self, instruction):
        """Fold constant instruction to constant value"""
        
        left_val = instruction.operands[0].value
        right_val = instruction.operands[1].value
        
        if instruction.opcode == 'ADD':
            result = left_val + right_val
        elif instruction.opcode == 'MUL':
            result = left_val * right_val
        # ... handle other operations
        
        return ConstantInstruction(result, instruction.type)
```

### Phase 5: Backend Selection

UHCR selects the optimal backend based on hardware capabilities:

```python
# uhcr/backends/backend_selector.py
class BackendSelector:
    def __init__(self, profile):
        self.profile = profile
        self.backends = self._discover_backends()
    
    def select_optimal(self, module):
        """Select best backend for given IR module"""
        
        compatible_backends = []
        
        for backend in self.backends:
            if backend.can_compile(module):
                score = self._score_backend(backend, module)
                compatible_backends.append((backend, score))
        
        if not compatible_backends:
            raise RuntimeError("No compatible backend found")
        
        # Sort by score (higher is better)
        compatible_backends.sort(key=lambda x: x[1], reverse=True)
        
        return compatible_backends[0][0]
    
    def _score_backend(self, backend, module):
        """Score backend based on capabilities and module requirements"""
        
        score = backend.base_priority
        
        # Bonus for hardware-specific features
        if hasattr(self.profile.cpu, 'has_avx512') and self.profile.cpu.has_avx512:
            if 'avx512' in backend.name.lower():
                score += 50
        
        if hasattr(self.profile.gpu, 'cuda_available') and self.profile.gpu.cuda_available:
            if 'cuda' in backend.name.lower():
                score += 100
        
        # Penalty for missing required features
        required_features = module.get_required_features()
        for feature in required_features:
            if not backend.supports_feature(feature):
                score -= 25
        
        return score
```

### Phase 6: Code Generation

The selected backend generates native machine code:

```python
# uhcr/backends/cpu_avx2.py
class AVX2Backend(BackendBase):
    def compile(self, module):
        """Compile IR module to AVX2 machine code"""
        
        codegen = AVX2CodeGenerator()
        
        for function in module.functions:
            # Generate function prologue
            codegen.function_prologue(function)
            
            # Compile each basic block
            for block in function.blocks:
                codegen.block_label(block.name)
                
                for instruction in block.instructions:
                    self._compile_instruction(codegen, instruction)
            
            # Generate function epilogue
            codegen.function_epilogue(function)
        
        # Assemble to machine code
        machine_code = codegen.assemble()
        
        return machine_code
    
    def _compile_instruction(self, codegen, instruction):
        """Compile single IR instruction to AVX2 assembly"""
        
        if instruction.opcode == 'VADD':
            # Vector addition with AVX2
            src1 = self._get_vector_register(instruction.operands[0])
            src2 = self._get_vector_register(instruction.operands[1])
            dst = self._allocate_vector_register()
            
            codegen.emit(f"vaddps {dst}, {src1}, {src2}")
            
        elif instruction.opcode == 'ADD':
            # Scalar addition
            src1 = self._get_register(instruction.operands[0])
            src2 = self._get_register(instruction.operands[1])
            
            codegen.emit(f"addq {src2}, {src1}")
        
        # ... handle other instructions
```

---

## Runtime System

### Memory Management

UHCR manages memory through a sophisticated allocation system:

```python
# uhcr/storage/memory_pool.py
class MemoryPool:
    def __init__(self, pool_size="1GB"):
        self.pool_size = self._parse_size(pool_size)
        self.pool = self._allocate_pool()
        self.free_blocks = [Block(0, self.pool_size)]
        self.allocated_blocks = {}
        self.alignment = 64  # SIMD alignment
    
    def allocate(self, size, alignment=None):
        """Allocate aligned memory block"""
        
        alignment = alignment or self.alignment
        aligned_size = self._align_size(size, alignment)
        
        # Find suitable free block
        for i, block in enumerate(self.free_blocks):
            if block.size >= aligned_size:
                # Split block if necessary
                if block.size > aligned_size:
                    remaining = Block(
                        block.offset + aligned_size,
                        block.size - aligned_size
                    )
                    self.free_blocks[i] = remaining
                else:
                    del self.free_blocks[i]
                
                # Return allocated block
                allocated = Block(block.offset, aligned_size)
                self.allocated_blocks[allocated.offset] = allocated
                
                return self.pool + allocated.offset
        
        raise MemoryError(f"Cannot allocate {size} bytes")
    
    def deallocate(self, ptr):
        """Deallocate memory block"""
        
        offset = ptr - self.pool
        
        if offset not in self.allocated_blocks:
            raise ValueError("Invalid pointer")
        
        block = self.allocated_blocks.pop(offset)
        
        # Add to free blocks and merge adjacent blocks
        self._merge_free_blocks(block)
```

### Thread Scheduling

UHCR uses a work-stealing scheduler for parallel execution:

```python
# uhcr/runtime/scheduler.py
class WorkStealingScheduler:
    def __init__(self, num_threads=None):
        self.num_threads = num_threads or self._detect_cores()
        self.work_queues = [Queue() for _ in range(self.num_threads)]
        self.workers = []
        self.running = False
    
    def start(self):
        """Start worker threads"""
        
        self.running = True
        
        for i in range(self.num_threads):
            worker = WorkerThread(
                thread_id=i,
                local_queue=self.work_queues[i],
                global_queues=self.work_queues,
                scheduler=self
            )
            worker.start()
            self.workers.append(worker)
    
    def submit(self, task):
        """Submit task to least loaded queue"""
        
        min_queue = min(self.work_queues, key=len)
        min_queue.put(task)
    
    def parallel_for(self, start, end, func, chunk_size=None):
        """Execute parallel for loop"""
        
        chunk_size = chunk_size or max(1, (end - start) // self.num_threads)
        
        futures = []
        
        for i in range(start, end, chunk_size):
            chunk_end = min(i + chunk_size, end)
            
            task = ParallelTask(
                func=func,
                args=(i, chunk_end),
                future=Future()
            )
            
            self.submit(task)
            futures.append(task.future)
        
        # Wait for all tasks to complete
        for future in futures:
            future.get()

class WorkerThread(Thread):
    def __init__(self, thread_id, local_queue, global_queues, scheduler):
        super().__init__()
        self.thread_id = thread_id
        self.local_queue = local_queue
        self.global_queues = global_queues
        self.scheduler = scheduler
    
    def run(self):
        """Worker thread main loop"""
        
        while self.scheduler.running:
            # Try to get task from local queue
            task = self._get_local_task()
            
            if task is None:
                # Steal work from other queues
                task = self._steal_work()
            
            if task:
                self._execute_task(task)
            else:
                # No work available, sleep briefly
                time.sleep(0.001)
    
    def _steal_work(self):
        """Steal work from other worker queues"""
        
        for i, queue in enumerate(self.global_queues):
            if i != self.thread_id and not queue.empty():
                try:
                    return queue.get_nowait()
                except:
                    continue
        
        return None
```

### Function Caching

Compiled functions are cached to avoid recompilation:

```python
# uhcr/runtime/function_cache.py
class FunctionCache:
    def __init__(self, max_size=1000):
        self.max_size = max_size
        self.cache = {}
        self.access_times = {}
        self.compilation_stats = {}
    
    def get_cache_key(self, func_name, arg_types, backend_name):
        """Generate cache key for function signature"""
        
        type_sig = tuple(t.name for t in arg_types)
        return f"{func_name}:{type_sig}:{backend_name}"
    
    def get_compiled_function(self, cache_key):
        """Get compiled function from cache"""
        
        if cache_key in self.cache:
            self.access_times[cache_key] = time.time()
            return self.cache[cache_key]
        
        return None
    
    def store_compiled_function(self, cache_key, compiled_func):
        """Store compiled function in cache"""
        
        # Evict if cache is full
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        self.cache[cache_key] = compiled_func
        self.access_times[cache_key] = time.time()
        
        # Update compilation statistics
        self.compilation_stats[cache_key] = {
            'compile_time': compiled_func.compile_time,
            'code_size': compiled_func.code_size,
            'optimizations_applied': compiled_func.optimizations
        }
    
    def _evict_oldest(self):
        """Evict least recently used function"""
        
        oldest_key = min(self.access_times.keys(),
                        key=lambda k: self.access_times[k])
        
        del self.cache[oldest_key]
        del self.access_times[oldest_key]
        del self.compilation_stats[oldest_key]
```

---

## Execution Flow

### Complete Execution Example

Here's how a complete execution flows through the system:

```python
# User code
@uhcr.jit(eager=True, verbose=True)
def matrix_multiply(a, b):
    result = 0.0
    for i in range(len(a)):
        result += a[i] * b[i]
    return result

# This call triggers the full pipeline
result = matrix_multiply([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
```

**Execution Steps:**

1. **Interception**: `JitFunction.__call__` intercepts the call
2. **Tracing**: Function executes with `TracedValue` objects
3. **IR Generation**: Traced operations → UHCR IR
4. **Optimization**: Multiple passes optimize the IR
5. **Backend Selection**: Hardware detection → optimal backend
6. **Code Generation**: Backend compiles IR → machine code
7. **Caching**: Compiled function stored in cache
8. **Execution**: Native machine code executes with real arguments
9. **Result**: Native result converted back to Python

### Performance Monitoring

UHCR tracks performance metrics throughout execution:

```python
# uhcr/runtime/profiler.py
class PerformanceProfiler:
    def __init__(self):
        self.compile_times = {}
        self.execution_times = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def record_compilation(self, func_name, compile_time):
        """Record compilation time"""
        
        if func_name not in self.compile_times:
            self.compile_times[func_name] = []
        
        self.compile_times[func_name].append(compile_time)
    
    def record_execution(self, func_name, execution_time):
        """Record execution time"""
        
        if func_name not in self.execution_times:
            self.execution_times[func_name] = []
        
        self.execution_times[func_name].append(execution_time)
    
    def get_performance_report(self):
        """Generate performance report"""
        
        report = {
            'compilation': {},
            'execution': {},
            'cache': {
                'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses),
                'total_hits': self.cache_hits,
                'total_misses': self.cache_misses
            }
        }
        
        # Compilation statistics
        for func_name, times in self.compile_times.items():
            report['compilation'][func_name] = {
                'count': len(times),
                'avg_time': sum(times) / len(times),
                'total_time': sum(times)
            }
        
        # Execution statistics
        for func_name, times in self.execution_times.items():
            report['execution'][func_name] = {
                'count': len(times),
                'avg_time': sum(times) / len(times),
                'total_time': sum(times),
                'speedup': self._calculate_speedup(func_name)
            }
        
        return report
```

This comprehensive overview shows how UHCR transforms Python functions into optimized native machine code through its sophisticated compilation pipeline and runtime system.

[Next: Runtime System →](runtime){: .btn .btn-primary }
[Previous: Plugins ←](plugins){: .btn }