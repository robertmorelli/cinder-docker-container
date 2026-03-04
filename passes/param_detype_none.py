"""
Pass: param_detype_none

None-annotated parameters are treated as passthrough (no detyping needed).
This stub exists to satisfy the TYPE_BIN_SPECS pass-name symmetry.
"""

from ast import AnnAssign, FunctionDef

from .context import PassContext


PASS_NAME = "param_detype_none"
POLICY = "detype"


def apply(
    fn: FunctionDef,
    pass_state: dict[str, bool],
    used_names: set[str],
    conversion_stmts: list[AnnAssign],
    ctx: PassContext,
) -> bool:
    return False
