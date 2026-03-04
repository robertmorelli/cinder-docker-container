from ast import (
    parse,
    dump as ast_dump,
    unparse,
    FunctionDef,
    AsyncFunctionDef,
    ClassDef,
    AnnAssign,
    Assign,
    expr,
    Name,
    iter_child_nodes,
    AST,
    fix_missing_locations,
    NodeTransformer,
    NodeVisitor,
    Import,
    ImportFrom,
    Constant,
    Call,
    Attribute,
    Load,
    Store,
    alias,
    Return,
    Starred,
    Subscript,
    Tuple as AstTuple,
    BinOp,
    BitOr,
)
from functools import cache
from itertools import chain
from random import sample
from subprocess import run, CompletedProcess
from time import perf_counter
from multiprocessing import Pool, cpu_count
from datetime import datetime
from json import dump
from builtins import __dict__ as btn_dict
from multiprocessing import Value, Lock
from time import sleep
from os import path, makedirs, environ
from copy import deepcopy
from hashlib import sha1
from typing import Tuple as TypingTuple
from argparse import ArgumentParser
from metadata.detype_metadata import DetypeMetadata
from passes import PARAM_PASS_APPLIERS, BODY_PASS_APPLIERS, RETURN_PASS_APPLIERS
from passes.context import PassContext
from passes.cleanup_inline import cleanup_inline_function
from passes.cleanup_wrappers import RedundantWrapperCleaner
from passes.wrappers import (
    is_box_call,
    coerce_primitive,
    wrap_construct,
    wrap_scalar_construct,
    ensure_static_imports,
)
from passes.decider import (
    decide_body_strategy,
    decide_param_strategy,
    decide_return_strategy,
    annotation_policy,
    pass_name_for_annotation,
    is_optional_or_union_annotation,
    is_passthrough_container_annotation,
    is_primitive_annotation,
    is_dynamic_annotation,
    is_none_annotation,
    is_constructor_annotation,
)
from passes.bins import (
    box_primitive_type_order,
    box_primitive_types,
    explicit_cast_type_order,
    scalar_construct_type_order,
    scalar_construct_types,
    container_construct_type_order,
    container_passthrough_type_order,
    container_construct_types,
    container_passthrough_types,
    BOX_LOGIC_BIN,
    CONSTRUCT_LOGIC_BIN,
    CAST_LOGIC_BIN,
    CAST_CONTAINER_PASSTHROUGH_LOGIC_BIN,
    NONE_LOGIC_BIN,
)

try:
    import black
except Exception:
    black = None


def split_lines(src: str) -> str:
    if black is None:
        return src
    return black.format_str(src, mode=black.Mode(line_length=1))


Permutation = TypingTuple[bool, ...]
GuideKey = tuple[str | None, str | None]
PassState = dict[str, bool]
GuideType = dict[GuideKey, PassState]

PASS_SCOPE_PARAM = "param"
PASS_SCOPE_BODY = "body"
PASS_SCOPE_RETURN = "return"
PASS_SCOPES = (PASS_SCOPE_PARAM, PASS_SCOPE_BODY, PASS_SCOPE_RETURN)

# Known limitations (intentional guardrails for deterministic correctness checks).
TRANSFORM_LIMITATIONS = (
    "class_members: body detyping never rewrites self.<field> declarations, reads, or writes",
    "top_level: module AnnAssign body detyping is always forced typed (plan keeps TOP_LEVEL bit)",
    "decl_only_annassign: body detyping skips declaration-only locals (`x: T`) to avoid dynamic seed / undefined-name edge cases",
    "vararg_param: detyping annotated *args/**kwargs parameters is unsupported",
    "starred_boundary_call: call-boundary rewrite does not support *args/**kwargs expansion at rewritten call sites",
    "body_cast_all: Optional[...] and union annotations are skipped (flow narrowing unsupported)",
    "nogo_types: Iterator/Iterable/Generator/Async*/Coroutine/Protocol/Callable annotations are never detyped",
    "imported_nominal_cast: cast(Name|module.Type, dyn) for imported nominal types is not reliably supported by the static compiler",
    "ambiguous_method_names: unresolved attribute calls are not boundary-rewritten when a method name appears in multiple unrelated class hierarchies",
)

