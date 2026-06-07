"""Tests for the string interning pool."""

import pytest
from uhcr.runtime.string_pool import StringPool, intern_string, release_string, get_global_pool


class TestStringPool:
    """Test cases for StringPool class."""
    
    def test_intern_creates_string(self):
        """Test that interning creates a new string."""
        pool = StringPool()
        s = pool.intern("hello")
        assert s.content == "hello"
        assert len(s) == 5
        assert s.ref_count == 1
    
    def test_intern_deduplicates(self):
        """Test that identical strings are deduplicated."""
        pool = StringPool()
        s1 = pool.intern("hello")
        s2 = pool.intern("hello")
        assert s1 is s2  # Same object
        assert s1.ref_count == 2
    
    def test_intern_different_strings(self):
        """Test that different strings are not deduplicated."""
        pool = StringPool()
        s1 = pool.intern("hello")
        s2 = pool.intern("world")
        assert s1 is not s2
        assert s1.content == "hello"
        assert s2.content == "world"
    
    def test_reference_counting(self):
        """Test reference counting."""
        pool = StringPool()
        s1 = pool.intern("test")
        assert s1.ref_count == 1
        
        s2 = pool.intern("test")
        assert s1.ref_count == 2
        assert s1 is s2
        
        pool.release(s1)
        assert s1.ref_count == 1
        
        pool.release(s2)
        assert s1.ref_count == 0
    
    def test_garbage_collection(self):
        """Test garbage collection removes unreferenced strings."""
        pool = StringPool()
        s1 = pool.intern("keep")
        s2 = pool.intern("remove")
        
        assert len(pool._pool) == 2
        
        pool.release(s2)
        removed = pool.garbage_collect()
        
        assert removed == 1
        assert len(pool._pool) == 1
        assert "keep" in pool._pool
        assert "remove" not in pool._pool
    
    def test_string_indexing(self):
        """Test character indexing."""
        pool = StringPool()
        s = pool.intern("hello")
        assert s[0] == "h"
        assert s[1] == "e"
        assert s[4] == "o"
    
    def test_string_indexing_out_of_bounds(self):
        """Test that out of bounds indexing raises IndexError."""
        pool = StringPool()
        s = pool.intern("hi")
        with pytest.raises(IndexError):
            _ = s[10]
    
    def test_utf8_validation(self):
        """Test UTF-8 validation."""
        pool = StringPool()
        
        # Valid UTF-8
        s = pool.intern("hello")
        assert s.content == "hello"
        
        # Valid UTF-8 with unicode
        s = pool.intern("café")
        assert s.content == "café"
        assert len(s) == 4
    
    def test_invalid_utf8(self):
        """Test that invalid UTF-8 raises ValueError."""
        pool = StringPool()
        
        # Invalid UTF-8 sequence
        with pytest.raises(ValueError):
            pool.intern("\udcff")  # Lone surrogate
    
    def test_string_equality(self):
        """Test string equality comparison."""
        pool = StringPool()
        s1 = pool.intern("hello")
        s2 = pool.intern("hello")
        s3 = pool.intern("world")
        
        assert s1 == s2
        assert s1 == "hello"
        assert s1 != s3
        assert s1 != "world"
    
    def test_string_hash(self):
        """Test string hashing."""
        pool = StringPool()
        s1 = pool.intern("hello")
        s2 = pool.intern("hello")
        
        # Same content should have same hash
        assert hash(s1) == hash(s2)
        assert s1.get_hash() == s2.get_hash()
    
    def test_pool_stats(self):
        """Test pool statistics."""
        pool = StringPool()
        pool.intern("hello")
        pool.intern("world")
        pool.intern("hello")  # Duplicate
        
        stats = pool.get_stats()
        assert stats['total_strings'] == 2
        assert stats['total_characters'] == 10  # 5 + 5
        assert stats['total_references'] == 3  # 2 + 1
    
    def test_global_pool(self):
        """Test global pool functions."""
        # Clear any existing global pool
        import uhcr.runtime.string_pool as sp
        sp._global_pool = None
        
        s1 = intern_string("global")
        s2 = intern_string("global")
        
        assert s1 is s2
        assert s1.ref_count == 2
        
        release_string(s1)
        assert s1.ref_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
