# Week 3 Baseline Diagnostics

This report diagnoses the conventional classification baseline. It does not contain an SNN result.

## Input audit

The model input is exactly 120 time points by seven payload channels (840 flattened values).

| Channel | Unit | Transformation |
|---|---|---|
| relative_position_x | meters | position_m[0] minus the first sample's position_m[0] |
| relative_position_y | meters | position_m[1] minus the first sample's position_m[1] |
| relative_position_z | meters | position_m[2] minus the first sample's position_m[2] |
| relative_orientation_x | dimensionless quaternion component | normalized, sign-continuous orientation relative to the first orientation |
| relative_orientation_y | dimensionless quaternion component | normalized, sign-continuous orientation relative to the first orientation |
| relative_orientation_z | dimensionless quaternion component | normalized, sign-continuous orientation relative to the first orientation |
| relative_orientation_w | dimensionless quaternion component | normalized, sign-continuous orientation relative to the first orientation |

Labels, identifiers, timestamps, tracking state, file names, row order, and generator seeds are excluded.
Logistic-regression scaling is fit only on training data through its sklearn Pipeline.

## Single-channel-group ablation

| Features | Logistic test accuracy | Logistic test macro-F1 | Forest test accuracy | Forest test macro-F1 |
|---|---:|---:|---:|---:|
| position_only | 0.6167 | 0.6129 | 0.5967 | 0.5969 |
| orientation_only | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| position_plus_orientation | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Leakage controls

- Five-class chance accuracy: 0.2000.
- Permuted-label logistic mean test accuracy: 0.1960.
- Permuted-label random-forest mean test accuracy: 0.1840.
- Safe metadata-only logistic test accuracy: 0.1850.
- Label-bearing identifier-text test accuracy: 1.0000.

The identifier-text control is intentionally unsafe: trial_id, source_trial_id, and window_id contain the class name. Its purpose is to prove why these strings must never enter the classifier.

## Five-seed conventional baseline

| Model | Test accuracy mean ± SD | Test macro-F1 mean ± SD | Inference p95 mean ± SD (ms) | Preprocess + inference p95 mean ± SD (ms) |
|---|---:|---:|---:|---:|
| logistic_regression | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 0.2097 ± 0.0052 | 0.8046 ± 0.0121 |
| random_forest | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 11.1533 ± 0.1893 | 11.7672 ± 0.1801 |

## Timing interpretation

These are per-window laptop/Python measurements on synthetic in-memory records. Loading, training, authentication, anomaly detection, logging, and the two-second capture interval are excluded. The JSON artifact contains mean, median, p95, maximum, warm-up count, timed count, timer, workstation, and software versions for every seed.

## Duplicate and near-duplicate interpretation

- Test windows with an exact training orientation match: 480.
- Test windows with an exact training combined-payload match: 0.
- Test windows with same-label standardized distance below 1e-6: 0.

The JSON artifact contains the per-class hash counts and full nearest-distance summaries. Exact orientation matches on the original data identify a reused synthetic template; zero matches on the revised data confirm that the added trial-level variation removed exact cross-split copies.

## Figures

- `orientation-trajectories-by-class.png`
- `position-trajectories-by-class.png`

## Scope statement

The results validate or diagnose this software generator and preprocessing pipeline only. They do not establish expected performance on real Quest motion, cross-person generalization, embedded latency, or physical-device effects.
