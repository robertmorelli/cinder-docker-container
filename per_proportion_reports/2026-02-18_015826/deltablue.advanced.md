# Per-Proportion Performance: deltablue (advanced)

- generated: `2026-02-18 08:58:26 UTC`
- seed: `1771404915`
- samples per point: `3`
- points requested: `8`
- max attempts per point: `3`
- alpha: `0.05`
- bootstrap resamples: `10`
- function count: `50`
- per-run timeout enabled: `10.0s`

## Results

| Detyped Fn | Detyped % | Samples | Mean (s) | StdDev (s) | Bootstrap CI | Signed-Rank CI | Speedup vs Typed |
|---:|---:|---:|---:|---:|---|---|---:|
| 0 | 0.0% | 3/3 | 0.928193 | 0.031483 | [0.913728, 0.942234] | [-0.588283, 2.444669] | 1.000x |
| 7 | 14.0% | 2/3 | 0.779694 | 0.556105 | [0.386469, 1.084444] | [-0.118219, 1.677607] | 1.190x |
| 14 | 28.0% | 1/3 | 0.477197 | 0.000000 | [0.477197, 0.477197] | [0.073591, 0.880803] | 1.945x |
| 21 | 42.0% | 1/3 | 0.469129 | 0.000000 | [0.469129, 0.469129] | [0.058578, 0.879680] | 1.979x |
| 29 | 58.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 36 | 72.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 43 | 86.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 50 | 100.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |

## Diagnostics

| Detyped Fn | Attempts | Typecheck Fails | Typecheck Timeouts | Run Fails | Run Timeouts | Parse Fails |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| 7 | 3 | 0 | 0 | 0 | 1 | 0 |
| 14 | 3 | 0 | 0 | 0 | 2 | 0 |
| 21 | 3 | 0 | 0 | 0 | 2 | 0 |
| 29 | 3 | 0 | 0 | 1 | 2 | 0 |
| 36 | 3 | 0 | 0 | 0 | 3 | 0 |
| 43 | 3 | 0 | 0 | 0 | 3 | 0 |
| 50 | 3 | 0 | 0 | 0 | 3 | 0 |

Notes:
- Runtime is parsed from each benchmark's own printed timing output (last float in stdout).
- Detyped proportion is sampled by selecting exactly K detyped functions at each point.
- `Speedup vs Typed` uses the 0-detyped mean runtime as baseline (`typed_mean / point_mean`).
