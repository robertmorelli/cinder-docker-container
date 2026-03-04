# Per-Proportion Performance: deltablue (advanced)

- generated: `2026-02-18 09:56:14 UTC`
- seed: `1771408355`
- samples per point: `3`
- points requested: `10`
- max attempts per point: `5`
- alpha: `0.05`
- bootstrap resamples: `10`
- function count: `50`
- per-run timeout enabled: `5.0s`

## Results

| Detyped Fn | Detyped % | Samples | Mean (s) | StdDev (s) | Bootstrap CI | Signed-Rank CI | Speedup vs Typed |
|---:|---:|---:|---:|---:|---|---|---:|
| 0 | 0.0% | 3/3 | 0.895371 | 0.028097 | [0.862927, 0.911643] | [-0.570241, 2.360983] | 1.000x |
| 6 | 12.0% | 2/3 | 0.657831 | 0.382166 | [0.387599, 0.928063] | [-0.226094, 1.541756] | 1.361x |
| 11 | 22.0% | 1/3 | 0.863151 | 0.000000 | [0.863151, 0.863151] | [0.469097, 1.257206] | 1.037x |
| 17 | 34.0% | 1/3 | 0.431998 | 0.000000 | [0.431998, 0.431998] | [0.030186, 0.833809] | 2.073x |
| 22 | 44.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 28 | 56.0% | 2/3 | 0.589373 | 0.091495 | [0.524676, 0.654069] | [-0.309546, 1.488291] | 1.519x |
| 33 | 66.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 39 | 78.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 44 | 88.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |
| 50 | 100.0% | 0/3 | N/A | N/A | N/A | N/A | N/A |

## Diagnostics

| Detyped Fn | Attempts | Typecheck Fails | Typecheck Timeouts | Run Fails | Run Timeouts | Parse Fails |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| 6 | 5 | 0 | 0 | 0 | 3 | 0 |
| 11 | 5 | 0 | 0 | 2 | 2 | 0 |
| 17 | 5 | 0 | 0 | 1 | 3 | 0 |
| 22 | 5 | 0 | 0 | 0 | 5 | 0 |
| 28 | 5 | 0 | 0 | 0 | 3 | 0 |
| 33 | 5 | 0 | 0 | 1 | 4 | 0 |
| 39 | 5 | 0 | 0 | 0 | 5 | 0 |
| 44 | 5 | 0 | 0 | 0 | 5 | 0 |
| 50 | 5 | 0 | 0 | 0 | 5 | 0 |

Notes:
- Runtime is parsed from each benchmark's own printed timing output (last float in stdout).
- Detyped proportion is sampled by selecting exactly K detyped functions at each point.
- `Speedup vs Typed` uses the 0-detyped mean runtime as baseline (`typed_mean / point_mean`).
