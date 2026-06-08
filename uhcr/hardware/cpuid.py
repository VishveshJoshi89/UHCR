import ctypes
import platform
import struct
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any

@dataclass
class CPUCapabilities:
    vendor: str = "Unknown"
    brand: str = "Unknown"
    cores: int = 1
    threads: int = 1
    features: List[str] = field(default_factory=list)
    cache_l1_data_kb: int = 0
    cache_l1_inst_kb: int = 0
    cache_l2_kb: int = 0
    cache_l3_kb: int = 0
    # New fields (v3)
    cache_l1_line_size: int = 0      # bytes
    cache_l1_associativity: int = 0  # ways
    cache_l2_line_size: int = 0      # bytes
    cache_l2_associativity: int = 0  # ways
    cache_l3_line_size: int = 0      # bytes
    cache_l3_associativity: int = 0  # ways
    
    # Feature helpers
    @property
    def has_sse(self) -> bool: return "sse" in self.features
    @property
    def has_sse2(self) -> bool: return "sse2" in self.features
    @property
    def has_sse3(self) -> bool: return "sse3" in self.features
    @property
    def has_sse4_1(self) -> bool: return "sse4_1" in self.features
    @property
    def has_sse4_2(self) -> bool: return "sse4_2" in self.features
    @property
    def has_avx(self) -> bool: return "avx" in self.features
    @property
    def has_avx2(self) -> bool: return "avx2" in self.features
    @property
    def has_avx512(self) -> bool: return any(f.startswith("avx512") for f in self.features)
    @property
    def has_fma(self) -> bool: return "fma" in self.features

# Executable memory allocator for JIT CPUID
PAGE_EXECUTE_READWRITE = 0x40
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000

PROT_READ = 0x1
PROT_WRITE = 0x2
PROT_EXEC = 0x4
MAP_PRIVATE = 0x02
MAP_ANONYMOUS = 0x20

def _allocate_executable_memory(size: int) -> Tuple[int, Any]:
    """Allocates executable memory and returns (address, handle/free_func)."""
    # Safety check before CPUID execution
    try:
        from uhcr.native import get_safety_monitor, SafetyStatus
        monitor = get_safety_monitor()
        if monitor and monitor.is_enabled():
            # Check CPU temperature before executing privileged code
            cpu_status = monitor.check_cpu_temperature()
            if cpu_status != SafetyStatus.OK:
                raise RuntimeError(
                    f"CPU temperature too high for CPUID execution: {monitor.get_last_error()}"
                )
            
            # Check for emergency stop
            if monitor.is_emergency_stopped():
                raise RuntimeError("Emergency stop active - cannot execute CPUID")
    except ImportError:
        pass
    
    os_name = platform.system()
    if os_name == "Windows":
        kernel32 = ctypes.windll.kernel32
        VirtualAlloc = kernel32.VirtualAlloc
        VirtualAlloc.restype = ctypes.c_void_p
        VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]
        
        addr = VirtualAlloc(None, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
        if not addr:
            raise OSError("VirtualAlloc failed")
            
        def free():
            VirtualFree = kernel32.VirtualFree
            VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong]
            VirtualFree(addr, 0, MEM_RELEASE)
            
        return addr, free
    else:
        # Unix (Linux, macOS)
        try:
            libc = ctypes.CDLL(None)
        except Exception:
            try:
                libc = ctypes.CDLL("libc.so.6")
            except Exception:
                libc = ctypes.CDLL("libc.dylib")
                
        mmap = libc.mmap
        mmap.restype = ctypes.c_void_p
        mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_longlong]
        
        # Flags might differ slightly but 0x22 (MAP_PRIVATE | MAP_ANONYMOUS) is standard on Linux/macOS
        # On macOS, MAP_JIT is 0x0800 if MAP_ANON/MAP_PRIVATE is used
        flags = MAP_PRIVATE | MAP_ANONYMOUS
        if os_name == "Darwin":
            flags |= 0x0800 # MAP_JIT
            
        addr = mmap(None, size, PROT_READ | PROT_WRITE | PROT_EXEC, flags, -1, 0)
        if addr == -1 or addr == 0 or addr is None:
            raise OSError("mmap failed")
            
        def free():
            munmap = libc.munmap
            munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            munmap(addr, size)
            
        return addr, free

