from enum import Enum, auto
from typing import List, Dict, Union, Any, Optional

class Type(Enum):
    I32 = "i32"
    I64 = "i64"
    F32 = "f32"
    F64 = "f64"
    V4F32 = "v4f32"  # 128-bit SIMD vector (4x float)
    V2F64 = "v2f64"  # 128-bit SIMD vector (2x double)
    V8F32 = "v8f32"  # 256-bit SIMD vector (8x float)
    V4I32 = "v4i32"  # 128-bit SIMD vector (4x int32)
    V8I16 = "v8i16"  # 128-bit SIMD vector (8x int16)
    V16I8 = "v16i8"  # 128-bit SIMD vector (16x int8)
    PTR = "ptr"      # Memory pointer
    STRING = "string"  # Immutable UTF-8 string type
    
    # List types (parameterized)
    LIST_I32 = "list<i32>"    # List of i32
    LIST_I64 = "list<i64>"    # List of i64
    LIST_F32 = "list<f32>"    # List of f32
    LIST_F64 = "list<f64>"    # List of f64
    LIST_STRING = "list<string>"  # List of strings
    
    VOID = "void"

    def __str__(self):
        return self.value


class ListType:
    """Represents a parameterized list type LIST<T>."""
    
    def __init__(self, element_type: Type):
        """Initialize a list type with an element type.
        
        Args:
            element_type: The type of elements in the list
        """
        if element_type not in (Type.I32, Type.I64, Type.F32, Type.F64, Type.STRING):
            raise ValueError(f"Unsupported list element type: {element_type}")
        self.element_type = element_type
    
    def __str__(self) -> str:
        return f"list<{self.element_type}>"
    
    def __repr__(self) -> str:
        return f"ListType({self.element_type})"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, ListType):
            return self.element_type == other.element_type
        return False
    
    def __hash__(self) -> int:
        return hash(self.element_type)
    
    @staticmethod
    def from_element_type(element_type: Type) -> Type:
        """Get the corresponding Type enum for a list of the given element type.
        
        Args:
            element_type: The element type
            
        Returns:
            The corresponding LIST type
        """
        mapping = {
            Type.I32: Type.LIST_I32,
            Type.I64: Type.LIST_I64,
            Type.F32: Type.LIST_F32,
            Type.F64: Type.LIST_F64,
            Type.STRING: Type.LIST_STRING,
        }
        if element_type not in mapping:
            raise ValueError(f"Cannot create list of type {element_type}")
        return mapping[element_type]
    
    @staticmethod
    def get_element_type(list_type: Type) -> Type:
        """Get the element type from a list type.
        
        Args:
            list_type: A LIST type
            
        Returns:
            The element type
        """
        mapping = {
            Type.LIST_I32: Type.I32,
            Type.LIST_I64: Type.I64,
            Type.LIST_F32: Type.F32,
            Type.LIST_F64: Type.F64,
            Type.LIST_STRING: Type.STRING,
        }
        if list_type not in mapping:
            raise ValueError(f"Not a list type: {list_type}")
        return mapping[list_type]
    
    @staticmethod
    def is_list_type(type_: Type) -> bool:
        """Check if a type is a list type.
        
        Args:
            type_: The type to check
            
        Returns:
            True if the type is a list type
        """
        return type_ in (Type.LIST_I32, Type.LIST_I64, Type.LIST_F32, Type.LIST_F64, Type.LIST_STRING)

