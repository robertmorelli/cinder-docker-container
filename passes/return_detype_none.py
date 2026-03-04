"""
Pass: return_detype_none

Erases explicit `-> None` return annotation.

Transform shape:
before:
  def reset() -> None: ...
after:
  def reset(): ...
"""

from ast import FunctionDef

from .context import PassContext
from .decider import is_none_annotation


PASS_NAME = "return_detype_none"
POLICY = "detype"


def apply(fn: FunctionDef, pass_state: dict[str, bool], ctx: PassContext) -> bool:
    # Own only explicit None return annotations (not missing annotations).
    if fn.returns is None or not is_none_annotation(fn.returns):
        return False
    # Respect per-function pass enablement.
    if not pass_state[PASS_NAME]:
        return False
    # Remove the return annotation; None is the implicit default.
    fn.returns = None
    return True
