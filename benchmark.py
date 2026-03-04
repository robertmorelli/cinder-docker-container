#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Any


DEFAULT_BENCHMARKS = "deltablue,chaos,nqueens,richards,go,nbody,fannkuch"
DEFAULT_LEVEL = "advanced"
JSON_START_MARKER = "<<<BENCHMARK_JSON_START>>>"
JSON_END_MARKER = "<<<BENCHMARK_JSON_END>>>"
FLOAT_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


@dataclass
class AttemptRecord:
    attempt_num: int
    status: str  # typecheck_timeout | typecheck_fail | run_timeout | run_crash | parse_fail | success
    source: str
    tc_stdout: str
    tc_stderr: str
    run_stdout: str
    run_stderr: str
    runtime: float | None


@dataclass
class PointResult:
    detyped_count: int
    detyped_ratio: float
    target_ratio: float
    requested_samples: int
    collected_samples: int
    attempts: int
    typecheck_failures: int
    typecheck_timeouts: int
    run_failures: int
    run_timeouts: int
    parse_failures: int
    runtimes: list[float]
    attempts_log: list[AttemptRecord]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate per-proportion de_typer_boxunbox performance markdown reports. "
            "Default mode runs once inside Docker and writes markdown files on the host."
        )
    )
    parser.add_argument("--benchmarks", default=DEFAULT_BENCHMARKS, help="CSV list of benchmarks")
    parser.add_argument("--level", default=DEFAULT_LEVEL, help="Benchmark level (advanced|shallow|untyped)")
    parser.add_argument("--samples-per-point", type=int, default=2, help="Runtime samples per detyped proportion")
    parser.add_argument("--points", type=int, default=11, help="Number of proportion points from 0%% to 100%%")
    parser.add_argument(
        "--max-attempts-per-point",
        type=int,
        default=200,
        help="Maximum random attempts to gather samples per point",
    )
    parser.add_argument("--alpha", type=float, default=0.05, help="Confidence interval alpha")
    parser.add_argument("--bootstrap-resamples", type=int, default=5000, help="Bootstrap resample count")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=0.0,
        help="Per-run timeout for typecheck/runtime (0 disables timeout)",
    )
    parser.add_argument("--seed", type=int, default=int(time.time()), help="Base random seed")
    parser.add_argument("--out-dir", default="per_proportion_reports", help="Host output directory")
    parser.add_argument("--scratch-dir", default="/tmp/detype_boxunbox", help="Scratch directory inside container")
    parser.add_argument("--python-bin", default="/cinder/python", help="Python executable inside container")
    parser.add_argument("--start-script", default="start.sh", help="Path to start.sh (host mode only)")
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def parse_benchmarks(csv_value: str) -> list[str]:
    benches = [x.strip() for x in csv_value.split(",")]
    return [x for x in benches if x]


