#!/usr/bin/env python3
"""UHCR CLI - Command-line interface for Universal Hardware-Aware Compute Runtime.

Provides commands for:
- Hardware detection and profiling
- JIT compilation and benchmarking
- Container generation (Docker, Kubernetes)
- Network server management (gRPC, HTTP)
- Safety monitoring and status
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional


def cmd_detect(args) -> int:
    """Detect hardware capabilities."""
    import uhcr
    from uhcr.native import get_safety_monitor
    
    # Safety check before hardware detection
    try:
        monitor = get_safety_monitor()
        if monitor and monitor.is_enabled():
            cpu_status = monitor.check_cpu_temperature()
            if cpu_status != 0:
                print(f"⚠️  Warning: CPU temperature elevated ({monitor.get_cpu_temperature()}°C)")
    except ImportError:
        print("⚠️  Warning: Native safety monitor not available")
    
    profile = uhcr.detect()
    
    if args.format == "json":
        print(profile.to_json())
    elif args.format == "table":
        print(profile.format_table())
    else:
        print(f"OS: {profile.os} {profile.os_release}")
        print(f"Architecture: {profile.architecture}")
        print(f"CPU: {profile.cpu.brand}")
        print(f"Features: {', '.join(profile.cpu.features)}")
        print(f"GPU: {profile.gpu.name}")
    
    return 0


def cmd_safety(args) -> int:
    """Display safety monitor status."""
    try:
        from uhcr.native import get_safety_monitor
        monitor = get_safety_monitor()
        
        if not monitor or not monitor.is_enabled():
            print("❌ Safety monitor: DISABLED")
            print("⚠️  Running without hardware protection!")
            print("\nTo enable:")
            print("  python uhcr/native/build_native.py")
            return 1
        
        print("✓ Safety monitor: ACTIVE")
        print("\n📊 Current Status:")
        print(f"  CPU Temperature: {monitor.get_cpu_temperature()}°C")
        print(f"  GPU Temperature: {monitor.get_gpu_temperature()}°C")
        print(f"  Memory Usage: {monitor.get_memory_usage() / 1024**3:.2f}GB")
        
        if monitor.is_emergency_stopped():
            print(f"\n🚨 EMERGENCY STOP ACTIVE")
            print(f"  Reason: {monitor.get_last_error()}")
            return 2
        
        print("\n✓ All systems operational")
        return 0
        
    except ImportError:
        print("❌ Safety monitor not found")
        print("Build it with: python uhcr/native/build_native.py")
        return 1


def cmd_compile(args) -> int:
    """Compile a Python script with UHCR JIT."""
    script_path = Path(args.script)
    
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}", file=sys.stderr)
        return 1
    
    # Read and execute script
    with open(script_path, 'r') as f:
        code = f.read()
    
    try:
        import uhcr
        namespace = {"uhcr": uhcr}
        exec(code, namespace)
        
        print(f"✓ Compiled {script_path}")
        return 0
    except Exception as e:
        print(f"Error compiling {script_path}: {e}", file=sys.stderr)
        return 1


def cmd_benchmark(args) -> int:
    """Run UHCR benchmarks."""
    try:
        from uhcr.benchmarks.runner import run_benchmarks
        results = run_benchmarks()
        
        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            print("=== UHCR Benchmark Results ===")
            for name, result in results.items():
                print(f"{name}: {result}")
        
        return 0
    except ImportError:
        print("Error: Benchmark module not available", file=sys.stderr)
        return 1


def cmd_docker(args) -> int:
    """Generate Dockerfile for deployment."""
    try:
        from uhcr.contanerization.config import DockerConfig
        from uhcr.contanerization.docker_generator import DockerGenerator
        
        config = DockerConfig(
            script_path=args.script,
            image_name=args.image or "uhcr-app",
            base_image=args.base or "python:3.10-slim",
            is_compiled=args.compiled
        )
        
        generator = DockerGenerator(config)
        output_path = generator.write(args.output or ".")
        
        print(f"✓ Generated Dockerfile: {output_path}")
        return 0
    except Exception as e:
        print(f"Error generating Dockerfile: {e}", file=sys.stderr)
        return 1


def cmd_k8s(args) -> int:
    """Generate Kubernetes deployment manifest."""
    try:
        from uhcr.contanerization.config import K8sConfig
        from uhcr.contanerization.k8s_generator import KubernetesGenerator
        
        config = K8sConfig(
            script_path=args.script,
            image_name=args.image or "uhcr-app:latest",
            namespace=args.namespace or "default",
            replicas=args.replicas or 1,
            cpu_request=args.cpu_request,
            cpu_limit=args.cpu_limit,
            memory_request=args.memory_request,
            memory_limit=args.memory_limit
        )
        
        generator = KubernetesGenerator(config)
        output_path = generator.write(args.output or ".")
        
        print(f"✓ Generated deployment.yaml: {output_path}")
        return 0
    except Exception as e:
        print(f"Error generating K8s manifest: {e}", file=sys.stderr)
        return 1


def cmd_server(args) -> int:
    """Start UHCR network server (HTTP + gRPC)."""
    try:
        import asyncio
        from uhcr.network.server import ProtocolServer
        
        async def run_server():
            server = ProtocolServer(
                host=args.host or "0.0.0.0",
                http_port=args.http_port or 8080,
                grpc_port=args.grpc_port or 50051,
                workers=args.workers or 4
            )
            
            print(f"Starting UHCR server...")
            print(f"  HTTP: {server.host}:{server.http_port}")
            print(f"  gRPC: {server.host}:{server.grpc_port}")
            
            await server.start()
            await server.wait_for_shutdown()
        
        asyncio.run(run_server())
        return 0
        
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        return 0
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="uhcr",
        description="Universal Hardware-Aware Compute Runtime CLI"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect hardware capabilities")
    detect_parser.add_argument(
        "--format", choices=["text", "json", "table"], default="table",
        help="Output format"
    )
    detect_parser.set_defaults(func=cmd_detect)
    
    # safety command
    safety_parser = subparsers.add_parser("safety", help="Check safety monitor status")
    safety_parser.set_defaults(func=cmd_safety)
    
    # compile command
    compile_parser = subparsers.add_parser("compile", help="Compile a Python script")
    compile_parser.add_argument("script", help="Path to Python script")
    compile_parser.set_defaults(func=cmd_compile)
    
    # benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run benchmarks")
    bench_parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format"
    )
    bench_parser.set_defaults(func=cmd_benchmark)
    
    # docker command
    docker_parser = subparsers.add_parser("docker", help="Generate Dockerfile")
    docker_parser.add_argument("script", help="Path to Python script")
    docker_parser.add_argument("--image", help="Docker image name")
    docker_parser.add_argument("--base", help="Base image")
    docker_parser.add_argument("--compiled", action="store_true", help="Use compiled mode")
    docker_parser.add_argument("--output", help="Output directory")
    docker_parser.set_defaults(func=cmd_docker)
    
    # k8s command
    k8s_parser = subparsers.add_parser("k8s", help="Generate Kubernetes manifest")
    k8s_parser.add_argument("script", help="Path to Python script")
    k8s_parser.add_argument("--image", help="Container image name")
    k8s_parser.add_argument("--namespace", help="Kubernetes namespace")
    k8s_parser.add_argument("--replicas", type=int, help="Number of replicas")
    k8s_parser.add_argument("--cpu-request", help="CPU request (e.g., '100m')")
    k8s_parser.add_argument("--cpu-limit", help="CPU limit")
    k8s_parser.add_argument("--memory-request", help="Memory request (e.g., '256Mi')")
    k8s_parser.add_argument("--memory-limit", help="Memory limit")
    k8s_parser.add_argument("--output", help="Output directory")
    k8s_parser.set_defaults(func=cmd_k8s)
    
    # server command
    server_parser = subparsers.add_parser("server", help="Start network server")
    server_parser.add_argument("--host", help="Host to bind to")
    server_parser.add_argument("--http-port", type=int, help="HTTP port")
    server_parser.add_argument("--grpc-port", type=int, help="gRPC port")
    server_parser.add_argument("--workers", type=int, help="Number of workers")
    server_parser.set_defaults(func=cmd_server)
    
    return parser


def main() -> int:
    """Main CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
