import ctypes
import os
import platform
import subprocess
import json
from dataclasses import dataclass

@dataclass
class GPUCapabilities:
    name: str = "Unknown"
    vendor: str = "Unknown"
    vram_bytes: int = 0
    driver_version: str = "Unknown"
    cuda_available: bool = False
    cuda_version: str = "Unknown"
    vulkan_available: bool = False
    rocm_available: bool = False
    metal_available: bool = False

def detect_gpu() -> GPUCapabilities:
    """Detects primary GPU vendor, details, and compiler driver interfaces (CUDA, Vulkan, etc.)."""
    gpu = GPUCapabilities()
    os_name = platform.system()
    
    # 1. Vendor & Model Detection
    if os_name == "Windows":
        try:
            # Query WMI via PowerShell to get complete video controller data
            cmd = ["powershell", "-NoProfile", "-Command", 
                   "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout.strip())
                # Handle single or multiple GPUs returned
                gpus = data if isinstance(data, list) else [data]
                
                # Pick the primary/discrete GPU if multiple, prioritize NVIDIA/AMD over Intel Integrated
                selected_gpu = gpus[0]
                for g in gpus:
                    name_lower = g.get("Name", "").lower()
                    if "nvidia" in name_lower or "geforce" in name_lower or "rtx" in name_lower or "amd" in name_lower or "radeon" in name_lower:
                        selected_gpu = g
                        break
                        
                gpu.name = selected_gpu.get("Name", "Unknown")
                gpu.vram_bytes = selected_gpu.get("AdapterRAM", 0)
                # AdapterRAM is signed 32-bit int in some WMI returns, so it might be negative or overflowed. Correct it:
                if gpu.vram_bytes < 0:
                    gpu.vram_bytes += 2**32
                gpu.driver_version = selected_gpu.get("DriverVersion", "Unknown")
        except Exception:
            # Fallback to wmic
            try:
                out = subprocess.check_output("wmic path win32_VideoController get Name,AdapterRAM,DriverVersion /format:list", shell=True, text=True)
                for line in out.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k == "Name": gpu.name = v
                        elif k == "AdapterRAM" and v.isdigit(): gpu.vram_bytes = int(v)
                        elif k == "DriverVersion": gpu.driver_version = v
            except Exception:
                pass
    elif os_name == "Linux":
        # Fallback to lspci and nvidia-smi
        try:
            lspci = subprocess.check_output("lspci", shell=True, text=True)
            for line in lspci.splitlines():
                if "VGA compatible controller" in line or "3D controller" in line:
                    gpu.name = line.split(": ", 1)[-1].strip()
                    break
        except Exception:
            pass
        
        # Check NVIDIA specifically
        if os.path.exists("/proc/driver/nvidia/gpus"):
            gpu.vendor = "NVIDIA"
            
    elif os_name == "Darwin":
        gpu.vendor = "Apple"
        gpu.metal_available = True
        try:
            out = subprocess.check_output(["system_profiler", "SPDisplaysDataType", "-json"], text=True)
            data = json.loads(out)
            sp_gpus = data.get("SPDisplaysDataType", [])
            if sp_gpus:
                selected_gpu = sp_gpus[0]
                gpu.name = selected_gpu.get("sppci_model", "Unknown")
                # Parse VRAM (e.g. "8 GB")
                vram_str = selected_gpu.get("spdisplays_ndrvs", [{}])[0].get("spdisplays_vram", "0")
                if "gb" in vram_str.lower():
                    gpu.vram_bytes = int(vram_str.lower().split("gb")[0].strip()) * 1024 * 1024 * 1024
        except Exception:
            pass

    # Normalize vendor
    name_lower = gpu.name.lower()
    if "nvidia" in name_lower or "geforce" in name_lower or "rtx" in name_lower or "quadro" in name_lower:
        gpu.vendor = "NVIDIA"
    elif "amd" in name_lower or "radeon" in name_lower or "navi" in name_lower:
        gpu.vendor = "AMD"
    elif "intel" in name_lower or "arc " in name_lower or "hd graphics" in name_lower or "iris" in name_lower:
        gpu.vendor = "Intel"
    elif "apple" in name_lower:
        gpu.vendor = "Apple"
        gpu.metal_available = True

    # 2. CUDA SDK Detection (NVIDIA Specific)
    cuda_lib_names = ["nvcuda.dll", "libcuda.so", "libcuda.dylib"]
    for lib_name in cuda_lib_names:
        try:
            cuda_lib = ctypes.CDLL(lib_name)
            gpu.cuda_available = True
            
            # Get driver version via cuDriverGetVersion
            cuDriverGetVersion = cuda_lib.cuDriverGetVersion
            cuDriverGetVersion.argtypes = [ctypes.POINTER(ctypes.c_int)]
            cuDriverGetVersion.restype = ctypes.c_int
            
            version = ctypes.c_int()
            res = cuDriverGetVersion(ctypes.byref(version))
            if res == 0:
                major = version.value // 1000
                minor = (version.value % 1000) // 10
                gpu.cuda_version = f"{major}.{minor}"
            break
        except Exception:
            pass

    # 3. Vulkan SDK Detection
    vulkan_lib_names = ["vulkan-1.dll", "libvulkan.so.1", "libvulkan.so", "libvulkan.1.dylib", "libMoltenVK.dylib"]
    for lib_name in vulkan_lib_names:
        try:
            ctypes.CDLL(lib_name)
            gpu.vulkan_available = True
            break
        except Exception:
            pass

    # 4. ROCm Detection (AMD Specific)
    rocm_lib_names = ["hiprtc64.dll", "libamdhip64.so", "libhip_hcc.so"]
    for lib_name in rocm_lib_names:
        try:
            ctypes.CDLL(lib_name)
            gpu.rocm_available = True
            break
        except Exception:
            pass

    return gpu

if __name__ == "__main__":
    g = detect_gpu()
    print("GPU Name:", g.name)
    print("GPU Vendor:", g.vendor)
    print("VRAM (MB):", g.vram_bytes / (1024 * 1024))
    print("Driver Version:", g.driver_version)
    print("CUDA Available:", g.cuda_available, "(v" + g.cuda_version + ")" if g.cuda_available else "")
    print("Vulkan Available:", g.vulkan_available)
    print("ROCm Available:", g.rocm_available)
    print("Metal Available:", g.metal_available)
