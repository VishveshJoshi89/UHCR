"""Containerization support for UHCR workloads.

Provides Docker and Kubernetes artifact generation for UHCR scripts.
"""

from uhcr.containerization.config import DockerConfig, K8sConfig
from uhcr.containerization.docker_generator import DockerGenerator
from uhcr.containerization.hardware_resources import compute_k8s_resources


def generate_dockerfile(config: DockerConfig) -> str:
    """Generate a Dockerfile for a UHCR workload.

    Args:
        config: Docker configuration specifying script path, image name,
                base image, and compilation mode.

    Returns:
        The generated Dockerfile content as a string.
    """
    generator = DockerGenerator(config)
    return generator.generate()


def generate_k8s_manifest(config: K8sConfig) -> str:
    """Generate a Kubernetes deployment manifest for a UHCR workload.

    Args:
        config: Kubernetes configuration specifying script path, image name,
                namespace, replicas, and resource requests/limits.

    Returns:
        The generated deployment.yaml content as a string.
    """
    from uhcr.containerization.k8s_generator import KubernetesGenerator

    generator = KubernetesGenerator(config)
    return generator.generate()


__all__ = [
    "DockerConfig",
    "K8sConfig",
    "compute_k8s_resources",
    "generate_dockerfile",
    "generate_k8s_manifest",
]
