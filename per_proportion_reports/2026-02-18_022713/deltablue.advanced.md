# Per-Proportion Performance: deltablue (advanced)

- generated: `2026-02-18 09:27:12 UTC`
- seed: `1771406810`
- samples per point: `3`
- points requested: `4`
- max attempts per point: `3`
- alpha: `0.05`
- bootstrap resamples: `10`
- function count: `50`
- per-run timeout enabled: `1.0s`

## Results

| Detyped Fn | Detyped % | Samples | Mean (s) | StdDev (s) | Bootstrap CI | Signed-Rank CI | Speedup vs Typed |
|---:|---:|---:|---:|---:|---|---|---:|
| 0 | 0.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 17 | 34.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 33 | 66.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 50 | 100.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |

## Diagnostics

| Detyped Fn | Attempts | Typecheck Fails | Typecheck Timeouts | Run Fails | Run Timeouts | Parse Fails |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3 | 0 | 0 | 0 | 3 | 0 |
| 17 | 3 | 0 | 0 | 0 | 3 | 0 |
| 33 | 3 | 0 | 0 | 0 | 3 | 0 |
| 50 | 3 | 0 | 0 | 0 | 3 | 0 |

Notes:
- Runtime is parsed from each benchmark's own printed timing output (last float in stdout).
- Detyped proportion is sampled by selecting exactly K detyped functions at each point.
- `Speedup vs Typed` uses the 0-detyped mean runtime as baseline (`typed_mean / point_mean`).
