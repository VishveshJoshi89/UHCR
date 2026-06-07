"""Example plugin entry point demonstrating the UHCR plugin API."""

from uhcr.plugins.base import Plugin


class ExamplePlugin(Plugin):
    """A minimal example plugin that registers a custom kernel."""

    @property
    def name(self) -> str:
        return "example-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def initialize(self, runtime) -> None:
        """Register a custom kernel on load."""
        self.register_kernel("example_relu", self._relu_kernel)
        print(f"[ExamplePlugin] Initialized v{self.version}")

    def shutdown(self) -> None:
        print("[ExamplePlugin] Shutdown")

    def _relu_kernel(self, x):
        """Simple ReLU: max(0, x) for each element."""
        return [max(0.0, v) for v in x]