def run_cpuid(leaf: int, subleaf: int = 0) -> Tuple[int, int, int, int]:
    """Runs CPUID instruction for a given leaf and subleaf, returning (EAX, EBX, ECX, EDX)."""
    arch = platform.machine().lower()
    if arch not in ("amd64", "x86_64", "x86", "i386"):
        # Fallback for non-x86 architectures (e.g. ARM)
        return (0, 0, 0, 0)

    # Machine code execution block
    os_name = platform.system()
    
    ''' write machine code that:
     1. Saves RBX (standard x86-64 ABI requirement)
     2. Sets EAX/ECX from arguments
     3. Runs CPUID
     4. Writes EAX, EBX, ECX, EDX to the output buffer pointer
     5. Restores RBX
     6. Returns '''
    
    if os_name == "Windows":
        # Windows x64 Calling Convention:
        # RCX = leaf (input)
        # RDX = output_ptr (pointer to 4 uint32s)
        # R8 = subleaf (input)
        #
        # Assembly:
        # 49 89 d2              mov r10, rdx      ; Save output_ptr to R10 (not touched by CPUID)
        # 53                    push rbx          ; Save RBX (must be preserved)
        # 89 c8                 mov eax, ecx      ; leaf
        # 44 89 c1              mov ecx, r8d      ; subleaf
        # 0f a2                 cpuid             ; Run CPUID (destroys eax, ebx, ecx, edx)
        # 41 89 02              mov [r10], eax    ; Write outputs using R10
        # 41 89 5a 04           mov [r10+4], ebx
        # 41 89 4a 08           mov [r10+8], ecx
        # 41 89 52 0c           mov [r10+12], edx
        # 5b                    pop rbx           ; Restore RBX
        # c3                    ret
        code_bytes = bytes([
            0x49, 0x89, 0xD2,
            0x53,
            0x89, 0xC8,
            0x44, 0x89, 0xC1,
            0x0F, 0xA2,
            0x41, 0x89, 0x02,
            0x41, 0x89, 0x5A, 0x04,
            0x41, 0x89, 0x4A, 0x08,
            0x41, 0x89, 0x52, 0x0C,
            0x5B,
            0xC3
        ])
    else:
        # System V AMD64 ABI (Linux, macOS):
        # RDI = leaf (input)
        # RSI = output_ptr (pointer to 4 uint32s)
        # RDX = subleaf (input)
        #
        # Assembly:
        # 49 89 f2              mov r10, rsi      ; Save output_ptr to R10
        # 53                    push rbx
        # 89 f8                 mov eax, edi
        # 89 d1                 mov ecx, edx
        # 0f a2                 cpuid
        # 41 89 02              mov [r10], eax
        # 41 89 5a 04           mov [r10+4], ebx
        # 41 89 4a 08           mov [r10+8], ecx
        # 41 89 52 0c           mov [r10+12], edx
        # 5b                    pop rbx
        # c3                    ret
        code_bytes = bytes([
            0x49, 0x89, 0xF2,
            0x53,
            0x89, 0xF8,
            0x89, 0xD1,
            0x0F, 0xA2,
            0x41, 0x89, 0x02,
            0x41, 0x89, 0x5A, 0x04,
            0x41, 0x89, 0x4A, 0x08,
            0x41, 0x89, 0x52, 0x0C,
            0x5B,
            0xC3
        ])
        
    addr, free_mem = _allocate_executable_memory(len(code_bytes))
    try:
        # Copy machine code bytes to allocated memory
        ctypes.memmove(addr, code_bytes, len(code_bytes))
        
        # Define output buffer type
        class CPUIDResult(ctypes.Structure):
            _fields_ = [
                ("eax", ctypes.c_uint32),
                ("ebx", ctypes.c_uint32),
                ("ecx", ctypes.c_uint32),
                ("edx", ctypes.c_uint32),
            ]
            
        result = CPUIDResult()
        
        # Create function prototype
        if os_name == "Windows":
            func_type = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.POINTER(CPUIDResult), ctypes.c_uint32)
        else:
            func_type = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.POINTER(CPUIDResult), ctypes.c_uint32)
            
        func = func_type(addr)
        func(leaf, ctypes.byref(result), subleaf)
        return (result.eax, result.ebx, result.ecx, result.edx)
    finally:
        free_mem()

