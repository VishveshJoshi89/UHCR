"""Tests for runtime, memory manager, scheduler, and plugin system."""
import ctypes
import threading
import pytest

import uhcr
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder
from uhcr.runtime.memory_manager import AlignedBuffer
from uhcr.runtime.scheduler import Scheduler


class TestAlignedBuffer:
    def test_allocation(self):
        buf = AlignedBuffer(1024, alignment=64)
        assert buf.address is not None
        assert buf.address % 64 == 0
        buf.free()

    def test_copy_from(self):
        buf = AlignedBuffer(256, alignment=64)
        buf.copy_from(b"\x01\x02\x03\x04")
        data = buf.copy_to()
        assert data[0] == 1
        assert data[1] == 2
        assert data[2] == 3
        assert data[3] == 4
        buf.free()

    def test_ctypes_array_view(self):
        buf = AlignedBuffer(32, alignment=32)
        arr = buf.as_ctypes_array(ctypes.c_float)
        arr[0] = 3.14
        assert abs(arr[0] - 3.14) < 0.001
        buf.free()

    def test_context_manager(self):
        with AlignedBuffer(64, alignment=64) as buf:
            assert buf.address is not None
        assert buf.address is None

    def test_free_idempotent(self):
        buf = AlignedBuffer(64, alignment=64)
        buf.free()
        buf.free()  # Should not crash


class TestScheduler:
    def test_parallel_for(self):
        results = []
        lock = threading.Lock()

        def worker(start, end):
            with lock:
                results.append((start, end))

        sched = Scheduler(num_threads=2)
        sched.parallel_for(100, worker)
        total = sum(end - start for start, end in results)
        assert total == 100

    def test_single_thread(self):
        results = []

        def worker(start, end):
            results.append((start, end))

        sched = Scheduler(num_threads=1)
        sched.parallel_for(50, worker)
        assert results == [(0, 50)]

    def test_small_iteration_count(self):
        results = []
        lock = threading.Lock()

        def worker(start, end):
            with lock:
                results.append((start, end))

        sched = Scheduler(num_threads=4)
        sched.parallel_for(2, worker)
        total = sum(end - start for start, end in results)
        assert total == 2


class TestRuntime:
    def test_get_runtime(self):
        rt = uhcr.get_runtime()
        assert rt is not None

    def test_runtime_singleton(self):
        rt1 = uhcr.get_runtime()
        rt2 = uhcr.get_runtime()
        assert rt1 is rt2

    def test_compilation_cache(self):
        rt = uhcr.get_runtime()
        builder = IRBuilder()
        builder.new_module()
        func = builder.new_function("cache_test", [Type.I64, Type.I64], Type.I64)
        entry = func.create_block("entry")
        builder.set_block(entry)
        builder.ret(builder.add(func.arguments[0], func.arguments[1]))

        fn1 = rt.compile(func)
        fn2 = rt.compile(func)
        assert fn1 is fn2


class TestPluginSystem:
    def test_plugin_import(self):
        from uhcr.plugins import Plugin, PluginManager
        assert Plugin is not None
        assert PluginManager is not None

    def test_plugin_manager_creation(self):
        from uhcr.plugins import PluginManager
        pm = PluginManager()
        assert pm.loaded_plugins == {}

    def test_discover_plugins(self):
        from pathlib import Path
        from uhcr.plugins import discover_plugins
        # Should find the example plugin
        found = discover_plugins([Path("plugins")])
        names = [p.name for p in found]
        assert "example_plugin" in names

    def test_load_example_plugin(self):
        from pathlib import Path
        from uhcr.plugins import load_plugin
        plugin = load_plugin(Path("plugins/example_plugin"))
        assert plugin is not None
        assert plugin.name == "example-plugin"
        assert plugin.version == "0.1.0"

    def test_plugin_kernel_registration(self):
        from pathlib import Path
        from uhcr.plugins import load_plugin
        from uhcr.plugins.base import get_registered_kernels

        rt = uhcr.get_runtime()
        plugin = load_plugin(Path("plugins/example_plugin"), runtime=rt)
        kernels = get_registered_kernels()
        assert "example_relu" in kernels
        # Test the kernel works
        result = kernels["example_relu"]([-1.0, 0.0, 2.0, -3.0])
        assert result == [0.0, 0.0, 2.0, 0.0]
