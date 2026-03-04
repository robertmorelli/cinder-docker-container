"""
Pass: param_cast_container_passthrough

Covers pass-through static container types (Array/Dict/List/Set/Tuple) using cast-based reprojection.

Transform shape:
before:
  def first(xs: Array[int64]) -> int64: ...
after:
  def first(_xs) -> int64:
      xs: Array[int64] = cast(Array[int64], _xs)
      ...
"""

from ast import AnnAssign, FunctionDef, Load, Name, Store
from copy import deepcopy
from itertools import chain

from .context import PassContext
from .util import fresh_hidden_name


PASS_NAME = "param_cast_container_passthrough"
POLICY = "cast"


def apply(
    fn: FunctionDef,
    pass_state: dict[str, bool],
    used_names: set[str],
    conversion_stmts: list[AnnAssign],
    ctx: PassContext,
) -> bool:
    # Specialized cast pass for static container passthrough bin.
    changed = False
    for a in chain(fn.args.posonlyargs, fn.args.args, fn.args.kwonlyargs):
        annotation = a.annotation
        if annotation is None:
            continue
        if a.arg in ("self", "cls"):
            continue
        # This pass still uses cast policy, but only for its specific pass-name bin.
        if ctx.annotation_policy(annotation) != POLICY:
            continue
        pass_name = ctx.pass_name_for_annotation("param", annotation)
        if pass_name != PASS_NAME:
            continue
        if not pass_state[pass_name]:
            continue
        # Signature detype + boundary reprojection statement.
        old_name = a.arg
        hidden_name = fresh_hidden_name(old_name, used_names)
        a.arg = hidden_name
        annotation_copy = deepcopy(annotation)
        conversion_stmts.append(
            AnnAssign(
                target=Name(id=old_name, ctx=Store()),
                annotation=annotation_copy,
                value=ctx.wrap_cast_or_construct(annotation_copy, Name(id=hidden_name, ctx=Load())),
                simple=1,
            )
        )
        # Remove source type annotation from signature.
        a.annotation = None
        changed = True
    return changed