def detect_cpu() -> CPUCapabilities:
    """Executes CPUID and gathers complete CPU feature set and topology information."""
    caps = CPUCapabilities()
    
    arch = platform.machine().lower()
    if arch not in ("amd64", "x86_64", "x86", "i386"):
        # ARM/Fallback
        caps.vendor = "Apple/ARM" if "darwin" in platform.system().lower() else "ARM/Generic"
        caps.brand = platform.processor() or "Generic ARM CPU"
        # Guess basic features on ARM
        caps.features = ["neon"]
        return caps

    try:
        # 1. Vendor String (Leaf 0)
        eax, ebx, ecx, edx = run_cpuid(0)
        if eax == 0:
            return caps
            
        # Unpack vendor string from EBX, EDX, ECX
        vendor = struct.pack("<III", ebx, edx, ecx).decode("ascii", errors="ignore").strip()
        caps.vendor = vendor
        max_leaf = eax
        
        # 2. Feature Flags (Leaf 1)
        if max_leaf >= 1:
            eax_1, ebx_1, ecx_1, edx_1 = run_cpuid(1)
            
            # EDX Flags
            if edx_1 & (1 << 25): caps.features.append("sse")
            if edx_1 & (1 << 26): caps.features.append("sse2")
            
            # ECX Flags
            if ecx_1 & (1 << 0): caps.features.append("sse3")
            if ecx_1 & (1 << 9): caps.features.append("ssse3")
            if ecx_1 & (1 << 19): caps.features.append("sse4_1")
            if ecx_1 & (1 << 20): caps.features.append("sse4_2")
            if ecx_1 & (1 << 12): caps.features.append("fma")
            if ecx_1 & (1 << 25): caps.features.append("aes")
            if ecx_1 & (1 << 23): caps.features.append("popcnt")
            
            # AVX requires OS support as well as CPU support
            if ecx_1 & (1 << 28):
                # Verify XSAVE/XRESTORE is supported by CPU (ECX bit 27) and enabled by OS (XCR0)
                if ecx_1 & (1 << 27):
                    # We can assume OS enables it since Windows 7 SP1/Linux 2.6.30+ support it
                    caps.features.append("avx")
                    
        # 3. Extended Feature Flags (Leaf 7, Subleaf 0)
        if max_leaf >= 7:
            eax_7, ebx_7, ecx_7, edx_7 = run_cpuid(7, 0)
            
            if ebx_7 & (1 << 3): caps.features.append("bmi1")
            if ebx_7 & (1 << 5): caps.features.append("avx2")
            if ebx_7 & (1 << 8): caps.features.append("bmi2")
            
            # AVX-512 flags
            if ebx_7 & (1 << 16): caps.features.append("avx512f")
            if ebx_7 & (1 << 17): caps.features.append("avx512dq")
            if ebx_7 & (1 << 28): caps.features.append("avx512cd")
            if ebx_7 & (1 << 30): caps.features.append("avx512bw")
            if ebx_7 & (1 << 31): caps.features.append("avx512vl")
            
        # 4. Brand String (Leaves 0x80000002 to 0x80000004)
        ext_eax, _, _, _ = run_cpuid(0x80000000)
        if ext_eax >= 0x80000004:
            brand_parts = []
            for leaf in range(0x80000002, 0x80000005):
                r_eax, r_ebx, r_ecx, r_edx = run_cpuid(leaf)
                brand_parts.append(struct.pack("<IIII", r_eax, r_ebx, r_ecx, r_edx))
            brand = b"".join(brand_parts).decode("ascii", errors="ignore").strip().rstrip('\x00')
            caps.brand = " ".join(brand.split()) # Clean double spaces
            
        # 5. Cache Info (Leaf 4, Subleaf 0, 1, 2, 3...)
        # We can extract cache topologies
        if max_leaf >= 4:
            for subleaf in range(4):
                c_eax, c_ebx, c_ecx, _ = run_cpuid(4, subleaf)
                cache_type = c_eax & 0x1F
                if cache_type == 0:
                    break
                cache_level = (c_eax >> 5) & 0x7
                ways = ((c_ebx >> 22) & 0x3FF) + 1
                partitions = ((c_ebx >> 12) & 0x3FF) + 1
                line_size = (c_ebx & 0xFFF) + 1
                sets = c_ecx + 1
                size_kb = (ways * partitions * line_size * sets) // 1024
                
                if cache_level == 1:
                    if cache_type == 1: caps.cache_l1_data_kb = size_kb
                    elif cache_type == 2: caps.cache_l1_inst_kb = size_kb
                elif cache_level == 2:
                    caps.cache_l2_kb = size_kb
                elif cache_level == 3:
                    caps.cache_l3_kb = size_kb
                    
        # Cores and threads info
        # Intel CPU topology query
        if caps.vendor == "GenuineIntel" and max_leaf >= 0xB:
            # Leaf 11 (0xB) provides extended topology info
            # Subleaf 0 = SMT level, Subleaf 1 = Core level
            # We get logical processors at Core level
            _, ebx_b, _, _ = run_cpuid(0xB, 1)
            caps.threads = ebx_b & 0xFFFF
            # Get core count from CPUID Leaf 4 (cores = EAX[31:26] + 1)
            c_eax, _, _, _ = run_cpuid(4, 0)
            caps.cores = ((c_eax >> 26) & 0x3F) + 1
        elif caps.vendor == "AuthenticAMD" and ext_eax >= 0x80000008:
            _, _, ecx_8, _ = run_cpuid(0x80000008)
            caps.threads = (ecx_8 & 0xFF) + 1
            caps.cores = caps.threads # Simple fallback
        else:
            # Fallback using python multiprocessing
            import os
            try:
                caps.threads = os.cpu_count() or 1
                caps.cores = caps.threads // 2 or 1
            except Exception:
                pass

    except Exception as e:
        # Fallback if execution fails
        caps.brand = f"Failed to execute CPUID JIT: {str(e)}"
        
    return caps

if __name__ == "__main__":
    c = detect_cpu()
    print("CPU Vendor:", c.vendor)
    print("CPU Brand:", c.brand)
    print("Cores / Threads:", c.cores, "/", c.threads)
    print("Features:", ", ".join(c.features))
    print(f"L1 Data Cache: {c.cache_l1_data_kb} KB, L2: {c.cache_l2_kb} KB, L3: {c.cache_l3_kb} KB")
