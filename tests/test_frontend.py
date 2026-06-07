"""Tests for the @jit frontend decorator."""
import pytest
import uhcr
from uhcr.frontend import jit


class TestJitDecorator:
    def test_basic_add(self):
        @jit(eager=True)
        def add(a, b):
            return a + b

        # First call triggers compilation
        result = add(10, 32)
        assert result == 42

    def test_multiply(self):
        @jit(eager=True)
        def mul(x, y):
            return x * y

        assert mul(7, 6) == 42

    def test_complex_expression(self):
        @jit(eager=True)
        def expr(a, b):
            return (a + b) * 2

        assert expr(10, 11) == 42

    def test_subtraction(self):
        @jit(eager=True)
        def sub(a, b):
            return a - b

        assert sub(100, 58) == 42

    def test_caching(self):
        @jit(eager=True)
        def cached_add(a, b):
            return a + b

        # First call compiles
        cached_add(1, 2)
        assert cached_add.is_compiled

        # Subsequent calls use cache
        assert cached_add(20, 22) == 42

    def test_invalidate(self):
        @jit(eager=True)
        def inv_test(a, b):
            return a + b

        inv_test(1, 2)
        assert inv_test.is_compiled
        inv_test.invalidate()
        assert not inv_test.is_compiled

    def test_python_fallback(self):
        """Non-compilable functions should fall back to Python."""
        @jit(eager=True)
        def string_fn(s):
            return s.upper()

        # Should work via Python fallback
        assert string_fn("hello") == "HELLO"

    def test_uhcr_jit_shortcut(self):
        """Test the uhcr.jit shortcut."""
        @uhcr.jit
        def shortcut_add(a, b):
            return a + b

        # Needs 3 calls to trigger compilation (non-eager)
        shortcut_add(1, 2)
        shortcut_add(1, 2)
        result = shortcut_add(1, 2)
        assert result == 3

    def test_original_function_accessible(self):
        @jit(eager=True)
        def original(a, b):
            return a + b

        assert original.python_function(10, 32) == 42
