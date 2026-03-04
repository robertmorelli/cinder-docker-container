"""Unit tests for passes/bins.py — bin definitions and disjointness."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from passes.bins import (
    BOX_LOGIC_BIN,
    CAST_CONTAINER_PASSTHROUGH_LOGIC_BIN,
    CAST_LOGIC_BIN,
    CONSTRUCT_LOGIC_BIN,
    box_primitive_type_order,
    box_primitive_types,
    cast_container_passthrough_bin_by_root,
    construct_bin_by_root,
    container_construct_type_order,
    container_construct_types,
    container_passthrough_type_order,
    container_passthrough_types,
    explicit_cast_type_order,
    explicit_cast_types,
    nogo_types,
    scalar_construct_type_order,
    scalar_construct_types,
)


class TestBinSetConsistency:
    """Frozensets match their ordered tuples."""

    def test_box_primitive_types_matches_order(self):
        assert box_primitive_types == frozenset(box_primitive_type_order)

    def test_explicit_cast_types_matches_order(self):
        assert explicit_cast_types == frozenset(explicit_cast_type_order)

    def test_scalar_construct_types_matches_order(self):
        assert scalar_construct_types == frozenset(scalar_construct_type_order)

    def test_container_construct_types_matches_order(self):
        assert container_construct_types == frozenset(container_construct_type_order)

    def test_container_passthrough_types_matches_order(self):
        assert container_passthrough_types == frozenset(container_passthrough_type_order)

    def test_order_tuples_have_no_duplicates(self):
        for name, order in [
            ("box_primitive", box_primitive_type_order),
            ("explicit_cast", explicit_cast_type_order),
            ("scalar_construct", scalar_construct_type_order),
            ("container_construct", container_construct_type_order),
            ("container_passthrough", container_passthrough_type_order),
        ]:
            assert len(order) == len(set(order)), f"duplicate in {name}"


class TestBinDisjointness:
    """No type name appears in more than one bin."""

    def test_box_disjoint_from_construct(self):
        assert box_primitive_types.isdisjoint(container_construct_types)
        assert box_primitive_types.isdisjoint(scalar_construct_types)

    def test_box_disjoint_from_passthrough(self):
        assert box_primitive_types.isdisjoint(container_passthrough_types)

    def test_box_disjoint_from_nogo(self):
        assert box_primitive_types.isdisjoint(nogo_types)

    def test_box_disjoint_from_explicit_cast(self):
        assert box_primitive_types.isdisjoint(explicit_cast_types)

    def test_construct_disjoint_from_passthrough(self):
        assert container_construct_types.isdisjoint(container_passthrough_types)

    def test_construct_disjoint_from_nogo(self):
        assert container_construct_types.isdisjoint(nogo_types)

    def test_passthrough_disjoint_from_nogo(self):
        assert container_passthrough_types.isdisjoint(nogo_types)

    def test_scalar_construct_disjoint_from_container_construct(self):
        assert scalar_construct_types.isdisjoint(container_construct_types)


class TestBinLookups:
    """Root-to-bin lookup dicts are consistent."""

    def test_construct_bin_keys_match_container_construct_types(self):
        assert set(construct_bin_by_root.keys()) == container_construct_types

    def test_construct_bin_values_are_construct_logic_bin(self):
        for root, bin_name in construct_bin_by_root.items():
            assert bin_name == CONSTRUCT_LOGIC_BIN, f"{root} maps to {bin_name}"

    def test_passthrough_bin_keys_match_container_passthrough_types(self):
        assert set(cast_container_passthrough_bin_by_root.keys()) == container_passthrough_types

    def test_passthrough_bin_values_are_passthrough_logic_bin(self):
        for root, bin_name in cast_container_passthrough_bin_by_root.items():
            assert bin_name == CAST_CONTAINER_PASSTHROUGH_LOGIC_BIN, f"{root} maps to {bin_name}"


class TestBinConstants:
    """Bin name constants are distinct strings."""

    def test_all_bin_names_distinct(self):
        names = [BOX_LOGIC_BIN, CONSTRUCT_LOGIC_BIN, CAST_LOGIC_BIN, CAST_CONTAINER_PASSTHROUGH_LOGIC_BIN]
        assert len(names) == len(set(names))

    def test_bin_names_are_nonempty_strings(self):
        for name in [BOX_LOGIC_BIN, CONSTRUCT_LOGIC_BIN, CAST_LOGIC_BIN, CAST_CONTAINER_PASSTHROUGH_LOGIC_BIN]:
            assert isinstance(name, str) and len(name) > 0


class TestBinNonEmpty:
    """Each bin category has at least one member."""

    def test_box_primitive_nonempty(self):
        assert len(box_primitive_types) > 0

    def test_container_construct_nonempty(self):
        assert len(container_construct_types) > 0

    def test_container_passthrough_nonempty(self):
        assert len(container_passthrough_types) > 0

    def test_nogo_nonempty(self):
        assert len(nogo_types) > 0

    def test_box_has_expected_members(self):
        for expected in ("int64", "int32", "double", "cbool"):
            assert expected in box_primitive_types

    def test_nogo_has_expected_members(self):
        for expected in ("Iterator", "Generator", "Callable"):
            assert expected in nogo_types

    def test_construct_has_expected_members(self):
        for expected in ("CheckedList", "CheckedDict"):
            assert expected in container_construct_types

    def test_passthrough_has_expected_members(self):
        for expected in ("Array", "List", "Dict"):
            assert expected in container_passthrough_types
