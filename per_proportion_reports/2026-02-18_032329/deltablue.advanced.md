# Per-Proportion Performance: deltablue (advanced)

- generated: `2026-02-18 10:23:29 UTC`
- seed: `1771410133`
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
| 0 | 0.0% | 3/3 | 0.884838 | 0.026418 | [0.868929, 0.900746] | [-0.598009, 2.367685] | 1.000x |
| 6 | 12.0% | 3/3 | 0.924826 | 0.069451 | [0.885449, 0.969479] | [-0.568234, 2.417886] | 0.957x |
| 11 | 22.0% | 3/3 | 0.977247 | 0.076242 | [0.933200, 1.021293] | [-0.513457, 2.467950] | 0.905x |
| 17 | 34.0% | 3/3 | 0.986752 | 0.062843 | [0.945255, 1.018913] | [-0.512110, 2.485614] | 0.897x |
| 22 | 44.0% | 3/3 | 1.113580 | 0.110329 | [1.007466, 1.113580] | [-0.401170, 2.628329] | 0.795x |
| 28 | 56.0% | 3/3 | 1.210521 | 0.057979 | [1.176082, 1.225012] | [-0.269593, 2.690636] | 0.731x |
| 33 | 66.0% | 3/3 | 1.185951 | 0.081057 | [1.137817, 1.235404] | [-0.317672, 2.689573] | 0.746x |
| 39 | 78.0% | 3/3 | 1.192849 | 0.087062 | [1.136342, 1.232583] | [-0.252799, 2.638496] | 0.742x |
| 44 | 88.0% | 3/3 | 1.323847 | 0.060284 | [1.294416, 1.362264] | [-0.154575, 2.802270] | 0.668x |
| 50 | 100.0% | 3/3 | 1.341580 | 0.063383 | [1.304710, 1.414746] | [-0.125881, 2.809040] | 0.660x |

## Diagnostics

| Detyped Fn | Attempts | Typecheck Fails | Typecheck Timeouts | Run Fails | Run Timeouts | Parse Fails |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| 6 | 3 | 0 | 0 | 0 | 0 | 0 |
| 11 | 3 | 0 | 0 | 0 | 0 | 0 |
| 17 | 3 | 0 | 0 | 0 | 0 | 0 |
| 22 | 3 | 0 | 0 | 0 | 0 | 0 |
| 28 | 3 | 0 | 0 | 0 | 0 | 0 |
| 33 | 3 | 0 | 0 | 0 | 0 | 0 |
| 39 | 3 | 0 | 0 | 0 | 0 | 0 |
| 44 | 3 | 0 | 0 | 0 | 0 | 0 |
| 50 | 3 | 0 | 0 | 0 | 0 | 0 |

Notes:
- Runtime is parsed from each benchmark's own printed timing output (last float in stdout).
- Detyped proportion is sampled by selecting exactly K detyped functions at each point.
- `Speedup vs Typed` uses the 0-detyped mean runtime as baseline (`typed_mean / point_mean`).
