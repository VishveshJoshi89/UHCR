from typing import List, Union, Any, Optional
from uhcr.compiler.ir import Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function, Module, ListType

class IRBuilder:
    """Builder class providing a fluent API for generating UHCR IR."""
    def __init__(self):
        self.module: Optional[Module] = None
        self.function: Optional[Function] = None
        self.current_block: Optional[BasicBlock] = None

    def new_module(self) -> Module:
        self.module = Module()
        return self.module

    def new_function(self, name: str, arg_types: List[Type], return_type: Type) -> Function:
        assert self.module is not None, "Must create a module before creating a function"
        self.function = Function(name, arg_types, return_type)
        self.module.add_function(self.function)
        return self.function

    def set_block(self, block: BasicBlock):
        self.current_block = block

    def _emit(self, opcode: Opcode, type_: Type, args: List[Value]) -> Instruction:
        assert self.current_block is not None, "Cannot emit instruction: no current basic block set"
        inst = Instruction(opcode, type_, args)
        self.current_block.add_instruction(inst)
        return inst

    def _val(self, val: Union[Value, int, float]) -> Value:
        """Helper to convert Python literals to Constant values, or pass through Value."""
        if isinstance(val, Value):
            return val
        if isinstance(val, int):
            return Constant(Type.I32, val)
        if isinstance(val, float):
            return Constant(Type.F32, val)
        raise TypeError(f"Cannot coerce {val} to an IR Value")

    # Math operations with type inference
    def add(self, a: Union[Value, int, float], b: Union[Value, int, float]) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        # Type inference
        t = va.type
        if t in (Type.F32, Type.F64):
            return self._emit(Opcode.FADD, t, [va, vb])
        return self._emit(Opcode.ADD, t, [va, vb])

    def sub(self, a: Union[Value, int, float], b: Union[Value, int, float]) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        t = va.type
        if t in (Type.F32, Type.F64):
            return self._emit(Opcode.FSUB, t, [va, vb])
        return self._emit(Opcode.SUB, t, [va, vb])

    def mul(self, a: Union[Value, int, float], b: Union[Value, int, float]) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        t = va.type
        if t in (Type.F32, Type.F64):
            return self._emit(Opcode.FMUL, t, [va, vb])
        return self._emit(Opcode.MUL, t, [va, vb])

    def div(self, a: Union[Value, int, float], b: Union[Value, int, float]) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        t = va.type
        if t in (Type.F32, Type.F64):
            return self._emit(Opcode.FDIV, t, [va, vb])
        return self._emit(Opcode.DIV, t, [va, vb])

    # Memory operations
    def load(self, ptr: Value, offset: Union[Value, int] = 0, type_: Type = Type.F32) -> Instruction:
        vptr = self._val(ptr)
        voff = self._val(offset)
        return self._emit(Opcode.LOAD, type_, [vptr, voff])

    def store(self, val: Value, ptr: Value, offset: Union[Value, int] = 0) -> Instruction:
        vval = self._val(val)
        vptr = self._val(ptr)
        voff = self._val(offset)
        return self._emit(Opcode.STORE, Type.VOID, [vval, vptr, voff])

    # Vector memory operations
    def vload(self, ptr: Value, offset: Union[Value, int] = 0, type_: Type = Type.V8F32) -> Instruction:
        vptr = self._val(ptr)
        voff = self._val(offset)
        return self._emit(Opcode.VLOAD, type_, [vptr, voff])

    def vstore(self, val: Value, ptr: Value, offset: Union[Value, int] = 0) -> Instruction:
        vval = self._val(val)
        vptr = self._val(ptr)
        voff = self._val(offset)
        return self._emit(Opcode.VSTORE, Type.VOID, [vval, vptr, voff])

    # Vector operations
    def vadd(self, a: Value, b: Value) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        assert va.type == vb.type and va.type in (Type.V4F32, Type.V8F32)
        return self._emit(Opcode.VADD, va.type, [va, vb])

    def vsub(self, a: Value, b: Value) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        assert va.type == vb.type and va.type in (Type.V4F32, Type.V8F32)
        return self._emit(Opcode.VSUB, va.type, [va, vb])

    def vmul(self, a: Value, b: Value) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        assert va.type == vb.type and va.type in (Type.V4F32, Type.V8F32)
        return self._emit(Opcode.VMUL, va.type, [va, vb])

    def vdiv(self, a: Value, b: Value) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        assert va.type == vb.type and va.type in (Type.V4F32, Type.V8F32)
        return self._emit(Opcode.VDIV, va.type, [va, vb])

    def vfmadd(self, acc: Value, a: Value, b: Value) -> Instruction:
        vacc = self._val(acc)
        va = self._val(a)
        vb = self._val(b)
        assert vacc.type == va.type == vb.type and va.type in (Type.V4F32, Type.V8F32, Type.V2F64)
        return self._emit(Opcode.VFMADD, va.type, [vacc, va, vb])

    # Control flow
    def cmp(self, cond: str, a: Value, b: Value) -> Instruction:
        """Compares values: cond can be 'eq', 'ne', 'lt', 'le', 'gt', 'ge'."""
        va = self._val(a)
        vb = self._val(b)
        return self._emit(Opcode.CMP, Type.I32, [Constant(Type.I32, cond), va, vb])

    def br(self, cond_val: Value, true_block: BasicBlock, false_block: BasicBlock) -> Instruction:
        vcond = self._val(cond_val)
        return self._emit(Opcode.BR, Type.VOID, [vcond, Constant(Type.PTR, true_block.label), Constant(Type.PTR, false_block.label)])

    def jmp(self, block: BasicBlock) -> Instruction:
        return self._emit(Opcode.JMP, Type.VOID, [Constant(Type.PTR, block.label)])

    def ret(self, val: Optional[Value] = None) -> Instruction:
        if val is None:
            return self._emit(Opcode.RET, Type.VOID, [])
        vval = self._val(val)
        return self._emit(Opcode.RET, Type.VOID, [vval])

    # High level tensor instructions
    def matmul(self, a: Value, b: Value, out: Value) -> Instruction:
        va = self._val(a)
        vb = self._val(b)
        vout = self._val(out)
        return self._emit(Opcode.MATMUL, Type.VOID, [va, vb, vout])

    def relu(self, a: Value, out: Value) -> Instruction:
        va = self._val(a)
        vout = self._val(out)
        return self._emit(Opcode.RELU, Type.VOID, [va, vout])

    # String operations
    def strlen(self, s: Value) -> Instruction:
        """Get string length. Returns i64."""
        vs = self._val(s)
        assert vs.type == Type.STRING, f"strlen requires STRING type, got {vs.type}"
        return self._emit(Opcode.STRLEN, Type.I64, [vs])

    def strcat(self, a: Value, b: Value) -> Instruction:
        """Concatenate two strings. Returns STRING."""
        va = self._val(a)
        vb = self._val(b)
        assert va.type == Type.STRING, f"strcat requires STRING type for first arg, got {va.type}"
        assert vb.type == Type.STRING, f"strcat requires STRING type for second arg, got {vb.type}"
        return self._emit(Opcode.STRCAT, Type.STRING, [va, vb])

    def strindex(self, s: Value, index: Value) -> Instruction:
        """Index into string. Returns i32 (character code)."""
        vs = self._val(s)
        vidx = self._val(index)
        assert vs.type == Type.STRING, f"strindex requires STRING type, got {vs.type}"
        # Convert I32 to I64 if needed
        if vidx.type == Type.I32:
            vidx = Constant(Type.I64, vidx.value if isinstance(vidx, Constant) else 0)
        assert vidx.type == Type.I64, f"strindex requires i64 index, got {vidx.type}"
        return self._emit(Opcode.STRINDEX, Type.I32, [vs, vidx])

    def strslice(self, s: Value, start: Value, end: Value) -> Instruction:
        """Slice string. Returns STRING."""
        vs = self._val(s)
        vstart = self._val(start)
        vend = self._val(end)
        assert vs.type == Type.STRING, f"strslice requires STRING type, got {vs.type}"
        # Convert I32 to I64 if needed
        if vstart.type == Type.I32:
            vstart = Constant(Type.I64, vstart.value if isinstance(vstart, Constant) else 0)
        if vend.type == Type.I32:
            vend = Constant(Type.I64, vend.value if isinstance(vend, Constant) else 0)
        assert vstart.type == Type.I64, f"strslice requires i64 start, got {vstart.type}"
        assert vend.type == Type.I64, f"strslice requires i64 end, got {vend.type}"
        return self._emit(Opcode.STRSLICE, Type.STRING, [vs, vstart, vend])

    def streq(self, a: Value, b: Value) -> Instruction:
        """Compare two strings for equality. Returns i32 (boolean)."""
        va = self._val(a)
        vb = self._val(b)
        assert va.type == Type.STRING, f"streq requires STRING type for first arg, got {va.type}"
        assert vb.type == Type.STRING, f"streq requires STRING type for second arg, got {vb.type}"
        return self._emit(Opcode.STREQ, Type.I32, [va, vb])

    def strhash(self, s: Value) -> Instruction:
        """Compute string hash. Returns i64."""
        vs = self._val(s)
        assert vs.type == Type.STRING, f"strhash requires STRING type, got {vs.type}"
        return self._emit(Opcode.STRHASH, Type.I64, [vs])

    # Loop control operations
    def loop(self, cond: Value, body_block: BasicBlock, exit_block: BasicBlock) -> Instruction:
        """Create a loop header with condition check.
        
        Args:
            cond: The loop condition (boolean value)
            body_block: The basic block for the loop body
            exit_block: The basic block to jump to when loop exits
            
        Returns:
            The loop instruction
        """
        vcond = self._val(cond)
        assert vcond.type in (Type.I32, Type.I64), f"loop condition must be integer, got {vcond.type}"
        return self._emit(Opcode.LOOP, Type.VOID, [vcond, Constant(Type.PTR, body_block.label), Constant(Type.PTR, exit_block.label)])

    def break_loop(self, target_block: BasicBlock) -> Instruction:
        """Break from the current loop.
        
        Args:
            target_block: The basic block to jump to (loop exit)
            
        Returns:
            The break instruction
        """
        return self._emit(Opcode.BREAK, Type.VOID, [Constant(Type.PTR, target_block.label)])

    def continue_loop(self, target_block: BasicBlock) -> Instruction:
        """Continue to the next iteration of the loop.
        
        Args:
            target_block: The basic block to jump to (loop header)
            
        Returns:
            The continue instruction
        """
        return self._emit(Opcode.CONTINUE, Type.VOID, [Constant(Type.PTR, target_block.label)])

    def phi(self, incoming_values: List[Value], incoming_blocks: List[BasicBlock], result_type: Type) -> Instruction:
        """Create a phi node to merge values from multiple predecessors.
        
        A phi node is used at the beginning of a basic block to select which value
        to use based on which predecessor block was executed.
        
        Args:
            incoming_values: List of values from each predecessor
            incoming_blocks: List of predecessor basic blocks
            result_type: The type of the result
            
        Returns:
            The phi instruction
        """
        assert len(incoming_values) == len(incoming_blocks), "Must have same number of values and blocks"
        assert len(incoming_values) >= 2, "Phi node must have at least 2 predecessors"
        
        # Create arguments: alternating values and block labels
        args = []
        for val, block in zip(incoming_values, incoming_blocks):
            vval = self._val(val)
            args.append(vval)
            args.append(Constant(Type.PTR, block.label))
        
        return self._emit(Opcode.PHI, result_type, args)

    # List operations
    def listlen(self, lst: Value) -> Instruction:
        """Get list length. Returns i64."""
        vlst = self._val(lst)
        assert ListType.is_list_type(vlst.type), f"listlen requires LIST type, got {vlst.type}"
        return self._emit(Opcode.LISTLEN, Type.I64, [vlst])

    def listindex(self, lst: Value, index: Value) -> Instruction:
        """Index into list. Returns the element type."""
        vlst = self._val(lst)
        vidx = self._val(index)
        assert ListType.is_list_type(vlst.type), f"listindex requires LIST type, got {vlst.type}"
        assert vidx.type in (Type.I32, Type.I64), f"listindex requires integer index, got {vidx.type}"
        
        # Get element type from list type
        elem_type = ListType.get_element_type(vlst.type)
        return self._emit(Opcode.LISTINDEX, elem_type, [vlst, vidx])

    def listslice(self, lst: Value, start: Value, end: Value) -> Instruction:
        """Slice list. Returns a new list of the same type."""
        vlst = self._val(lst)
        vstart = self._val(start)
        vend = self._val(end)
        assert ListType.is_list_type(vlst.type), f"listslice requires LIST type, got {vlst.type}"
        assert vstart.type in (Type.I32, Type.I64), f"listslice requires integer start, got {vstart.type}"
        assert vend.type in (Type.I32, Type.I64), f"listslice requires integer end, got {vend.type}"
        
        return self._emit(Opcode.LISTSLICE, vlst.type, [vlst, vstart, vend])

    def listappend(self, lst: Value, elem: Value) -> Instruction:
        """Append element to list. Returns void."""
        vlst = self._val(lst)
        velem = self._val(elem)
        assert ListType.is_list_type(vlst.type), f"listappend requires LIST type, got {vlst.type}"
        
        # Verify element type matches list element type
        elem_type = ListType.get_element_type(vlst.type)
        assert velem.type == elem_type, f"listappend element type mismatch: expected {elem_type}, got {velem.type}"
        
        return self._emit(Opcode.LISTAPPEND, Type.VOID, [vlst, velem])

    def listpop(self, lst: Value) -> Instruction:
        """Pop from list. Returns the element type."""
        vlst = self._val(lst)
        assert ListType.is_list_type(vlst.type), f"listpop requires LIST type, got {vlst.type}"
        
        # Get element type from list type
        elem_type = ListType.get_element_type(vlst.type)
        return self._emit(Opcode.LISTPOP, elem_type, [vlst])

    def listinsert(self, lst: Value, index: Value, elem: Value) -> Instruction:
        """Insert element into list. Returns void."""
        vlst = self._val(lst)
        vidx = self._val(index)
        velem = self._val(elem)
        assert ListType.is_list_type(vlst.type), f"listinsert requires LIST type, got {vlst.type}"
        assert vidx.type in (Type.I32, Type.I64), f"listinsert requires integer index, got {vidx.type}"
        
        # Verify element type matches list element type
        elem_type = ListType.get_element_type(vlst.type)
        assert velem.type == elem_type, f"listinsert element type mismatch: expected {elem_type}, got {velem.type}"
        
        return self._emit(Opcode.LISTINSERT, Type.VOID, [vlst, vidx, velem])

    def listremove(self, lst: Value, elem: Value) -> Instruction:
        """Remove element from list. Returns void."""
        vlst = self._val(lst)
        velem = self._val(elem)
        assert ListType.is_list_type(vlst.type), f"listremove requires LIST type, got {vlst.type}"
        
        # Verify element type matches list element type
        elem_type = ListType.get_element_type(vlst.type)
        assert velem.type == elem_type, f"listremove element type mismatch: expected {elem_type}, got {velem.type}"
        
        return self._emit(Opcode.LISTREMOVE, Type.VOID, [vlst, velem])