def quantile(sorted_values: list[float], q: float) -> float:
    assert 0.0 <= q <= 1.0, "q out of range"
    assert len(sorted_values) > 0, "quantile requires non-empty data"
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def bootstrap_confidence_interval(
    data: list[float], alpha: float, num_resamples: int, rng: random.Random
) -> tuple[float, float]:
    assert len(data) > 0, "bootstrap requires non-empty data"
    means: list[float] = []
    n = len(data)
    for _ in range(num_resamples):
        sample = [data[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return quantile(means, alpha / 2.0), quantile(means, 1.0 - alpha / 2.0)


def signed_rank_confidence_interval(data: list[float], alpha: float, rng: random.Random) -> tuple[float, float]:
    assert len(data) > 0, "signed rank interval requires non-empty data"
    ordered = sorted(data)
    n = len(ordered)
    ranks = list(range(1, n + 1))
    med = quantile(ordered, 0.5)
    signed_ranks = [rank if value > med else -rank for value, rank in zip(ordered, ranks)]
    sample_mean = sum(ordered) / n
    _sum_ranks = sum(signed_ranks)
    se = math.sqrt((n * (n + 1) * (2 * n + 1)) / 6.0)
    normals = sorted(rng.gauss(0.0, 1.0) for _ in range(10000))
    z_alpha = abs(quantile(normals, 1.0 - alpha / 2.0))
    low = sample_mean - (z_alpha * se / math.sqrt(24.0))
    high = sample_mean + (z_alpha * se / math.sqrt(24.0))
    return low, high


def parse_runtime_seconds(stdout: str) -> float | None:
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    if len(lines) == 0:
        return None
    for line in reversed(lines):
        matches = FLOAT_PATTERN.findall(line)
        if len(matches) == 0:
            continue
        try:
            return float(matches[-1])
        except ValueError:
            continue
    return None


def make_perm(fun_count: int, detyped_count: int, rng: random.Random) -> tuple[bool, ...]:
    assert 0 <= detyped_count <= fun_count, "detyped_count out of range"
    if detyped_count == 0:
        return tuple(False for _ in range(fun_count))
    if detyped_count == fun_count:
        return tuple(True for _ in range(fun_count))
    idxs = set(rng.sample(range(fun_count), detyped_count))
    return tuple(i in idxs for i in range(fun_count))


def run_command(
    cmd: list[str],
    cwd: str,
    env: dict[str, str],
    timeout_seconds: float,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    run_kwargs: dict[str, Any] = dict(
        args=cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if timeout_seconds > 0:
        run_kwargs["timeout"] = timeout_seconds
    try:
        result = subprocess.run(**run_kwargs)
        return result, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if len(stderr) > 0:
            stderr += "\n"
        stderr += f"TimeoutExpired: {timeout_seconds}s"
        return subprocess.CompletedProcess(cmd, 124, stdout, stderr), True


def run_typecheck(
    detyper: Any,
    perm: tuple[bool, ...],
    timeout_seconds: float,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    file_name = detyper.perm_file_name(perm)
    cmd = [
        detyper.python,
        "-m",
        "cinderx.compiler",
        "--static",
        "-c",
        file_name,
    ]
    return run_command(cmd=cmd, cwd=detyper.benchmark_dir, env=detyper._run_env(), timeout_seconds=timeout_seconds)


def run_benchmark(
    detyper: Any,
    perm: tuple[bool, ...],
    timeout_seconds: float,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    file_name = detyper.perm_file_name(perm)
    cmd = [
        detyper.python,
        "-X",
        "jit",
        "-X",
        "jit-enable-jit-list-wildcards",
        "-X",
        "jit-shadow-frame",
        file_name,
        *detyper.params,
    ]
    return run_command(cmd=cmd, cwd=detyper.benchmark_dir, env=detyper._run_env(), timeout_seconds=timeout_seconds)


def build_detyped_points(fun_count: int, points: int) -> list[tuple[int, float]]:
    assert points >= 2, "points must be >= 2"
    if fun_count == 0:
        return [(0, 0.0)]
    targets = [i / (points - 1) for i in range(points)]
    deduped: list[tuple[int, float]] = []
    seen_counts: set[int] = set()
    for target_ratio in targets:
        detyped_count = int(round(target_ratio * fun_count))
        if detyped_count in seen_counts:
            continue
        seen_counts.add(detyped_count)
        deduped.append((detyped_count, target_ratio))
    return deduped


def render_benchmark_markdown(
    bench: str,
    level: str,
    seed: int,
    samples_per_point: int,
    points: int,
    max_attempts_per_point: int,
    alpha: float,
    bootstrap_resamples: int,
    fun_count: int,
    results: list[PointResult],
    note_lines: list[str],
) -> str:
    now_utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    md: list[str] = []
    md.append(f"# Per-Proportion Performance: {bench} ({level})")
    md.append("")
    md.append(f"- generated: `{now_utc}`")
    md.append(f"- seed: `{seed}`")
    md.append(f"- samples per point: `{samples_per_point}`")
    md.append(f"- points requested: `{points}`")
    md.append(f"- max attempts per point: `{max_attempts_per_point}`")
    md.append(f"- alpha: `{alpha}`")
    md.append(f"- bootstrap resamples: `{bootstrap_resamples}`")
    md.append(f"- function count: `{fun_count}`")
    for line in note_lines:
        md.append(f"- {line}")
    md.append("")

    typed_point = next((row for row in results if row.detyped_count == 0 and row.collected_samples > 0), None)
    typed_mean = mean(typed_point.runtimes) if typed_point is not None else None

    md.append("## Results")
    md.append("")
    md.append("| Detyped Fn | Detyped % | Samples | Mean (s) | StdDev (s) | Bootstrap CI | Signed-Rank CI | Speedup vs Typed |")
    md.append("|---:|---:|---:|---:|---:|---|---|---:|")
    for row in results:
        if row.collected_samples == 0:
            md.append(
                f"| {row.detyped_count} | {row.detyped_ratio * 100:.1f}% | "
                f"0/{row.requested_samples} | N/A | N/A | N/A | N/A | N/A |"
            )
            continue
        row_mean = mean(row.runtimes)
        row_std = stdev(row.runtimes) if row.collected_samples >= 2 else 0.0
        ci_rng = random.Random(seed + row.detyped_count * 101 + 17)
        b_lo, b_hi = bootstrap_confidence_interval(
            row.runtimes,
            alpha=alpha,
            num_resamples=bootstrap_resamples,
            rng=ci_rng,
        )
        s_lo, s_hi = signed_rank_confidence_interval(row.runtimes, alpha=alpha, rng=ci_rng)
        if typed_mean is not None and row_mean > 0:
            speedup_txt = f"{typed_mean / row_mean:.3f}x"
        else:
            speedup_txt = "N/A"
        md.append(
            "| "
            f"{row.detyped_count} | {row.detyped_ratio * 100:.1f}% | "
            f"{row.collected_samples}/{row.requested_samples} | "
            f"{row_mean:.6f} | {row_std:.6f} | "
            f"[{b_lo:.6f}, {b_hi:.6f}] | [{s_lo:.6f}, {s_hi:.6f}] | {speedup_txt} |"
        )

    md.append("")
    md.append("## Diagnostics")
    md.append("")
    md.append("| Detyped Fn | Attempts | Typecheck Fails | Typecheck Timeouts | Run Fails | Run Timeouts | Parse Fails |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|")
    for row in results:
        md.append(
            f"| {row.detyped_count} | {row.attempts} | {row.typecheck_failures} | "
            f"{row.typecheck_timeouts} | {row.run_failures} | {row.run_timeouts} | {row.parse_failures} |"
        )
    md.append("")
    md.append("Notes:")
    md.append("- Runtime is parsed from each benchmark's own printed timing output (last float in stdout).")
    md.append("- Detyped proportion is sampled by selecting exactly K detyped functions at each point.")
    md.append("- `Speedup vs Typed` uses the 0-detyped mean runtime as baseline (`typed_mean / point_mean`).")
    return "\n".join(md)


def run_one_inside(
    bench: str,
    level: str,
    seed: int,
    samples_per_point: int,
    points: int,
    max_attempts_per_point: int,
    alpha: float,
    bootstrap_resamples: int,
    scratch_dir: str,
    python_bin: str,
    timeout_seconds: float,
) -> tuple[str, str]:
    tools_dir = "/cinder/Tools/benchmarks"
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from de_typer_boxunbox import CinderDetyperBoxUnbox

    benchmark_path = f"/root/static-python-perf/Benchmark/{bench}/{level}/main.py"
    if not Path(benchmark_path).exists():
        body = "\n".join(
            [
                f"# Per-Proportion Performance: {bench} ({level})",
                "",
                "## Status",
                "",
                f"- missing benchmark file: `{benchmark_path}`",
            ]
        )
        return "missing", body, {}

    detyper = CinderDetyperBoxUnbox(
        benchmark_file_name=benchmark_path,
        python=python_bin,
        scratch_dir=scratch_dir,
        params=(),
    )
    fun_count = detyper.fun_count()
    note_lines: list[str] = []
    if timeout_seconds > 0:
        note_lines.append(f"per-run timeout enabled: `{timeout_seconds}s`")

    typed_perm = detyper.get_fully_typed_perm()
    detyper.write_permutation(typed_perm)
    typed_tc, typed_tc_timeout = run_typecheck(detyper, typed_perm, timeout_seconds=timeout_seconds)
    if typed_tc_timeout:
        body = "\n".join(
            [
                f"# Per-Proportion Performance: {bench} ({level})",
                "",
                "## Status",
                "",
                f"- baseline typed typecheck timed out after `{timeout_seconds}s`",
            ]
        )
        return "failed", body, {}
    if typed_tc.returncode != 0:
        tail = [ln.strip() for ln in typed_tc.stderr.splitlines() if ln.strip()]
        err_tail = tail[-1] if len(tail) > 0 else "<no stderr>"
        body = "\n".join(
            [
                f"# Per-Proportion Performance: {bench} ({level})",
                "",
                "## Status",
                "",
                "- baseline typed typecheck failed",
                f"- error: `{err_tail}`",
            ]
        )
        return "failed", body, {}

    results: list[PointResult] = []
    detyped_points = build_detyped_points(fun_count=fun_count, points=points)
    total_points = len(detyped_points)
    rng = random.Random(seed)
    for pt_idx, (detyped_count, target_ratio) in enumerate(detyped_points, start=1):
        point_rng = random.Random(rng.randrange(1 << 62))
        attempts = 0
        tc_fail = 0
        tc_timeout = 0
        run_fail = 0
        run_timeout = 0
        parse_fail = 0
        runtimes: list[float] = []
        seen_perm_names: set[str] = set()
        attempts_log: list[AttemptRecord] = []

        print(
            f"  point {pt_idx}/{total_points}  detyped={detyped_count}/{fun_count}"
            f" ({target_ratio * 100:.0f}%)  need={samples_per_point} sample(s)",
            file=sys.stderr, flush=True,
        )
        while len(runtimes) < samples_per_point and attempts < max_attempts_per_point:
            attempts += 1
            perm = make_perm(fun_count=fun_count, detyped_count=detyped_count, rng=point_rng)
            if detyped_count not in (0, fun_count):
                perm_name = CinderDetyperBoxUnbox._perm_name(perm)
                if perm_name in seen_perm_names:
                    continue
                seen_perm_names.add(perm_name)

            detyper.write_permutation(perm)
            source = Path(detyper.perm_file_name(perm)).read_text(encoding="utf-8", errors="replace")

            print(f"    attempt {attempts}: static typecheck...", end=" ", file=sys.stderr, flush=True)
            tc_res, tc_did_timeout = run_typecheck(detyper, perm, timeout_seconds=timeout_seconds)
            if tc_did_timeout:
                tc_timeout += 1
                print("TIMEOUT", file=sys.stderr, flush=True)
                attempts_log.append(AttemptRecord(
                    attempt_num=attempts, status="typecheck_timeout", source=source,
                    tc_stdout="", tc_stderr=tc_res.stderr, run_stdout="", run_stderr="", runtime=None,
                ))
                continue
            if tc_res.returncode != 0:
                tc_fail += 1
                err_lines = [l.strip() for l in tc_res.stderr.splitlines() if l.strip()]
                reason = err_lines[-1] if err_lines else "no stderr"
                print(f"FAIL (exit {tc_res.returncode}): {reason}", file=sys.stderr, flush=True)
                attempts_log.append(AttemptRecord(
                    attempt_num=attempts, status="typecheck_fail", source=source,
                    tc_stdout=tc_res.stdout, tc_stderr=tc_res.stderr, run_stdout="", run_stderr="", runtime=None,
                ))
                continue

            print(f"ok  JIT execute benchmark ({bench})...", end=" ", file=sys.stderr, flush=True)
            run_res, run_did_timeout = run_benchmark(detyper, perm, timeout_seconds=timeout_seconds)
            if run_did_timeout:
                run_timeout += 1
                print("TIMEOUT", file=sys.stderr, flush=True)
                attempts_log.append(AttemptRecord(
                    attempt_num=attempts, status="run_timeout", source=source,
                    tc_stdout=tc_res.stdout, tc_stderr=tc_res.stderr, run_stdout="", run_stderr=run_res.stderr, runtime=None,
                ))
                continue
            if run_res.returncode != 0:
                run_fail += 1
                print(f"CRASHED (exit {run_res.returncode})", file=sys.stderr, flush=True)
                attempts_log.append(AttemptRecord(
                    attempt_num=attempts, status="run_crash", source=source,
                    tc_stdout=tc_res.stdout, tc_stderr=tc_res.stderr, run_stdout=run_res.stdout, run_stderr=run_res.stderr, runtime=None,
                ))
                continue

            runtime = parse_runtime_seconds(run_res.stdout)
            if runtime is None:
                parse_fail += 1
                print("PARSE FAIL (no float found in stdout)", file=sys.stderr, flush=True)
                attempts_log.append(AttemptRecord(
                    attempt_num=attempts, status="parse_fail", source=source,
                    tc_stdout=tc_res.stdout, tc_stderr=tc_res.stderr, run_stdout=run_res.stdout, run_stderr=run_res.stderr, runtime=None,
                ))
                continue
            runtimes.append(runtime)
            print(f"{runtime:.3f}s  [sample {len(runtimes)}/{samples_per_point}]", file=sys.stderr, flush=True)
            attempts_log.append(AttemptRecord(
                attempt_num=attempts, status="success", source=source,
                tc_stdout=tc_res.stdout, tc_stderr=tc_res.stderr, run_stdout=run_res.stdout, run_stderr=run_res.stderr, runtime=runtime,
            ))

        print(
            f"  point {pt_idx}/{total_points} done:"
            f" {len(runtimes)}/{samples_per_point} samples  ({attempts} attempts)",
            file=sys.stderr, flush=True,
        )
        results.append(
            PointResult(
                detyped_count=detyped_count,
                detyped_ratio=(detyped_count / fun_count) if fun_count > 0 else 0.0,
                target_ratio=target_ratio,
                requested_samples=samples_per_point,
                collected_samples=len(runtimes),
                attempts=attempts,
                typecheck_failures=tc_fail,
                typecheck_timeouts=tc_timeout,
                run_failures=run_fail,
                run_timeouts=run_timeout,
                parse_failures=parse_fail,
                runtimes=runtimes,
                attempts_log=attempts_log,
            )
        )

    report_status = "ok"
    if any(row.collected_samples == 0 for row in results):
        report_status = "partial"
    markdown = render_benchmark_markdown(
        bench=bench,
        level=level,
        seed=seed,
        samples_per_point=samples_per_point,
        points=points,
        max_attempts_per_point=max_attempts_per_point,
        alpha=alpha,
        bootstrap_resamples=bootstrap_resamples,
        fun_count=fun_count,
        results=results,
        note_lines=note_lines,
    )
    artifacts: dict[str, Any] = {}
    for pt_idx, (result, (detyped_count, target_ratio)) in enumerate(zip(results, detyped_points), start=1):
        point_folder = (
            f"point_{pt_idx:02d}_detyped{result.detyped_count:03d}of{fun_count}"
            f"_{int(target_ratio * 100):03d}pct"
        )
        artifacts[point_folder] = {}
        for rec in result.attempts_log:
            attempt_folder = f"attempt_{rec.attempt_num:03d}_{rec.status}"
            artifacts[point_folder][attempt_folder] = {
                "source.py": rec.source,
                "typecheck_stdout.txt": rec.tc_stdout,
                "typecheck_stderr.txt": rec.tc_stderr,
                "run_stdout.txt": rec.run_stdout,
                "run_stderr.txt": rec.run_stderr,
                "status.txt": f"status: {rec.status}\nruntime: {rec.runtime}\n",
            }

    return report_status, markdown, artifacts


def run_inside(args: argparse.Namespace) -> None:
    reports: dict[str, str] = {}
    statuses: dict[str, str] = {}
    all_artifacts: dict[str, Any] = {}
    benches = parse_benchmarks(args.benchmarks)
    total_benches = len(benches)

    print(
        f"benchmarks={total_benches}  level={args.level}"
        f"  points={args.points}  samples/point={args.samples_per_point}"
        f"  max-attempts={args.max_attempts_per_point}"
        + (f"  timeout={args.timeout_seconds}s" if args.timeout_seconds > 0 else "  timeout=off"),
        file=sys.stderr, flush=True,
    )

    for idx, bench in enumerate(benches, start=1):
        print(f"\n[{idx}/{total_benches}] {bench}", file=sys.stderr, flush=True)
        bench_seed = args.seed + idx
        status, report, bench_artifacts = run_one_inside(
            bench=bench,
            level=args.level,
            seed=bench_seed,
            samples_per_point=args.samples_per_point,
            points=args.points,
            max_attempts_per_point=args.max_attempts_per_point,
            alpha=args.alpha,
            bootstrap_resamples=args.bootstrap_resamples,
            scratch_dir=args.scratch_dir,
            python_bin=args.python_bin,
            timeout_seconds=args.timeout_seconds,
        )
        statuses[bench] = status
        reports[f"{bench}.{args.level}.md"] = report
        all_artifacts[bench] = bench_artifacts

    lines: list[str] = []
    lines.append("# Per-Proportion Performance Reports")
    lines.append("")
    lines.append("- generated by `benchmark.py`")
    lines.append(f"- level: `{args.level}`")
    lines.append(f"- samples per point: `{args.samples_per_point}`")
    lines.append(f"- points: `{args.points}`")
    lines.append(f"- max attempts per point: `{args.max_attempts_per_point}`")
    lines.append(f"- alpha: `{args.alpha}`")
    lines.append(f"- bootstrap resamples: `{args.bootstrap_resamples}`")
    lines.append(f"- timeout seconds: `{args.timeout_seconds}`")
    lines.append(f"- seed: `{args.seed}`")
    lines.append("")
    lines.append("## Reports")
    lines.append("")
    for bench in benches:
        suffix = ""
        status = statuses.get(bench, "unknown")
        if status != "ok":
            suffix = f" ({status})"
        lines.append(f"- [{bench}]({bench}.{args.level}.md){suffix}")
    reports["README.md"] = "\n".join(lines)

    payload = {"reports": reports, "statuses": statuses, "artifacts": all_artifacts}
    print(JSON_START_MARKER)
    print(json.dumps(payload))
    print(JSON_END_MARKER)


def build_inside_cmd(args: argparse.Namespace, start_script: Path) -> list[str]:
    return [
        "bash",
        str(start_script),
        args.python_bin,
        "-",
        "--inside",
        "--benchmarks",
        args.benchmarks,
        "--level",
        args.level,
        "--samples-per-point",
        str(args.samples_per_point),
        "--points",
        str(args.points),
        "--max-attempts-per-point",
        str(args.max_attempts_per_point),
        "--alpha",
        str(args.alpha),
        "--bootstrap-resamples",
        str(args.bootstrap_resamples),
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--seed",
        str(args.seed),
        "--scratch-dir",
        args.scratch_dir,
        "--python-bin",
        args.python_bin,
    ]


def parse_inner_payload(stdout: str) -> dict[str, Any]:
    start_idx = stdout.find(JSON_START_MARKER)
    end_idx = stdout.rfind(JSON_END_MARKER)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise ValueError("Could not find JSON payload markers in inner runner output")
    payload_text = stdout[start_idx + len(JSON_START_MARKER):end_idx].strip()
    return json.loads(payload_text)


def run_host(args: argparse.Namespace) -> int:
    start_script = Path(args.start_script)
    if not start_script.is_absolute():
        start_script = Path(__file__).resolve().parent / start_script
    if not start_script.exists():
        print(f"missing start script: {start_script}", file=sys.stderr)
        return 2

    self_source = Path(__file__).read_text(encoding="utf-8")
    cmd = build_inside_cmd(args=args, start_script=start_script)
    env = dict(os.environ)
    env.setdefault("START_SKIP_BUILD", "1")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,  # inherit: progress streams to terminal in real time
        text=True,
        env=env,
    )
    stdout_data, _ = proc.communicate(input=self_source)
    if proc.returncode != 0:
        if stdout_data.strip():
            print(stdout_data.strip(), file=sys.stderr)
        return proc.returncode

    payload = parse_inner_payload(stdout_data)
    reports = payload["reports"]
    artifacts = payload.get("artifacts", {})

    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    out_dir = Path(args.out_dir).resolve() / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    for file_name, body in reports.items():
        (out_dir / file_name).write_text(body + "\n", encoding="utf-8")

    for bench_name, bench_artifacts in artifacts.items():
        for point_folder, point_data in bench_artifacts.items():
            for attempt_folder, attempt_files in point_data.items():
                attempt_dir = out_dir / bench_name / point_folder / attempt_folder
                attempt_dir.mkdir(parents=True, exist_ok=True)
                for file_name, content in attempt_files.items():
                    (attempt_dir / file_name).write_text(content, encoding="utf-8")

    cwd = Path.cwd()
    try:
        rel_out_dir = out_dir.relative_to(cwd)
    except ValueError:
        rel_out_dir = out_dir
    print(f"wrote output to: {rel_out_dir}")
    print(f"index: {rel_out_dir / 'README.md'}")
    return 0


def main() -> int:
    args = parse_args()
    if args.inside:
        run_inside(args)
        return 0
    return run_host(args)


if __name__ == "__main__":
    raise SystemExit(main())
