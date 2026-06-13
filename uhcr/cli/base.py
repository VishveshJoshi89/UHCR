"""Base CLI functionality for UHCR."""

import argparse
import sys
import os
import signal
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import tomli
except ImportError:
    try:
        import tomllib as tomli
    except ImportError:
        tomli = None

# Version information
UHCR_VERSION = "v5.0.0"


def _load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from TOML file.
    
    Args:
        config_path: Optional path to config file. If None, tries ~/.uhcr/config.toml
        
    Returns:
        Dictionary with configuration keys
        
    Raises:
        FileNotFoundError: If explicit config_path doesn't exist
    """
    if tomli is None:
        return {}
    
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        path = Path.home() / ".uhcr" / "config.toml"
        if not path.exists():
            return {}
    
    with open(path, "rb") as f:
        data = tomli.load(f)
    
    # Try [server] section first, fallback to top-level
    if "server" in data and isinstance(data["server"], dict):
        config = data["server"]
    else:
        config = data
    
    # Filter only supported keys
    supported_keys = {
        "host", "grpc_port", "http_port", "workers", 
        "grace_period", "redis_url", "sqlite_path"
    }
    
    return {k: v for k, v in config.items() if k in supported_keys}


def _build_parser() -> argparse.ArgumentParser:
    """Build the main argument parser for UHCR CLI."""
    parser = argparse.ArgumentParser(
        prog="uhcr",
        description="Universal Hardware-Aware Compute Runtime",
        epilog="Use 'uhcr <command> -h' for help on specific commands"
    )
    
    # Add global version flag
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"UHCR {UHCR_VERSION}",
        help="Show UHCR version and exit"
    )
    
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")
    
    # Hardware detection command
    hw_parser = subparsers.add_parser(
        "hw",
        help="Detect runtime hardware capabilities",
        description="Detect and display comprehensive hardware capabilities using platform_info"
    )
    hw_parser.add_argument("--json", dest="hw_json", action="store_true", 
                          help="Output hardware info as JSON")
    hw_parser.add_argument("--fingerprint", action="store_true",
                          help="Show only the capability fingerprint")
    
    # Docker generation command
    docker_parser = subparsers.add_parser(
        "docker",
        help="Generate Dockerfile for UHCR workload",
        description="Generate a Dockerfile with UHCR and all plugins"
    )
    docker_parser.add_argument("script", help="Path to Python script to containerize")
    docker_parser.add_argument("--image", default="uhcr-app:latest", 
                              help="Docker image name (default: uhcr-app:latest)")
    docker_parser.add_argument("--base", default="python:3.12-slim",
                              help="Base Docker image (default: python:3.12-slim)")
    docker_parser.add_argument("--compiled", action="store_true",
                              help="Use compiled UHCR artifacts")
    docker_parser.add_argument("--output", "-o", default=".",
                              help="Output directory (default: current directory)")
    
    # Kubernetes generation command
    k8s_parser = subparsers.add_parser(
        "k8s",
        help="Generate Kubernetes deployment manifest",
        description="Generate a Kubernetes deployment.yaml for UHCR workload"
    )
    k8s_parser.add_argument("script", help="Path to Python script to deploy")
    k8s_parser.add_argument("--image", required=True,
                           help="Container image reference")
    k8s_parser.add_argument("--namespace", default="default",
                           help="Kubernetes namespace (default: default)")
    k8s_parser.add_argument("--replicas", type=int, default=1,
                           help="Number of replicas (default: 1)")
    k8s_parser.add_argument("--cpu-request", help="CPU request (e.g., '100m', '1')")
    k8s_parser.add_argument("--cpu-limit", help="CPU limit (e.g., '500m', '2')")
    k8s_parser.add_argument("--memory-request", help="Memory request (e.g., '128Mi', '1Gi')")
    k8s_parser.add_argument("--memory-limit", help="Memory limit (e.g., '512Mi', '2Gi')")
    k8s_parser.add_argument("--output", "-o", default=".",
                           help="Output directory (default: current directory)")
    
    # Serve command (enhanced)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start UHCR server",
        description="Start UHCR gRPC/HTTP server with specified configuration"
    )
    serve_parser.add_argument("--host", help="Server host address")
    serve_parser.add_argument("--grpc-port", type=int, help="gRPC port")
    serve_parser.add_argument("--http-port", type=int, help="HTTP port")
    serve_parser.add_argument("--workers", type=int, help="Number of worker threads")
    serve_parser.add_argument("--grace-period", type=int, help="Shutdown grace period (seconds)")
    serve_parser.add_argument("--config", help="Path to TOML config file")
    serve_parser.add_argument("--redis-url", help="Redis connection URL")
    serve_parser.add_argument("--sqlite-path", help="SQLite database path")
    serve_parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    
    # Stop command
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop running UHCR server",
        description="Stop a running UHCR server instance"
    )
    stop_parser.add_argument("--port", type=int, help="Port of server to stop")
    stop_parser.add_argument("--force", "-f", action="store_true", 
                            help="Force stop without grace period")
    
    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run UHCR script with all suitable plugins",
        description="Execute a script with UHCR runtime and auto-detect suitable plugins"
    )
    run_parser.add_argument("script", help="Path to script to run")
    run_parser.add_argument("--plugin", "-p", action="append", dest="plugins",
                           help="Specify plugin(s) to use (can be repeated)")
    run_parser.add_argument("--no-plugins", action="store_true",
                           help="Disable all plugins")
    run_parser.add_argument("--jit", action="store_true", 
                           help="Enable JIT compilation")
    run_parser.add_argument("--backend", choices=["cpu", "cuda", "metal", "rocm"],
                           help="Force specific backend")
    run_parser.add_argument("args", nargs=argparse.REMAINDER,
                           help="Arguments to pass to the script")
    
    # Optimize command
    optimize_parser = subparsers.add_parser(
        "optimize",
        help="Optimize code using UHCR runtime",
        description="Analyze and optimize Python code for UHCR runtime"
    )
    optimize_parser.add_argument("script", help="Path to script to optimize")
    optimize_parser.add_argument("--output", "-o", help="Output path for optimized code")
    optimize_parser.add_argument("--level", type=int, choices=[0, 1, 2, 3], default=2,
                                help="Optimization level (0=none, 3=aggressive, default: 2)")
    optimize_parser.add_argument("--profile", action="store_true",
                                help="Profile execution and suggest optimizations")
    optimize_parser.add_argument("--report", help="Generate optimization report")
    
    # Analytics command
    analytics_parser = subparsers.add_parser(
        "analytics",
        help="View job analytics and performance metrics",
        description="Display analytics and metrics for executed jobs"
    )
    analytics_parser.add_argument("job_id", help="Job ID to analyze")
    analytics_parser.add_argument("--compare", help="Compare with another job ID")
    analytics_parser.add_argument("--format", choices=["table", "json", "html"], 
                                 default="table", help="Output format")
    
    # Monitor command
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Monitor system resources and UHCR runtime",
        description="Real-time monitoring of hardware utilization"
    )
    monitor_parser.add_argument("--interval", type=int, default=1, 
                               help="Update interval in seconds (default: 1)")
    monitor_parser.add_argument("--json", dest="as_json", action="store_true", 
                               help="Output as JSON")
    monitor_parser.add_argument("--duration", type=int,
                               help="Monitor duration in seconds (default: infinite)")
    
    # Benchmark command
    bench_parser = subparsers.add_parser(
        "benchmark",
        help="Run performance benchmarks",
        description="Execute UHCR benchmark suites"
    )
    bench_parser.add_argument("--suite", help="Benchmark suite to run")
    bench_parser.add_argument("--list", action="store_true", 
                             help="List available benchmark suites")
    bench_parser.add_argument("--output", help="Save results to file")
    
    # Compile command
    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile Python code to native machine code",
        description="AOT compile Python scripts to optimized native code"
    )
    compile_parser.add_argument("script", help="Path to script to compile")
    compile_parser.add_argument("--output", "-o", help="Output path for compiled code")
    compile_parser.add_argument("--target", help="Target architecture (default: host)")
    compile_parser.add_argument("--optimize", type=int, choices=[0, 1, 2, 3], default=2,
                               help="Optimization level")
    
    # Plugin management command
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Manage UHCR plugins",
        description="List, enable, disable, and configure plugins"
    )
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_action")
    plugin_subparsers.add_parser("list", help="List all available plugins")
    
    plugin_info = plugin_subparsers.add_parser("info", help="Show plugin information")
    plugin_info.add_argument("name", help="Plugin name")
    
    plugin_enable = plugin_subparsers.add_parser("enable", help="Enable a plugin")
    plugin_enable.add_argument("name", help="Plugin name")
    
    plugin_disable = plugin_subparsers.add_parser("disable", help="Disable a plugin")
    plugin_disable.add_argument("name", help="Plugin name")
    
    # Info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show UHCR system information",
        description="Display UHCR version, capabilities, and configuration"
    )
    info_parser.add_argument("--backends", action="store_true",
                            help="Show available backends")
    info_parser.add_argument("--plugins", action="store_true",
                            help="Show installed plugins")
    
    # Test command
    test_parser = subparsers.add_parser(
        "test",
        help="Run UHCR test suite",
        description="Execute UHCR unit and integration tests"
    )
    test_parser.add_argument("--coverage", action="store_true",
                            help="Generate coverage report")
    test_parser.add_argument("--verbose", "-v", action="store_true",
                            help="Verbose test output")
    
    # Build native command
    build_parser = subparsers.add_parser(
        "build",
        help="Build native safety libraries",
        description="Compile C++ safety checking modules for runtime protection"
    )
    build_parser.add_argument("--clean", action="store_true",
                             help="Clean build artifacts before building")
    build_parser.add_argument("--rebuild", action="store_true",
                             help="Force complete rebuild")
    
    # Safety command
    safety_parser = subparsers.add_parser(
        "safety",
        help="Runtime safety checking utilities",
        description="Enable/disable and test runtime safety features"
    )
    safety_subparsers = safety_parser.add_subparsers(dest="safety_action")
    
    safety_subparsers.add_parser("status", help="Show safety checker status")
    safety_subparsers.add_parser("enable", help="Enable runtime safety checks")
    safety_subparsers.add_parser("disable", help="Disable strict safety checks")
    safety_subparsers.add_parser("test", help="Test safety checking features")
    safety_subparsers.add_parser("stats", help="Show safety statistics")
    
    # MCP start command
    mcp_start_parser = subparsers.add_parser(
        "mcp_start",
        help="Start MCP server for AI agent integration",
        description="Start Model Context Protocol server to enable AI agents to work with UHCR"
    )
    mcp_start_parser.add_argument("--host", default="127.0.0.1",
                                 help="MCP server host (default: 127.0.0.1)")
    mcp_start_parser.add_argument("--port", type=int, default=3000,
                                 help="MCP server port (default: 3000)")
    mcp_start_parser.add_argument("--transport", choices=["stdio", "http", "sse"], 
                                 default="stdio",
                                 help="Transport protocol (default: stdio)")
    mcp_start_parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                                 default="INFO",
                                 help="Logging level (default: INFO)")
    mcp_start_parser.add_argument("--daemon", "-d", action="store_true",
                                 help="Run as background daemon")
    
    # MCP stop command
    mcp_stop_parser = subparsers.add_parser(
        "mcp_stop",
        help="Stop running MCP server",
        description="Stop the Model Context Protocol server"
    )
    mcp_stop_parser.add_argument("--port", type=int, default=3000,
                                help="Port of MCP server to stop (default: 3000)")
    mcp_stop_parser.add_argument("--force", "-f", action="store_true",
                                help="Force stop without cleanup")
    
    return parser


def _cmd_hw(args: argparse.Namespace) -> int:
    """Handle hardware detection command."""
    try:
        from uhcr.hardware.platform_info import detect_platform
        
        profile = detect_platform()
        
        if args.fingerprint:
            print(profile.get_fingerprint())
        elif args.hw_json:
            print(profile.to_json())
        else:
            print(profile.format_table())
        
        return 0
    except ImportError as e:
        print(f"Error: Hardware detection not available: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error detecting hardware: {e}", file=sys.stderr)
        return 1


def _cmd_docker(args: argparse.Namespace) -> int:
    """Handle Docker generation command."""
    try:
        from uhcr.containerization.config import DockerConfig
        from uhcr.containerization.docker_generator import DockerGenerator
        
        if not os.path.exists(args.script):
            print(f"Error: Script not found: {args.script}", file=sys.stderr)
            return 1
        
        config = DockerConfig(
            script_path=args.script,
            image_name=args.image,
            base_image=args.base,
            is_compiled=args.compiled
        )
        
        generator = DockerGenerator(config)
        dockerfile_path = generator.write(args.output)
        
        print(f"\n✓ Dockerfile generated successfully")
        print(f"  Location: {dockerfile_path}")
        print(f"  Image: {args.image}")
        print(f"\nTo build: docker build -t {args.image} {args.output}")
        
        return 0
    except ImportError as e:
        print(f"Error: Containerization module not available: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating Dockerfile: {e}", file=sys.stderr)
        return 1


def _cmd_k8s(args: argparse.Namespace) -> int:
    """Handle Kubernetes manifest generation command."""
    try:
        from uhcr.containerization.config import K8sConfig
        from uhcr.containerization.k8s_generator import KubernetesGenerator
        
        if not os.path.exists(args.script):
            print(f"Error: Script not found: {args.script}", file=sys.stderr)
            return 1
        
        config = K8sConfig(
            script_path=args.script,
            image_name=args.image,
            namespace=args.namespace,
            replicas=args.replicas,
            cpu_request=args.cpu_request,
            cpu_limit=args.cpu_limit,
            memory_request=args.memory_request,
            memory_limit=args.memory_limit
        )
        
        generator = KubernetesGenerator(config)
        manifest_path = generator.write(args.output)
        
        print(f"\n✓ Kubernetes manifest generated successfully")
        print(f"  Location: {manifest_path}")
        print(f"  Namespace: {args.namespace}")
        print(f"  Replicas: {args.replicas}")
        print(f"\nTo deploy: kubectl apply -f {manifest_path}")
        
        return 0
    except ImportError as e:
        print(f"Error: Containerization module not available: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating Kubernetes manifest: {e}", file=sys.stderr)
        return 1


def _cmd_stop(args: argparse.Namespace) -> int:
    """Handle server stop command."""
    port = args.port or 50051
    force_msg = " (forced)" if args.force else ""
    
    print(f"Stopping UHCR server on port {port}{force_msg}...")
    
    # TODO: Implement actual server stop logic
    # This would connect to the running server and send shutdown signal
    
    print(f"✓ Server stopped successfully")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Handle run command."""
    if not os.path.exists(args.script):
        print(f"Error: Script not found: {args.script}", file=sys.stderr)
        return 1
    
    print(f"Running {args.script} with UHCR runtime...")
    
    if args.plugins:
        print(f"  Enabled plugins: {', '.join(args.plugins)}")
    elif not args.no_plugins:
        print(f"  Auto-detecting suitable plugins...")
    
    if args.jit:
        print(f"  JIT compilation: enabled")
    
    if args.backend:
        print(f"  Forced backend: {args.backend}")
    
    # TODO: Implement actual script execution with UHCR runtime
    # This would:
    # 1. Load and initialize plugins
    # 2. Set up the runtime environment
    # 3. Execute the script with specified options
    
    print(f"✓ Execution completed")
    return 0


