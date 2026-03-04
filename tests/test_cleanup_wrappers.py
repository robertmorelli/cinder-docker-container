"""Unit tests for passes/cleanup_wrappers.py — redundant wrapper cleanup."""

from __future__ import annotations

import sys
from ast import Call, Constant, Load, Name, Subscript, expr, unparse
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from passes.cleanup_wrappers import RedundantWrapperCleaner, annotations_equal


def _name(id: str) -> Name:
    return Name(id=id, ctx=Load())


def _call(func_name: str, *args: expr) -> Call:
    return Call(func=_name(func_name), args=list(args), keywords=[])


def _cast(annotation: expr, value: expr) -> Call:
    return Call(func=_name("cast"), args=[annotation, value], keywords=[])


def _subscript(base: str, inner: str) -> Subscript:
    return Subscript(value=Name(id=base, ctx=Load()), slice=Name(id=inner, ctx=Load()), ctx=Load())


class TestAnnotationsEqual:
    def test_same_name(self):
        assert annotations_equal(_name("Foo"), _name("Foo"))

    def test_different_name(self):
        assert not annotations_equal(_name("Foo"), _name("Bar"))

    def test_same_subscript(self):
        assert annotations_equal(_subscript("List", "int"), _subscript("List", "int"))

    def test_different_subscript(self):
        assert not annotations_equal(_subscript("List", "int"), _subscript("List", "str"))


class TestRedundantCastCollapse:
    def test_double_cast_same_annotation_collapses(self):
        """cast(Foo, cast(Foo, x)) → cast(Foo, x)"""
        inner = _cast(_name("Foo"), _name("x"))
        outer = _cast(_name("Foo"), inner)
        result = RedundantWrapperCleaner().visit(outer)
        # Should be cast(Foo, x), not cast(Foo, cast(Foo, x))
        assert unparse(result) == unparse(_cast(_name("Foo"), _name("x")))

    def test_double_cast_different_annotation_kept(self):
        """cast(Foo, cast(Bar, x)) stays as-is."""
        inner = _cast(_name("Bar"), _name("x"))
        outer = _cast(_name("Foo"), inner)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(outer)

    def test_triple_cast_collapses_fully(self):
        """cast(T, cast(T, cast(T, x))) → cast(T, x)"""
        innermost = _cast(_name("T"), _name("x"))
        middle = _cast(_name("T"), innermost)
        outer = _cast(_name("T"), middle)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(_cast(_name("T"), _name("x")))

    def test_subscript_annotation_cast_collapse(self):
        """cast(Array[int64], cast(Array[int64], x)) → cast(Array[int64], x)"""
        ann = _subscript("Array", "int64")
        inner = _cast(_subscript("Array", "int64"), _name("x"))
        outer = _cast(ann, inner)
        result = RedundantWrapperCleaner().visit(outer)
        unparsed = unparse(result)
        assert "cast(Array[int64], x)" == unparsed


class TestIdempotentUnaryCollapse:
    @pytest.mark.parametrize("wrapper", ["int64", "int32", "double", "cbool", "uint8", "box"])
    def test_double_unary_collapses(self, wrapper):
        """wrapper(wrapper(x)) → wrapper(x)"""
        inner = _call(wrapper, _name("x"))
        outer = _call(wrapper, inner)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(_call(wrapper, _name("x")))

    def test_triple_unary_collapses(self):
        """int64(int64(int64(x))) → int64(x)"""
        innermost = _call("int64", _name("x"))
        middle = _call("int64", innermost)
        outer = _call("int64", middle)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(_call("int64", _name("x")))

    def test_different_unary_names_not_collapsed(self):
        """int64(double(x)) stays."""
        inner = _call("double", _name("x"))
        outer = _call("int64", inner)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(outer)

    def test_non_idempotent_wrapper_not_collapsed(self):
        """len(len(x)) stays — len is not in idempotent set."""
        inner = _call("len", _name("x"))
        outer = _call("len", inner)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(outer)

    def test_float_collapse(self):
        """float(float(x)) → float(x)"""
        inner = _call("float", _name("x"))
        outer = _call("float", inner)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(_call("float", _name("x")))


class TestMixedCastAndUnary:
    def test_box_inside_cast_not_collapsed(self):
        """cast(Foo, box(x)) stays — different wrappers."""
        inner = _call("box", _name("x"))
        outer = _cast(_name("Foo"), inner)
        result = RedundantWrapperCleaner().visit(outer)
        assert unparse(result) == unparse(outer)

    def test_non_call_arg_unchanged(self):
        """cast(Foo, x) where x is Name stays."""
        node = _cast(_name("Foo"), _name("x"))
        result = RedundantWrapperCleaner().visit(node)
        assert unparse(result) == unparse(node)

    def test_constant_arg_unchanged(self):
        """int64(42) stays."""
        node = _call("int64", Constant(value=42))
        result = RedundantWrapperCleaner().visit(node)
        assert unparse(result) == unparse(node)
