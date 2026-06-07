import ctypes
import sys
import platform

class AlignedBuffer:
    """Manages aligned native memory buffers required for safe SIMD hardware vector access."""
    def __init__(self, size_bytes: int, alignment: int = 64):
        self.size = size_bytes
        self.alignment = alignment
        self.address = None
        self.system = platform.system()
        self._allocate()

    def _allocate(self):
        if self.system == "Windows":
            # Load msvcrt for _aligned_malloc
            try:
                self.libc = ctypes.cdll.msvcrt
            except Exception:
                self.libc = ctypes.CDLL("msvcrt.dll")
            
            # void* _aligned_malloc(size_t size, size_t alignment)
            self.libc._aligned_malloc.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
            self.libc._aligned_malloc.restype = ctypes.c_void_p
            
            self.address = self.libc._aligned_malloc(self.size, self.alignment)
            if not self.address:
                raise MemoryError("Windows _aligned_malloc failed")
        else:
            # POSIX posix_memalign
            try:
                self.libc = ctypes.CDLL(None)
            except Exception:
                try:
                    self.libc = ctypes.CDLL("libc.so.6")
                except Exception:
                    raise MemoryError("Could not load POSIX libc for aligned memory allocation")
                    
            # int posix_memalign(void **memptr, size_t alignment, size_t size)
            posix_memalign = self.libc.posix_memalign
            posix_memalign.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t, ctypes.c_size_t]
            posix_memalign.restype = ctypes.c_int
            
            ptr = ctypes.c_void_p(0)
            res = posix_memalign(ctypes.byref(ptr), self.alignment, self.size)
            if res != 0:
                raise MemoryError(f"POSIX posix_memalign failed with error code: {res}")
            self.address = ptr.value

    def free(self):
        """Frees the aligned buffer."""
        if not self.address:
            return
            
        if self.system == "Windows":
            # void _aligned_free(void *memblock)
            self.libc._aligned_free.argtypes = [ctypes.c_void_p]
            self.libc._aligned_free(self.address)
        else:
            # free(void *ptr)
            free = self.libc.free
            free.argtypes = [ctypes.c_void_p]
            free(self.address)
            
        self.address = None

    def as_ctypes_array(self, ctypes_type):
        """Returns a ctypes array view over the aligned buffer."""
        assert self.address is not None, "Memory already freed"
        count = self.size // ctypes.sizeof(ctypes_type)
        return (ctypes_type * count).from_address(self.address)

    def copy_from(self, src_bytes: bytes):
        """Copies raw bytes into the aligned buffer."""
        assert len(src_bytes) <= self.size, "Source bytes exceed buffer size"
        ctypes.memmove(self.address, src_bytes, len(src_bytes))

    def copy_to(self) -> bytes:
        """Copies the contents of the aligned buffer into a Python bytes object."""
        assert self.address is not None, "Memory already freed"
        return ctypes.string_at(self.address, self.size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.free()

    def __del__(self):
        try:
            self.free()
        except Exception:
            pass  # Suppress errors during interpreter shutdown
