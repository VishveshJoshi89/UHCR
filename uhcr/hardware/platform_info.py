import json
import platform
from dataclasses import dataclass, asdict
from typing import Dict, Any

from uhcr.hardware.cpuid import detect_cpu, CPUCapabilities
from uhcr.hardware.gpu_detect import detect_gpu, GPUCapabilities
from uhcr.hardware.memory_detect import detect_memory, MemoryCapabilities
from uhcr.hardware.cache_detect import detect_cache

@dataclass
class HardwareProfile:
    os: str
    os_release: str
    architecture: str
    cpu: CPUCapabilities
    gpu: GPUCapabilities
    memory: MemoryCapabilities

    def to_dict(self) -> Dict[str, Any]:
        """Serializes hardware capabilities into a dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 4) -> str:
        """Serializes hardware capabilities into a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def get_fingerprint(self) -> str:
        """Generates a capability-driven hardware signature for backend targeting."""
        cpu_features = []
        for feat in ["avx512f", "avx2", "avx", "fma", "sse4_2", "sse2", "neon"]:
            if feat in self.cpu.features:
                cpu_features.append(feat)
                break
        if not cpu_features:
            cpu_features.append("generic_x86")

        gpu_features = []
        if self.gpu.cuda_available:
            gpu_features.append(f"cuda_{self.gpu.cuda_version}")
        if self.gpu.vulkan_available:
            gpu_features.append("vulkan")
        if self.gpu.rocm_available:
            gpu_features.append("rocm")
        if self.gpu.metal_available:
            gpu_features.append("metal")

        gpu_fingerprint = "+".join(gpu_features) if gpu_features else "cpu_only"
        return f"{self.os}-{self.architecture}-{cpu_features[0]}-{gpu_fingerprint}"

    def format_table(self) -> str:
        """Returns a formatted CLI table showing detected capabilities."""
        # Detect if we can use unicode or fallback to ASCII
        import sys
        use_ascii = False
        if sys.stdout and sys.stdout.encoding:
            try:
                "┌├└".encode(sys.stdout.encoding)
            except UnicodeEncodeError:
                use_ascii = True
        else:
            use_ascii = True

        # Use box characters based on console encoding capabilities
        TL = "+" if use_ascii else "┌"
        TR = "+" if use_ascii else "┐"
        HL = "-" if use_ascii else "─"
        VL = "|" if use_ascii else "│"
        ML = "+" if use_ascii else "├"
        MR = "+" if use_ascii else "┤"
        MM = "+" if use_ascii else "┼"

        lines = []
        lines.append(f"{TL}{HL*58}{TR}")
        lines.append(f"{VL}           UHCR HARDWARE DETECTION ENGINE REPORT          {VL}")
        lines.append(f"{ML}{HL*26}{MM}{HL*31}{MR}")
        lines.append(f"{VL} Operating System         {VL} {self.os} ({self.os_release})")
        lines.append(f"{VL} Architecture             {VL} {self.architecture}")
        lines.append(f"{ML}{HL*26}{MM}{HL*31}{MR}")
        lines.append(f"{VL} CPU Vendor               {VL} {self.cpu.vendor}")
        lines.append(f"{VL} CPU Model / Brand        {VL} {self.cpu.brand[:28]}")
        lines.append(f"{VL} CPU Topology             {VL} {self.cpu.cores} Cores / {self.cpu.threads} Threads")
        
        # CPU SIMD features, split into lines if too long
        features_str = ", ".join(self.cpu.features)
        if len(features_str) > 28:
            parts = [features_str[i:i+28] for i in range(0, len(features_str), 28)]
            lines.append(f"{VL} CPU Instruction Sets     {VL} {parts[0]}")
            for p in parts[1:]:
                lines.append(f"{VL}                          {VL} {p}")
        else:
            lines.append(f"{VL} CPU Instruction Sets     {VL} {features_str}")
            
        lines.append(f"{VL} CPU Cache Topology       {VL} L1:{self.cpu.cache_l1_data_kb}K / L2:{self.cpu.cache_l2_kb}K / L3:{self.cpu.cache_l3_kb}K")
        lines.append(f"{VL} Cache Details            {VL} L1:{self.cpu.cache_l1_line_size}B/{self.cpu.cache_l1_associativity}-way L2:{self.cpu.cache_l2_line_size}B/{self.cpu.cache_l2_associativity}-way L3:{self.cpu.cache_l3_line_size}B/{self.cpu.cache_l3_associativity}-way")
        lines.append(f"{ML}{HL*26}{MM}{HL*31}{MR}")
        lines.append(f"{VL} Primary GPU Name         {VL} {self.gpu.name[:28]}")
        lines.append(f"{VL} GPU Vendor               {VL} {self.gpu.vendor}")
        lines.append(f"{VL} GPU VRAM                 {VL} {(self.gpu.vram_bytes or 0) / (1024**2):.1f} MB")
        lines.append(f"{VL} GPU Driver               {VL} {self.gpu.driver_version[:28]}")
        
        accels = []
        if self.gpu.cuda_available: accels.append(f"CUDA (v{self.gpu.cuda_version})")
        if self.gpu.vulkan_available: accels.append("Vulkan")
        if self.gpu.rocm_available: accels.append("ROCm")
        if self.gpu.metal_available: accels.append("Metal")
        accels_str = ", ".join(accels) if accels else "None"
        lines.append(f"{VL} Accelerated Runtimes     {VL} {accels_str}")
        lines.append(f"{ML}{HL*26}{MM}{HL*31}{MR}")
        lines.append(f"{VL} Total Memory             {VL} {self.memory.total_bytes / (1024**3):.2f} GB")
        lines.append(f"{VL} RAM Speed/Type           {VL} {self.memory.speed_mhz} MHz {self.memory.memory_type}")
        lines.append(f"{VL} Memory Topology          {VL} {self.memory.numa_nodes} NUMA Nodes")
        lines.append(f"{VL} Page Size                {VL} {self.memory.page_size} bytes")
        lines.append(f"{ML}{HL*26}{MM}{HL*31}{MR}")
        lines.append(f"{VL} Capability Fingerprint   {VL} {self.get_fingerprint()[:28]}")
        
        # Bottom border
        BL = "+" if use_ascii else "└"
        BR = "+" if use_ascii else "┘"
        BM = "+" if use_ascii else "┴"
        
        # Standardize lines padding for box drawing
        formatted_lines = []
        for line in lines:
            if line.startswith(TL) or line.startswith(ML):
                formatted_lines.append(line)
            else:
                # Pad data rows to fit the box
                parts = line.split(VL)
                col1 = parts[1]
                col2 = parts[2]
                col1_padded = col1.ljust(26)
                col2_padded = col2.ljust(31)
                formatted_lines.append(f"{VL}{col1_padded}{VL}{col2_padded}{VL}")
        
        # Add bottom border
        formatted_lines.append(f"{BL}{HL*26}{BM}{HL*31}{BR}")
                
        return "\n".join(formatted_lines)

