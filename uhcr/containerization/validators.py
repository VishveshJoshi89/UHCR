"""Input validators for containerization options."""

import os
import re

# Valid characters for Docker image names: lowercase alphanumeric, hyphens, periods, slashes, underscores
_IMAGE_NAME_PATTERN = re.compile(r"^[a-z0-9._/\-]+$")

# Valid characters for Kubernetes namespaces: lowercase alphanumeric and hyphens
_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9\-]+$")

# Characters valid in a derived image name (after prefix): lowercase alphanumeric, hyphens, periods
_DERIVED_VALID_CHARS = re.compile(r"[^a-z0-9.\-]")

_MAX_IMAGE_NAME_LENGTH = 128
_MAX_NAMESPACE_LENGTH = 63
_MIN_REPLICAS = 1
_MAX_REPLICAS = 1024


def validate_image_name(name: str) -> tuple[bool, str]:
    """Validates Docker image name. Returns (is_valid, error_message).

    Valid names contain only lowercase alphanumeric characters, hyphens,
    periods, forward slashes, and underscores. Max 128 chars, non-empty.
    """
    if not name:
        return (False, "Invalid image name: must not be empty")
    if len(name) > _MAX_IMAGE_NAME_LENGTH:
        return (
            False,
            "Invalid image name: must be lowercase alphanumeric with hyphens, "
            "periods, slashes, underscores (max 128 chars)",
        )
    if not _IMAGE_NAME_PATTERN.match(name):
        return (
            False,
            "Invalid image name: must be lowercase alphanumeric with hyphens, "
            "periods, slashes, underscores (max 128 chars)",
        )
    return (True, "")


def validate_namespace(ns: str) -> tuple[bool, str]:
    """Validates Kubernetes namespace. Returns (is_valid, error_message).

    Valid namespaces contain only lowercase alphanumeric characters and hyphens.
    Max 63 chars, non-empty.
    """
    if not ns:
        return (False, "Invalid namespace: must not be empty")
    if len(ns) > _MAX_NAMESPACE_LENGTH:
        return (
            False,
            "Invalid namespace: must be lowercase alphanumeric with hyphens (max 63 chars)",
        )
    if not _NAMESPACE_PATTERN.match(ns):
        return (
            False,
            "Invalid namespace: must be lowercase alphanumeric with hyphens (max 63 chars)",
        )
    return (True, "")


def validate_replicas(n: int) -> tuple[bool, str]:
    """Validates replica count (1-1024). Returns (is_valid, error_message)."""
    if not isinstance(n, int) or isinstance(n, bool):
        return (False, "Invalid replicas: must be an integer between 1 and 1024")
    if n < _MIN_REPLICAS or n > _MAX_REPLICAS:
        return (False, "Invalid replicas: must be an integer between 1 and 1024")
    return (True, "")


def derive_image_name(script_path: str) -> str:
    """Derives a Docker image name from a script filename.

    Extracts the filename without extension, converts to lowercase,
    replaces invalid chars (anything not a-z, 0-9, -, .) with '-',
    and prefixes with 'uhcr-'. The result is truncated to 128 chars
    and always passes validate_image_name.
    """
    # Extract filename without extension
    basename = os.path.basename(script_path)
    name_without_ext = os.path.splitext(basename)[0]

    # Convert to lowercase
    name_lower = name_without_ext.lower()

    # Replace invalid characters with hyphens
    sanitized = _DERIVED_VALID_CHARS.sub("-", name_lower)

    # Prefix with 'uhcr-'
    result = f"uhcr-{sanitized}"

    # Truncate to max length
    if len(result) > _MAX_IMAGE_NAME_LENGTH:
        result = result[:_MAX_IMAGE_NAME_LENGTH]

    return result