def _sanitize_pass_token(name: str) -> str:
    out = []
    previous_underscore = False
    for ch in name:
        if ch.isalnum():
            out.append(ch.lower())
            previous_underscore = False
        else:
            if not previous_underscore:
                out.append("_")
                previous_underscore = True
    token = "".join(out).strip("_")
    assert token != "", f"invalid pass token: {name!r}"
    return token


TYPE_BIN_SPECS: tuple[tuple[str, str], ...] = (
    ("box", BOX_LOGIC_BIN),
    ("construct", CONSTRUCT_LOGIC_BIN),
    ("cast", CAST_LOGIC_BIN),
    ("cast", CAST_CONTAINER_PASSTHROUGH_LOGIC_BIN),
    ("detype", NONE_LOGIC_BIN),
)

PASS_SPECS: tuple[tuple[str, str, str, str], ...] = tuple(
    (
        scope_name,
        policy_name,
        bin_name,
        f"{scope_name}_{policy_name}_{bin_name}",
    )
    for scope_name in PASS_SCOPES
    for policy_name, bin_name in TYPE_BIN_SPECS
)
PASS_NAMES: tuple[str, ...] = tuple(pass_name for _, _, _, pass_name in PASS_SPECS)
PASS_NAME_LOOKUP: dict[tuple[str, str, str], str] = dict(
    ((scope_name, policy_name, bin_name), pass_name)
    for scope_name, policy_name, bin_name, pass_name in PASS_SPECS
)
PASS_NAMES_BY_SCOPE: dict[str, tuple[str, ...]] = dict(
    (
        scope_name,
        tuple(pass_name for pass_scope, _, _, pass_name in PASS_SPECS if pass_scope == scope_name),
    )
    for scope_name in PASS_SCOPES
)
PASS_COUNT = len(PASS_NAMES)


def is_builtin_class_name(name: str):
    return name in btn_dict and isinstance(btn_dict[name], type)


TIME = False
TOP_LEVEL = (None, None)


class Timer:
    def __init__(self, name):
        self.name = name
        self.start = perf_counter() if TIME else 0

    def end(self):
        if TIME:
            dt = perf_counter() - self.start
            print(f"{self.name}: {dt:.6f}s")


class PermutationLocker:
    _g_counter = None
    _g_lock = None

    @staticmethod
    def _init_worker(counter, lock):
        PermutationLocker._g_counter = counter
        PermutationLocker._g_lock = lock

    @staticmethod
    def run_perm_worker(args):
        me, perm = args
        stderr = me.run_permutation(perm)
        with PermutationLocker._g_lock:
            PermutationLocker._g_counter.value += 1
        return CinderDetyperBoxUnbox._perm_name(perm), stderr


