"""Unit tests for passes/cleanup_inline.py — inline cleanup pass."""

from __future__ import annotations

import sys
from ast import (
    AnnAssign,
    Attribute,
    Call,
    Constant,
    FunctionDef,
    Load,
    Name,
    Return,
    Store,
    arg,
    arguments,
)
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from passes.cleanup_inline import cleanup_inline_function, is_inline_function


def _name_load(id: str) -> Name:
    return Name(id=id, ctx=Load())


def _name_store(id: str) -> Name:
    return Name(id=id, ctx=Store())


def _inline_decorator() -> Name:
    return _name_load("inline")


def _attr_inline_decorator() -> Attribute:
    return Attribute(value=_name_load("module"), attr="inline", ctx=Load())


def _make_fn(
    name: str,
    params: list[tuple[str, object | None]],
    body: list,
    decorators: list | None = None,
    returns=None,
) -> FunctionDef:
    args_list = []
    for pname, ann in params:
        a = arg(arg=pname)
        a.annotation = ann
        args_list.append(a)
    return FunctionDef(
        name=name,
        args=arguments(
            posonlyargs=[], args=args_list, vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=body,
        decorator_list=decorators or [],
        returns=returns,
    )


def _projection_stmt(local_name: str, annotation_id: str, hidden_name: str) -> AnnAssign:
    """x: int64 = int64(_x)"""
    return AnnAssign(
        target=_name_store(local_name),
        annotation=_name_load(annotation_id),
        value=Call(func=_name_load(annotation_id), args=[_name_load(hidden_name)], keywords=[]),
        simple=1,
    )


def _cast_projection_stmt(local_name: str, annotation_id: str, hidden_name: str) -> AnnAssign:
    """foo: Foo = cast(Foo, _foo)"""
    return AnnAssign(
        target=_name_store(local_name),
        annotation=_name_load(annotation_id),
        value=Call(func=_name_load("cast"), args=[_name_load(annotation_id), _name_load(hidden_name)], keywords=[]),
        simple=1,
    )


class TestIsInlineFunction:
    def test_bare_inline_decorator(self):
        fn = _make_fn("f", [], [], decorators=[_inline_decorator()])
        assert is_inline_function(fn)

    def test_attribute_inline_decorator(self):
        fn = _make_fn("f", [], [], decorators=[_attr_inline_decorator()])
        assert is_inline_function(fn)

    def test_no_decorator(self):
        fn = _make_fn("f", [], [])
        assert not is_inline_function(fn)

    def test_other_decorator(self):
        fn = _make_fn("f", [], [], decorators=[_name_load("staticmethod")])
        assert not is_inline_function(fn)


class TestCleanupInlineFunction:
    def test_single_param_inline_collapse(self):
        """@inline def f(_x): x: int64 = int64(_x); return x  →  return int64(_x)"""
        fn = _make_fn(
            "f",
            [("_x", None)],
            [
                _projection_stmt("x", "int64", "_x"),
                Return(value=_name_load("x")),
            ],
            decorators=[_inline_decorator()],
        )
        result = cleanup_inline_function(fn)
        assert result is True
        assert len(fn.body) == 1
        assert isinstance(fn.body[0], Return)
        ret_val = fn.body[0].value
        assert isinstance(ret_val, Call)
        assert isinstance(ret_val.func, Name) and ret_val.func.id == "int64"

    def test_cast_projection_collapse(self):
        """@inline def f(_foo): foo: Foo = cast(Foo, _foo); return foo  →  return cast(Foo, _foo)"""
        fn = _make_fn(
            "f",
            [("_foo", None)],
            [
                _cast_projection_stmt("foo", "Foo", "_foo"),
                Return(value=_name_load("foo")),
            ],
            decorators=[_inline_decorator()],
        )
        result = cleanup_inline_function(fn)
        assert result is True
        assert len(fn.body) == 1
        ret_val = fn.body[0].value
        assert isinstance(ret_val, Call)
        assert isinstance(ret_val.func, Name) and ret_val.func.id == "cast"

    def test_non_inline_function_unchanged(self):
        """Non-inline function is not touched."""
        body = [Return(value=_name_load("x"))]
        fn = _make_fn("f", [("x", None)], deepcopy(body))
        result = cleanup_inline_function(fn)
        assert result is True
        assert len(fn.body) == 1

    def test_multi_param_inline(self):
        """@inline def f(_x, _y): x: int64 = int64(_x); y: double = double(_y); return x + y"""
        from ast import Add, BinOp

        fn = _make_fn(
            "f",
            [("_x", None), ("_y", None)],
            [
                _projection_stmt("x", "int64", "_x"),
                _projection_stmt("y", "double", "_y"),
                Return(value=BinOp(left=_name_load("x"), op=Add(), right=_name_load("y"))),
            ],
            decorators=[_inline_decorator()],
        )
        result = cleanup_inline_function(fn)
        assert result is True
        assert len(fn.body) == 1
        assert isinstance(fn.body[0], Return)

    def test_inline_with_no_projections_just_return(self):
        """@inline def f(x): return x  →  body unchanged (no hidden names)"""
        fn = _make_fn(
            "f",
            [("x", None)],
            [Return(value=_name_load("x"))],
            decorators=[_inline_decorator()],
        )
        result = cleanup_inline_function(fn)
        assert result is True
        assert len(fn.body) == 1

    def test_inline_with_extra_statements_fails(self):
        """@inline with non-projection body can't be collapsed."""
        from ast import Assign

        fn = _make_fn(
            "f",
            [("_x", None)],
            [
                _projection_stmt("x", "int64", "_x"),
                Assign(targets=[_name_store("y")], value=Constant(value=1)),
                Return(value=_name_load("x")),
            ],
            decorators=[_inline_decorator()],
        )
        result = cleanup_inline_function(fn)
        assert result is False
