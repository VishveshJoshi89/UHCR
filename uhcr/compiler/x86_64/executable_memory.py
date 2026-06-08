import ctypes
import sys
import platform

class ExecutableMemory:
    """Manages raw executable memory allocation and cleanup across platforms."""
    def __init__(self, size: int):
        self.size = size
        self.address = None
        self.system = platform.system()
        self._safety_validated = False
        self._allocate()

    def _allocate(self):
        # Safety check before allocation
        try:
            from uhcr.native import get_safety_monitor, SafetyStatus
            monitor = get_safety_monitor()
            if monitor and monitor.is_enabled():
                # Check if emergency stop is active
                if monitor.is_emergency_stopped():
                    raise RuntimeError("Emergency stop active - cannot allocate executable memory")
                
                # Validate memory allocation request
                status = monitor.validate_memory(0, self.size, False)
                if status != SafetyStatus.OK:
                    raise RuntimeError(f"Memory safety check failed: {monitor.get_last_error()}")
                
                self._safety_validated = True
        except ImportError:
            # Safety monitor not available - continue without protection
            pass
        
        if self.system == "Windows":
            # Win32 VirtualAlloc
            MEM_COMMIT = 0x1000
            MEM_RESERVE = 0x2000
            PAGE_EXECUTE_READWRITE = 0x40
            
            kernel32 = ctypes.windll.kernel32
            VirtualAlloc = kernel32.VirtualAlloc
            VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]
            VirtualAlloc.restype = ctypes.c_void_p
            
            self.address = VirtualAlloc(None, self.size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            if not self.address:
                raise RuntimeError("Windows VirtualAlloc failed to allocate executable memory")
        else:
            # POSIX mmap
            # mmap(void *addr, size_t len, int prot, int flags, int fd, off_t offset)
            PROT_READ = 0x1
            PROT_WRITE = 0x2
            PROT_EXEC = 0x4
            MAP_PRIVATE = 0x02
            MAP_ANONYMOUS = 0x20 if self.system == "Linux" else 0x1000 # macOS anonymous flag is 0x1000
            
            try:
                libc = ctypes.CDLL(None)
            except Exception:
                try:
                    libc = ctypes.CDLL("libc.so.6")
                except Exception:
                    raise RuntimeError("Could not load POSIX libc for mmap")
            
            mmap = libc.mmap
            mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_size_t]
            mmap.restype = ctypes.c_void_p
            
            self.address = mmap(None, self.size, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)
            # mmap returns -1 (MAP_FAILED) on error, which translates to a high void pointer (e.g. 0xfffffffffffffff)
            if not self.address or self.address == ctypes.c_void_p(-1).value or self.address == 0xffffffffffffffff:
                raise RuntimeError("POSIX mmap failed to allocate executable memory")

    def write(self, data: bytes):
        """Writes machine code bytes into the allocated executable memory buffer."""
        assert len(data) <= self.size, f"Data size {len(data)} exceeds allocated size {self.size}"
        
        # Safety check before writing
        if self._safety_validated:
            try:
                from uhcr.native import get_safety_monitor, SafetyStatus
                monitor = get_safety_monitor()
                if monitor and monitor.is_enabled():
                    # Validate write operation
                    status = monitor.validate_memory(self.address, len(data), True)
                    if status != SafetyStatus.OK:
                        raise RuntimeError(f"Memory write safety check failed: {monitor.get_last_error()}")
            except ImportError:
                pass
        
        ctypes.memmove(self.address, data, len(data))

    def get_function(self, ctypes_proto):
        """Converts the executable memory pointer into a callable ctypes function wrapper."""
        assert self.address is not None, "Memory already freed"
        return ctypes_proto(self.address)

    def free(self):
        """Frees the executable memory back to the operating system."""
        if not self.address:
            return
        
        try:
            if self.system == "Windows":
                MEM_RELEASE = 0x8000
                kernel32 = ctypes.windll.kernel32
                VirtualFree = kernel32.VirtualFree
                VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong]
                VirtualFree.restype = ctypes.c_bool
                VirtualFree(self.address, 0, MEM_RELEASE)
            else:
                try:
                    libc = ctypes.CDLL(None)
                except Exception:
                    libc = ctypes.CDLL("libc.so.6")
                munmap = libc.munmap
                munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                munmap.restype = ctypes.c_int
                munmap(self.address, self.size)
        except (OSError, TypeError, ValueError):
            pass  # Interpreter shutting down, ctypes unavailable
            
        self.address = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.free()

    def __del__(self):
        # During interpreter shutdown, ctypes may be None
        if ctypes is None:
            return
        try:
            self.free()
        except Exception:
            pass
