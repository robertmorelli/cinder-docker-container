"""Unit tests for return passes — all four return pass modules tested in isolation."""

from __future__ import annotations

import sys
from ast import FunctionDef, Load, Name, Subscript, arg, arguments
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from passes.return_box_primitive import apply as apply_box, PASS_NAME as BOX_PASS
from passes.return_construct_container import apply as apply_construct, PASS_NAME as CONSTRUCT_PASS
from passes.return_cast_all import apply as apply_cast, PASS_NAME as CAST_PASS
from passes.return_cast_container_passthrough import apply as apply_passthrough, PASS_NAME as PASSTHROUGH_PASS

from tests.conftest import all_passes_enabled, all_passes_disabled, only_pass_enabled


def _name(id: str) -> Name:
    return Name(id=id, ctx=Load())


def _subscript(base: str, inner: str) -> Subscript:
    return Subscript(value=Name(id=base, ctx=Load()), slice=Name(id=inner, ctx=Load()), ctx=Load())


def _make_fn(returns) -> FunctionDef:
    return FunctionDef(
        name="test_fn",
        args=arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[],
        decorator_list=[],
        returns=returns,
    )


class TestReturnBoxPrimitive:
    def test_removes_primitive_return_annotation(self, pass_ctx):
        fn = _make_fn(returns=_name("int64"))
        state = all_passes_enabled()
        changed = apply_box(fn, state, pass_ctx)
        assert changed is True
        assert fn.returns is None

    def test_skips_non_primitive(self, pass_ctx):
        fn = _make_fn(returns=_name("Widget"))
        state = all_passes_enabled()
        changed = apply_box(fn, state, pass_ctx)
        assert changed is False
        assert fn.returns is not None

    def test_skips_when_disabled(self, pass_ctx):
        fn = _make_fn(returns=_name("int64"))
        state = all_passes_disabled()
        changed = apply_box(fn, state, pass_ctx)
        assert changed is False
        assert fn.returns is not None

    def test_skips_no_return_annotation(self, pass_ctx):
        fn = _make_fn(returns=None)
        state = all_passes_enabled()
        changed = apply_box(fn, state, pass_ctx)
        assert changed is False

    @pytest.mark.parametrize("prim", ["int64", "double", "cbool", "int32", "uint8"])
    def test_all_primitives(self, pass_ctx, prim):
        fn = _make_fn(returns=_name(prim))
        state = all_passes_enabled()
        changed = apply_box(fn, state, pass_ctx)
        assert changed is True
        assert fn.returns is None


class TestReturnConstructContainer:
    def test_removes_construct_return_annotation(self, pass_ctx):
        fn = _make_fn(returns=_subscript("CheckedList", "int64"))
        state = all_passes_enabled()
        changed = apply_construct(fn, state, pass_ctx)
        assert changed is True
        assert fn.returns is None

    def test_skips_primitive(self, pass_ctx):
        fn = _make_fn(returns=_name("int64"))
        state = all_passes_enabled()
        changed = apply_construct(fn, state, pass_ctx)
        assert changed is False

    def test_skips_passthrough_container(self, pass_ctx):
        fn = _make_fn(returns=_subscript("Array", "int64"))
        state = all_passes_enabled()
        changed = apply_construct(fn, state, pass_ctx)
        assert changed is False

    def test_skips_when_disabled(self, pass_ctx):
        fn = _make_fn(returns=_subscript("CheckedList", "int64"))
        state = all_passes_disabled()
        changed = apply_construct(fn, state, pass_ctx)
        assert changed is False

    @pytest.mark.parametrize("root", ["CheckedList", "CheckedDict", "CheckedSet"])
    def test_all_construct_roots(self, pass_ctx, root):
        fn = _make_fn(returns=_subscript(root, "int64"))
        state = all_passes_enabled()
        changed = apply_construct(fn, state, pass_ctx)
        assert changed is True
        assert fn.returns is None


class TestReturnCastAll:
    def test_removes_cast_return_annotation(self, pass_ctx):
        fn = _make_fn(returns=_name("Widget"))
        state = all_passes_enabled()
        changed = apply_cast(fn, state, pass_ctx)
        assert changed is True
        assert fn.returns is None

    def test_skips_primitive(self, pass_ctx):
        fn = _make_fn(returns=_name("int64"))
        state = all_passes_enabled()
        changed = apply_cast(fn, state, pass_ctx)
        assert changed is False

    def test_skips_constructor(self, pass_ctx):
        fn = _make_fn(returns=_subscript("CheckedList", "int64"))
        state = all_passes_enabled()
        changed = apply_cast(fn, state, pass_ctx)
        assert changed is False

    def test_skips_when_disabled(self, pass_ctx):
        fn = _make_fn(returns=_name("Widget"))
        state = all_passes_disabled()
        changed = apply_cast(fn, state, pass_ctx)
        assert changed is False

    def test_skips_no_return(self, pass_ctx):
        fn = _make_fn(returns=None)
        state = all_passes_enabled()
        changed = apply_cast(fn, state, pass_ctx)
        assert changed is False


class TestReturnCastContainerPassthrough:
    def test_removes_passthrough_return_annotation(self, pass_ctx):
        fn = _make_fn(returns=_subscript("Array", "int64"))
        state = all_passes_enabled()
        changed = apply_passthrough(fn, state, pass_ctx)
        assert changed is True
        assert fn.returns is None

    def test_skips_construct_container(self, pass_ctx):
        fn = _make_fn(returns=_subscript("CheckedList", "int64"))
        state = all_passes_enabled()
        changed = apply_passthrough(fn, state, pass_ctx)
        assert changed is False

    def test_skips_primitive(self, pass_ctx):
        fn = _make_fn(returns=_name("int64"))
        state = all_passes_enabled()
        changed = apply_passthrough(fn, state, pass_ctx)
        assert changed is False

    def test_skips_when_disabled(self, pass_ctx):
        fn = _make_fn(returns=_subscript("Array", "int64"))
        state = all_passes_disabled()
        changed = apply_passthrough(fn, state, pass_ctx)
        assert changed is False

    @pytest.mark.parametrize("root", ["Array", "Dict", "List", "Set", "Tuple"])
    def test_all_passthrough_roots(self, pass_ctx, root):
        fn = _make_fn(returns=_subscript(root, "int64"))
        state = all_passes_enabled()
        changed = apply_passthrough(fn, state, pass_ctx)
        assert changed is True
        assert fn.returns is None