_cached_profile = None

def detect_platform() -> HardwareProfile:
    """Detects and caches the complete hardware capabilities of the machine."""
    global _cached_profile
    if _cached_profile is not None:
        return _cached_profile

    cpu_caps = detect_cpu()
    gpu_caps = detect_gpu()
    mem_caps = detect_memory()

    # Populate cache topology details from detect_cache()
    topology = detect_cache()
    cpu_caps.cache_l1_line_size = topology.l1_data.line_size_bytes
    cpu_caps.cache_l1_associativity = topology.l1_data.associativity
    cpu_caps.cache_l2_line_size = topology.l2.line_size_bytes
    cpu_caps.cache_l2_associativity = topology.l2.associativity
    cpu_caps.cache_l3_line_size = topology.l3.line_size_bytes
    cpu_caps.cache_l3_associativity = topology.l3.associativity

    # Populate cache size fields if they're still at default (0)
    if cpu_caps.cache_l1_data_kb == 0:
        cpu_caps.cache_l1_data_kb = topology.l1_data.size_kb
    if cpu_caps.cache_l1_inst_kb == 0:
        cpu_caps.cache_l1_inst_kb = topology.l1_instruction.size_kb
    if cpu_caps.cache_l2_kb == 0:
        cpu_caps.cache_l2_kb = topology.l2.size_kb
    if cpu_caps.cache_l3_kb == 0:
        cpu_caps.cache_l3_kb = topology.l3.size_kb

    _cached_profile = HardwareProfile(
        os=platform.system(),
        os_release=platform.release(),
        architecture=platform.machine(),
        cpu=cpu_caps,
        gpu=gpu_caps,
        memory=mem_caps
    )
    return _cached_profile

if __name__ == "__main__":
    profile = detect_platform()
    print(profile.format_table())
