"""ARM64 target device profiles for mobile, IoT, desktop, and Apple Silicon."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import List

from uhcr.compiler.aarch64.apple_silicon import AppleSiliconInfo


@dataclass
class TargetProfile:
    """Describes the capabilities and constraints of an ARM64 target device.

    Attributes:
        architecture: Always ``"aarch64"`` for this profile type.
        baseline: Minimum ISA baseline, e.g. ``"armv8.0"`` or ``"armv8.2"``.
        features: List of optional ISA extensions available on the target,
            e.g. ``["neon", "fp16", "dotprod", "sve"]``.
        apple_silicon: ``True`` when targeting Apple M-series hardware.
        low_memory_mode: When ``True``, the memory pool is capped at 64 MB,
            suitable for IoT and other resource-constrained devices.
        thermal_constrained: When ``True``, the code generator prefers
            lower-power instruction sequences over peak-throughput ones.
        pic_enabled: When ``True``, the code generator emits
            position-independent code (ADRP+ADD addressing) suitable for
            shared libraries on ARM Linux and Android.
    """

    architecture: str = "aarch64"
    baseline: str = "armv8.0"
    features: List[str] = field(default_factory=list)
    apple_silicon: bool = False
    low_memory_mode: bool = False
    thermal_constrained: bool = False
    pic_enabled: bool = False

    # ------------------------------------------------------------------
    # Instance helpers
    # ------------------------------------------------------------------

    def supports_feature(self, feature: str) -> bool:
        """Return ``True`` if *feature* is present in this profile's feature list.

        The comparison is case-insensitive.

        Args:
            feature: Feature name to query, e.g. ``"neon"``, ``"fp16"``.

        Returns:
            ``True`` if the feature is supported, ``False`` otherwise.

        Example::

            profile = TargetProfile.default()
            assert profile.supports_feature("neon")
            assert not profile.supports_feature("sve2")
        """
        return feature.lower() in (f.lower() for f in self.features)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "TargetProfile":
        """Full-featured desktop/server profile.

        Targets ARMv8.2 baseline with a broad set of NEON and optional
        extensions enabled.  Suitable for server-class ARM hardware such as
        Ampere Altra, AWS Graviton 2/3, or Neoverse N1/N2.

        Returns:
            A :class:`TargetProfile` with ARMv8.2 baseline and all common
            features enabled.
        """
        return cls(
            architecture="aarch64",
            baseline="armv8.2",
            features=["neon", "fp16", "dotprod", "rcpc", "lse", "crypto", "sha2", "aes"],
            apple_silicon=False,
            low_memory_mode=False,
            thermal_constrained=False,
            pic_enabled=False,
        )

    @classmethod
    def mobile_iot(cls) -> "TargetProfile":
        """Mobile / IoT profile for resource-constrained ARM devices.

        Uses the conservative ARMv8.0 baseline so that generated code runs on
        the widest range of ARM Cortex-A and Cortex-M class devices.
        ``low_memory_mode`` is enabled to cap the memory pool at 64 MB, and
        ``thermal_constrained`` is enabled to prefer power-efficient instruction
        sequences.

        Returns:
            A :class:`TargetProfile` suitable for mobile and IoT deployment.
        """
        return cls(
            architecture="aarch64",
            baseline="armv8.0",
            features=["neon"],
            apple_silicon=False,
            low_memory_mode=True,
            thermal_constrained=True,
            pic_enabled=True,
        )

    @classmethod
    def apple_silicon_profile(cls) -> "TargetProfile":
        """Apple M-series (Apple Silicon) profile.

        Enables the full 128-bit NEON pipeline and all extensions available on
        Apple M1 through M4 chips.  ``apple_silicon=True`` activates
        Apple-specific optimisations such as MAP_JIT memory allocation and the
        ``apple-aapcs64`` calling convention.

        Returns:
            A :class:`TargetProfile` optimised for Apple Silicon.
        """
        return cls(
            architecture="aarch64",
            baseline="armv8.5",
            features=[
                "neon",
                "fp16",
                "dotprod",
                "rcpc",
                "lse",
                "crypto",
                "sha2",
                "sha3",
                "aes",
                "bf16",
                "i8mm",
            ],
            apple_silicon=True,
            low_memory_mode=False,
            thermal_constrained=False,
            pic_enabled=False,
        )

    @classmethod
    def detect(cls) -> "TargetProfile":
        """Auto-detect the target profile from the current platform.

        Uses :class:`~uhcr.compiler.aarch64.apple_silicon.AppleSiliconInfo`
        to determine whether the host is Apple Silicon, then returns the
        appropriate pre-built profile.  On non-ARM64 hosts (e.g. x86_64) the
        :meth:`default` profile is returned as a safe cross-compilation
        baseline.

        Returns:
            A :class:`TargetProfile` matching the detected hardware.

        Example::

            profile = TargetProfile.detect()
            if profile.apple_silicon:
                print("Running on Apple Silicon")
        """
        machine = platform.machine().lower()

        # Only attempt Apple Silicon detection on ARM64 hosts.
        if machine in ("arm64", "aarch64"):
            info: AppleSiliconInfo = AppleSiliconInfo.detect()
            if info.is_apple_silicon:
                return cls.apple_silicon_profile()

            # Generic ARM64 host — use the full desktop/server profile.
            return cls.default()

        # Non-ARM64 host (e.g. x86_64 cross-compiling to ARM64).
        # Return the default profile as a safe baseline for cross-compilation.
        return cls.default()
