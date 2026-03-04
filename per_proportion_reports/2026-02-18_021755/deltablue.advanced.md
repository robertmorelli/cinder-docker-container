# Per-Proportion Performance: deltablue (advanced)

- generated: `2026-02-18 09:17:55 UTC`
- seed: `1771406249`
- samples per point: `3`
- points requested: `4`
- max attempts per point: `3`
- alpha: `0.05`
- bootstrap resamples: `10`
- function count: `50`
- per-run timeout enabled: `2.0s`

## Results

| Detyped Fn | Detyped % | Samples | Mean (s) | StdDev (s) | Bootstrap CI | Signed-Rank CI | Speedup vs Typed |
|---:|---:|---:|---:|---:|---|---|---:|
| 0 | 0.0% | 3/3 | 0.066187 | 0.003035 | [0.063367, 0.069398] | [-1.419997, 1.552371] | 1.000x |
| 17 | 34.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 33 | 66.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 50 | 100.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |

## Diagnostics

| Detyped Fn | Attempts | Typecheck Fails | Typecheck Timeouts | Run Fails | Run Timeouts | Parse Fails |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| 17 | 3 | 0 | 0 | 1 | 2 | 0 |
| 33 | 3 | 0 | 0 | 0 | 3 | 0 |
| 50 | 3 | 0 | 0 | 0 | 3 | 0 |

Notes:
- Runtime is parsed from each benchmark's own printed timing output (last float in stdout).
- Detyped proportion is sampled by selecting exactly K detyped functions at each point.
- `Speedup vs Typed` uses the 0-detyped mean runtime as baseline (`typed_mean / point_mean`).
