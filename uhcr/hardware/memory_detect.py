import ctypes
import os
import platform
import subprocess
from dataclasses import dataclass

@dataclass
class MemoryCapabilities:
    total_bytes: int = 0
    available_bytes: int = 0
    numa_nodes: int = 1
    page_size: int = 4096
    speed_mhz: int = 0
    memory_type: str = "Unknown"

# SMBIOSMemoryType mapping (SMBIOS specification)
SMBIOS_MEMORY_TYPE_MAP = {
    20: "DDR",
    21: "DDR2",
    22: "DDR2 FB-DIMM",
    24: "DDR3",
    26: "DDR4",
    34: "DDR5",
}


def _detect_memory_speed_type_windows() -> tuple[int, str]:
    """Detect RAM speed and type on Windows using wmic.

    Returns:
        Tuple of (speed_mhz, memory_type). Defaults to (0, "Unknown") on failure.
    """
    try:
        output = subprocess.check_output(
            ["wmic", "memorychip", "get", "Speed,SMBIOSMemoryType"],
            text=True,
            timeout=10,
        )
        lines = [line for line in output.strip().splitlines() if line.strip()]
        # First line is the header, subsequent lines are data rows
        if len(lines) < 2:
            return 0, "Unknown"

        # Parse header to find column positions
        header = lines[0]
        speed_idx = header.lower().find("speed")
        smbios_idx = header.lower().find("smbiosmemorytype")

        if speed_idx == -1 or smbios_idx == -1:
            return 0, "Unknown"

        # Determine which column comes first to parse positionally
        # wmic uses fixed-width columns based on header positions
        data_line = lines[1]

        if smbios_idx < speed_idx:
            # SMBIOSMemoryType comes first, Speed comes second
            parts = data_line.split()
            if len(parts) < 2:
                return 0, "Unknown"
            smbios_type = int(parts[0])
            speed_mhz = int(parts[1])
        else:
            # Speed comes first, SMBIOSMemoryType comes second
            parts = data_line.split()
            if len(parts) < 2:
                return 0, "Unknown"
            speed_mhz = int(parts[0])
            smbios_type = int(parts[1])

        memory_type = SMBIOS_MEMORY_TYPE_MAP.get(smbios_type, "Unknown")
        return speed_mhz, memory_type
    except Exception:
        return 0, "Unknown"


def _detect_memory_speed_type_linux() -> tuple[int, str]:
    """Detect RAM speed and type on Linux using dmidecode.

    Returns:
        Tuple of (speed_mhz, memory_type). Defaults to (0, "Unknown") on failure.
    """
    try:
        output = subprocess.check_output(
            ["dmidecode", "--type", "memory"],
            text=True,
            timeout=10,
        )
        speed_mhz = 0
        memory_type = "Unknown"

        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("Speed:") and "MHz" in stripped:
                # e.g. "Speed: 3200 MHz"
                try:
                    speed_str = stripped.split(":")[1].strip().split()[0]
                    speed_mhz = int(speed_str)
                except (ValueError, IndexError):
                    pass
            elif stripped.startswith("Type:") and memory_type == "Unknown":
                # e.g. "Type: DDR4"
                type_str = stripped.split(":")[1].strip()
                if type_str and type_str != "Unknown":
                    memory_type = type_str

        return speed_mhz, memory_type
    except Exception:
        return 0, "Unknown"


def _detect_memory_speed_type_macos() -> tuple[int, str]:
    """Detect RAM speed and type on macOS using system_profiler.

    Returns:
        Tuple of (speed_mhz, memory_type). Defaults to (0, "Unknown") on failure.
    """
    try:
        output = subprocess.check_output(
            ["system_profiler", "SPMemoryDataType"],
            text=True,
            timeout=10,
        )
        speed_mhz = 0
        memory_type = "Unknown"

        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("Speed:") and speed_mhz == 0:
                # e.g. "Speed: 3200 MHz" or "Speed: 2667 MHz"
                try:
                    speed_str = stripped.split(":")[1].strip().split()[0]
                    speed_mhz = int(speed_str)
                except (ValueError, IndexError):
                    pass
            elif stripped.startswith("Type:") and memory_type == "Unknown":
                # e.g. "Type: DDR4" or "Type: LPDDR5"
                type_str = stripped.split(":")[1].strip()
                if type_str and type_str != "Unknown":
                    memory_type = type_str

        return speed_mhz, memory_type
    except Exception:
        return 0, "Unknown"


