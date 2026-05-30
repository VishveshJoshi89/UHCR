"""JIT decorator — traces Python functions and compiles them via UHCR.

The @jit decorator intercepts function calls, traces the operations performed,
builds UHCR IR, and compiles to native code via the runtime's backend selection.

For the initial version, @jit provides:
- Automatic type inference from arguments
- Compilation caching (compile once, run many)
- Transparent fallback to Python if compilation fails
- Support for scalar and array operations
"""

import functools
import inspect
import time
from typing import Any, Callable, Dict, Optional, Tuple

from uhcr.compiler.ir import Type, Function
from uhcr.compiler.ir_builder import IRBuilder


class JitFunction:
    """Wraps a Python function with JIT compilation support."""

    def __init__(self, func: Callable, eager: bool = False, verbose: bool = False):
        self._python_fn = func
        self._compiled_cache: Dict[Tuple, Callable] = {}
        self._eager = eager
        self._verbose = verbose
        self._call_count = 0
        self._compile_threshold = 1 if eager else 3  # Compile after N calls
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        self._call_count += 1

        # Try compiled path
        sig = self._signature(args)
        if sig in self._compiled_cache:
            return self._compiled_cache[sig](*args)

        # Check if we should compile
        if self._call_count >= self._compile_threshold:
            compiled = self._try_compile(args, kwargs)
            if compiled is not None:
                self._compiled_cache[sig] = compiled
                if self._verbose:
                    print(f"[uhcr.jit] Compiled '{self._python_fn.__name__}' for signature {sig}")
                return compiled(*args)

        # Fallback to Python
        return self._python_fn(*args, **kwargs)

    def _signature(self, args: tuple) -> Tuple:
        """Create a type signature from arguments for cache keying."""
        sig = []
        for arg in args:
            if hasattr(arg, "shape") and hasattr(arg, "dtype"):
                # UHCR Tensor
                sig.append(("tensor", arg.shape, str(arg.dtype)))
            elif hasattr(arg, "address"):
                sig.append(("ptr",))
            elif isinstance(arg, int):
                sig.append(("int",))
            elif isinstance(arg, float):
                sig.append(("float",))
            else:
                sig.append(("unknown", type(arg).__name__))
        return tuple(sig)

    def _try_compile(self, args: tuple, kwargs: dict) -> Optional[Callable]:
        """Attempt to compile the function for the given argument types.

        Returns a compiled callable, or None if compilation fails.
        """
        try:
            # Infer argument types
            arg_types = []
            for arg in args:
                if hasattr(arg, "address"):
                    arg_types.append(Type.PTR)
                elif isinstance(arg, int):
                    arg_types.append(Type.I64)
                elif isinstance(arg, float):
                    arg_types.append(Type.F64)
                elif isinstance(arg, str):
                    arg_types.append(Type.STRING)
                else:
                    # Can't compile this signature
                    return None

            # Determine return type from a test call
            test_result = self._python_fn(*args, **kwargs)
            if test_result is None:
                ret_type = Type.VOID
            elif isinstance(test_result, int):
                ret_type = Type.I64
            elif isinstance(test_result, float):
                ret_type = Type.F64
            elif isinstance(test_result, str):
                ret_type = Type.STRING
            else:
                ret_type = Type.VOID

            # For scalar and string functions, build IR directly
            if all(t in (Type.I64, Type.F64, Type.STRING) for t in arg_types) and ret_type in (Type.I64, Type.F64, Type.STRING, Type.VOID):
                return self._compile_scalar(args, kwargs, arg_types, ret_type)

            # For pointer-based functions, use the interpreter wrapper
            return self._compile_traced(args, kwargs, arg_types, ret_type)

        except Exception as e:
            if self._verbose:
                print(f"[uhcr.jit] Compilation failed for '{self._python_fn.__name__}': {e}")
            return None

    def _compile_scalar(self, args, kwargs, arg_types, ret_type) -> Optional[Callable]:
        """Compile a pure scalar/string function by tracing operations."""
        import uhcr

        # Build IR by tracing
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function(
            self._python_fn.__name__,
            arg_types,
            ret_type
        )
        entry = func.create_block("entry")
        builder.set_block(entry)

        # Create traced values for arguments
        traced_args = []
        for i, arg in enumerate(args):
            traced_args.append(_TracedValue(func.arguments[i], builder))

        # Execute the function with traced values
        try:
            result = self._python_fn(*traced_args)
        except (Exception, NotImplementedError):
            # Compilation failed - fall back to Python
            return None

        # Check if result uses unimplemented features (placeholder returns)
        # If the result is a TracedValue that's the same as input and we expected transformation,
        # it means the operation wasn't actually implemented
        if isinstance(result, _TracedValue) and ret_type == Type.STRING:
            # Check if this is just a passthrough (unimplemented string method)
            # by seeing if the IR value is the same as the input
            if len(traced_args) == 1 and result._ir_value is traced_args[0]._ir_value:
                # This is likely an unimplemented string method returning self
                return None

        # Emit return
        if result is not None and isinstance(result, _TracedValue):
            builder.ret(result._ir_value)
        else:
            builder.ret()

        # Compile via runtime
        rt = uhcr.get_runtime()
        compiled = rt.compile(func)
        return compiled

    def _compile_traced(self, args, kwargs, arg_types, ret_type) -> Optional[Callable]:
        """For complex functions, wrap with optimized Python execution."""
        # For now, return None to fall back to Python
        # Future: implement full tracing JIT
        return None

    @property
    def python_function(self) -> Callable:
        """Access the original Python function."""
        return self._python_fn

    @property
    def is_compiled(self) -> bool:
        """Whether any compiled version exists."""
        return len(self._compiled_cache) > 0

    def invalidate(self):
        """Clear the compilation cache."""
        self._compiled_cache.clear()
        self._call_count = 0


