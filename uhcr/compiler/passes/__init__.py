"""IR Optimization Passes for UHCR.

This module provides a pipeline of optimization passes that transform
UHCR IR functions to produce more efficient code before backend compilation.

Available passes:
- constant_fold: Evaluate constant expressions at compile time
- dead_code_eliminate: Remove instructions whose results are never used
- strength_reduce: Replace expensive ops with cheaper equivalents
- common_subexpression_eliminate: Reuse previously computed values
"""

from uhcr.compiler.passes.pipeline import OptimizationPipeline, run_default_passes
from uhcr.compiler.passes.constant_folding import ConstantFoldingPass
from uhcr.compiler.passes.dead_code import DeadCodeEliminationPass
from uhcr.compiler.passes.strength_reduction import StrengthReductionPass
from uhcr.compiler.passes.cse import CommonSubexpressionEliminationPass

__all__ = [
    "OptimizationPipeline",
    "run_default_passes",
    "ConstantFoldingPass",
    "DeadCodeEliminationPass",
    "StrengthReductionPass",
    "CommonSubexpressionEliminationPass",
]
