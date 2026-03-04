"""
Pass: body_checkedlist_flow

CheckedList-specific body flow rewrite used with body construct detyping.

Behavior (function-local):
- Erase local `x: CheckedList[T] = v` annotation to `x = v`
- Track `x -> T` provenance
- Reproject element reads:
  - `x[i]` load -> `T(x[i])` for primitives, else `cast(T, x[i])`
  - `x.pop(...)` -> same projection
- Wrap call arguments when local checked list crosses a boundary:
  - `foo(x)` -> `foo(CheckedList[T](x))`
"""

from __future__ import annotations

from ast import (
    Assign,
    AsyncFunctionDef,
    AugAssign,
    Call,
    ClassDef,
    Constant,
    FunctionDef,
    Lambda,
    Load,
    Name,
    NodeTransformer,
    Slice,
    Subscript,
    dump as ast_dump,
    expr,
)
from copy import deepcopy

from .context import PassContext


PASS_NAME = "body_construct_container"


def _is_checkedlist_annotation(annotation: expr | None) -> bool:
    return (
        isinstance(annotation, Subscript)
        and isinstance(annotation.value, Name)
        and annotation.value.id == "CheckedList"
    )


def _checkedlist_element_annotation(annotation: Subscript) -> expr:
    return deepcopy(annotation.slice)


def _make_checkedlist_annotation(element_annotation: expr) -> Subscript:
    return Subscript(value=Name(id="CheckedList", ctx=Load()), slice=deepcopy(element_annotation), ctx=Load())


def _checkedlist_ctor_element(node: expr) -> expr | None:
    if not isinstance(node, Call):
        return None
    if len(node.args) != 1 or len(node.keywords) != 0:
        return None
    if not _is_checkedlist_annotation(node.func):
        return None
    assert isinstance(node.func, Subscript), "CheckedList constructor annotation must be subscript"
    return _checkedlist_element_annotation(node.func)


def _is_same_construct_wrapper(node: expr, annotation: expr) -> bool:
    return (
        isinstance(node, Call)
        and len(node.args) == 1
        and len(node.keywords) == 0
        and ast_dump(node.func, include_attributes=False) == ast_dump(annotation, include_attributes=False)
    )