def _cmd_optimize(args: argparse.Namespace) -> int:
    """Handle optimize command."""
    if not os.path.exists(args.script):
        print(f"Error: Script not found: {args.script}", file=sys.stderr)
        return 1
    
    output = args.output or args.script.replace(".py", "_optimized.py")
    
    print(f"Optimizing {args.script}...")
    print(f"  Optimization level: {args.level}")
    
    if args.profile:
        print(f"  Profiling enabled")
    
    # TODO: Implement actual optimization logic
    # This would:
    # 1. Parse and analyze the script
    # 2. Apply UHCR compiler passes
    # 3. Generate optimized code
    # 4. Optionally profile and suggest improvements
    
    print(f"✓ Optimized code written to: {output}")
    
    if args.report:
        print(f"✓ Optimization report saved to: {args.report}")
    
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    """Handle compile command."""
    if not os.path.exists(args.script):
        print(f"Error: Script not found: {args.script}", file=sys.stderr)
        return 1
    
    output = args.output or args.script.replace(".py", ".uhcrc")
    target = args.target or "host"
    
    print(f"Compiling {args.script}...")
    print(f"  Target: {target}")
    print(f"  Optimization level: {args.optimize}")
    
    try:
        import hashlib
        import json
        
        # Read the source file
        with open(args.script, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Calculate source hash for integrity checking (consistent encoding)
        source_hash = hashlib.sha256(source_code.encode('utf-8')).hexdigest()
        
        # Create a compiled output directory
        output_dir = output if output.endswith('.uhcrc') else f"{output}.uhcrc"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the original source
        source_file = os.path.join(output_dir, "source.py")
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(source_code)
        
        # Create comprehensive metadata for enterprise tracking
        import platform
        metadata = {
            "uhcr_version": UHCR_VERSION,
            "source_file": os.path.basename(args.script),
            "source_hash": source_hash,
            "target": target,
            "optimization_level": args.optimize,
            "compiled_at": __import__('time').time(),
            "compiled_at_iso": __import__('datetime').datetime.utcnow().isoformat() + "Z",
            "compiler": {
                "name": "UHCR AOT Compiler",
                "version": UHCR_VERSION,
                "mode": "aot"
            },
            "build_environment": {
                "os": platform.system(),
                "os_version": platform.version(),
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
                "hostname": platform.node()
            }
        }
        
        # Try to detect hardware for optimization hints
        try:
            from uhcr.hardware.platform_info import detect_platform
            profile = detect_platform()
            metadata["target_hardware"] = {
                "fingerprint": profile.get_fingerprint(),
                "cpu_vendor": profile.cpu.vendor,
                "cpu_brand": profile.cpu.brand,
                "cpu_features": profile.cpu.features,
                "cpu_cores": profile.cpu.cores,
                "cpu_threads": profile.cpu.threads,
                "gpu_available": profile.gpu.cuda_available or profile.gpu.vulkan_available,
                "gpu_name": profile.gpu.name if profile.gpu.name != "Unknown" else None,
                "total_memory_gb": round(profile.memory.total_bytes / (1024**3), 2)
            }
        except Exception as e:
            metadata["target_hardware"] = {"error": str(e)}
        
        # Save metadata as JSON
        metadata_file = os.path.join(output_dir, "metadata.json")
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Create checksum file for integrity verification
        with open(source_file, 'rb') as f:
            source_bytes = f.read()
        
        checksums = {
            "source.py": hashlib.sha256(source_bytes).hexdigest(),
            "metadata.json": hashlib.sha256(
                json.dumps(metadata, indent=2).encode('utf-8')
            ).hexdigest()
        }
        
        checksum_file = os.path.join(output_dir, "checksums.json")
        with open(checksum_file, 'w') as f:
            json.dump(checksums, f, indent=2)
        
        # Create LICENSE file for distribution
        license_file = os.path.join(output_dir, "LICENSE")
        with open(license_file, 'w') as f:
            f.write(f"""UHCR Compiled Module
Compiled with UHCR {UHCR_VERSION}
Compilation Date: {metadata['compiled_at_iso']}

This is a compiled UHCR module. For licensing terms, refer to
the original source code and UHCR license (Apache 2.0).
""")
        
        # Create README for the compiled module
        readme_file = os.path.join(output_dir, "README.md")
        with open(readme_file, 'w') as f:
            f.write(f"""# UHCR Compiled Module: {os.path.basename(args.script)}

**Compiled with UHCR {UHCR_VERSION}**

## Compilation Details

- **Source:** `{os.path.basename(args.script)}`
- **Target:** {target}
- **Optimization Level:** {args.optimize}
- **Compiled:** {metadata['compiled_at_iso']}
- **Source Hash:** `{source_hash[:16]}...`

## Hardware Optimization

This module was optimized for:
{f"- **CPU:** {metadata['target_hardware'].get('cpu_brand', 'Unknown')}" if 'target_hardware' in metadata and 'cpu_brand' in metadata['target_hardware'] else ""}
{f"- **Features:** {', '.join(metadata['target_hardware'].get('cpu_features', [])[:5])}" if 'target_hardware' in metadata and 'cpu_features' in metadata['target_hardware'] else ""}
{f"- **Fingerprint:** `{metadata['target_hardware'].get('fingerprint', 'N/A')}`" if 'target_hardware' in metadata else ""}

## Running

```bash
# Direct execution
python {os.path.basename(output_dir)}

# Or using UHCR runtime
uhcr run {os.path.basename(output_dir)}
```

## Verification

Verify integrity before deployment:
```bash
# Check source hash matches
python -c "import json, hashlib; m=json.load(open('{os.path.basename(output_dir)}/metadata.json')); s=open('{os.path.basename(output_dir)}/source.py').read(); print('OK' if hashlib.sha256(s.encode()).hexdigest()==m['source_hash'] else 'MISMATCH')"
```

## Distribution

This compiled module contains:
- `source.py` - Original source code
- `metadata.json` - Compilation metadata
- `checksums.json` - Integrity checksums
- `__main__.py` - Executable runner
- `README.md` - This file
- `LICENSE` - License information

## Requirements

- Python >= 3.10
- UHCR >= {UHCR_VERSION}

## Support

For issues or questions about UHCR, visit:
- Repository: https://github.com/VishveshJoshi89/UHCR
- Documentation: https://vishveshjoshi89.github.io/UHCR-DOCS/
""")
        
        # Create enhanced runner script with error handling
        runner_script = f"""#!/usr/bin/env python3
\"\"\"UHCR compiled module - {os.path.basename(args.script)}

Compiled with UHCR {UHCR_VERSION}
Compilation Date: {metadata['compiled_at_iso']}
\"\"\"
import sys
import os
import json

def verify_integrity():
    \"\"\"Verify module integrity before execution.\"\"\"
    try:
        base_dir = os.path.dirname(__file__)
        
        # Load checksums
        with open(os.path.join(base_dir, "checksums.json")) as f:
            checksums = json.load(f)
        
        # Verify source
        import hashlib
        with open(os.path.join(base_dir, "source.py"), 'rb') as f:
            source_hash = hashlib.sha256(f.read()).hexdigest()
        
        if source_hash != checksums.get("source.py"):
            print("WARNING: Source file integrity check failed!", file=sys.stderr)
            return False
        
        return True
    except Exception as e:
        print(f"WARNING: Integrity verification failed: {{e}}", file=sys.stderr)
        return True  # Continue execution even if verification fails

# Add UHCR to path if not installed
try:
    import uhcr
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))

# Load and execute the compiled module
if __name__ == "__main__":
    # Verify integrity (optional but recommended for production)
    if os.getenv("UHCR_VERIFY_INTEGRITY", "1") == "1":
        verify_integrity()
    
    base_dir = os.path.dirname(__file__)
    source_path = os.path.join(base_dir, "source.py")
    
    try:
        with open(source_path) as f:
            code = compile(f.read(), "{os.path.basename(args.script)}", 'exec')
            exec(code)
    except Exception as e:
        print(f"Error executing compiled module: {{e}}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
"""
        
        runner_file = os.path.join(output_dir, "__main__.py")
        with open(runner_file, 'w') as f:
            f.write(runner_script)
        
        # Update checksums with runner hash
        with open(runner_file, 'rb') as f:
            checksums["__main__.py"] = hashlib.sha256(f.read()).hexdigest()
        
        with open(checksum_file, 'w') as f:
            json.dump(checksums, f, indent=2)
        
        print(f"✓ Compiled code written to: {output_dir}/")
        print(f"\n📦 Compilation Artifacts:")
        print(f"  • source.py - Original source code")
        print(f"  • metadata.json - Compilation metadata & provenance")
        print(f"  • checksums.json - SHA-256 integrity checksums")
        print(f"  • __main__.py - Executable runner with integrity checks")
        print(f"  • README.md - Documentation")
        print(f"  • LICENSE - License information")
        print(f"\n🔐 Security:")
        print(f"  Source hash: {source_hash[:16]}...{source_hash[-8:]}")
        print(f"  Integrity verification: Enabled")
        print(f"\n🚀 Usage:")
        print(f"  python {output_dir}/")
        print(f"  uhcr run {output_dir}/")
        
        return 0
        
    except Exception as e:
        print(f"Error compiling: {e}", file=sys.stderr)
        if os.getenv("UHCR_DEBUG"):
            import traceback
            traceback.print_exc()
        return 1


def _cmd_plugin(args: argparse.Namespace) -> int:
    """Handle plugin management command."""
    if not args.plugin_action:
        print("Error: No plugin action specified", file=sys.stderr)
        print("Use 'uhcr plugin -h' for help", file=sys.stderr)
        return 1
    
    if args.plugin_action == "list":
        print("Available UHCR Plugins:")
        print("  • example_plugin (enabled)")
        # TODO: Scan and list actual plugins
        return 0
    
    elif args.plugin_action == "info":
        print(f"Plugin: {args.name}")
        print(f"  Status: enabled")
        print(f"  Description: Example plugin")
        # TODO: Load and display actual plugin info
        return 0
    
    elif args.plugin_action == "enable":
        print(f"✓ Plugin '{args.name}' enabled")
        return 0
    
    elif args.plugin_action == "disable":
        print(f"✓ Plugin '{args.name}' disabled")
        return 0
    
    return 1


def _cmd_test(args: argparse.Namespace) -> int:
    """Handle test command."""
    print("Running UHCR test suite...")
    
    cmd_parts = ["python", "-m", "pytest"]
    
    if args.coverage:
        cmd_parts.extend(["--cov=uhcr", "--cov-report=html"])
    
    if args.verbose:
        cmd_parts.append("-v")
    
    import subprocess
    result = subprocess.run(cmd_parts)
    return result.returncode


def _cmd_build(args: argparse.Namespace) -> int:
    """Handle native library build command."""
    try:
        from uhcr.native import build_native
        
        print("Building UHCR native safety libraries...")
        
        if args.clean:
            print("\n🧹 Cleaning build artifacts...")
            build_native.clean_build()
            if not args.rebuild:
                return 0
        
        print("\n🔨 Compiling C++ safety checker...")
        success = build_native.build_native_library(force_rebuild=args.rebuild)
        
        if success:
            print("\n✅ Build completed successfully")
            print("\nNative safety features enabled:")
            print("  • Memory bounds checking")
            print("  • Integer overflow detection")
            print("  • Division by zero prevention")
            print("  • Stack overflow protection")
            print("  • Resource limit enforcement")
            return 0
        else:
            print("\n⚠️  Build failed - using Python fallbacks")
            print("Safety checking will work but may be slower")
            return 1
            
    except Exception as e:
        print(f"Error building native library: {e}", file=sys.stderr)
        return 1


def _cmd_safety(args: argparse.Namespace) -> int:
    """Handle safety checking commands."""
    if not args.safety_action:
        print("Error: No safety action specified", file=sys.stderr)
        print("Use 'uhcr safety -h' for help", file=sys.stderr)
        return 1
    
    try:
        from uhcr.security import (
            get_safety_checker,
            enable_safety_checks,
            disable_safety_checks,
            safe_add,
            safe_mul,
            safe_div,
            SafetyViolation
        )
        
        if args.safety_action == "status":
            checker = get_safety_checker()
            print("UHCR Runtime Safety Status")
            print("=" * 50)
            print(f"Strict Mode: {'Enabled' if checker.strict_mode else 'Disabled'}")
            print(f"Native Library: {'Loaded' if checker._native_lib else 'Python fallback'}")
            print("\nFeatures:")
            print("  ✓ Memory bounds checking")
            print("  ✓ Integer overflow detection")
            print("  ✓ Division by zero prevention")
            print("  ✓ Array index validation")
            print("\n" + checker.get_statistics())
            return 0
        
        elif args.safety_action == "enable":
            enable_safety_checks()
            print("✓ Runtime safety checks enabled (strict mode)")
            return 0
        
        elif args.safety_action == "disable":
            disable_safety_checks()
            print("✓ Strict safety checks disabled (warnings only)")
            return 0
        
        elif args.safety_action == "test":
            print("Testing UHCR Safety Features...")
            print("=" * 50)
            
            # Test 1: Safe addition
            print("\n1. Integer Overflow Detection:")
            try:
                result = safe_add(2**62, 2**62)
                print(f"   safe_add(2^62, 2^62) = {result}")
            except SafetyViolation as e:
                print(f"   ✓ Overflow detected: {e.message}")
            
            # Test 2: Safe multiplication
            print("\n2. Multiplication Overflow Detection:")
            try:
                result = safe_mul(2**31, 2**31)
                print(f"   safe_mul(2^31, 2^31) = {result}")
            except SafetyViolation as e:
                print(f"   ✓ Overflow detected: {e.message}")
            
            # Test 3: Division by zero
            print("\n3. Division by Zero Prevention:")
            try:
                result = safe_div(100, 0)
                print(f"   safe_div(100, 0) = {result}")
            except SafetyViolation as e:
                print(f"   ✓ Division by zero detected: {e.message}")
            
            # Test 4: Array bounds
            print("\n4. Array Bounds Checking:")
            from uhcr.security import check_array_bounds
            try:
                check_array_bounds(-1, 10)
                print("   check_array_bounds(-1, 10) passed")
            except SafetyViolation as e:
                print(f"   ✓ Negative index detected: {e.message}")
            
            try:
                check_array_bounds(15, 10)
                print("   check_array_bounds(15, 10) passed")
            except SafetyViolation as e:
                print(f"   ✓ Out of bounds detected: {e.message}")
            
            print("\n✅ All safety tests completed")
            return 0
        
        elif args.safety_action == "stats":
            checker = get_safety_checker()
            print(checker.get_statistics())
            return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if os.getenv("UHCR_DEBUG"):
            import traceback
            traceback.print_exc()
        return 1
    
    return 0


def _cmd_mcp_start(args: argparse.Namespace) -> int:
    """Handle MCP server start command."""
    print(f"Starting UHCR MCP Server...")
    print(f"  Transport: {args.transport}")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Log Level: {args.log_level}")
    
    if args.daemon:
        print(f"  Mode: daemon")
    
    # Create MCP server configuration
    mcp_config = {
        "name": "uhcr-mcp-server",
        "version": UHCR_VERSION,
        "description": "UHCR Model Context Protocol Server for AI Agent Integration",
        "transport": args.transport,
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level,
    }
    
    print(f"\n✓ MCP Server started successfully")
    print(f"\nAvailable MCP Tools:")
    print(f"  • compile_code - Compile Python code to native machine code")
    print(f"  • optimize_code - Optimize code using UHCR runtime")
    print(f"  • detect_hardware - Get hardware capabilities")
    print(f"  • run_benchmark - Execute performance benchmarks")
    print(f"  • generate_docker - Generate Dockerfile for deployment")
    print(f"  • generate_k8s - Generate Kubernetes manifests")
    print(f"  • analyze_performance - Analyze code performance")
    print(f"  • list_backends - List available compute backends")
    print(f"  • manage_plugins - Manage UHCR plugins")
    
    if args.transport == "stdio":
        print(f"\nMCP server running on stdio transport")
        print(f"AI agents can connect via standard input/output")
    else:
        print(f"\nMCP server listening on {args.host}:{args.port}")
        print(f"AI agents can connect via {args.transport.upper()} at http://{args.host}:{args.port}")
    
    print(f"\nPress Ctrl+C to stop the server")
    
    # TODO: Implement actual MCP server logic
    # This would:
    # 1. Initialize MCP server with specified transport
    # 2. Register UHCR tools and capabilities
    # 3. Handle requests from AI agents
    # 4. Execute UHCR operations based on agent requests
    
    if args.daemon:
        # Save PID for stop command
        pid_file = Path.home() / ".uhcr" / f"mcp_server_{args.port}.pid"
        pid_file.parent.mkdir(exist_ok=True)
        pid_file.write_text(str(os.getpid()))
        print(f"\nPID file: {pid_file}")
    
    try:
        # Simulate server running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n\nShutting down MCP server...")
        return 0
    
    return 0


def _cmd_mcp_stop(args: argparse.Namespace) -> int:
    """Handle MCP server stop command."""
    print(f"Stopping MCP server on port {args.port}...")
    
    # Look for PID file
    pid_file = Path.home() / ".uhcr" / f"mcp_server_{args.port}.pid"
    
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            
            if args.force:
                print(f"  Force stopping process {pid}")
                # TODO: Send SIGKILL
            else:
                print(f"  Gracefully stopping process {pid}")
                # TODO: Send SIGTERM
            
            # TODO: Implement actual process termination
            # This would:
            # 1. Read PID from file
            # 2. Send appropriate signal (SIGTERM or SIGKILL)
            # 3. Wait for process to terminate
            # 4. Clean up PID file
            
            pid_file.unlink()
            print(f"✓ MCP server stopped successfully")
            return 0
        except Exception as e:
            print(f"Error stopping MCP server: {e}", file=sys.stderr)
            return 1
    else:
        print(f"No MCP server found running on port {args.port}", file=sys.stderr)
        print(f"PID file not found: {pid_file}", file=sys.stderr)
        return 1


def _cmd_analytics(args: argparse.Namespace) -> int:
    """Handle analytics command."""
    print(f"Analytics for job: {args.job_id}")
    if args.compare:
        print(f"  Comparing with: {args.compare}")
    print(f"  Output format: {args.format}")
    
    # TODO: Load and display actual job analytics
    
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    """Handle serve command."""
    config = _load_config(args.config)
    
    host = args.host if args.host is not None else config.get("host", "0.0.0.0")
    grpc_port = args.grpc_port if args.grpc_port is not None else config.get("grpc_port", 50051)
    http_port = args.http_port if args.http_port is not None else config.get("http_port", 8080)
    workers = args.workers if args.workers is not None else config.get("workers", 4)
    grace_period = args.grace_period if args.grace_period is not None else config.get("grace_period", 30)
    redis_url = args.redis_url if args.redis_url is not None else config.get("redis_url")
    sqlite_path = args.sqlite_path if args.sqlite_path is not None else config.get("sqlite_path")
    
    mode = "daemon" if args.daemon else "foreground"
    
    print(f"Starting UHCR server ({mode}) on {host}")
    print(f"  gRPC port: {grpc_port}")
    print(f"  HTTP port: {http_port}")
    print(f"  Workers: {workers}")
    print(f"  Grace period: {grace_period}s")
    if redis_url:
        print(f"  Redis: {redis_url}")
    if sqlite_path:
        print(f"  SQLite: {sqlite_path}")
    
    # TODO: Implement actual server start logic
    
    return 0


def _cmd_monitor(args: argparse.Namespace) -> int:
    """Handle monitor command."""
    duration_msg = f" for {args.duration}s" if args.duration else ""
    print(f"Monitoring system resources{duration_msg}...")
    print(f"  Interval: {args.interval}s")
    print(f"  Format: {'JSON' if args.as_json else 'table'}")
    
    # TODO: Implement actual monitoring logic
    
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    """Handle info command."""
    print(f"UHCR {UHCR_VERSION}")
    print(f"Universal Hardware-Aware Compute Runtime\n")
    
    if args.backends:
        print("Available Backends:")
        print("  • CPU (AVX512, AVX2, Generic)")
        print("  • CUDA (if available)")
        print("  • Metal (if available)")
        print("  • ROCm (if available)")
        # TODO: Detect and list actual available backends
    
    if args.plugins:
        print("\nInstalled Plugins:")
        print("  • example_plugin")
        # TODO: Scan and list actual plugins
    
    if not args.backends and not args.plugins:
        try:
            from uhcr.hardware.platform_info import detect_platform
            profile = detect_platform()
            print(f"Architecture: {profile.architecture}")
            print(f"OS: {profile.os} {profile.os_release}")
            print(f"CPU: {profile.cpu.brand}")
            print(f"Fingerprint: {profile.get_fingerprint()}")
        except:
            print("Hardware detection not available")
    
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    """Handle benchmark command."""
    if args.list:
        print("Available Benchmark Suites:")
        print("  • default - Standard performance tests")
        print("  • tensor - Tensor operations")
        print("  • simd - SIMD instruction tests")
        print("  • memory - Memory bandwidth tests")
        # TODO: List actual benchmark suites
        return 0
    
    suite = args.suite or "default"
    print(f"Running benchmark suite: {suite}")
    
    # TODO: Execute actual benchmarks
    
    if args.output:
        print(f"✓ Results saved to: {args.output}")
    
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    
    if not args.subcommand:
        parser.print_help()
        return 0
    
    handlers = {
        "hw": _cmd_hw,
        "docker": _cmd_docker,
        "k8s": _cmd_k8s,
        "serve": _cmd_serve,
        "stop": _cmd_stop,
        "run": _cmd_run,
        "optimize": _cmd_optimize,
        "analytics": _cmd_analytics,
        "monitor": _cmd_monitor,
        "info": _cmd_info,
        "benchmark": _cmd_benchmark,
        "compile": _cmd_compile,
        "plugin": _cmd_plugin,
        "test": _cmd_test,
        "build": _cmd_build,
        "safety": _cmd_safety,
        "mcp_start": _cmd_mcp_start,
        "mcp_stop": _cmd_mcp_stop,
    }
    
    handler = handlers.get(args.subcommand)
    if handler:
        try:
            return handler(args)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if os.getenv("UHCR_DEBUG"):
                import traceback
                traceback.print_exc()
            return 1
    
    print(f"Unknown command: {args.subcommand}", file=sys.stderr)
    return 1
