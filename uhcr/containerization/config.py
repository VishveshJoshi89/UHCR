"""Configuration dataclasses for containerization generators."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DockerConfig:
    """Configuration for Dockerfile generation."""

    script_path: str
    image_name: str  # Derived or user-specified
    base_image: str  # Default: "python:3.12-slim"
    is_compiled: bool  # True when invoked from `uhcr compile`


@dataclass
class K8sConfig:
    """Configuration for Kubernetes manifest generation."""

    script_path: str
    image_name: str  # Container image reference
    namespace: str  # Default: "default"
    replicas: int  # Default: 1
    cpu_request: Optional[str]  # Kubernetes resource quantity or None
    cpu_limit: Optional[str]  # Kubernetes resource quantity or None
    memory_request: Optional[str]  # Kubernetes resource quantity or None
    memory_limit: Optional[str]  # Kubernetes resource quantity or None
