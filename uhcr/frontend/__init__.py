"""UHCR Frontend — Python-to-IR compilation via decorators.

Usage:
    import uhcr
    from uhcr.frontend import jit

    @jit
    def vector_add(a, b, out, n):
        for i in range(n):
            out[i] = a[i] + b[i]
"""

from uhcr.frontend.decorator import jit

__all__ = ["jit"]
