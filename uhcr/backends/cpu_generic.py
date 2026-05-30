import ctypes
from typing import Callable, Any, Dict, List, Union
from uhcr.backends.backend_base import Backend, register_backend
from uhcr.compiler.ir import Type, Opcode, Value, Constant, Argument, Instruction, BasicBlock, Function
from uhcr.compiler.x86_64.codegen import X86_64CodeGenerator
from uhcr.compiler.x86_64.executable_memory import ExecutableMemory
from uhcr.hardware.platform_info import HardwareProfile

class CPUGenericBackend(Backend):
    """Generic CPU execution path using scalar x86-64 compilation or Python interpreter fallback."""
    @property
    def name(self) -> str:
        return "cpu_generic"

    @property
    def priority(self) -> int:
        return 1

    def supports(self, profile: HardwareProfile) -> bool:
        # Always supported on any hardware as a baseline fallback
        return True

    def compile(self, func: Function) -> Callable:
        # Check if the function uses vector operations or high-level intrinsics
        has_vectors = False
        has_intrinsics = False
        for block in func.blocks:
            for inst in block.instructions:
                if inst.type in (Type.V4F32, Type.V8F32) or inst.opcode in (
                    Opcode.VLOAD, Opcode.VSTORE, Opcode.VADD, Opcode.VSUB, Opcode.VMUL, Opcode.VDIV, Opcode.VFMADD
                ):
                    has_vectors = True
                    break
                if inst.opcode in (Opcode.MATMUL, Opcode.RELU):
                    has_intrinsics = True
        
        # If it's a scalar function (no vectors, no intrinsics) and we are on x86_64, compile to native
        import platform
        if not has_vectors and not has_intrinsics and platform.machine() in ["AMD64", "x86_64"]:
            try:
                codegen = X86_64CodeGenerator(func)
                code_bytes = codegen.compile()
                mem = ExecutableMemory(len(code_bytes))
                mem.write(code_bytes)
                
                # Deduce ctypes arg types
                arg_types = []
                for arg in func.arguments:
                    if arg.type == Type.PTR:
                        arg_types.append(ctypes.c_void_p)
                    elif arg.type == Type.I32:
                        arg_types.append(ctypes.c_int32)
                    elif arg.type == Type.I64:
                        arg_types.append(ctypes.c_int64)
                    elif arg.type == Type.F32:
                        arg_types.append(ctypes.c_float)
                    elif arg.type == Type.F64:
                        arg_types.append(ctypes.c_double)
                
                ret_type = None
                if func.return_type == Type.I32:
                    ret_type = ctypes.c_int32
                elif func.return_type == Type.I64:
                    ret_type = ctypes.c_int64
                elif func.return_type == Type.F32:
                    ret_type = ctypes.c_float
                elif func.return_type == Type.F64:
                    ret_type = ctypes.c_double
                
                proto = ctypes.WINFUNCTYPE(ret_type, *arg_types) if platform.system() == "Windows" else ctypes.CFUNCTYPE(ret_type, *arg_types)
                native_fn = mem.get_function(proto)
                
                # Keep mem alive by binding it to the returned wrapper
                def native_wrapper(*args):
                    resolved = [arg.address if hasattr(arg, "address") else arg for arg in args]
                    return native_fn(*resolved)
                native_wrapper._mem_ref = mem
                return native_wrapper
            except Exception:
                # Fallback to interpreter if native compilation fails
                pass
                
        # Fallback path: Pure Python IR Interpreter
        return self._make_interpreter(func)

    def _make_interpreter(self, func: Function) -> Callable:
        def interpreter_fn(*args):
            # Map argument names to values
            env: Dict[Union[Instruction, Argument], Any] = {}
            for arg, val in zip(func.arguments, args):
                env[arg] = val

            # Basic block execution
            block_map = {b.label: b for b in func.blocks}
            current_block = func.blocks[0]
            
            while True:
                idx = 0
                while idx < len(current_block.instructions):
                    inst = current_block.instructions[idx]
                    opcode = inst.opcode
                    
                    def resolve(val):
                        if isinstance(val, (Instruction, Argument)):
                            v = env[val]
                            if hasattr(v, "address"):
                                return v.address
                            return v
                        elif isinstance(val, Constant):
                            return val.value
                        return val

                    if opcode in (Opcode.ADD, Opcode.FADD):
                        env[inst] = resolve(inst.args[0]) + resolve(inst.args[1])
                    elif opcode in (Opcode.SUB, Opcode.FSUB):
                        env[inst] = resolve(inst.args[0]) - resolve(inst.args[1])
                    elif opcode in (Opcode.MUL, Opcode.FMUL):
                        env[inst] = resolve(inst.args[0]) * resolve(inst.args[1])
                    elif opcode in (Opcode.DIV, Opcode.FDIV):
                        env[inst] = resolve(inst.args[0]) / resolve(inst.args[1])
                        
                    elif opcode == Opcode.LOAD:
                        # args: [ptr, offset]
                        ptr = resolve(inst.args[0])
                        offset = resolve(inst.args[1])
                        
                        # ptr can be a ctypes pointer or a python list/array
                        if isinstance(ptr, ctypes.c_void_p) or isinstance(ptr, int):
                            ptr_val = ptr.value if isinstance(ptr, ctypes.c_void_p) else ptr
                            element_type = ctypes.c_float if inst.type == Type.F32 else ctypes.c_int32
                            val = element_type.from_address(ptr_val + offset * ctypes.sizeof(element_type)).value
                            env[inst] = val
                        else:
                            # Python list/array fallback
                            env[inst] = ptr[offset]
                            
                    elif opcode == Opcode.STORE:
                        # args: [val, ptr, offset]
                        val = resolve(inst.args[0])
                        ptr = resolve(inst.args[1])
                        offset = resolve(inst.args[2])
                        
                        if isinstance(ptr, ctypes.c_void_p) or isinstance(ptr, int):
                            ptr_val = ptr.value if isinstance(ptr, ctypes.c_void_p) else ptr
                            val_type = inst.args[0].type
                            element_type = ctypes.c_float if val_type == Type.F32 else ctypes.c_int32
                            element_type.from_address(ptr_val + offset * ctypes.sizeof(element_type)).value = val
                        else:
                            ptr[offset] = val
                            
                    elif opcode == Opcode.VLOAD:
                        ptr = resolve(inst.args[0])
                        offset = resolve(inst.args[1])
                        
                        vector_len = 8 if inst.type == Type.V8F32 else 4
                        if isinstance(ptr, ctypes.c_void_p) or isinstance(ptr, int):
                            ptr_val = ptr.value if isinstance(ptr, ctypes.c_void_p) else ptr
                            arr_type = ctypes.c_float * vector_len
                            val = list(arr_type.from_address(ptr_val + offset * 4))
                            env[inst] = val
                        else:
                            env[inst] = list(ptr[offset : offset + vector_len])
                            
                    elif opcode == Opcode.VSTORE:
                        val = resolve(inst.args[0])
                        ptr = resolve(inst.args[1])
                        offset = resolve(inst.args[2])
                        
                        vector_len = len(val)
                        if isinstance(ptr, ctypes.c_void_p) or isinstance(ptr, int):
                            ptr_val = ptr.value if isinstance(ptr, ctypes.c_void_p) else ptr
                            arr_type = ctypes.c_float * vector_len
                            target = arr_type.from_address(ptr_val + offset * 4)
                            for i in range(vector_len):
                                target[i] = val[i]
                        else:
                            for i in range(vector_len):
                                ptr[offset + i] = val[i]
                                
                    elif opcode == Opcode.VADD:
                        v1 = resolve(inst.args[0])
                        v2 = resolve(inst.args[1])
                        env[inst] = [x + y for x, y in zip(v1, v2)]
                    elif opcode == Opcode.VSUB:
                        v1 = resolve(inst.args[0])
                        v2 = resolve(inst.args[1])
                        env[inst] = [x - y for x, y in zip(v1, v2)]
                    elif opcode == Opcode.VMUL:
                        v1 = resolve(inst.args[0])
                        v2 = resolve(inst.args[1])
                        env[inst] = [x * y for x, y in zip(v1, v2)]
                    elif opcode == Opcode.VDIV:
                        v1 = resolve(inst.args[0])
                        v2 = resolve(inst.args[1])
                        env[inst] = [x / y for x, y in zip(v1, v2)]
                    elif opcode == Opcode.VFMADD:
                        vacc = resolve(inst.args[0])
                        v1 = resolve(inst.args[1])
                        v2 = resolve(inst.args[2])
                        env[inst] = [acc + x * y for acc, x, y in zip(vacc, v1, v2)]
                        
                    elif opcode == Opcode.CMP:
                        cond = resolve(inst.args[0])
                        v1 = resolve(inst.args[1])
                        v2 = resolve(inst.args[2])
                        if cond == "lt":
                            res = v1 < v2
                        elif cond == "le":
                            res = v1 <= v2
                        elif cond == "gt":
                            res = v1 > v2
                        elif cond == "ge":
                            res = v1 >= v2
                        elif cond == "eq":
                            res = v1 == v2
                        elif cond == "ne":
                            res = v1 != v2
                        env[inst] = res
                        
                    elif opcode == Opcode.BR:
                        cond_val = resolve(inst.args[0])
                        true_lbl = inst.args[1].value
                        false_lbl = inst.args[2].value
                        current_block = block_map[true_lbl] if cond_val else block_map[false_lbl]
                        break # Break inner instruction loop, jump to new block
                        
                    elif opcode == Opcode.JMP:
                        current_block = block_map[inst.args[0].value]
                        break

                    elif opcode == Opcode.MATMUL:
                        # High-level matmul: args are [ptr_A, ptr_B, ptr_C]
                        # The function also receives M, N, K as arguments 3, 4, 5
                        ptr_a = resolve(inst.args[0])
                        ptr_b = resolve(inst.args[1])
                        ptr_c = resolve(inst.args[2])
                        # Get M, N, K from function arguments (indices 3, 4, 5)
                        M_val = env[func.arguments[3]]
                        N_val = env[func.arguments[4]]
                        K_val = env[func.arguments[5]]
                        
                        ptr_a_val = ptr_a.value if isinstance(ptr_a, ctypes.c_void_p) else ptr_a
                        ptr_b_val = ptr_b.value if isinstance(ptr_b, ctypes.c_void_p) else ptr_b
                        ptr_c_val = ptr_c.value if isinstance(ptr_c, ctypes.c_void_p) else ptr_c
                        
                        float_size = ctypes.sizeof(ctypes.c_float)
                        for i in range(M_val):
                            for j in range(N_val):
                                acc = 0.0
                                for k in range(K_val):
                                    a_val = ctypes.c_float.from_address(ptr_a_val + (i * K_val + k) * float_size).value
                                    b_val = ctypes.c_float.from_address(ptr_b_val + (k * N_val + j) * float_size).value
                                    acc += a_val * b_val
                                ctypes.c_float.from_address(ptr_c_val + (i * N_val + j) * float_size).value = acc
                        
                    elif opcode == Opcode.RET:
                        if inst.args:
                            return resolve(inst.args[0])
                        return None
                    
                    idx += 1
                    
        return interpreter_fn

register_backend(CPUGenericBackend())