class CinderDetyperBoxUnbox:
    permutation_to_result = dict()

    def __init__(
        self,
        benchmark_file_name: str,
        python: str,
        scratch_dir: str,
        params: tuple[str, ...] = (),
        strict_limitations: bool = False,
    ):
        t1 = Timer("init")
        self.params = params
        self.python = python
        self.benchmark_file_name = benchmark_file_name
        self.scratch_dir = scratch_dir
        self.strict_limitations = strict_limitations
        self.benchmark_dir = path.dirname(path.abspath(benchmark_file_name))

        t2 = Timer("enumerate")
        self.metadata = DetypeMetadata.build(self._read_ast(), TOP_LEVEL)
        self.class_antrs = self.metadata.class_antrs
        self.fun_names = self.metadata.fun_names
        self.ambiguous_method_names = self.metadata.ambiguous_method_names
        self.plan_names = self.metadata.plan_names
        assert len(self.plan_names) <= len(self.fun_names), "plan name enumeration mismatch"
        t2.end()
        t1.end()

    def _strict_fail(self, limitation_name: str, detail: str):
        if not self.strict_limitations:
            return
        assert False, f"strict limitation hit [{limitation_name}]: {detail}"

    def fun_count(self):
        return len(self.fun_names)

    def pass_count(self):
        return PASS_COUNT

    def plan_bit_count(self):
        return len(self.plan_names)

    @staticmethod
    @cache
    def read_text(file_name):
        with open(file_name, encoding="utf-8") as f:
            return f.read()
        raise RuntimeError("python file not found")

    @cache
    def _read_ast(self):
        return parse(CinderDetyperBoxUnbox.read_text(self.benchmark_file_name), type_comments=True)

    def _detype_funs(self, tree: AST, guide: GuideType) -> str:
        from transformer import detype_funs
        return detype_funs(
            tree,
            guide,
            class_antrs=self.class_antrs,
            fun_names=self.fun_names,
            ambiguous_method_names=self.ambiguous_method_names,
            benchmark_file_name=self.benchmark_file_name,
            strict_limitations=self.strict_limitations,
            format_source=split_lines,
        )

    @cache
    @staticmethod
    def _perm_name(perm: Permutation) -> str:
        return hex(int("".join(str(int(b)) for b in perm), 2))

    @staticmethod
    def _all_pass_state(value: bool) -> PassState:
        return dict((pass_name, value) for pass_name in PASS_NAMES)

    @staticmethod
    def _pass_state_from_enabled_passes(enabled_pass_names: tuple[str, ...] | None) -> PassState:
        if enabled_pass_names is None:
            return CinderDetyperBoxUnbox._all_pass_state(True)
        unknown = tuple(pass_name for pass_name in enabled_pass_names if pass_name not in PASS_NAMES)
        assert len(unknown) == 0, f"unknown pass names: {unknown}"
        enabled_set = set(enabled_pass_names)
        return dict((pass_name, pass_name in enabled_set) for pass_name in PASS_NAMES)

    def _base_guide(self, value: bool) -> GuideType:
        return dict((q_fun_name, CinderDetyperBoxUnbox._all_pass_state(value)) for q_fun_name in self.fun_names)

    def _guide_from_fun_permutation(self, perm: Permutation, enabled_pass_names: tuple[str, ...] | None = None) -> GuideType:
        assert len(perm) == self.fun_count(), f"function permutation length mismatch: {len(perm)} vs {self.fun_count()}"
        disabled_pass_state = CinderDetyperBoxUnbox._all_pass_state(False)
        enabled_pass_state = CinderDetyperBoxUnbox._pass_state_from_enabled_passes(enabled_pass_names)
        plan_enabled = dict((q_fun_name, perm[i]) for i, q_fun_name in enumerate(self.fun_names))
        guide = {}
        for q_fun_name in self.fun_names:
            antr_name, fun_name = q_fun_name
            is_ambiguous_method = antr_name is not None and fun_name in self.ambiguous_method_names
            if is_ambiguous_method:
                if plan_enabled[q_fun_name]:
                    self._strict_fail("ambiguous_method_names", f"plan selected ambiguous method: {q_fun_name}")
                guide[q_fun_name] = dict(disabled_pass_state)
            else:
                guide[q_fun_name] = dict(enabled_pass_state if plan_enabled[q_fun_name] else disabled_pass_state)
        # Keep top-level in the plan bitset, but force module body detyping off.
        if TOP_LEVEL in guide:
            guide[TOP_LEVEL] = dict(disabled_pass_state)
        return guide

    def _guide_from_permutation(self, perm: Permutation, enabled_pass_names: tuple[str, ...] | None = None) -> GuideType:
        assert len(perm) == self.fun_count(), f"permutation length mismatch: {len(perm)} vs {self.fun_count()}"
        return self._guide_from_fun_permutation(perm, enabled_pass_names=enabled_pass_names)

    @cache
    def _perm_from_name(self, perm_str: str) -> Permutation:
        n = int(perm_str, 16)
        bits = bin(n)[2:].ljust(self.fun_count(), "0")
        return tuple(c == "1" for c in bits)

    @cache
    @staticmethod
    def file_trunc(file_name: str):
        trunc_name, *xts = file_name.split(".")
        assert len(xts) < 2, "multiple extensions not supported"
        assert len(xts) > 0, "extensionless files not supported"
        assert xts[0] == "py", "only '.py' files supported"
        return trunc_name

    @cache
    @staticmethod
    def q_file_trunc(perm: Permutation, file_name: str):
        trunc_name = CinderDetyperBoxUnbox.file_trunc(path.basename(file_name))
        bit_string = "".join("1" if b else "0" for b in perm)
        digest = sha1(bit_string.encode("ascii")).hexdigest()[:16]
        perm_string = f"p{len(perm)}_{digest}"
        return f"{trunc_name}_{perm_string}"

    def _detype_by_permutation(self, perm: Permutation, enabled_pass_names: tuple[str, ...] | None = None) -> str:
        tree = deepcopy(self._read_ast())
        guide: GuideType = self._guide_from_permutation(perm, enabled_pass_names=enabled_pass_names)
        return self._detype_funs(tree, guide)

    def perm_file_name(self, perm: Permutation):
        benchmark_name = path.basename(path.dirname(self.benchmark_dir))
        level_name = path.basename(self.benchmark_dir)
        file_stem = CinderDetyperBoxUnbox.q_file_trunc(perm, self.benchmark_file_name)
        return f"{self.scratch_dir}/{benchmark_name}_{level_name}_{file_stem}.py"

    def _ensure_scratch_dir(self):
        makedirs(self.scratch_dir, exist_ok=True)

    def write_permutation_hex(self, perm_str: str):
        self.write_permutation(self._perm_from_name(perm_str))

    def execute_permutation_hex(self, perm_str: str):
        return self.execute_permutation(self._perm_from_name(perm_str))

    def run_permutation_hex(self, perm_str: str):
        return self.run_permutation(self._perm_from_name(perm_str))

    def write_permutation(self, perm: Permutation, enabled_pass_names: tuple[str, ...] | None = None):
        self._ensure_scratch_dir()
        t1 = Timer("retype")
        new_file_string = self._detype_by_permutation(perm, enabled_pass_names=enabled_pass_names)
        new_file_name = self.perm_file_name(perm)
        t1.end()
        t2 = Timer("write file")
        with open(new_file_name, mode="w", encoding="utf-8") as f:
            f.write(new_file_string)
        t2.end()

    def _run_env(self):
        env = dict(environ)
        py_paths = [self.benchmark_dir]
        current = env.get("PYTHONPATH")
        if current:
            py_paths.append(current)
        env["PYTHONPATH"] = ":".join(py_paths)
        return env

    def execute_typecheck_permutation(self, perm: Permutation):
        file_name = self.perm_file_name(perm)
        t3 = Timer("run typecheck")
        cmd = " ".join(
            (
                self.python,
                "-m cinderx.compiler",
                "--static",
                "-c",
                file_name,
            )
        )
        result = run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            cwd=self.benchmark_dir,
            env=self._run_env(),
        )
        t3.end()
        return result

    def execute_permutation(self, perm: Permutation):
        file_name = self.perm_file_name(perm)
        t3 = Timer("run cmd")
        cmd = " ".join(
            (
                self.python,
                "-X jit",
                "-X jit-enable-jit-list-wildcards",
                "-X jit-shadow-frame",
                file_name,
                *self.params,
            )
        )
        result = run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            cwd=self.benchmark_dir,
            env=self._run_env(),
        )
        t3.end()
        return result

    def run_permutation(self, perm: Permutation, enabled_pass_names: tuple[str, ...] | None = None) -> CompletedProcess[str]:
        self.write_permutation(perm, enabled_pass_names=enabled_pass_names)
        typecheck_result = self.execute_typecheck_permutation(perm)
        if typecheck_result.returncode != 0:
            return typecheck_result
        return self.execute_permutation(perm)

    def _get_prep_perm(self, preportion: float):
        typed_count = self.fun_count() * preportion
        typed_count = round(typed_count)
        untyped_count = self.fun_count() - typed_count
        return tuple(sample((False, True), counts=(typed_count, untyped_count), k=self.fun_count()))

    @staticmethod
    def _collect_failure_stats(results: dict[str, CompletedProcess[str]]):
        counts = {}
        unknown = []
        success_count = 0
        successes = []
        failures = []

        for perm, result in results.items():
            stderr = result.stderr
            if result.returncode == 0:
                success_count += 1
                successes.append(perm)
                continue

            err_name = "<unknown>"
            if stderr:
                lines = stderr.strip().splitlines()
                err_name = lines[-1].split(":")[0] if lines else "<unknown>"
            if err_name == "<unknown>":
                unknown.append(stderr)

            counts[err_name] = counts.get(err_name, 0) + 1
            failures.append(str((perm, err_name)))

        return unknown, counts, success_count, successes, failures

    @staticmethod
    def _make_info_dump(results: dict[str, CompletedProcess[str]]):
        return dict(
            (perm_name, {"returncode": out.returncode, "stdout": out.stdout, "stderr": out.stderr})
            for perm_name, out in results.items()
        )

    def find_permutation_errors(self, samples=2, granularity=1):
        self._ensure_scratch_dir()

        def xp_gen():
            yield self._get_prep_perm(1.0)
            yield self._get_prep_perm(0.0)
            for i in range(1, self.fun_count(), granularity):
                preportion = i / self.fun_count()
                for _ in range(samples):
                    yield self._get_prep_perm(preportion)

        xps = tuple(xp_gen())
        task_args = tuple(reversed(tuple(map(tuple, zip((self,) * len(xps), xps)))))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trunk = CinderDetyperBoxUnbox.file_trunc(path.basename(self.benchmark_file_name))
        results_file_name = f"results_BOXUNBOX_{trunk}_{stamp}_samples_{samples}_granularity_{granularity}.json"

        total = len(task_args)
        counter = Value("i", 0)
        lock = Lock()
        print(f"deploying {total} tasks")
        results = dict()

        with Pool(cpu_count(), initializer=PermutationLocker._init_worker, initargs=(counter, lock)) as pool:
            async_res = pool.map_async(PermutationLocker.run_perm_worker, task_args)
            bar_width = 10
            while not async_res.ready():
                done = counter.value
                frac = done / total
                filled = int(frac * bar_width)
                print(
                    f"\r[{'#' * filled}{'-' * (bar_width - filled)}] {done}/{total} {round(10000 * (done/total)) / 100}%",
                    end="",
                    flush=True,
                )
                sleep(0.1)
            print(f"\r[{'#' * bar_width}] {total}/{total} 100%", end="", flush=True)
            print()
            results = dict(async_res.get())

        unknowns, failure_stats, success_count, successes, failures = CinderDetyperBoxUnbox._collect_failure_stats(results)

        total = len(results)
        failure_count = total - success_count
        print(f"{success_count} successes, {failure_count} failures out of {total}")

        with open(results_file_name, "w", encoding="utf-8") as f:
            dump(
                {
                    "source": self.benchmark_file_name,
                    "success count": success_count,
                    "failure count": failure_count,
                    "failure stats": failure_stats,
                    "successes": successes,
                    "failures": failures,
                    "unknowns": unknowns,
                    "info_dump": CinderDetyperBoxUnbox._make_info_dump(results),
                },
                f,
                indent=2,
            )
        print(f"results in {results_file_name}")

    def get_fully_typed_perm(self):
        return tuple(False for _ in range(self.fun_count()))

    def get_fully_detyped_perm(self):
        return tuple(True for _ in range(self.fun_count()))

    def test_correctness(self):
        typed = self.run_permutation(self.get_fully_typed_perm())
        detyped = self.run_permutation(self.get_fully_detyped_perm())
        return typed, detyped

    def run_pass_only_signals(self):
        fully_detyped = self.get_fully_detyped_perm()
        cases: list[tuple[str, Permutation, tuple[str, ...] | None]] = [
            ("fully_typed", self.get_fully_typed_perm(), None),
            ("fully_detyped", fully_detyped, None),
        ]
        for pass_name in PASS_NAMES:
            cases.append((pass_name, fully_detyped, (pass_name,)))

        out: list[tuple[str, str, int, str]] = []
        for case_name, perm, enabled_pass_names in cases:
            result = self.run_permutation(perm, enabled_pass_names=enabled_pass_names)
            stderr_lines = result.stderr.strip().splitlines()
            detail = stderr_lines[-1] if len(stderr_lines) > 0 else "<no stderr>"
            if enabled_pass_names is None:
                perm_name = CinderDetyperBoxUnbox._perm_name(perm)
            else:
                perm_name = f"{CinderDetyperBoxUnbox._perm_name(perm)}+{enabled_pass_names[0]}"
            out.append((case_name, perm_name, result.returncode, detail))
        return out