class Opcode(Enum):
    # Scalar integer
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    
    # Scalar float
    FADD = "fadd"
    FSUB = "fsub"
    FMUL = "fmul"
    FDIV = "fdiv"
    
    # Memory
    LOAD = "load"
    STORE = "store"
    
    # Vector
    VLOAD = "vload"   # Load vector from memory
    VSTORE = "vstore" # Store vector to memory
    VADD = "vadd"     # Vector add
    VSUB = "vsub"     # Vector subtract
    VMUL = "vmul"     # Vector multiply
    VDIV = "vdiv"     # Vector divide
    VFMADD = "vfmadd" # Vector Fused Multiply-Add (acc = acc + a * b)
    
    # String operations
    STRLEN = "strlen"     # Get string length
    STRCAT = "strcat"     # Concatenate strings
    STRINDEX = "strindex" # Index into string
    STRSLICE = "strslice" # Slice string
    STREQ = "streq"       # String equality
    STRHASH = "strhash"   # Compute string hash
    
    # Control flow
    CMP = "cmp"       # Compare scalar values (sets flags)
    JMP = "jmp"       # Unconditional jump
    BR = "br"         # Conditional branch (based on compare result)
    RET = "ret"       # Return from function
    
    # Loop control
    LOOP = "loop"     # Loop header (condition check)
    BREAK = "break"   # Break from loop
    CONTINUE = "continue"  # Continue to next iteration
    PHI = "phi"       # Phi node (merge values from multiple predecessors)
    
    # List operations
    LISTLEN = "listlen"         # Get list length
    LISTINDEX = "listindex"     # Index into list
    LISTSLICE = "listslice"     # Slice list
    LISTAPPEND = "listappend"   # Append to list
    LISTPOP = "listpop"         # Pop from list
    LISTINSERT = "listinsert"   # Insert into list
    LISTREMOVE = "listremove"   # Remove from list
    
    # Intrinsics / High-level
    MATMUL = "matmul"
    RELU = "relu"

class Value:
    """Base class for any value in the compiler pipeline."""
    def __init__(self, type_: Type):
        self.type = type_

class Constant(Value):
    """A constant literal value (integer, float)."""
    def __init__(self, type_: Type, value: Any):
        super().__init__(type_)
        self.value = value

    def __repr__(self):
        return f"{self.type} {self.value}"

class Argument(Value):
    """A function argument."""
    def __init__(self, type_: Type, name: str):
        super().__init__(type_)
        self.name = name

    def __repr__(self):
        return f"%{self.name}"

class Instruction(Value):
    """An IR instruction representing an operation."""
    def __init__(self, opcode: Opcode, type_: Type, args: List[Value], id_: int = -1):
        super().__init__(type_)
        self.opcode = opcode
        self.args = args
        self.id = id_  # Will be assigned by BasicBlock/Function

    @property
    def name(self) -> str:
        return f"%{self.id}"

    def __repr__(self):
        args_str = ", ".join([str(arg.name) if isinstance(arg, (Instruction, Argument)) else str(arg) for arg in self.args])
        if self.type == Type.VOID:
            return f"{self.opcode.value} {args_str}"
        return f"{self.name} = {self.opcode.value} {self.type} {args_str}"

class BasicBlock:
    """A basic block is a straight-line sequence of instructions with no branches except at the end."""
    def __init__(self, label: str):
        self.label = label
        self.instructions: List[Instruction] = []
        self.parent: Optional['Function'] = None

    def add_instruction(self, inst: Instruction):
        inst.parent_block = self
        self.instructions.append(inst)
        if self.parent:
            self.parent._assign_id(inst)

    def __repr__(self):
        lines = [f"{self.label}:"]
        for inst in self.instructions:
            lines.append(f"  {inst}")
        return "\n".join(lines)

