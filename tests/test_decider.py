"""Unit tests for passes/decider.py — strategy decisions for all annotation categories."""

from __future__ import annotations

import sys
from ast import BinOp, BitOr, Constant, Load, Name, Subscript, expr
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from passes.bins import box_primitive_types, container_construct_types, container_passthrough_types, nogo_types
from passes.decider import (
    StrategyDecision,
    annotation_policy,
    annotation_root_name,
    decide_body_strategy,
    decide_param_strategy,
    decide_return_strategy,
    decide_scope_strategy,
    is_constructor_annotation,
    is_dynamic_annotation,
    is_nogo_annotation,
    is_none_annotation,
    is_optional_or_union_annotation,
    is_passthrough_container_annotation,
    is_primitive_annotation,
    pass_name_for_annotation,
)


# ---- Annotation helpers ----

def _name(id: str) -> Name:
    return Name(id=id, ctx=Load())


def _subscript(base: str, arg: str) -> Subscript:
    return Subscript(value=Name(id=base, ctx=Load()), slice=Name(id=arg, ctx=Load()), ctx=Load())


def _optional(inner: str) -> Subscript:
    return _subscript("Optional", inner)


def _union_binop(left: str, right: str) -> BinOp:
    return BinOp(left=Name(id=left, ctx=Load()), op=BitOr(), right=Name(id=right, ctx=Load()))


# ---- Predicate tests ----

class TestIsNoneAnnotation:
    def test_none_value(self):
        assert is_none_annotation(None)

    def test_constant_none(self):
        assert is_none_annotation(Constant(value=None))

    def test_name_none(self):
        assert is_none_annotation(_name("None"))

    def test_name_int64_not_none(self):
        assert not is_none_annotation(_name("int64"))

    def test_subscript_not_none(self):
        assert not is_none_annotation(_subscript("List", "int"))


class TestIsDynamicAnnotation:
    def test_dynamic(self):
        assert is_dynamic_annotation(_name("dynamic"))

    def test_not_dynamic(self):
        assert not is_dynamic_annotation(_name("int64"))

    def test_none_not_dynamic(self):
        assert not is_dynamic_annotation(None)


class TestIsPrimitiveAnnotation:
    @pytest.mark.parametrize("prim", sorted(box_primitive_types))
    def test_all_primitives(self, prim):
        assert is_primitive_annotation(_name(prim))

    def test_non_primitive(self):
        assert not is_primitive_annotation(_name("Foo"))

    def test_none(self):
        assert not is_primitive_annotation(None)

    def test_subscript_not_primitive(self):
        assert not is_primitive_annotation(_subscript("int64", "x"))


class TestIsConstructorAnnotation:
    @pytest.mark.parametrize("root", sorted(container_construct_types))
    def test_all_construct_roots(self, root):
        assert is_constructor_annotation(_subscript(root, "int64"))

    def test_bare_name_not_constructor(self):
        assert not is_constructor_annotation(_name("CheckedList"))

    def test_passthrough_not_constructor(self):
        assert not is_constructor_annotation(_subscript("Array", "int64"))

    def test_none(self):
        assert not is_constructor_annotation(None)


class TestIsPassthroughContainerAnnotation:
    @pytest.mark.parametrize("root", sorted(container_passthrough_types))
    def test_all_passthrough_roots(self, root):
        assert is_passthrough_container_annotation(_subscript(root, "int64"))

    def test_bare_name_not_passthrough(self):
        assert not is_passthrough_container_annotation(_name("Array"))

    def test_construct_not_passthrough(self):
        assert not is_passthrough_container_annotation(_subscript("CheckedList", "int64"))

    def test_none(self):
        assert not is_passthrough_container_annotation(None)


class TestIsNogoAnnotation:
    @pytest.mark.parametrize("nogo", sorted(nogo_types))
    def test_all_nogo_types(self, nogo):
        assert is_nogo_annotation(_name(nogo))

    def test_non_nogo(self):
        assert not is_nogo_annotation(_name("int64"))

    def test_none(self):
        assert not is_nogo_annotation(None)


class TestIsOptionalOrUnionAnnotation:
    def test_optional(self):
        assert is_optional_or_union_annotation(_optional("int"))

    def test_union_subscript(self):
        assert is_optional_or_union_annotation(_subscript("Union", "int"))

    def test_binop_union(self):
        assert is_optional_or_union_annotation(_union_binop("int", "str"))

    def test_not_union(self):
        assert not is_optional_or_union_annotation(_name("int64"))

    def test_none(self):
        assert not is_optional_or_union_annotation(None)


class TestAnnotationRootName:
    def test_name(self):
        assert annotation_root_name(_name("Foo")) == "Foo"

    def test_subscript(self):
        assert annotation_root_name(_subscript("List", "int")) == "List"

    def test_none(self):
        assert annotation_root_name(None) is None


# ---- Strategy decision tests ----

