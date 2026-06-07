"""Tests for the Tensor API and operations."""
import ctypes
import platform
import pytest

import uhcr
from uhcr.compiler.ir import Type


def test_tensor_creation():
    t = uhcr.tensor([[1.0, 2.0], [3.0, 4.0]])
    assert t.shape == (2, 2)
    assert t.dtype == Type.F32


def test_tensor_data_access():
    t = uhcr.tensor([[1.0, 2.0, 3.0]])
    arr = t.buffer.as_ctypes_array(ctypes.c_float)
    assert abs(arr[0] - 1.0) < 0.001
    assert abs(arr[1] - 2.0) < 0.001
    assert abs(arr[2] - 3.0) < 0.001


def test_tensor_address():
    t = uhcr.tensor([[1.0]])
    assert t.address > 0
    # Address should be 64-byte aligned
    assert t.address % 64 == 0


def test_tensor_repr():
    t = uhcr.tensor([[1.0, 2.0]])
    r = repr(t)
    assert "Tensor" in r
    assert "f32" in r
    assert "(1, 2)" in r


def test_tensor_matmul_2x2():
    a = uhcr.tensor([[1.0, 2.0], [3.0, 4.0]])
    b = uhcr.tensor([[5.0, 6.0], [7.0, 8.0]])
    c = a.matmul(b)

    arr = c.buffer.as_ctypes_array(ctypes.c_float)
    expected = [19.0, 22.0, 43.0, 50.0]
    for i, e in enumerate(expected):
        assert abs(arr[i] - e) < 0.1, f"Mismatch at {i}: {arr[i]} vs {e}"


def test_tensor_matmul_3x3():
    a = uhcr.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    b = uhcr.tensor([[9.0, 8.0, 7.0], [6.0, 5.0, 4.0], [3.0, 2.0, 1.0]])
    c = a.matmul(b)

    arr = c.buffer.as_ctypes_array(ctypes.c_float)
    expected = [30.0, 24.0, 18.0, 84.0, 69.0, 54.0, 138.0, 114.0, 90.0]
    for i, e in enumerate(expected):
        assert abs(arr[i] - e) < 0.5, f"Mismatch at {i}: {arr[i]} vs {e}"


def test_tensor_addition():
    x = uhcr.tensor([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]])
    y = uhcr.tensor([[10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]])
    z = x + y

    arr = z.buffer.as_ctypes_array(ctypes.c_float)
    expected = [11.0, 22.0, 33.0, 44.0, 55.0, 66.0, 77.0, 88.0]
    for i, e in enumerate(expected):
        assert abs(arr[i] - e) < 0.01


def test_tensor_matmul_shape_mismatch():
    a = uhcr.tensor([[1.0, 2.0, 3.0]])  # 1x3
    b = uhcr.tensor([[1.0, 2.0]])  # 1x2
    with pytest.raises(AssertionError):
        a.matmul(b)
