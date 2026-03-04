"""Shared utility helpers for pass modules."""

from __future__ import annotations


def fresh_hidden_name(base_name: str, used_names: set[str]) -> str:
    """Generate a collision-free hidden parameter name by prepending underscores.

    Shifts the original parameter name behind one or more '_' prefixes,
    checking against `used_names` to avoid collisions. Adds the result
    to `used_names` before returning.
    """
    hidden = f"_{base_name}"
    while hidden in used_names:
        hidden = f"_{hidden}"
    used_names.add(hidden)
    return hidden
