#!/usr/bin/env python3
"""Build script for UHCR native safety checker library.

This script compiles the C++ safety checking modules for runtime protection.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path


def find_cmake():
    """Find CMake executable."""
    cmake = shutil.which("cmake")
    if cmake is None:
        print("Error: CMake not found. Please install CMake to build native modules.")
        print("  Windows: choco install cmake")
        print("  macOS: brew install cmake")
        print("  Linux: apt-get install cmake or yum install cmake")
        return None
    return cmake


def find_compiler():
    """Detect available C++ compiler."""
    compilers = []
    
    if platform.system() == "Windows":
        # Check for MSVC
        if shutil.which("cl"):
            compilers.append("msvc")
        # Check for MinGW
        if shutil.which("g++"):
            compilers.append("mingw")
    else:
        # Check for GCC
        if shutil.which("g++"):
            compilers.append("gcc")
        # Check for Clang
        if shutil.which("clang++"):
            compilers.append("clang")
    
    return compilers


def build_native_library(force_rebuild=False):
    """Build the native safety checker library.
    
    Args:
        force_rebuild: If True, clean and rebuild from scratch
        
    Returns:
        True if build succeeded, False otherwise
    """
    native_dir = Path(__file__).parent
    build_dir = native_dir / "build"
    
    # Check if CMake is available
    cmake = find_cmake()
    if cmake is None:
        print("Skipping native build - CMake not found")
        return False
    
    # Check for compiler
    compilers = find_compiler()
    if not compilers:
        print("Error: No C++ compiler found")
        print("  Windows: Install Visual Studio Build Tools or MinGW")
        print("  macOS: xcode-select --install")
        print("  Linux: apt-get install build-essential")
        return False
    
    print(f"Building UHCR Safety Checker (using {compilers[0]})...")
    
    # Clean if requested
    if force_rebuild and build_dir.exists():
        print("Cleaning build directory...")
        shutil.rmtree(build_dir)
    
    # Create build directory
    build_dir.mkdir(exist_ok=True)
    
    try:
        # Configure with CMake
        print("Configuring with CMake...")
        configure_cmd = [cmake, ".."]
        
        # Add generator for Windows
        if platform.system() == "Windows" and "msvc" in compilers:
            configure_cmd.extend(["-G", "Visual Studio 17 2022"])
        
        result = subprocess.run(
            configure_cmd,
            cwd=build_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"CMake configuration failed:\n{result.stderr}")
            return False
        
        # Build
        print("Building...")
        build_cmd = [cmake, "--build", ".", "--config", "Release"]
        
        result = subprocess.run(
            build_cmd,
            cwd=build_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Build failed:\n{result.stderr}")
            return False
        
        print("✓ Native safety library built successfully")
        
        # Copy library to native directory for easy access
        lib_extensions = [".dll", ".so", ".dylib"]
        for ext in lib_extensions:
            lib_files = list(build_dir.rglob(f"*uhcr_safety{ext}"))
            for lib_file in lib_files:
                dest = native_dir / lib_file.name
                shutil.copy2(lib_file, dest)
                print(f"  Installed: {dest.name}")
        
        return True
        
    except Exception as e:
        print(f"Build error: {e}")
        return False


def clean_build():
    """Remove build artifacts."""
    native_dir = Path(__file__).parent
    build_dir = native_dir / "build"
    
    if build_dir.exists():
        print("Cleaning build directory...")
        shutil.rmtree(build_dir)
        print("✓ Build directory cleaned")
    
    # Remove library files
    lib_extensions = [".dll", ".so", ".dylib", ".lib", ".a"]
    for ext in lib_extensions:
        for lib_file in native_dir.glob(f"*{ext}"):
            print(f"  Removing: {lib_file.name}")
            lib_file.unlink()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build UHCR native safety library")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_build()
    elif args.rebuild:
        build_native_library(force_rebuild=True)
    else:
        build_native_library()
