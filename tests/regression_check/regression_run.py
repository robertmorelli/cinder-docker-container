#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from hashlib import sha1
from pathlib import Path
from subprocess import run, CompletedProcess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Use the existing detyper logic
from de_typer_boxunbox import CinderDetyperBoxUnbox, PASS_NAMES  # noqa: E402


def parse_plan(plan_items: list[str], detyper: CinderDetyperBoxUnbox):
    known = set(detyper.fun_names)
    selected: list[tuple[str | None, str | None]] = []
    for token in plan_items:
        if token == "__TOP_LEVEL__":
            key = (None, None)
        elif "." in token:
            antr, fun = token.split(".", 1)
            key = (antr, fun)
        else:
            key = (None, token)
        assert key in known, f"unknown plan key {key}"
        selected.append(key)
    return tuple(selected)


def perm_from_plan(detyper: CinderDetyperBoxUnbox, plan_items: list[str]):
    if len(plan_items) == 0:
        return detyper.get_fully_detyped_perm()
    selected = set(parse_plan(plan_items, detyper))
    return tuple(q in selected for q in detyper.fun_names)


def last_error(stderr: str):
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    return lines[-1] if lines else "<no stderr>"


def run_case(case: dict[str, Any], root: Path, python_bin: str, scratch: str) -> tuple[bool, str]:
    name = case["name"]
    file_path = (root / case["file"]).resolve()
    enabled_passes = tuple(case.get("enabled_passes", []))
    
    # 1. Transform
    detyper = CinderDetyperBoxUnbox(
        benchmark_file_name=str(file_path),
        python=python_bin,
        scratch_dir=scratch,
        params=(),
    )
    plan_items = list(case.get("plan", []))
    perm = perm_from_plan(detyper, plan_items)

    try:
        detyper.write_permutation(perm, enabled_pass_names=enabled_passes)
    except Exception as exc:
        return False, f"transform_fail: {exc}"

    # 2. Typecheck (Static)
    typecheck_res = detyper.execute_typecheck_permutation(perm)
    if typecheck_res.returncode != 0:
        return False, f"typecheck_fail: {last_error(typecheck_res.stderr)}"
    
    # 3. Run (Dynamic) - THIS IS THE NEW PART
    # We execute the transformed file to ensure it doesn't crash at runtime.
    run_res = detyper.execute_permutation(perm)
    if run_res.returncode != 0:
        return False, f"runtime_fail: {last_error(run_res.stderr)}"

    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="tests/regression_check/manifest.json")
    default_python = "/cinder/python"
    if not os.path.exists(default_python):
        default_python = sys.executable

    parser.add_argument("--python", default=default_python)
    parser.add_argument("--scratch", default="/tmp/mirror_run_check")
    parser.add_argument("cases", nargs="*")
    args = parser.parse_args()

    manifest_path = (REPO_ROOT / args.manifest).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    
    selected = []
    requested = set(args.cases)
    for case in data:
        if not requested or case["name"] in requested:
            selected.append(case)

    case_results = []
    failures = []
    root = manifest_path.parent
    
    print(f"Running {len(selected)} cases (Transform + Typecheck + Runtime)...")

    for case in selected:
        name = case["name"]
        ok, detail = run_case(case, root, args.python, args.scratch)
        status = "PASS" if ok else "FAIL"
        print(f"{name}: {status} ({detail})")
        case_results.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            failures.append((name, detail))

    if failures:
        print(f"\n{len(failures)} cases failed.")
        return 1
    
    print("\nAll cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
