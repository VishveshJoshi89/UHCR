import uhcr
from uhcr.plugins.base import Plugin
from uhcr.compiler.ir import Type
from uhcr.compiler.ir_builder import IRBuilder
from uhcr.runtime.memory_manager import AlignedBuffer

class CPUAVX2Plugin(Plugin):
    @property
    def name(self): return "cpu_avx2"
    @property
    def version(self): return "1.0.0"

    def initialize(self, runtime):
        # Pre-compile AVX2 vector add via UHCR IR
        b = IRBuilder(); b.new_module()
        f = b.new_function("avx2_vadd", [Type.PTR, Type.PTR, Type.PTR, Type.I32, Type.PTR], Type.VOID)
        en = f.create_block("en"); lc = f.create_block("lc")
        lb = f.create_block("lb"); ex = f.create_block("ex")
        b.set_block(en); b.store(0, f.arguments[4], 0); b.jmp(lc)
        b.set_block(lc)
        idx = b.load(f.arguments[4], 0, Type.I32)
        b.br(b.cmp("lt", idx, f.arguments[3]), lb, ex)
        b.set_block(lb)
        b.vstore(b.vadd(b.vload(f.arguments[0], idx, Type.V8F32), b.vload(f.arguments[1], idx, Type.V8F32)), f.arguments[2], idx)
        b.store(b.add(idx, 8), f.arguments[4], 0); b.jmp(lc)
        b.set_block(ex); b.ret()
        self._vadd = runtime.compile(f)

        @uhcr.jit(eager=True)
        def _loop(n): return n + 1
        self._jit_loop = _loop

        @uhcr.jit(eager=True)
        def _ops(a, b): return (a * b) + (a - b)
        self._jit_ops = _ops

    def bench_string(self, s1, s2, n):
        return "".join([s1 + s2 for _ in range(n)])

    def bench_loops(self, n):
        return [self._jit_loop(i) for i in range(n)]

    def bench_lists(self, n):
        from uhcr.runtime.list_runtime import create_list
        lst = create_list('i32', n)
        for i in range(n): lst.append(i)
        return lst

    def bench_arrays(self, x, y, out):
        with AlignedBuffer(4, alignment=64) as idx_buf:
            self._vadd(x.address, y.address, out.address, x.size, idx_buf.address)

    def bench_matmul(self, A, B):
        return A.matmul(B)

    def bench_ops(self, n):
        return [self._jit_ops(i, 2) for i in range(n)]
