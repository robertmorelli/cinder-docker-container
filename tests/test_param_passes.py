"""Unit tests for param passes — all four param pass modules tested in isolation."""

from __future__ import annotations

import sys
from ast import AnnAssign, FunctionDef, Load, Name, Store, arg, arguments, dump as ast_dump
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ast import Subscript

from passes.param_box_primitive import apply as apply_box, PASS_NAME as BOX_PASS
from passes.param_construct_container import apply as apply_construct, PASS_NAME as CONSTRUCT_PASS
from passes.param_cast_all import apply as apply_cast, PASS_NAME as CAST_PASS
from passes.param_cast_container_passthrough import apply as apply_passthrough, PASS_NAME as PASSTHROUGH_PASS

from tests.conftest import all_passes_enabled, all_passes_disabled, only_pass_enabled


def _name(id: str) -> Name:
    return Name(id=id, ctx=Load())


def _subscript(base: str, inner: str) -> Subscript:
    return Subscript(value=Name(id=base, ctx=Load()), slice=Name(id=inner, ctx=Load()), ctx=Load())


def _make_fn(params: list[tuple[str, object | None]], returns=None) -> FunctionDef:
    args_list = []
    for name, ann in params:
        a = arg(arg=name)
        a.annotation = ann
        args_list.append(a)
    fn = FunctionDef(
        name="test_fn",
        args=arguments(
            posonlyargs=[],
            args=args_list,
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=[],
        decorator_list=[],
        returns=returns,
    )
    return fn


class TestParamBoxPrimitive:
    def test_rewrites_primitive_param(self, pass_ctx):
        fn = _make_fn([("x", _name("int64"))])
        state = all_passes_enabled()
        used = {"x"}
        stmts: list[AnnAssign] = []
        changed = apply_box(fn, state, used, stmts, pass_ctx)
        assert changed is True
        assert fn.args.args[0].arg == "_x"
        assert fn.args.args[0].annotation is None
        assert len(stmts) == 1
        assert isinstance(stmts[0], AnnAssign)
        assert isinstance(stmts[0].target, Name) and stmts[0].target.id == "x"

    def test_skips_non_primitive(self, pass_ctx):
        fn = _make_fn([("x", _name("Widget"))])
        state = all_passes_enabled()
        used = {"x"}
        stmts: list[AnnAssign] = []
        changed = apply_box(fn, state, used, stmts, pass_ctx)
        assert changed is False
        assert fn.args.args[0].arg == "x"
        assert len(stmts) == 0

    def test_skips_self(self, pass_ctx):
        fn = _make_fn([("self", _name("int64"))])
        state = all_passes_enabled()
        used = {"self"}
        stmts: list[AnnAssign] = []
        changed = apply_box(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_cls(self, pass_ctx):
        fn = _make_fn([("cls", _name("int64"))])
        state = all_passes_enabled()
        used = {"cls"}
        stmts: list[AnnAssign] = []
        changed = apply_box(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_unannotated(self, pass_ctx):
        fn = _make_fn([("x", None)])
        state = all_passes_enabled()
        used = {"x"}
        stmts: list[AnnAssign] = []
        changed = apply_box(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_when_pass_disabled(self, pass_ctx):
        fn = _make_fn([("x", _name("int64"))])
        state = all_passes_disabled()
        used = {"x"}
        stmts: list[AnnAssign] = []
        changed = apply_box(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_multiple_params_mixed(self, pass_ctx):
        fn = _make_fn([("a", _name("int64")), ("b", _name("Widget")), ("c", _name("double"))])
        state = all_passes_enabled()
        used = {"a", "b", "c"}
        stmts: list[AnnAssign] = []
        changed = apply_box(fn, state, used, stmts, pass_ctx)
        assert changed is True
        assert fn.args.args[0].arg == "_a"
        assert fn.args.args[1].arg == "b"  # Widget untouched
        assert fn.args.args[2].arg == "_c"
        assert len(stmts) == 2

    def test_hidden_name_collision_avoidance(self, pass_ctx):
        fn = _make_fn([("x", _name("int64"))])
        state = all_passes_enabled()
        used = {"x", "_x"}  # _x already taken
        stmts: list[AnnAssign] = []
        apply_box(fn, state, used, stmts, pass_ctx)
        assert fn.args.args[0].arg == "__x"


class TestParamConstructContainer:
    def test_rewrites_construct_param(self, pass_ctx):
        fn = _make_fn([("xs", _subscript("CheckedList", "int64"))])
        state = all_passes_enabled()
        used = {"xs"}
        stmts: list[AnnAssign] = []
        changed = apply_construct(fn, state, used, stmts, pass_ctx)
        assert changed is True
        assert fn.args.args[0].arg == "_xs"
        assert fn.args.args[0].annotation is None
        assert len(stmts) == 1

    def test_skips_primitive(self, pass_ctx):
        fn = _make_fn([("x", _name("int64"))])
        state = all_passes_enabled()
        used = {"x"}
        stmts: list[AnnAssign] = []
        changed = apply_construct(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_passthrough_container(self, pass_ctx):
        fn = _make_fn([("xs", _subscript("Array", "int64"))])
        state = all_passes_enabled()
        used = {"xs"}
        stmts: list[AnnAssign] = []
        changed = apply_construct(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_when_disabled(self, pass_ctx):
        fn = _make_fn([("xs", _subscript("CheckedList", "int64"))])
        state = all_passes_disabled()
        used = {"xs"}
        stmts: list[AnnAssign] = []
        changed = apply_construct(fn, state, used, stmts, pass_ctx)
        assert changed is False


class TestParamCastAll:
    def test_rewrites_cast_param(self, pass_ctx):
        fn = _make_fn([("foo", _name("Widget"))])
        state = all_passes_enabled()
        used = {"foo"}
        stmts: list[AnnAssign] = []
        changed = apply_cast(fn, state, used, stmts, pass_ctx)
        assert changed is True
        assert fn.args.args[0].arg == "_foo"
        assert fn.args.args[0].annotation is None
        assert len(stmts) == 1

    def test_skips_primitive(self, pass_ctx):
        fn = _make_fn([("x", _name("int64"))])
        state = all_passes_enabled()
        used = {"x"}
        stmts: list[AnnAssign] = []
        changed = apply_cast(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_constructor(self, pass_ctx):
        fn = _make_fn([("xs", _subscript("CheckedList", "int64"))])
        state = all_passes_enabled()
        used = {"xs"}
        stmts: list[AnnAssign] = []
        changed = apply_cast(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_self(self, pass_ctx):
        fn = _make_fn([("self", _name("Widget"))])
        state = all_passes_enabled()
        used = {"self"}
        stmts: list[AnnAssign] = []
        changed = apply_cast(fn, state, used, stmts, pass_ctx)
        assert changed is False


class TestParamCastContainerPassthrough:
    def test_rewrites_passthrough_param(self, pass_ctx):
        fn = _make_fn([("xs", _subscript("Array", "int64"))])
        state = all_passes_enabled()
        used = {"xs"}
        stmts: list[AnnAssign] = []
        changed = apply_passthrough(fn, state, used, stmts, pass_ctx)
        assert changed is True
        assert fn.args.args[0].arg == "_xs"
        assert fn.args.args[0].annotation is None
        assert len(stmts) == 1

    def test_skips_construct_container(self, pass_ctx):
        fn = _make_fn([("xs", _subscript("CheckedList", "int64"))])
        state = all_passes_enabled()
        used = {"xs"}
        stmts: list[AnnAssign] = []
        changed = apply_passthrough(fn, state, used, stmts, pass_ctx)
        assert changed is False

    def test_skips_primitive(self, pass_ctx):
        fn = _make_fn([("x", _name("int64"))])
        state = all_passes_enabled()
        used = {"x"}
        stmts: list[AnnAssign] = []
        changed = apply_passthrough(fn, state, used, stmts, pass_ctx)
        assert changed is False

    @pytest.mark.parametrize("root", ["List", "Dict", "Set", "Tuple", "Array"])
    def test_all_passthrough_roots(self, pass_ctx, root):
        fn = _make_fn([("xs", _subscript(root, "int64"))])
        state = all_passes_enabled()
        used = {"xs"}
        stmts: list[AnnAssign] = []
        changed = apply_passthrough(fn, state, used, stmts, pass_ctx)
        assert changed is True
