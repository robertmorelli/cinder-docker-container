"""
Cleanup pass: checkedlist return wraps

Collapses redundant cross-function CheckedList wrapping:
- call site: `CheckedList[T](foo(...))`
- callee body: `return CheckedList[T](expr)`
becomes:
- call site unchanged
- callee body: `return expr`

Safety guard:
- only rewrites top-level functions whose return annotation is already erased/dynamic.
"""

from __future__ import annotations

from ast import AST, Call, FunctionDef, Name, NodeTransformer, NodeVisitor, Return, Subscript, dump as ast_dump, expr
from copy import deepcopy


def _is_none_or_dynamic(annotation: expr | None) -> bool:
    if annotation is None:
        return True
    return isinstance(annotation, Name) and annotation.id == "dynamic"


def _checkedlist_wrap_parts(node: expr) -> tuple[expr, expr] | None:
    if not isinstance(node, Call):
        return None
    if len(node.args) != 1 or len(node.keywords) != 0:
        return None
    func = node.func
    if not isinstance(func, Subscript):
        return None
    if not isinstance(func.value, Name) or func.value.id != "CheckedList":
        return None
    return deepcopy(func), node.args[0]


class _WrappedCallCollector(NodeVisitor):
    def __init__(self):
        self.by_function_name: dict[str, set[str]] = {}

    def visit_Call(self, node: Call):
        outer = _checkedlist_wrap_parts(node)
        if outer is not None:
            checkedlist_annotation, inner = outer
            if isinstance(inner, Call) and isinstance(inner.func, Name):
                self.by_function_name.setdefault(inner.func.id, set()).add(
                    ast_dump(checkedlist_annotation, include_attributes=False)
                )
        self.generic_visit(node)


class _ReturnUnwrapper(NodeTransformer):
    def __init__(self, by_function_name: dict[str, set[str]]):
        self.by_function_name = by_function_name
        self._active_annotations: set[str] | None = None

    def visit_FunctionDef(self, node: FunctionDef):
        previous = self._active_annotations
        if _is_none_or_dynamic(getattr(node, "returns", None)):
            self._active_annotations = self.by_function_name.get(node.name)
        else:
            self._active_annotations = None
        self.generic_visit(node)
        self._active_annotations = previous
        return node

    def visit_Return(self, node: Return):
        if self._active_annotations is None or node.value is None:
            return node
        wrapped = _checkedlist_wrap_parts(node.value)
        if wrapped is None:
            return node
        checkedlist_annotation, inner = wrapped
        key = ast_dump(checkedlist_annotation, include_attributes=False)
        if key not in self._active_annotations:
            return node
        return Return(value=inner)


def cleanup_checkedlist_return_wraps(module: AST) -> AST:
    collector = _WrappedCallCollector()
    collector.visit(module)
    if len(collector.by_function_name) == 0:
        return module
    return _ReturnUnwrapper(collector.by_function_name).visit(module)
