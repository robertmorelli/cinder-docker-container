"""Shared fixtures for pass unit tests."""

from __future__ import annotations

import sys
from ast import Call, Load, Name, Store, expr
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from passes.context import PassContext
from passes.decider import (
    annotation_policy,
    is_optional_or_union_annotation,
    is_passthrough_container_annotation,
    is_primitive_annotation,
    is_constructor_annotation,
    pass_name_for_annotation,
)
from de_typer_boxunbox import PASS_NAMES


def _stub_coerce_primitive(annotation: expr | None, node: expr) -> expr:
    if not is_primitive_annotation(annotation):
        return node
    return Call(func=Name(id=annotation.id, ctx=Load()), args=[node], keywords=[])


def _stub_wrap_box(node: expr) -> expr:
    return Call(func=Name(id="box", ctx=Load()), args=[node], keywords=[])


def _stub_wrap_construct(annotation: expr, node: expr) -> expr:
    return Call(func=deepcopy(annotation), args=[node], keywords=[])


def _stub_wrap_cast_or_construct(annotation: expr, node: expr) -> expr:
    return Call(
        func=Name(id="cast", ctx=Load()),
        args=[deepcopy(annotation), node],
        keywords=[],
    )


@pytest.fixture
def pass_ctx() -> PassContext:
    """A PassContext wired to real decider functions and simple stub wrappers."""
    return PassContext(
        annotation_policy=annotation_policy,
        pass_name_for_annotation=pass_name_for_annotation,
        coerce_primitive=_stub_coerce_primitive,
        wrap_construct=_stub_wrap_construct,
        wrap_cast_or_construct=_stub_wrap_cast_or_construct,
        wrap_box=_stub_wrap_box,
        is_passthrough_container_annotation=is_passthrough_container_annotation,
        is_optional_or_union_annotation=is_optional_or_union_annotation,
    )


def all_passes_enabled() -> dict[str, bool]:
    return {name: True for name in PASS_NAMES}


def all_passes_disabled() -> dict[str, bool]:
    return {name: False for name in PASS_NAMES}


def only_pass_enabled(pass_name: str) -> dict[str, bool]:
    state = all_passes_disabled()
    assert pass_name in state, f"unknown pass name: {pass_name}"
    state[pass_name] = True
    return state
