import ctypes
from typing import List, Tuple, Union
from uhcr.runtime.memory_manager import AlignedBuffer
from uhcr import get_runtime
from uhcr.compiler.ir import Type

class Tensor:
    """N-dimensional hardware-aligned array for high-performance mathematical operations."""
    def __init__(self, data: Union[List, float, AlignedBuffer], shape: Tuple[int, ...] = None, dtype=Type.F32):
        self.dtype = dtype
        
        if isinstance(data, AlignedBuffer):
            assert shape is not None, "Shape must be provided when wrapping an AlignedBuffer"
            self.buffer = data
            self.shape = shape
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
        """Performs hardware-accelerated matrix multiplication."""
        assert len(self.shape) == 2 and len(other.shape) == 2, "Matmul requires 2D matrices"
        M, K = self.shape
        K2, N = other.shape
        assert K == K2, f"Matrix size mismatch: {K} != {K2}"
        
        # Create output tensor
        out = Tensor([0.0] * (M * N), shape=(M, N), dtype=self.dtype)
        
        # Dispatch to ops pipeline
        from uhcr.api.ops import dispatch_matmul
        dispatch_matmul(self, other, out)
        return out

    def __add__(self, other: Union['Tensor', float]) -> 'Tensor':
        """Performs element-wise tensor addition."""
        out = Tensor([0.0] * self.size, shape=self.shape, dtype=self.dtype)
        from uhcr.api.ops import dispatch_vadd
        if isinstance(other, Tensor):
            assert self.shape == other.shape, "Shape mismatch for addition"
            dispatch_vadd(self, other, out)
        else:
            # Scalar add
            pass
        return out
