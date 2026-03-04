"""Pure wrapping helpers for AST detyping transforms.

These functions are stateless/pure — they build AST nodes without
capturing mutable state. State-dependent wrappers (wrap_box, wrap_cast)
remain as closures in the transform pipeline.
"""

from __future__ import annotations

from ast import (
    AST,
    Call,
    Import,
    ImportFrom,
    Load,
    Name,
    alias,
    expr,
)
from copy import deepcopy

from .decider import is_constructor_annotation, is_primitive_annotation


def is_box_call(node: expr) -> bool:
    return isinstance(node, Call) and isinstance(node.func, Name) and node.func.id == "box"


def coerce_primitive(annotation: expr | None, node: expr) -> expr:
    if not is_primitive_annotation(annotation):
        return node
    return Call(
        func=Name(id=annotation.id, ctx=Load()),
        args=[node],
        keywords=[],
    )


def wrap_construct(annotation: expr, node: expr) -> expr:
    assert is_constructor_annotation(annotation), f"expected constructor annotation, got: {annotation}"
    return Call(
        func=deepcopy(annotation),
        args=[node],
        keywords=[],
    )


def wrap_scalar_construct(annotation: expr, node: expr) -> expr:
    assert isinstance(annotation, Name), "scalar construct annotation must be simple name"
    return Call(
        func=Name(id=annotation.id, ctx=Load()),
        args=[node],
        keywords=[],
    )


def ensure_static_imports(module: AST, names: set[str]) -> None:
    if len(names) == 0:
        return
    names = set(names)
    for child in module.body:
        if isinstance(child, ImportFrom) and child.module == "__static__":
            existing = set(alias_node.name for alias_node in child.names)
            for import_name in sorted(names):
                if import_name not in existing:
                    child.names.append(alias(name=import_name, asname=None))
            return

    insert_pos = 0
    for i, child in enumerate(module.body):
        if isinstance(child, (Import, ImportFrom)):
            insert_pos = i + 1
    module.body.insert(
        insert_pos,
        ImportFrom(
            module="__static__",
            names=[alias(name=import_name, asname=None) for import_name in sorted(names)],
            level=0,
        ),
    )