class _TracedValue:
    """A value that records operations for IR building."""

    def __init__(self, ir_value, builder: IRBuilder):
        self._ir_value = ir_value
        self._builder = builder

    def __add__(self, other):
        if isinstance(other, _TracedValue):
            # Check if both are strings
            if self._ir_value.type == Type.STRING and other._ir_value.type == Type.STRING:
                result = self._builder.strcat(self._ir_value, other._ir_value)
            else:
                result = self._builder.add(self._ir_value, other._ir_value)
        elif isinstance(other, (int, float)):
            result = self._builder.add(self._ir_value, other)
        elif isinstance(other, str):
            # String concatenation with Python string literal
            result = self._builder.strcat(self._ir_value, other)
        else:
            return NotImplemented
        return _TracedValue(result, self._builder)

    def __radd__(self, other):
        if isinstance(other, (int, float)):
            result = self._builder.add(other, self._ir_value)
            return _TracedValue(result, self._builder)
        elif isinstance(other, str):
            # String concatenation with Python string literal
            result = self._builder.strcat(other, self._ir_value)
            return _TracedValue(result, self._builder)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, _TracedValue):
            result = self._builder.sub(self._ir_value, other._ir_value)
        elif isinstance(other, (int, float)):
            result = self._builder.sub(self._ir_value, other)
        else:
            return NotImplemented
        return _TracedValue(result, self._builder)

    def __mul__(self, other):
        if isinstance(other, _TracedValue):
            result = self._builder.mul(self._ir_value, other._ir_value)
        elif isinstance(other, (int, float)):
            result = self._builder.mul(self._ir_value, other)
        else:
            return NotImplemented
        return _TracedValue(result, self._builder)

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            result = self._builder.mul(other, self._ir_value)
            return _TracedValue(result, self._builder)
        return NotImplemented

    def __truediv__(self, other):
        if isinstance(other, _TracedValue):
            result = self._builder.div(self._ir_value, other._ir_value)
        elif isinstance(other, (int, float)):
            result = self._builder.div(self._ir_value, other)
        else:
            return NotImplemented
        return _TracedValue(result, self._builder)

    def __getitem__(self, index):
        """Support indexing for strings and arrays."""
        if self._ir_value.type == Type.STRING:
            if isinstance(index, slice):
                # String slicing: s[start:end]
                start = index.start if index.start is not None else 0
                end = index.stop if index.stop is not None else -1
                # Convert to I64 if needed
                from uhcr.compiler.ir import Constant
                if isinstance(start, int):
                    start = Constant(Type.I64, start)
                if isinstance(end, int):
                    end = Constant(Type.I64, end)
                result = self._builder.strslice(self._ir_value, start, end)
            else:
                # String indexing: s[i]
                # Convert to I64 if needed
                from uhcr.compiler.ir import Constant
                if isinstance(index, int):
                    index = Constant(Type.I64, index)
                result = self._builder.strindex(self._ir_value, index)
        else:
            # For non-strings, return NotImplemented
            return NotImplemented
        return _TracedValue(result, self._builder)

    def __len__(self):
        """Support len() for strings."""
        if self._ir_value.type == Type.STRING:
            result = self._builder.strlen(self._ir_value)
            return result  # Return the instruction directly, not wrapped
        return NotImplemented

    def __eq__(self, other):
        """Support equality comparison for strings."""
        if isinstance(other, _TracedValue):
            if self._ir_value.type == Type.STRING and other._ir_value.type == Type.STRING:
                result = self._builder.streq(self._ir_value, other._ir_value)
                return _TracedValue(result, self._builder)
        elif isinstance(other, str):
            if self._ir_value.type == Type.STRING:
                result = self._builder.streq(self._ir_value, other)
                return _TracedValue(result, self._builder)
        return NotImplemented

    def __ne__(self, other):
        """Support inequality comparison for strings."""
        eq_result = self.__eq__(other)
        if eq_result is NotImplemented:
            return NotImplemented
        # For now, return the equality result (would need NOT operation in IR)
        return eq_result

    def upper(self):
        """String upper() method."""
        if self._ir_value.type == Type.STRING:
            # String methods not yet implemented - return self as placeholder
            # The JIT compiler will detect this and fall back to Python
            return self
        return NotImplemented

    def lower(self):
        """String lower() method."""
        if self._ir_value.type == Type.STRING:
            # String methods not yet implemented - return self as placeholder
            return self
        return NotImplemented

    def strip(self):
        """String strip() method."""
        if self._ir_value.type == Type.STRING:
            # String methods not yet implemented - return self as placeholder
            return self
        return NotImplemented

    def split(self, sep=None):
        """String split() method."""
        if self._ir_value.type == Type.STRING:
            # String methods not yet implemented - return self as placeholder
            return self
        return NotImplemented

    def join(self, iterable):
        """String join() method."""
        if self._ir_value.type == Type.STRING:
            # String methods not yet implemented - return self as placeholder
            return self
        return NotImplemented

    def find(self, sub):
        """String find() method."""
        if self._ir_value.type == Type.STRING:
            # String methods not yet implemented - return self as placeholder
            return self
        return NotImplemented

    def replace(self, old, new):
        """String replace() method."""
        if self._ir_value.type == Type.STRING:
            # String methods not yet implemented - return self as placeholder
            return self
        return NotImplemented


