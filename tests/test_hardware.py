"""Tests for hardware detection layer."""
import platform
import pytest
import uhcr


def test_detect_returns_profile():
    profile = uhcr.detect()
    assert profile is not None
    assert profile.os == platform.system()
    assert profile.architecture == platform.machine()


def test_cpu_features_detected():
    profile = uhcr.detect()
    # On any x86_64 machine, at least SSE2 should be present
    if platform.machine().lower() in ("amd64", "x86_64"):
        assert "sse2" in profile.cpu.features


def test_cpu_has_properties():
    profile = uhcr.detect()
    cpu = profile.cpu
    # These properties should exist and return booleans
    assert isinstance(cpu.has_sse2, bool)
    assert isinstance(cpu.has_avx, bool)
    assert isinstance(cpu.has_avx2, bool)
    assert isinstance(cpu.has_avx512, bool)
    assert isinstance(cpu.has_fma, bool)


def test_gpu_detection():
    profile = uhcr.detect()
    gpu = profile.gpu
    # GPU detection should always return a GPUCapabilities object
    assert gpu is not None
    assert isinstance(gpu.cuda_available, bool)
    assert isinstance(gpu.vulkan_available, bool)


def test_memory_detection():
    profile = uhcr.detect()
    mem = profile.memory
    assert mem.total_bytes > 0
    assert mem.page_size > 0
    assert mem.numa_nodes >= 1


def test_memory_speed_and_type_fields():
    """Test that memory speed and type fields are populated with valid values."""
    from uhcr.hardware.memory_detect import detect_memory
    mem = detect_memory()
    # speed_mhz should be a non-negative integer
    assert isinstance(mem.speed_mhz, int)
    assert mem.speed_mhz >= 0
    # memory_type should be a non-empty string
    assert isinstance(mem.memory_type, str)
    assert len(mem.memory_type) > 0


def test_memory_speed_type_fallback():
    """Test that memory detection returns valid defaults even if detection fails."""
    from uhcr.hardware.memory_detect import MemoryCapabilities
    # Default values should be safe fallbacks
    mem = MemoryCapabilities()
    assert mem.speed_mhz == 0
    assert mem.memory_type == "Unknown"


def test_fingerprint():
    profile = uhcr.detect()
    fp = profile.get_fingerprint()
    assert isinstance(fp, str)
    assert len(fp) > 0
    assert profile.os in fp


def test_json_serialization():
    profile = uhcr.detect()
    json_str = profile.to_json()
    assert '"os"' in json_str
    assert '"cpu"' in json_str
    assert '"gpu"' in json_str


def test_json_includes_ram_and_cache_fields():
    """Verify to_json() includes new RAM speed/type and cache topology fields via asdict()."""
    import json as json_mod
    profile = uhcr.detect()
    json_str = profile.to_json()
    data = json_mod.loads(json_str)

    # RAM fields in memory section
    assert "speed_mhz" in data["memory"], "speed_mhz missing from JSON memory section"
    assert "memory_type" in data["memory"], "memory_type missing from JSON memory section"
    assert isinstance(data["memory"]["speed_mhz"], int)
    assert isinstance(data["memory"]["memory_type"], str)

    # Cache topology fields in cpu section
    cache_fields = [
        "cache_l1_line_size",
        "cache_l1_associativity",
        "cache_l2_line_size",
        "cache_l2_associativity",
        "cache_l3_line_size",
        "cache_l3_associativity",
    ]
    for field_name in cache_fields:
        assert field_name in data["cpu"], f"{field_name} missing from JSON cpu section"
        assert isinstance(data["cpu"][field_name], int)


def test_format_table():
    profile = uhcr.detect()
    table = profile.format_table()
    assert "UHCR HARDWARE DETECTION" in table
    assert profile.cpu.vendor in table
