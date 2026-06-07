"""Tests for list type system."""

import pytest
from uhcr.compiler.ir import Type, ListType, Opcode


class TestListType:
    """Test list type representation."""
    
    def test_list_type_creation(self):
        """Test creating list types."""
        list_i32 = ListType(Type.I32)
        assert list_i32.element_type == Type.I32
        assert str(list_i32) == "list<i32>"
    
    def test_list_type_equality(self):
        """Test list type equality."""
        list_i32_a = ListType(Type.I32)
        list_i32_b = ListType(Type.I32)
        list_i64 = ListType(Type.I64)
        
        assert list_i32_a == list_i32_b
        assert list_i32_a != list_i64
    
    def test_list_type_hash(self):
        """Test list type hashing."""
        list_i32_a = ListType(Type.I32)
        list_i32_b = ListType(Type.I32)
        
        # Should be hashable and have same hash
        assert hash(list_i32_a) == hash(list_i32_b)
        
        # Should work in sets and dicts
        s = {list_i32_a, list_i32_b}
        assert len(s) == 1
    
    def test_list_type_from_element_type(self):
        """Test getting list type from element type."""
        list_type = ListType.from_element_type(Type.I32)
        assert list_type == Type.LIST_I32
        
        list_type = ListType.from_element_type(Type.F64)
        assert list_type == Type.LIST_F64
        
        list_type = ListType.from_element_type(Type.STRING)
        assert list_type == Type.LIST_STRING
    
    def test_list_type_get_element_type(self):
        """Test getting element type from list type."""
        elem_type = ListType.get_element_type(Type.LIST_I32)
        assert elem_type == Type.I32
        
        elem_type = ListType.get_element_type(Type.LIST_STRING)
        assert elem_type == Type.STRING
    
    def test_list_type_is_list_type(self):
        """Test checking if a type is a list type."""
        assert ListType.is_list_type(Type.LIST_I32)
        assert ListType.is_list_type(Type.LIST_I64)
        assert ListType.is_list_type(Type.LIST_F32)
        assert ListType.is_list_type(Type.LIST_F64)
        assert ListType.is_list_type(Type.LIST_STRING)
        
        assert not ListType.is_list_type(Type.I32)
        assert not ListType.is_list_type(Type.STRING)
        assert not ListType.is_list_type(Type.PTR)
    
    def test_list_type_invalid_element_type(self):
        """Test that invalid element types are rejected."""
        with pytest.raises(ValueError):
            ListType(Type.PTR)
        
        with pytest.raises(ValueError):
            ListType(Type.VOID)
        
        with pytest.raises(ValueError):
            ListType(Type.V4F32)
    
    def test_list_type_invalid_conversion(self):
        """Test that invalid conversions raise errors."""
        with pytest.raises(ValueError):
            ListType.from_element_type(Type.PTR)
        
        with pytest.raises(ValueError):
            ListType.get_element_type(Type.I32)


class TestListOpcodes:
    """Test list operation opcodes."""
    
    def test_list_opcodes_exist(self):
        """Test that list opcodes are defined."""
        assert hasattr(Opcode, 'LISTLEN')
        assert hasattr(Opcode, 'LISTINDEX')
        assert hasattr(Opcode, 'LISTSLICE')
        assert hasattr(Opcode, 'LISTAPPEND')
        assert hasattr(Opcode, 'LISTPOP')
        assert hasattr(Opcode, 'LISTINSERT')
        assert hasattr(Opcode, 'LISTREMOVE')
    
    def test_list_opcode_values(self):
        """Test list opcode values."""
        assert Opcode.LISTLEN.value == "listlen"
        assert Opcode.LISTINDEX.value == "listindex"
        assert Opcode.LISTSLICE.value == "listslice"
        assert Opcode.LISTAPPEND.value == "listappend"
        assert Opcode.LISTPOP.value == "listpop"
        assert Opcode.LISTINSERT.value == "listinsert"
        assert Opcode.LISTREMOVE.value == "listremove"


class TestListTypeEnum:
    """Test list type enum values."""
    
    def test_list_type_enum_values(self):
        """Test that list type enum values are correct."""
        assert Type.LIST_I32.value == "list<i32>"
        assert Type.LIST_I64.value == "list<i64>"
        assert Type.LIST_F32.value == "list<f32>"
        assert Type.LIST_F64.value == "list<f64>"
        assert Type.LIST_STRING.value == "list<string>"
    
    def test_list_type_enum_string_representation(self):
        """Test string representation of list type enums."""
        assert str(Type.LIST_I32) == "list<i32>"
        assert str(Type.LIST_STRING) == "list<string>"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
