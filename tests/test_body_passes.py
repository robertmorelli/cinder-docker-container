"""Unit tests for body passes — all four body pass modules tested in isolation."""

from __future__ import annotations

import sys
from ast import Call, Constant, Load, Name, Subscript, expr
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from passes.body_box_primitive import apply as apply_box, PASS_NAME as BOX_PASS
from passes.body_construct_container import apply as apply_construct, PASS_NAME as CONSTRUCT_PASS
from passes.body_cast_all import apply as apply_cast, PASS_NAME as CAST_PASS
from passes.body_cast_container_passthrough import apply as apply_passthrough, PASS_NAME as PASSTHROUGH_PASS

from tests.conftest import all_passes_enabled, all_passes_disabled, only_pass_enabled


def _name(id: str) -> Name:
    return Name(id=id, ctx=Load())


def _subscript(base: str, inner: str) -> Subscript:
    return Subscript(value=Name(id=base, ctx=Load()), slice=Name(id=inner, ctx=Load()), ctx=Load())


def _const(val: int) -> Constant:
    return Constant(value=val)


class TestBodyBoxPrimitive:
    def test_rewrites_primitive_body(self, pass_ctx):
        ann = _name("int64")
        value = _const(42)
        state = all_passes_enabled()
        result = apply_box(ann, value, state, pass_ctx)
        assert result is not None
        # Should be box(int64(42))
        assert isinstance(result, Call)
        assert isinstance(result.func, Name) and result.func.id == "box"

    def test_none_value_returns_constant_none(self, pass_ctx):
        ann = _name("int64")
        state = all_passes_enabled()
        result = apply_box(ann, None, state, pass_ctx)
        assert result is not None
        assert isinstance(result, Constant) and result.value is None

    def test_skips_non_primitive(self, pass_ctx):
        ann = _name("Widget")
        value = _const(42)
        state = all_passes_enabled()
        result = apply_box(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_when_disabled(self, pass_ctx):
        ann = _name("int64")
        value = _const(42)
        state = all_passes_disabled()
        result = apply_box(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_constructor_annotation(self, pass_ctx):
        ann = _subscript("CheckedList", "int64")
        value = _const(42)
        state = all_passes_enabled()
        result = apply_box(ann, value, state, pass_ctx)
        assert result is None

    @pytest.mark.parametrize("prim", ["int64", "int32", "double", "cbool", "uint8"])
    def test_all_primitive_types(self, pass_ctx, prim):
        ann = _name(prim)
        value = _const(0)
        state = all_passes_enabled()
        result = apply_box(ann, value, state, pass_ctx)
        assert result is not None


class TestBodyConstructContainer:
    def test_rewrites_construct_body(self, pass_ctx):
        ann = _subscript("CheckedList", "int64")
        value = Name(id="items", ctx=Load())
        state = all_passes_enabled()
        result = apply_construct(ann, value, state, pass_ctx)
        assert result is not None
        assert isinstance(result, Call)

    def test_none_value_returns_constant_none(self, pass_ctx):
        ann = _subscript("CheckedList", "int64")
        state = all_passes_enabled()
        result = apply_construct(ann, None, state, pass_ctx)
        assert isinstance(result, Constant) and result.value is None

    def test_skips_primitive(self, pass_ctx):
        ann = _name("int64")
        value = _const(1)
        state = all_passes_enabled()
        result = apply_construct(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_passthrough_container(self, pass_ctx):
        ann = _subscript("Array", "int64")
        value = _name("xs")
        state = all_passes_enabled()
        result = apply_construct(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_when_disabled(self, pass_ctx):
        ann = _subscript("CheckedList", "int64")
        value = _name("xs")
        state = all_passes_disabled()
        result = apply_construct(ann, value, state, pass_ctx)
        assert result is None

    @pytest.mark.parametrize("root", ["CheckedList", "CheckedDict", "CheckedSet"])
    def test_all_construct_roots(self, pass_ctx, root):
        ann = _subscript(root, "int64")
        value = _name("items")
        state = all_passes_enabled()
        result = apply_construct(ann, value, state, pass_ctx)
        assert result is not None


class TestBodyCastAll:
    def test_rewrites_cast_body(self, pass_ctx):
        ann = _name("Widget")
        value = Name(id="make_widget", ctx=Load())
        state = all_passes_enabled()
        result = apply_cast(ann, value, state, pass_ctx)
        assert result is not None
        assert isinstance(result, Call)

    def test_none_value_returns_constant_none(self, pass_ctx):
        ann = _name("Widget")
        state = all_passes_enabled()
        result = apply_cast(ann, None, state, pass_ctx)
        assert isinstance(result, Constant) and result.value is None

    def test_skips_primitive(self, pass_ctx):
        ann = _name("int64")
        value = _const(1)
        state = all_passes_enabled()
        result = apply_cast(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_optional_annotation(self, pass_ctx):
        ann = _subscript("Optional", "int")
        value = _name("x")
        state = all_passes_enabled()
        result = apply_cast(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_when_disabled(self, pass_ctx):
        ann = _name("Widget")
        value = _name("x")
        state = all_passes_disabled()
        result = apply_cast(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_constructor_annotation(self, pass_ctx):
        ann = _subscript("CheckedList", "int64")
        value = _name("xs")
        state = all_passes_enabled()
        result = apply_cast(ann, value, state, pass_ctx)
        assert result is None


class TestBodyCastContainerPassthrough:
    def test_rewrites_passthrough_body(self, pass_ctx):
        ann = _subscript("Array", "int64")
        value = _name("xs")
        state = all_passes_enabled()
        result = apply_passthrough(ann, value, state, pass_ctx)
        assert result is not None
        assert isinstance(result, Call)

    def test_none_value_returns_constant_none(self, pass_ctx):
        ann = _subscript("Array", "int64")
        state = all_passes_enabled()
        result = apply_passthrough(ann, None, state, pass_ctx)
        assert isinstance(result, Constant) and result.value is None

    def test_skips_primitive(self, pass_ctx):
        ann = _name("int64")
        value = _const(1)
        state = all_passes_enabled()
        result = apply_passthrough(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_construct_container(self, pass_ctx):
        ann = _subscript("CheckedList", "int64")
        value = _name("xs")
        state = all_passes_enabled()
        result = apply_passthrough(ann, value, state, pass_ctx)
        assert result is None

    def test_skips_when_disabled(self, pass_ctx):
        ann = _subscript("Array", "int64")
        value = _name("xs")
        state = all_passes_disabled()
        result = apply_passthrough(ann, value, state, pass_ctx)
        assert result is None

    @pytest.mark.parametrize("root", ["Array", "Dict", "List", "Set", "Tuple"])
    def test_all_passthrough_roots(self, pass_ctx, root):
        ann = _subscript(root, "int64")
        value = _name("items")
        state = all_passes_enabled()
        result = apply_passthrough(ann, value, state, pass_ctx)
        assert result is not None