def apply(fn, pass_state: dict[str, bool], ctx: PassContext) -> bool:
    if not pass_state[PASS_NAME]:
        return False
    return_annotation = deepcopy(getattr(fn, "returns", None))
    return_checkedlist_annotation = return_annotation if _is_checkedlist_annotation(return_annotation) else None

    class _CheckedListFlowRewriter(NodeTransformer):
        def __init__(self):
            self.changed = False
            self.local_elements: dict[str, expr] = {}

        def _iter_bound_names(self, target) -> list[str]:
            if isinstance(target, Name):
                return [target.id]
            if hasattr(target, "elts"):
                out: list[str] = []
                for child in target.elts:
                    out.extend(self._iter_bound_names(child))
                return out
            return []

        def _infer_assigned_element(self, value: expr) -> expr | None:
            tracked = self._tracked_element(value)
            if tracked is not None:
                return deepcopy(tracked)
            return _checkedlist_ctor_element(value)

        def _update_tracking_for_assignment_target(self, target, value_element: expr | None):
            for name in self._iter_bound_names(target):
                if value_element is None:
                    self.local_elements.pop(name, None)
                else:
                    self.local_elements[name] = deepcopy(value_element)

        def _project_element(self, node: expr, element_annotation: expr) -> expr:
            if ctx.annotation_policy(element_annotation) == "box":
                return ctx.coerce_primitive(element_annotation, node)
            return ctx.wrap_cast_or_construct(element_annotation, node)

        def _tracked_element(self, node: expr) -> expr | None:
            if isinstance(node, Name):
                return self.local_elements.get(node.id)
            return None

        def visit_AnnAssign(self, node):
            self.generic_visit(node)
            if not isinstance(node.target, Name):
                return node
            annotation = getattr(node, "annotation", None)
            if not _is_checkedlist_annotation(annotation):
                self.local_elements.pop(node.target.id, None)
                return node
            assert isinstance(annotation, Subscript), "CheckedList annotation must be subscript"
            # Record declared CheckedList element type even for declaration-only locals.
            self.local_elements[node.target.id] = _checkedlist_element_annotation(annotation)
            if node.value is None:
                self.changed = True
                return Assign(targets=[node.target], value=Constant(value=None), type_comment=None)
            self.changed = True
            return Assign(targets=[node.target], value=node.value, type_comment=None)

        def visit_Assign(self, node: Assign):
            self.generic_visit(node)
            value_element = self._infer_assigned_element(node.value)
            for target in node.targets:
                self._update_tracking_for_assignment_target(target, value_element)
            return node

        def visit_AugAssign(self, node: AugAssign):
            self.generic_visit(node)
            # `x += ...` may change runtime shape; clear tracked binding conservatively.
            self._update_tracking_for_assignment_target(node.target, None)
            return node

        def visit_FunctionDef(self, node: FunctionDef):
            # Keep pass local to current function body; nested scopes are rewritten
            # when/if they are detyped directly by orchestration.
            return node

        def visit_AsyncFunctionDef(self, node: AsyncFunctionDef):
            return node

        def visit_ClassDef(self, node: ClassDef):
            return node

        def visit_Lambda(self, node: Lambda):
            return node

        def visit_Subscript(self, node: Subscript):
            self.generic_visit(node)
            if not isinstance(node.ctx, Load):
                return node
            if isinstance(node.slice, Slice):
                # Slice reads return list-like values, not single CheckedList elements.
                return node
            element_annotation = self._tracked_element(node.value)
            if element_annotation is None:
                return node
            self.changed = True
            return self._project_element(node, element_annotation)

        def visit_Call(self, node: Call):
            self.generic_visit(node)

            # x.pop(...) returns element type for tracked CheckedList locals.
            if (
                hasattr(node.func, "attr")
                and getattr(node.func, "attr", None) == "pop"
                and hasattr(node.func, "value")
            ):
                receiver = getattr(node.func, "value", None)
                element_annotation = self._tracked_element(receiver) if isinstance(receiver, expr) else None
                if element_annotation is not None:
                    self.changed = True
                    node = self._project_element(node, element_annotation)

            # CheckedList local crossing call boundary: wrap argument.
            new_args: list[expr] = []
            for arg_node in node.args:
                element_annotation = self._tracked_element(arg_node)
                if element_annotation is None:
                    new_args.append(arg_node)
                    continue
                checkedlist_annotation = _make_checkedlist_annotation(element_annotation)
                if _is_same_construct_wrapper(arg_node, checkedlist_annotation):
                    new_args.append(arg_node)
                    continue
                self.changed = True
                new_args.append(ctx.wrap_construct(checkedlist_annotation, arg_node))
            node.args = new_args

            for kw in node.keywords:
                element_annotation = self._tracked_element(kw.value)
                if element_annotation is None:
                    continue
                checkedlist_annotation = _make_checkedlist_annotation(element_annotation)
                if _is_same_construct_wrapper(kw.value, checkedlist_annotation):
                    continue
                self.changed = True
                kw.value = ctx.wrap_construct(checkedlist_annotation, kw.value)
            return node

        def visit_Return(self, node):
            self.generic_visit(node)
            if return_checkedlist_annotation is None:
                return node
            if node.value is None:
                return node
            if _is_same_construct_wrapper(node.value, return_checkedlist_annotation):
                return node
            self.changed = True
            node.value = ctx.wrap_construct(return_checkedlist_annotation, node.value)
            return node

    rewriter = _CheckedListFlowRewriter()
    fn.body = [rewriter.visit(stmt) for stmt in fn.body]
    return rewriter.changed
