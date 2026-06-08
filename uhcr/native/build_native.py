#!/usr/bin/env python3
"""Build script for UHCR native safety monitor."""

import os
import platform
import subprocess
import sys
from pathlib import Path

def build_windows():
    """Build on Windows using MSVC."""
    print("Building on Windows with MSVC...")
    
    cmd = [
        "cl",
        "/EHsc",
        "/std:c++17",
        "/O2",
        "/LD",  # Build DLL
        "safety_monitor.cpp",
        "/link",
        "/OUT:safety_monitor.dll",
        "psapi.lib",  # For process memory info
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✓ Built safety_monitor.dll")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Build failed: {e}")
        return False

def build_unix():
    """Build on Linux/macOS using GCC/Clang."""
    system = platform.system()
    print(f"Building on {system} with GCC/Clang...")
    
    if system == "Darwin":
        lib_name = "safety_monitor.dylib"
    else:
        lib_name = "safety_monitor.so"
    
    cmd = [
        "g++",
        "-std=c++17",
        "-O2",
        "-shared",
        "-fPIC",
        "safety_monitor.cpp",
        "-o", lib_name,
        "-pthread",
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✓ Built {lib_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Build failed: {e}")
        return False

def main():
    """Main build entry point."""
    # Change to the native directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print("=" * 60)
    print("UHCR Native Safety Monitor Build")
    print("=" * 60)
    
    system = platform.system()
    if system == "Windows":
        success = build_windows()
    else:
        success = build_unix()
    
    if success:
        print("\n✓ Build completed successfully!")
        print("\nThe native safety layer will now protect against:")
        print("  - Memory overflows")
        print("  - CPU thermal damage")
        print("  - GPU thermal damage")
        print("  - Resource exhaustion")
        return 0
    else:
        print("\n✗ Build failed!")
        print("\nRunning without native safety layer (Python fallback mode)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