def resolve_benchmark_path(benchmark_or_path: str, level: str, root: str):
    if path.isfile(benchmark_or_path):
        return benchmark_or_path
    return f"{root}/{benchmark_or_path}/{level}/main.py"


def main():
    parser = ArgumentParser()
    parser.add_argument("benchmark", help="benchmark name (e.g. deltablue) or path to main.py")
    parser.add_argument("--level", default="advanced", choices=("advanced", "shallow", "untyped"))
    parser.add_argument("--root", default="/root/static-python-perf/Benchmark")
    parser.add_argument("--python", default="/cinder/python")
    parser.add_argument("--scratch", default="/tmp/detype_boxunbox")
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--granularity", type=int, default=1)
    parser.add_argument("--param", action="append", default=[], help="benchmark runtime arg (repeatable)")
    parser.add_argument("--show-perm", type=str, default=None, help="hex permutation id to print transformed source")
    parser.add_argument("--test", action="store_true", help="run typed and fully detyped once")
    parser.add_argument("--signals", action="store_true", help="run deterministic pass-only signal report")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="assert when transform limitations are encountered instead of silently skipping",
    )
    args = parser.parse_args()

    benchmark_path = resolve_benchmark_path(args.benchmark, args.level, args.root)
    if not path.exists(benchmark_path):
        raise FileNotFoundError(f"benchmark file not found: {benchmark_path}")

    detyper = CinderDetyperBoxUnbox(
        benchmark_file_name=benchmark_path,
        python=args.python,
        scratch_dir=args.scratch,
        params=tuple(args.param),
        strict_limitations=args.strict,
    )

    print(f"benchmark: {benchmark_path}")
    print(f"functions: {detyper.fun_count()}")
    print(f"passes: {PASS_COUNT} ({', '.join(PASS_NAMES)})")
    print(f"plan bits: {detyper.plan_bit_count()}")
    print(f"strict: {args.strict}")

    if args.show_perm is not None:
        perm = detyper._perm_from_name(args.show_perm)
        print(detyper._detype_by_permutation(perm))
        return

    if args.test:
        typed, detyped = detyper.test_correctness()
        print(f"typed return code: {typed.returncode}")
        print(f"detyped return code: {detyped.returncode}")
        if typed.returncode != 0:
            print(typed.stderr)
        if detyped.returncode != 0:
            print(detyped.stderr)
        return

    if args.signals:
        for case_name, perm_name, return_code, detail in detyper.run_pass_only_signals():
            state = "ok" if return_code == 0 else "fail"
            print(f"{case_name}: {state} perm={perm_name}")
            if return_code != 0:
                print(f"  {detail}")
        return

    detyper.find_permutation_errors(samples=args.samples, granularity=args.granularity)


if __name__ == "__main__":
    main()