# Win32 Memory Structures
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

def detect_memory() -> MemoryCapabilities:
    """Detects system memory characteristics and topology across platforms."""
    mem = MemoryCapabilities()
    os_name = platform.system()
    
    # 1. Total & Available Memory
    if os_name == "Windows":
        try:
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            kernel32 = ctypes.windll.kernel32
            if kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                mem.total_bytes = stat.ullTotalPhys
                mem.available_bytes = stat.ullAvailPhys
        except Exception:
            pass
            
        # Page size
        try:
            class SYSTEM_INFO(ctypes.Structure):
                _fields_ = [
                    ("wProcessorArchitecture", ctypes.c_ushort),
                    ("wReserved", ctypes.c_ushort),
                    ("dwPageSize", ctypes.c_ulong),
                    ("lpMinimumApplicationAddress", ctypes.c_void_p),
                    ("lpMaximumApplicationAddress", ctypes.c_void_p),
                    ("dwActiveProcessorMask", ctypes.c_void_p),
                    ("dwNumberOfProcessors", ctypes.c_ulong),
                    ("dwProcessorType", ctypes.c_ulong),
                    ("dwAllocationGranularity", ctypes.c_ulong),
                    ("wProcessorLevel", ctypes.c_ushort),
                    ("wProcessorRevision", ctypes.c_ushort),
                ]
            sys_info = SYSTEM_INFO()
            kernel32.GetSystemInfo(ctypes.byref(sys_info))
            mem.page_size = sys_info.dwPageSize
        except Exception:
            pass
            
        # NUMA Nodes
        try:
            highest_node = ctypes.c_ulong()
            if kernel32.GetNumaHighestNodeNumber(ctypes.byref(highest_node)):
                mem.numa_nodes = highest_node.value + 1
        except Exception:
            pass
            
    elif os_name == "Linux":
        # /proc/meminfo
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem.total_bytes = int(line.split()[1]) * 1024
                    elif line.startswith("MemAvailable:"):
                        mem.available_bytes = int(line.split()[1]) * 1024
        except Exception:
            pass
            
        # Page size
        try:
            mem.page_size = os.sysconf("SC_PAGESIZE")
        except Exception:
            pass
            
        # NUMA Nodes
        try:
            import glob
            numa_dirs = glob.glob("/sys/devices/system/node/node[0-9]*")
            if numa_dirs:
                mem.numa_nodes = len(numa_dirs)
        except Exception:
            pass
            
    elif os_name == "Darwin":
        # macOS sysctl
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            mem.total_bytes = int(out.strip())
            
            # available memory (approximate)
            vm = subprocess.check_output(["vm_stat"], text=True)
            page_size = 4096
            free_pages = 0
            for line in vm.splitlines():
                if "page size of" in line:
                    page_size = int(line.split()[-2])
                elif "Pages free:" in line:
                    free_pages = int(line.split()[-1].replace(".", ""))
            mem.available_bytes = free_pages * page_size
            mem.page_size = page_size
        except Exception:
            pass

    # 2. RAM Speed and Type Detection
    try:
        if os_name == "Windows":
            mem.speed_mhz, mem.memory_type = _detect_memory_speed_type_windows()
        elif os_name == "Linux":
            mem.speed_mhz, mem.memory_type = _detect_memory_speed_type_linux()
        elif os_name == "Darwin":
            mem.speed_mhz, mem.memory_type = _detect_memory_speed_type_macos()
    except Exception:
        # Fallback: keep defaults (speed_mhz=0, memory_type="Unknown")
        pass

    return mem

if __name__ == "__main__":
    m = detect_memory()
    print("Total Memory (GB):", m.total_bytes / (1024**3))
    print("Available Memory (GB):", m.available_bytes / (1024**3))
    print("NUMA Nodes:", m.numa_nodes)
    print("Page Size (bytes):", m.page_size)
    print("RAM Speed (MHz):", m.speed_mhz)
    print("Memory Type:", m.memory_type)
