"""String interning pool for UHCR.

This module implements an efficient string interning pool that deduplicates
identical strings and manages their memory using reference counting.
"""

import hashlib
from typing import Dict, Optional, Tuple
from threading import Lock


class InternedString:
    """Represents an interned string with reference counting."""
    
    def __init__(self, content: str, string_id: int):
        """Initialize an interned string.
        
        Args:
            content: The UTF-8 string content
            string_id: Unique identifier for this string in the pool
        """
        # Validate UTF-8 encoding
        try:
            self.content = content.encode('utf-8').decode('utf-8')
        except UnicodeDecodeError as e:
            raise ValueError(f"Invalid UTF-8 encoding: {e}")
        
        self.string_id = string_id
        self.ref_count = 1
        self._hash = None  # Lazy hash computation
    
    def __len__(self) -> int:
        """Return the number of characters in the string."""
        return len(self.content)
    
    def __getitem__(self, index: int) -> str:
        """Get character at index."""
        if not (0 <= index < len(self.content)):
            raise IndexError(f"String index out of range: {index}")
        return self.content[index]
    
    def __eq__(self, other) -> bool:
        """Compare with another string."""
        if isinstance(other, InternedString):
            return self.content == other.content
        if isinstance(other, str):
            return self.content == other
        return False
    
    def __hash__(self) -> int:
        """Compute hash lazily."""
        if self._hash is None:
            self._hash = hash(self.content)
        return self._hash
    
    def __repr__(self) -> str:
        return f"InternedString(id={self.string_id}, len={len(self.content)}, refs={self.ref_count})"
    
    def increment_ref(self) -> None:
        """Increment reference count."""
        self.ref_count += 1
    
    def decrement_ref(self) -> int:
        """Decrement reference count and return new count."""
        self.ref_count -= 1
        return self.ref_count
    
    def get_hash(self) -> int:
        """Get the hash value of this string."""
        return hash(self.content)


class StringPool:
    """Global string interning pool for deduplicating identical strings.
    
    The pool maintains a hash table mapping string content to InternedString objects.
    Reference counting is used to track active references and enable garbage collection.
    """
    
    def __init__(self):
        """Initialize the string pool."""
        self._pool: Dict[str, InternedString] = {}
        self._next_id = 0
        self._lock = Lock()
        self._gc_threshold = 1000  # Trigger GC after this many strings
    
    def intern(self, content: str) -> InternedString:
        """Intern a string, returning the canonical InternedString object.
        
        If the string already exists in the pool, returns the existing object
        and increments its reference count. Otherwise, creates a new InternedString.
        
        Args:
            content: The string content to intern
            
        Returns:
            The InternedString object for this content
            
        Raises:
            ValueError: If the string is not valid UTF-8
        """
        with self._lock:
            # Validate UTF-8 encoding
            try:
                normalized = content.encode('utf-8').decode('utf-8')
            except UnicodeDecodeError as e:
                raise ValueError(f"Invalid UTF-8 encoding: {e}")
            
            # Check if already in pool
            if normalized in self._pool:
                interned = self._pool[normalized]
                interned.increment_ref()
                return interned
            
            # Create new interned string
            interned = InternedString(normalized, self._next_id)
            self._next_id += 1
            self._pool[normalized] = interned
            
            # Trigger GC if pool is getting large
            if len(self._pool) >= self._gc_threshold:
                self._garbage_collect()
            
            return interned
    
    def release(self, interned: InternedString) -> None:
        """Release a reference to an interned string.
        
        Decrements the reference count. If the count reaches zero,
        the string may be removed from the pool during garbage collection.
        
        Args:
            interned: The InternedString to release
        """
        with self._lock:
            ref_count = interned.decrement_ref()
            if ref_count < 0:
                raise RuntimeError(f"Reference count underflow for string {interned.string_id}")
    
    def _garbage_collect(self) -> None:
        """Remove unreferenced strings from the pool.
        
        This is called periodically when the pool reaches a size threshold.
        Must be called with the lock held.
        """
        # Find all strings with zero references
        unreferenced = [content for content, interned in self._pool.items() 
                       if interned.ref_count == 0]
        
        # Remove them from the pool
        for content in unreferenced:
            del self._pool[content]
    
    def garbage_collect(self) -> int:
        """Manually trigger garbage collection.
        
        Returns:
            The number of strings removed from the pool
        """
        with self._lock:
            before = len(self._pool)
            self._garbage_collect()
            after = len(self._pool)
            return before - after
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the string pool.
        
        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            total_strings = len(self._pool)
            total_chars = sum(len(s.content) for s in self._pool.values())
            total_refs = sum(s.ref_count for s in self._pool.values())
            unreferenced = sum(1 for s in self._pool.values() if s.ref_count == 0)
            
            return {
                'total_strings': total_strings,
                'total_characters': total_chars,
                'total_references': total_refs,
                'unreferenced_strings': unreferenced,
                'next_id': self._next_id,
            }
    
    def clear(self) -> None:
        """Clear all strings from the pool.
        
        Warning: This should only be called when no strings are in use.
        """
        with self._lock:
            self._pool.clear()
            self._next_id = 0


# Global string pool instance
_global_pool: Optional[StringPool] = None


def get_global_pool() -> StringPool:
    """Get or create the global string pool instance."""
    global _global_pool
    if _global_pool is None:
        _global_pool = StringPool()
    return _global_pool


def intern_string(content: str) -> InternedString:
    """Convenience function to intern a string using the global pool."""
    return get_global_pool().intern(content)


def release_string(interned: InternedString) -> None:
    """Convenience function to release a string using the global pool."""
    get_global_pool().release(interned)
