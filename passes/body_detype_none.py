"""
Pass: body_detype_none

None-annotated body AnnAssigns are treated as passthrough (no detyping needed).
This stub exists to satisfy the TYPE_BIN_SPECS pass-name symmetry.
"""

from ast import expr

from .context import PassContext


PASS_NAME = "body_detype_none"
POLICY = "detype"


def apply(annotation: expr, value: expr | None, pass_state: dict[str, bool], ctx: PassContext) -> expr | None:
    return None
