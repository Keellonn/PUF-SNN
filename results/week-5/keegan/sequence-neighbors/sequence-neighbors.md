# Nearest-training orientation and complete-input audit

## Question and frozen scope

Does the corrected held-out motion remain close to training when the entire 120 x 7 model input is compared, rather than orientation alone? This is a data-similarity audit, not a new classifier, feature ablation, tuned leakage threshold or generalization experiment. Session 1 supplies all references/scaling; Sessions 2 and 3 are queries only. Original leakage evidence is retained, not replaced.

## Exact orientation metric

For each already fixed-grid window, use p_rel[t] = p[t] - p[0] and q_rel[t] = inverse(q[0]) * q[t] in xyzw order, after unit-normalizing quaternions and making adjacent equivalent signs continuous. Re-normalize relative quaternions before the dot product. For aligned sample index t:

`theta[t] = (180/pi) * 2 * acos(clip(abs(dot(q_rel_query[t], q_rel_train[t])), 0, 1))`

`d_orientation = sqrt((1/120) * sum_t theta[t]^2)`

This is root-mean-square shortest rotation angle in degrees, not the mean angle or maximum angle. Absolute starting pose is removed. The absolute dot product makes the physical metric invariant to q versus -q. Find the minimum distance over all 600 training windows (any-label scope), or over the 120 training windows with the query's intended class (same-label scope). Same-label filtering is a descriptive stratification, not a feature or prediction.

### Alignment and processing boundary

The input has 120 ordered samples on a shared grid: adjacent interval 16666667 ns; last relative timestamp 1983333373 ns. Align t with t after subtracting each window's first timestamp. There is no dynamic time warping, interpolation, phase matching or time-shift search. The clean synthetic generator already outputs this grid; no resampling occurs in this audit. The physical orientation distance is after quaternion normalization/first-pose subtraction, but before learned statistical normalization and before Wire 2.0 binary32 conversion. It is not a distance on irregular raw Quest captures.

## Complete 120 x 7 input metric

Fit one mean mu[c] and population standard deviation sigma[c] per pose channel across all 600 training windows and all 120 time points. Replace sigma <= 1e-12 with 1, matching the SNN pipeline. No validation/test observation affects scaling. Save all seven means/SDs and the ordered training source IDs. Normalize using the existing SNN routine and its float32 model-input rounding; promote to float64 only to accumulate distances.

`z[t,c] = float32((x_rel[t,c] - mu[c]) / sigma[c])`

`d_sequence = sqrt((1/840) * sum_{t=0..119,c=0..6} (z_query[t,c] - z_train[t,c])^2)`

All 840 coordinates contribute: three relative-position channels and four relative-quaternion channels. This distance is dimensionless. It uses the SNN's seven-channel training scaler, not LR's 840-feature scaler. Quaternion-component Euclidean distance is not the same as geodesic rotation distance; the canonical first-relative identity and continuous-sign preprocessing fix the model's representation. Retain the physical orientation metric alongside it. Labels, IDs, timestamps, tracking flags and attack settings are not input coordinates.

Nearest feature and nearest orientation references may differ; per-source rows save both reference IDs and the physical orientation distance to the feature-nearest reference. Ties choose the first lexicographically sorted training ID. No near/far cutoff is selected from held-out results. A small distance does not by itself prove leakage, and a nonzero distance does not establish real-world generalization. Still-like trajectories can legitimately be similar.

## Historical orientation evidence, retained

The rows below reuse the hash-checked Week 4 test-to-training physical distances. The original full 120 x 7 distance is not recalculated or implied here; the new full-input audit uses the corrected frozen dataset. This preserves the original orientation-template failure without executing an old generator.

| Dataset | Scope | Windows | Minimum orientation RMS (deg) | Median orientation RMS (deg) |
|---|---|---:|---:|---:|
| Original | any_label | 600 | 0.000000 | 0.000000 |
| Original | same_label | 600 | 0.000000 | 0.000000 |
| Corrected | any_label | 600 | 2.509239 | 6.425321 |
| Corrected | same_label | 600 | 2.509239 | 6.588885 |

All 1,200 corrected historical test/scope distances were reconciled. Maximum recomputation difference: 1.50990331e-13 degrees (tolerance 1e-5 degrees, only for floating-point quaternion renormalization). No original report or result manifest was modified.

## New corrected-input results

| Query split | Scope | Metric | Windows | Minimum | Median | p95 |
|---|---|---|---:|---:|---:|---:|
| validation | any_label | orientation_rms_deg | 600 | 2.882320 | 6.584683 | 10.870260 |
| validation | any_label | normalized_sequence_rms | 600 | 0.481008 | 0.712748 | 0.977175 |
| validation | same_label | orientation_rms_deg | 600 | 2.882320 | 6.736998 | 10.870260 |
| validation | same_label | normalized_sequence_rms | 600 | 0.481008 | 0.737899 | 0.997050 |
| test | any_label | orientation_rms_deg | 600 | 2.509239 | 6.425321 | 11.773732 |
| test | any_label | normalized_sequence_rms | 600 | 0.517395 | 0.710372 | 1.100239 |
| test | same_label | orientation_rms_deg | 600 | 2.509239 | 6.588885 | 11.773732 |
| test | same_label | normalized_sequence_rms | 600 | 0.517395 | 0.738643 | 1.101235 |

`summary.json` also reports each class separately with count/minimum/p05/median/mean/p95/maximum. `nearest-training.csv` retains every query and both scopes (2,400 rows). Exact full-content equality across all three split pairs is checked separately by the existing full-window hash policy, which includes relative timing and tracking quality.

## Seed roles and limitations

Data generation uses seed 7. Fixed session-index assignment has no split RNG. Re-running that generator is deterministic reproduction, not a second sampled dataset. Conventional/SNN fitting seeds do not alter these frozen input windows. This audit trains no model and uses no RNG. Model-seed performance variation and data-generation variation must not be pooled as independent replications. LR's lbfgs solver is deterministic for its fixed inputs; identical scores across seed labels are not independent stochastic performance samples.

Claims remain limited to cross-session synthetic evaluation with six fixed simulated device profiles. No cross-device, cross-person, physical headset, adversarial robustness, entropy/security or real-world transfer conclusion follows from these distances. The audit does not change data, model selection, anomaly thresholds or authentication state.

## Artifacts

- `nearest-training.csv`: per-query full-input/physical distance and nearest reference IDs, both query splits/scopes.
- `summary.json`: all-class and per-class distance distributions.
- `training-normalization.json`: seven training-only means/SDs and ordered training window IDs.
- `audit-settings.json`: formulas, alignment, dtype, query/reference roles and historical reconciliation.
- `manifest.json`, `COMPLETE` and `.gitattributes`: input/source/artifact hashes, completion binding and byte-preserving checkouts.