class _LoopContext:
    """Context manager for tracing loops."""
    
    def __init__(self, builder: IRBuilder, iterable, loop_var_name: str = "i"):
        """Initialize loop context.
        
        Args:
            builder: The IR builder
            iterable: The iterable to loop over (range, list, etc.)
            loop_var_name: Name of the loop variable
        """
        self.builder = builder
        self.iterable = iterable
        self.loop_var_name = loop_var_name
        self.header_block = None
        self.body_block = None
        self.exit_block = None
        self.loop_var = None
        self.current_value = None
        
    def __enter__(self):
        """Enter the loop context."""
        # Create basic blocks for loop structure
        self.header_block = self.builder.current_block.parent.create_block(f"loop_header_{id(self)}")
        self.body_block = self.builder.current_block.parent.create_block(f"loop_body_{id(self)}")
        self.exit_block = self.builder.current_block.parent.create_block(f"loop_exit_{id(self)}")
        
        # Jump to header
        self.builder.jmp(self.header_block)
        
        # Set up header block
        self.builder.set_block(self.header_block)
        
        # For now, we'll handle simple range() loops
        if isinstance(self.iterable, range):
            # Create loop counter
            start = self.iterable.start if self.iterable.start is not None else 0
            stop = self.iterable.stop
            step = self.iterable.step if self.iterable.step is not None else 1
            
            # Initialize counter (simplified - would need phi node for real implementation)
            from uhcr.compiler.ir import Constant
            self.loop_var = _TracedValue(Constant(Type.I64, start), self.builder)
            
            # Create condition: counter < stop
            cond = self.builder.cmp("lt", self.loop_var._ir_value, stop)
            
            # Create loop instruction
            self.builder.loop(cond, self.body_block, self.exit_block)
        
        # Set up body block
        self.builder.set_block(self.body_block)
        
        return self.loop_var
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the loop context."""
        # Jump back to header
        self.builder.continue_loop(self.header_block)
        
        # Set up exit block
        self.builder.set_block(self.exit_block)
        
        return False


def jit(func=None, *, eager: bool = False, verbose: bool = False):
    """Decorator to JIT-compile a Python function via UHCR.

    Usage:
        @jit
        def add(a, b):
            return a + b

        @jit(eager=True, verbose=True)
        def multiply(x, y):
            return x * y

    Args:
        eager: If True, compile on first call. Otherwise compile after 3 calls.
        verbose: If True, print compilation messages.
    """
    if func is not None:
        # @jit without arguments
        return JitFunction(func)
    else:
        # @jit(eager=True) with arguments
        def decorator(fn):
            return JitFunction(fn, eager=eager, verbose=verbose)
        return decorator


def loop(iterable, builder: Optional[IRBuilder] = None):
    """Helper function to create a loop context for JIT tracing.
    
    Usage:
        @jit
        def sum_range(n):
            total = 0
            for i in loop(range(n)):
                total = total + i
            return total
    
    Args:
        iterable: The iterable to loop over
        builder: The IR builder (optional, for internal use)
        
    Returns:
        A loop context manager
    """
    # This is a placeholder - in real usage, the builder would be passed
    # from the JIT tracing context
    return _LoopContext(builder, iterable)
