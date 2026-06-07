import ctypes
import os
import sys
import platform
import threading
from typing import Callable, List

class Scheduler:
    """Manages parallel work execution and thread affinity mapping for maximum cache locality."""
    def __init__(self, num_threads: int = None):
        self.num_threads = num_threads or os.cpu_count() or 1
        self.threads: List[threading.Thread] = []
        self.system = platform.system()

    def pin_current_thread(self, core_id: int):
        """Pins the calling thread to a specific CPU core for NUMA/cache optimization."""
        if self.system == "Windows":
            try:
                # SetThreadAffinityMask
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetCurrentThread()
                mask = 1 << core_id
                kernel32.SetThreadAffinityMask(handle, mask)
            except Exception:
                pass
        elif self.system == "Linux":
            try:
                # pthread_setaffinity_np
                libc = ctypes.CDLL("libc.so.6")
                # cpu_set_t representation in ctypes (usually an array of unsigned longs)
                # We can just use sched_setaffinity via syscall
                # syscall(SYS_sched_setaffinity, pid, size, mask)
                SYS_sched_setaffinity = 203
                mask = (ctypes.c_ulong * 16)()
                mask[core_id // 64] |= 1 << (core_id % 64)
                libc.syscall(SYS_sched_setaffinity, 0, ctypes.sizeof(mask), ctypes.byref(mask))
            except Exception:
                pass

    def parallel_for(self, total_iterations: int, callback: Callable[[int, int], None]):
        """Executes a loop range in parallel across threads.
        
        callback signature: callback(start_idx, end_idx)
        """
        if self.num_threads <= 1 or total_iterations <= self.num_threads:
            # Single-threaded execution shortcut
            callback(0, total_iterations)
            return

        chunk_size = (total_iterations + self.num_threads - 1) // self.num_threads
        threads = []

        def worker(thread_id: int, start: int, end: int):
            self.pin_current_thread(thread_id % (os.cpu_count() or 1))
            callback(start, end)

        for i in range(self.num_threads):
            start = i * chunk_size
            end = min(start + chunk_size, total_iterations)
            if start >= total_iterations:
                break
            t = threading.Thread(target=worker, args=(i, start, end))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
