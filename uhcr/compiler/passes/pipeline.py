"""Optimization pipeline — chains passes together and runs them on IR functions."""

from abc import ABC, abstractmethod
from typing import List, Optional

from uhcr.compiler.ir import Function


class Pass(ABC):
    """Abstract base class for an IR optimization pass."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable pass name."""
        ...

    @abstractmethod
    def run(self, func: Function) -> Function:
        """Run this pass on a function, returning the (possibly modified) function.

        Passes may mutate the function in-place and return it, or return a new Function.
        """
        ...

    @property
    def stats(self) -> dict:
        """Optional statistics about what the pass did (e.g., instructions removed)."""
        return {}


class OptimizationPipeline:
    """Chains multiple optimization passes and runs them in sequence.

    Example:
        pipeline = OptimizationPipeline()
        pipeline.add(ConstantFoldingPass())
        pipeline.add(DeadCodeEliminationPass())
        optimized_func = pipeline.run(func)
    """

    def __init__(self):
        self._passes: List[Pass] = []
        self._stats: List[dict] = []

    def add(self, pass_: Pass) -> "OptimizationPipeline":
        """Add a pass to the pipeline. Returns self for chaining."""
        self._passes.append(pass_)
        return self

    def run(self, func: Function, max_iterations: int = 3) -> Function:
        """Run all passes on the function.

        Args:
            func: The IR function to optimize.
            max_iterations: Maximum number of full pipeline iterations (for fixed-point).

        Returns:
            The optimized function.
        """
        self._stats.clear()
        
        # Safety check before optimization
        try:
            from uhcr.native import get_safety_monitor, SafetyStatus
            monitor = get_safety_monitor()
            if monitor and monitor.is_enabled():
                # Start operation with timeout
                status = monitor.start_operation(30000)  # 30 second timeout for optimization
                if status != SafetyStatus.OK:
                    raise RuntimeError(f"Cannot start optimization: {monitor.get_last_error()}")
        except ImportError:
            pass

        for iteration in range(max_iterations):
            changed = False
            for pass_ in self._passes:
                # Count instructions before
                before_count = sum(len(b.instructions) for b in func.blocks)
                func = pass_.run(func)
                after_count = sum(len(b.instructions) for b in func.blocks)

                if before_count != after_count:
                    changed = True

                self._stats.append({
                    "pass": pass_.name,
                    "iteration": iteration,
                    "before": before_count,
                    "after": after_count,
                })

            # Fixed-point: stop if no pass changed anything
            if not changed:
                break
            
            # Check for timeout during optimization
            try:
                from uhcr.native import get_safety_monitor
                monitor = get_safety_monitor()
                if monitor and monitor.is_enabled():
                    if monitor.check_timeout():
                        raise RuntimeError("Optimization timeout exceeded")
            except ImportError:
                pass
        
        # End operation timer
        try:
            from uhcr.native import get_safety_monitor
            monitor = get_safety_monitor()
            if monitor and monitor.is_enabled():
                monitor.end_operation()
        except ImportError:
            pass

        return func

    @property
    def stats(self) -> List[dict]:
        """Returns statistics from the last run."""
        return list(self._stats)

    def __repr__(self) -> str:
        names = [p.name for p in self._passes]
        return f"OptimizationPipeline([{', '.join(names)}])"


def run_default_passes(func: Function) -> Function:
    """Run the default optimization pipeline on a function.

    Default order:
    1. Constant folding (evaluate compile-time constants)
    2. Strength reduction (replace expensive ops)
    3. Dead code elimination (remove unused instructions)
    4. Common subexpression elimination (reuse computed values)
    5. Dead code elimination again (clean up after CSE)
    """
    from uhcr.compiler.passes.constant_folding import ConstantFoldingPass
    from uhcr.compiler.passes.dead_code import DeadCodeEliminationPass
    from uhcr.compiler.passes.strength_reduction import StrengthReductionPass
    from uhcr.compiler.passes.cse import CommonSubexpressionEliminationPass

    pipeline = OptimizationPipeline()
    pipeline.add(ConstantFoldingPass())
    pipeline.add(StrengthReductionPass())
    pipeline.add(DeadCodeEliminationPass())
    pipeline.add(CommonSubexpressionEliminationPass())
    pipeline.add(DeadCodeEliminationPass())

    return pipeline.run(func)