class TestDecideScopeStrategy:
    """Test decide_scope_strategy for every annotation category."""

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    def test_none_is_passthrough(self, scope):
        d = decide_scope_strategy(scope, None)
        assert d.strategy == "passthrough"
        assert d.pass_name is None
        assert not d.can_detype

    @pytest.mark.parametrize("scope", ["param", "body"])
    def test_constant_none_is_passthrough(self, scope):
        d = decide_scope_strategy(scope, Constant(value=None))
        assert d.strategy == "passthrough"

    def test_constant_none_return_is_detype(self):
        d = decide_scope_strategy("return", Constant(value=None))
        assert d.strategy == "detype"
        assert d.pass_name == "return_detype_none"
        assert d.can_detype

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    def test_dynamic_is_passthrough(self, scope):
        d = decide_scope_strategy(scope, _name("dynamic"))
        assert d.strategy == "passthrough"

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    @pytest.mark.parametrize("nogo", sorted(nogo_types))
    def test_nogo_types(self, scope, nogo):
        d = decide_scope_strategy(scope, _name(nogo))
        assert d.strategy == "nogo"
        assert d.pass_name is None
        assert not d.can_detype

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    @pytest.mark.parametrize("prim", ["int64", "double", "cbool"])
    def test_primitive_is_box(self, scope, prim):
        d = decide_scope_strategy(scope, _name(prim))
        assert d.strategy == "box"
        assert d.pass_name == f"{scope}_box_primitive"
        assert d.can_detype

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    @pytest.mark.parametrize("root", sorted(container_construct_types))
    def test_constructor_annotation(self, scope, root):
        d = decide_scope_strategy(scope, _subscript(root, "int64"))
        assert d.strategy == "construct"
        assert d.pass_name == f"{scope}_construct_container"
        assert d.can_detype

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    @pytest.mark.parametrize("root", sorted(container_passthrough_types))
    def test_passthrough_container(self, scope, root):
        d = decide_scope_strategy(scope, _subscript(root, "int64"))
        assert d.strategy == "cast"
        assert d.pass_name == f"{scope}_cast_container_passthrough"
        assert d.can_detype

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    def test_unknown_name_falls_to_cast_all(self, scope):
        d = decide_scope_strategy(scope, _name("Widget"))
        assert d.strategy == "cast"
        assert d.pass_name == f"{scope}_cast_all"
        assert d.can_detype

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    def test_unknown_subscript_falls_to_cast_all(self, scope):
        d = decide_scope_strategy(scope, _subscript("SomeGeneric", "T"))
        assert d.strategy == "cast"
        assert d.pass_name == f"{scope}_cast_all"


class TestScopedConvenienceFunctions:
    def test_decide_param_strategy(self):
        d = decide_param_strategy(_name("int64"))
        assert d.pass_name == "param_box_primitive"

    def test_decide_body_strategy(self):
        d = decide_body_strategy(_name("int64"))
        assert d.pass_name == "body_box_primitive"

    def test_decide_return_strategy(self):
        d = decide_return_strategy(_name("int64"))
        assert d.pass_name == "return_box_primitive"


class TestAnnotationPolicy:
    def test_primitive_returns_box(self):
        assert annotation_policy(_name("int64")) == "box"

    def test_widget_returns_cast(self):
        assert annotation_policy(_name("Widget")) == "cast"

    def test_none_returns_passthrough(self):
        assert annotation_policy(None) == "passthrough"

    def test_constructor_returns_construct(self):
        assert annotation_policy(_subscript("CheckedList", "int64")) == "construct"


class TestPassNameForAnnotation:
    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    def test_primitive(self, scope):
        assert pass_name_for_annotation(scope, _name("int64")) == f"{scope}_box_primitive"

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    def test_none_returns_none(self, scope):
        assert pass_name_for_annotation(scope, None) is None

    @pytest.mark.parametrize("scope", ["param", "body", "return"])
    def test_nogo_returns_none(self, scope):
        assert pass_name_for_annotation(scope, _name("Iterator")) is None


class TestExactlyOneClassifier:
    """For any non-None annotation, exactly one classifier predicate is true."""

    @pytest.mark.parametrize(
        "annotation",
        [
            _name("int64"),
            _name("Widget"),
            _name("Iterator"),
            _name("dynamic"),
            _name("None"),
            _subscript("CheckedList", "int64"),
            _subscript("Array", "int64"),
            _subscript("Optional", "int"),
            _union_binop("int", "str"),
        ],
        ids=["prim", "cast", "nogo", "dynamic", "noneName", "construct", "passthrough", "optional", "union"],
    )
    def test_at_most_one_primary_classifier(self, annotation):
        results = {
            "primitive": is_primitive_annotation(annotation),
            "constructor": is_constructor_annotation(annotation),
            "passthrough": is_passthrough_container_annotation(annotation),
            "nogo": is_nogo_annotation(annotation),
            "dynamic": is_dynamic_annotation(annotation),
            "none": is_none_annotation(annotation),
        }
        true_count = sum(1 for v in results.values() if v)
        assert true_count <= 1, f"multiple classifiers true: {[k for k, v in results.items() if v]}"
