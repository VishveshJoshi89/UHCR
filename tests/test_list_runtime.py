"""Tests for list runtime."""

import pytest
from uhcr.runtime.list_runtime import List, create_list


class TestListBasics:
    """Test basic list operations."""
    
    def test_list_creation(self):
        """Test creating a list."""
        lst = List("i32")
        assert len(lst) == 0
        assert lst.capacity >= 16
    
    def test_list_append(self):
        """Test appending to a list."""
        lst = List("i32")
        lst.append(1)
        lst.append(2)
        lst.append(3)
        
        assert len(lst) == 3
        assert lst[0] == 1
        assert lst[1] == 2
        assert lst[2] == 3
    
    def test_list_indexing(self):
        """Test list indexing."""
        lst = List("i32")
        lst.append(10)
        lst.append(20)
        lst.append(30)
        
        assert lst[0] == 10
        assert lst[1] == 20
        assert lst[2] == 30
    
    def test_list_indexing_out_of_bounds(self):
        """Test that out of bounds indexing raises IndexError."""
        lst = List("i32")
        lst.append(1)
        
        with pytest.raises(IndexError):
            _ = lst[10]
        
        with pytest.raises(IndexError):
            _ = lst[-1]
    
    def test_list_setitem(self):
        """Test setting list elements."""
        lst = List("i32")
        lst.append(1)
        lst.append(2)
        
        lst[0] = 10
        lst[1] = 20
        
        assert lst[0] == 10
        assert lst[1] == 20
    
    def test_list_pop(self):
        """Test popping from a list."""
        lst = List("i32")
        lst.append(1)
        lst.append(2)
        lst.append(3)
        
        assert lst.pop() == 3
        assert len(lst) == 2
        assert lst.pop() == 2
        assert len(lst) == 1
    
    def test_list_pop_empty(self):
        """Test that popping from empty list raises IndexError."""
        lst = List("i32")
        with pytest.raises(IndexError):
            lst.pop()
    
    def test_list_insert(self):
        """Test inserting into a list."""
        lst = List("i32")
        lst.append(1)
        lst.append(3)
        
        lst.insert(1, 2)
        
        assert len(lst) == 3
        assert lst[0] == 1
        assert lst[1] == 2
        assert lst[2] == 3
    
    def test_list_insert_at_beginning(self):
        """Test inserting at the beginning."""
        lst = List("i32")
        lst.append(2)
        lst.append(3)
        
        lst.insert(0, 1)
        
        assert lst[0] == 1
        assert lst[1] == 2
        assert lst[2] == 3
    
    def test_list_insert_at_end(self):
        """Test inserting at the end."""
        lst = List("i32")
        lst.append(1)
        lst.append(2)
        
        lst.insert(2, 3)
        
        assert lst[0] == 1
        assert lst[1] == 2
        assert lst[2] == 3
    
    def test_list_remove(self):
        """Test removing from a list."""
        lst = List("i32")
        lst.append(1)
        lst.append(2)
        lst.append(3)
        
        lst.remove(2)
        
        assert len(lst) == 2
        assert lst[0] == 1
        assert lst[1] == 3
    
    def test_list_remove_not_found(self):
        """Test that removing non-existent value raises ValueError."""
        lst = List("i32")
        lst.append(1)
        
        with pytest.raises(ValueError):
            lst.remove(10)
    
    def test_list_slice(self):
        """Test slicing a list."""
        lst = List("i32")
        for i in range(10):
            lst.append(i)
        
        sliced = lst.slice(2, 5)
        
        assert len(sliced) == 3
        assert sliced[0] == 2
        assert sliced[1] == 3
        assert sliced[2] == 4
    
    def test_list_slice_negative_indices(self):
        """Test slicing with negative indices."""
        lst = List("i32")
        for i in range(5):
            lst.append(i)
        
        sliced = lst.slice(-3, -1)
        
        assert len(sliced) == 2
        assert sliced[0] == 2
        assert sliced[1] == 3
    
    def test_list_equality(self):
        """Test list equality comparison."""
        lst1 = List("i32")
        lst1.append(1)
        lst1.append(2)
        lst1.append(3)
        
        lst2 = List("i32")
        lst2.append(1)
        lst2.append(2)
        lst2.append(3)
        
        lst3 = List("i32")
        lst3.append(1)
        lst3.append(2)
        
        assert lst1 == lst2
        assert lst1 != lst3
    
    def test_list_clear(self):
        """Test clearing a list."""
        lst = List("i32")
        lst.append(1)
        lst.append(2)
        lst.append(3)
        
        lst.clear()
        
        assert len(lst) == 0
    
    def test_list_capacity_growth(self):
        """Test that list capacity grows when needed."""
        lst = List("i32", initial_capacity=2)
        initial_capacity = lst.capacity
        
        # Add more elements than initial capacity
        for i in range(10):
            lst.append(i)
        
        # Capacity should have grown
        assert lst.capacity > initial_capacity
        assert len(lst) == 10
        
        # All elements should be intact
        for i in range(10):
            assert lst[i] == i
    
    def test_list_stats(self):
        """Test getting list statistics."""
        lst = List("i32", initial_capacity=16)
        lst.append(1)
        lst.append(2)
        
        stats = lst.get_stats()
        
        assert stats['element_type'] == 'i32'
        assert stats['length'] == 2
        assert stats['capacity'] == 16
        assert stats['utilization'] == 2 / 16


class TestListTypes:
    """Test lists with different element types."""
    
    def test_list_f32(self):
        """Test list of f32."""
        lst = List("f32")
        lst.append(1.5)
        lst.append(2.5)
        lst.append(3.5)
        
        assert len(lst) == 3
        assert lst[0] == 1.5
        assert lst[1] == 2.5
        assert lst[2] == 3.5
    
    def test_list_string(self):
        """Test list of strings."""
        lst = List("string")
        lst.append("hello")
        lst.append("world")
        
        assert len(lst) == 2
        assert lst[0] == "hello"
        assert lst[1] == "world"
    
    def test_list_mixed_types(self):
        """Test that lists can store mixed types (Python lists are not type-safe)."""
        lst = List("any")
        lst.append(1)
        lst.append("hello")
        lst.append(3.14)
        
        assert len(lst) == 3
        assert lst[0] == 1
        assert lst[1] == "hello"
        assert lst[2] == 3.14


class TestListHelpers:
    """Test helper functions."""
    
    def test_create_list(self):
        """Test create_list helper."""
        lst = create_list("i32")
        assert isinstance(lst, List)
        assert len(lst) == 0
    
    def test_create_list_with_capacity(self):
        """Test create_list with initial capacity."""
        lst = create_list("i32", 32)
        assert lst.capacity == 32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