class Function:
    """Represents a function containing basic blocks and arguments."""
    def __init__(self, name: str, arg_types: List[Type], return_type: Type):
        self.name = name
        self.return_type = return_type
        self.arguments: List[Argument] = [Argument(t, f"arg{i}") for i, t in enumerate(arg_types)]
        self.blocks: List[BasicBlock] = []
        self._next_inst_id = 0
        
        # Initialize safety monitor for complex function operations
        self._safety_monitor = None
        self._init_safety()
    
    def _init_safety(self):
        """Initialize the hardware safety monitor."""
        try:
            from uhcr.native import get_safety_monitor
            self._safety_monitor = get_safety_monitor()
        except Exception:
            # Safety monitor not available, continue without protection
            pass

    def create_block(self, label: str) -> BasicBlock:
        # Safety check: prevent creating too many blocks during thermal stress
        if self._safety_monitor and self._safety_monitor.is_enabled():
            if self._safety_monitor.is_emergency_stopped():
                raise RuntimeError(
                    "Emergency stop is active. Cannot create new basic blocks. "
                    "System must cool down before resuming operations."
                )
            
            # Warn if creating many blocks (potential complexity issue)
            if len(self.blocks) > 1000:
                cpu_status = self._safety_monitor.check_cpu_temperature()
                if cpu_status != 0:
                    cpu_temp = self._safety_monitor.get_cpu_temperature()
                    raise RuntimeError(
                        f"CPU temperature too high ({cpu_temp}°C) for complex function "
                        f"with {len(self.blocks)} blocks. Simplify function or wait for cooldown."
                    )
        
        block = BasicBlock(label)
        block.parent = self
        self.blocks.append(block)
        return block

    def _assign_id(self, inst: Instruction):
        if inst.id == -1:
            inst.id = self._next_inst_id
            self._next_inst_id += 1

    def validate(self) -> bool:
        """Simple validator for IR consistency with safety checks."""
        # Safety check before validation
        if self._safety_monitor and self._safety_monitor.is_enabled():
            if self._safety_monitor.is_emergency_stopped():
                raise RuntimeError(
                    "Emergency stop is active. Cannot validate function. "
                    "System must cool down before resuming operations."
                )
        
        # Ensure the last block has a terminator (RET or JMP/BR)
        if not self.blocks:
            return False
        for block in self.blocks:
            if not block.instructions:
                return False
            # Check last instruction is a terminator
            last = block.instructions[-1]
            if last.opcode not in (Opcode.RET, Opcode.JMP, Opcode.BR):
                # Return validation warning/error?
                pass
        return True

    def __repr__(self):
        args_str = ", ".join([f"{arg.type} %{arg.name}" for arg in self.arguments])
        header = f"func {self.name}({args_str}) -> {self.return_type} {{"
        blocks_str = "\n\n".join([str(block) for block in self.blocks])
        return f"{header}\n{blocks_str}\n}}"

class Module:
    """A compiler module contains a collection of functions."""
    def __init__(self):
        self.functions: Dict[str, Function] = {}

    def add_function(self, func: Function):
        self.functions[func.name] = func

    def __repr__(self):
        return "\n\n".join([str(func) for func in self.functions.values()])


# Type validation and inference helpers
def is_valid_string_type(type_: Type) -> bool:
    """Check if a type is a valid string type."""
    return type_ == Type.STRING


def infer_string_type(value: Any) -> Optional[Type]:
    """Infer STRING type from a Python string value."""
    if isinstance(value, str):
        return Type.STRING
    return None


def validate_string_opcode_args(opcode: Opcode, args: List[Value]) -> bool:
    """Validate that arguments to string opcodes have correct types."""
    if opcode == Opcode.STRLEN:
        # strlen(string) -> i64
        return len(args) == 1 and args[0].type == Type.STRING
    elif opcode == Opcode.STRCAT:
        # strcat(string, string) -> string
        return len(args) == 2 and all(arg.type == Type.STRING for arg in args)
    elif opcode == Opcode.STRINDEX:
        # strindex(string, i64) -> i32 (character code)
        return len(args) == 2 and args[0].type == Type.STRING and args[1].type == Type.I64
    elif opcode == Opcode.STRSLICE:
        # strslice(string, i64, i64) -> string
        return len(args) == 3 and args[0].type == Type.STRING and args[1].type == Type.I64 and args[2].type == Type.I64
    elif opcode == Opcode.STREQ:
        # streq(string, string) -> i32 (boolean)
        return len(args) == 2 and all(arg.type == Type.STRING for arg in args)
    elif opcode == Opcode.STRHASH:
        # strhash(string) -> i64
        return len(args) == 1 and args[0].type == Type.STRING
    return False
