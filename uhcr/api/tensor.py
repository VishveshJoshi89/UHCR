import ctypes
from typing import List, Tuple, Union, Dict, Callable
from uhcr.runtime.memory_manager import AlignedBuffer
from uhcr import get_runtime
from uhcr.compiler.ir import Type

class Tensor:
    """N-dimensional hardware-aligned array for high-performance mathematical operations."""
    
    # Class-level operation cache for compiled functions
    _op_cache: Dict[tuple, Callable] = {}
    _memory_pool: Dict[int, List[AlignedBuffer]] = {}
    _pool_max_size = 50
    
    def __init__(self, data: Union[List, float, AlignedBuffer], shape: Tuple[int, ...] = None, dtype=Type.F32):
        self.dtype = dtype
        
        if isinstance(data, AlignedBuffer):
            assert shape is not None, "Shape must be provided when wrapping an AlignedBuffer"
            self.buffer = data
            self.shape  = shape
            self.size   = 1
            for dim in self.shape:
                self.size *= dim
        else:
            # Recursively analyze nested list to find shape and elements
            if shape is None:
                shape, flat_data = self._parse_data(data)
            else:
                flat_data = data
                
            self.shape = shape
            self.size = 1
            for dim in self.shape:
                self.size *= dim
                
            element_size = 4 if self.dtype == Type.F32 else 8
            self.buffer = AlignedBuffer(self.size * element_size, alignment=64)
            
            # Load data
            ctypes_type = ctypes.c_float if self.dtype == Type.F32 else ctypes.c_double
            arr = self.buffer.as_ctypes_array(ctypes_type)
            for i, val in enumerate(flat_data):
                arr[i] = float(val)

    def _parse_data(self, data) -> Tuple[Tuple[int, ...], List[float]]:
        if not isinstance(data, list):
            return (), [float(data)]
            
        # Inspect shape
        shape = []
        curr = data
        while isinstance(curr, list):
            shape.append(len(curr))
            if len(curr) == 0:
                break
            curr = curr[0]
            
        # Flatten list
        flat = []
        def flatten(lst):
            for item in lst:
                if isinstance(item, list):
                    flatten(item)
                else:
                    flat.append(float(item))
        flatten(data)
        return tuple(shape), flat

    @property
    def address(self) -> int:
        """Returns the native memory address of the aligned buffer."""
        return self.buffer.address
    
    @classmethod
    def _get_pooled_buffer(cls, size: int) -> AlignedBuffer:
        """Get buffer from pool or allocate new."""
        if size in cls._memory_pool and cls._memory_pool[size]:
            return cls._memory_pool[size].pop()
        return AlignedBuffer(size, alignment=64)
    
    @classmethod
    def _return_to_pool(cls, buffer: AlignedBuffer):
        """Return buffer to pool for reuse."""
        size = len(buffer.data) if hasattr(buffer, 'data') else buffer.size
        if size not in cls._memory_pool:
            cls._memory_pool[size] = []
        if len(cls._memory_pool[size]) < cls._pool_max_size:
            cls._memory_pool[size].append(buffer)
    
    def _operation_signature(self, op: str, other=None) -> tuple:
        """Create cache key for operation."""
        if other is None:
            return (op, self.shape, self.dtype)
        if isinstance(other, Tensor):
            return (op, self.shape, self.dtype, other.shape, other.dtype)
        return (op, self.shape, self.dtype, type(other).__name__)
    
    @classmethod
    def _get_cached_op(cls, sig: tuple) -> Callable:
        """Get cached compiled operation."""
        return cls._op_cache.get(sig)
    
    @classmethod
    def _cache_op(cls, sig: tuple, compiled_fn: Callable):
        """Cache compiled operation."""
        cls._op_cache[sig] = compiled_fn

    def to_numpy(self):
        """Converts the tensor to a NumPy array (if numpy is installed)."""
        import numpy as np
        ctypes_type = ctypes.c_float if self.dtype == Type.F32 else ctypes.c_double
        np_type = np.float32 if self.dtype == Type.F32 else np.float64
        arr = self.buffer.as_ctypes_array(ctypes_type)
        return np.ctypeslib.as_array(arr).reshape(self.shape).copy()

    def __repr__(self):
        # Quick formatted preview of array data
        ctypes_type = ctypes.c_float if self.dtype == Type.F32 else ctypes.c_double
        arr = self.buffer.as_ctypes_array(ctypes_type)
        preview_len = min(self.size, 16)
        preview = [str(arr[i]) for i in range(preview_len)]
        if self.size > 16:
            preview.append("...")
        return f"Tensor(shape={self.shape}, dtype={self.dtype.value}, data=[{', '.join(preview)}])"

    # Tensor math dispatches
    def matmul(self, other: 'Tensor') -> 'Tensor':
        """Performs hardware-accelerated matrix multiplication with BLAS optimization."""
        assert len(self.shape) == 2 and len(other.shape) == 2, "Matmul requires 2D matrices"
        M, K = self.shape
        K2, N = other.shape
        assert K == K2, f"Matrix size mismatch: {K} != {K2}"
        
        # Use optimized BLAS for larger matrices
        if M >= 32 and N >= 32:
            try:
                return self._matmul_blas(other, M, K, N)
            except:
                pass  # Fall back to UHCR implementation
        
        # Create output tensor
        out = Tensor([0.0] * (M * N), shape=(M, N), dtype=self.dtype)
        
        # Dispatch to ops pipeline
        from uhcr.api.ops import dispatch_matmul
        dispatch_matmul(self, other, out)
        return out
    
    def _matmul_blas(self, other: 'Tensor', M: int, K: int, N: int) -> 'Tensor':
        """Use system BLAS for matrix multiplication."""
        try:
            import numpy as np
            # Convert to numpy, use its matmul (which uses BLAS), convert back
            a_np = self.to_numpy()
            b_np = other.to_numpy()
            result_np = np.matmul(a_np, b_np)
            
            # Convert back to Tensor
            result = Tensor(result_np.flatten().tolist(), shape=(M, N), dtype=self.dtype)
            return result
        except ImportError:
            raise  # No numpy available, caller will fall back

    def __add__(self, other: Union['Tensor', float]) -> 'Tensor':
        """Performs element-wise tensor addition with optimized vectorization."""
        if isinstance(other, Tensor):
            assert self.shape == other.shape, "Shape mismatch for addition"
            
            # Try vectorized operation first for better performance
            try:
                from uhcr.api.vectorized_ops import get_vectorized_op
                vec_op = get_vectorized_op('add', self.size)
                
                # Use pooled buffer for output
                element_size = 4 if self.dtype == Type.F32 else 8
                out_buffer = self._get_pooled_buffer(self.size * element_size)
                
                # Execute vectorized operation
                vec_op(self.address, other.address, out_buffer.address, self.size)
                
                out = Tensor(out_buffer, shape=self.shape, dtype=self.dtype)
                return out
            except:
                # Fall back to cached compilation
                pass
            
            # Check cache
            sig = self._operation_signature('add', other)
            cached_fn = self._get_cached_op(sig)
            
            if cached_fn is None:
                # Compile and cache
                from uhcr.api.ops import compile_vadd
                cached_fn = compile_vadd(self.size)
                self._cache_op(sig, cached_fn)
            
            # Use pooled buffer for output
            element_size = 4 if self.dtype == Type.F32 else 8
            out_buffer = self._get_pooled_buffer(self.size * element_size)
            
            # Execute cached operation
            cached_fn(self.address, other.address, out_buffer.address, self.size)
            
            out = Tensor(out_buffer, shape=self.shape, dtype=self.dtype)
            return out
        else:
            # Scalar add - TODO
            out = Tensor([0.0] * self.size, shape=self.shape, dtype=self.dtype)
            return out
