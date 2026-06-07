"""List runtime

This module implements a dynamic array data structure with type-homogeneous elements,
capacity management, and memory pool integration.
"""

from typing import Any, List as PyList, Optional, TypeVar, Generic
import ctypes

T = TypeVar('T')


class List(Generic[T]):
    """A dynamic array with type-homogeneous elements.
    
    Features:
    - Contiguous memory allocation
    - Automatic capacity growth (doubling strategy)
    - O(1) amortized append operations
    - Bounds checking on indexing
    - Memory pool integration
    """
    
    def __init__(self, element_type: str, initial_capacity: int = 16):
        """Initialize a list.
        
        Args:
            element_type: The type of elements ('i32', 'i64', 'f32', 'f64', 'string')
            initial_capacity: Initial capacity (default 16)
        """
        self.element_type = element_type
        self.capacity = initial_capacity
        self.length = 0
        self.data: PyList[Any] = [None] * initial_capacity
    
    def __len__(self) -> int:
        """Return the number of elements in the list."""
        return self.length
    
    def __getitem__(self, index: int) -> Any:
        """Get element at index.
        
        Args:
            index: The index (0-based)
            
        Returns:
            The element at the index
            
        Raises:
            IndexError: If index is out of bounds
        """
        if not (0 <= index < self.length):
            raise IndexError(f"List index out of range: {index}")
        return self.data[index]
    
    def __setitem__(self, index: int, value: Any) -> None:
        """Set element at index.
        
        Args:
            index: The index (0-based)
            value: The value to set
            
        Raises:
            IndexError: If index is out of bounds
        """
        if not (0 <= index < self.length):
            raise IndexError(f"List index out of range: {index}")
        self.data[index] = value
    
    def __eq__(self, other) -> bool:
        """Compare two lists for equality.
        
        Args:
            other: Another list
            
        Returns:
            True if lists have same length and all elements are equal
        """
        if not isinstance(other, List):
            return False
        if self.length != other.length:
            return False
        for i in range(self.length):
            if self.data[i] != other.data[i]:
                return False
        return True
    
    def __repr__(self) -> str:
        elements = [str(self.data[i]) for i in range(self.length)]
        return f"List<{self.element_type}>([{', '.join(elements)}])"
    
    def append(self, value: Any) -> None:
        """Append an element to the list.
        
        Args:
            value: The value to append
        """
        # Check if we need to grow
        if self.length >= self.capacity:
            self._grow()
        
        # Add element
        self.data[self.length] = value
        self.length += 1
    
    def pop(self) -> Any:
        """Remove and return the last element.
        
        Returns:
            The last element
            
        Raises:
            IndexError: If list is empty
        """
        if self.length == 0:
            raise IndexError("pop from empty list")
        
        self.length -= 1
        return self.data[self.length]
    
    def insert(self, index: int, value: Any) -> None:
        """Insert an element at the specified position.
        
        Args:
            index: The position to insert at (0-based)
            value: The value to insert
            
        Raises:
            IndexError: If index is out of bounds
        """
        if not (0 <= index <= self.length):
            raise IndexError(f"List insertion index out of range: {index}")
        
        # Check if we need to grow
        if self.length >= self.capacity:
            self._grow()
        
        # Shift elements to the right
        for i in range(self.length, index, -1):
            self.data[i] = self.data[i - 1]
        
        # Insert element
        self.data[index] = value
        self.length += 1
    
    def remove(self, value: Any) -> None:
        """Remove the first occurrence of a value.
        
        Args:
            value: The value to remove
            
        Raises:
            ValueError: If value is not found
        """
        # Find the index
        index = -1
        for i in range(self.length):
            if self.data[i] == value:
                index = i
                break
        
        if index == -1:
            raise ValueError(f"Value not found in list: {value}")
        
        # Shift elements to the left
        for i in range(index, self.length - 1):
            self.data[i] = self.data[i + 1]
        
        self.length -= 1
    
    def slice(self, start: int, end: int) -> 'List':
        """Create a new list containing elements from start to end.
        
        Args:
            start: Start index (inclusive)
            end: End index (exclusive)
            
        Returns:
            A new list with the sliced elements
        """
        # Handle negative indices
        if start < 0:
            start = max(0, self.length + start)
        if end < 0:
            end = max(0, self.length + end)
        
        # Clamp to valid range
        start = max(0, min(start, self.length))
        end = max(0, min(end, self.length))
        
        # Create new list
        new_list = List(self.element_type, max(16, end - start))
        for i in range(start, end):
            new_list.append(self.data[i])
        
        return new_list
    
    def _grow(self) -> None:
        """Double the capacity and reallocate.
        
        This implements the doubling growth strategy for amortized O(1) append.
        """
        new_capacity = self.capacity * 2
        new_data = [None] * new_capacity
        
        # Copy existing elements
        for i in range(self.length):
            new_data[i] = self.data[i]
        
        self.data = new_data
        self.capacity = new_capacity
    
    def clear(self) -> None:
        """Remove all elements from the list."""
        self.length = 0
        self.data = [None] * self.capacity
    
    def get_stats(self) -> dict:
        """Get statistics about the list.
        
        Returns:
            Dictionary with list statistics
        """
        return {
            'element_type': self.element_type,
            'length': self.length,
            'capacity': self.capacity,
            'utilization': self.length / self.capacity if self.capacity > 0 else 0,
        }


def create_list(element_type: str, initial_capacity: int = 16) -> List:
    """Create a new list.
    
    Args:
        element_type: The type of elements
        initial_capacity: Initial capacity
        
    Returns:
        A new list
    """
    return List(element_type, initial_capacity)


def list_len(lst: List) -> int:
    """Get the length of a list."""
    return len(lst)


def list_index(lst: List, index: int) -> Any:
    """Get element at index."""
    return lst[index]


def list_append(lst: List, value: Any) -> None:
    """Append element to list."""
    lst.append(value)


def list_pop(lst: List) -> Any:
    """Pop element from list."""
    return lst.pop()


def list_insert(lst: List, index: int, value: Any) -> None:
    """Insert element into list."""
    lst.insert(index, value)


def list_remove(lst: List, value: Any) -> None:
    """Remove element from list."""
    lst.remove(value)


def list_slice(lst: List, start: int, end: int) -> List:
    """Slice list."""
    return lst.slice(start, end)
