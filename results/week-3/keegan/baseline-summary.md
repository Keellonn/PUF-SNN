# Conventional Classification Baselines

This experiment used the synthetic Quest-like dataset.
These results test the corrected pipeline and dont represent real Quest performance yet.

## Dataset

- Training windows: 600
- Validation windows: 600
- Testing windows: 600
- Features per window: 840
- Generator seed: 7
- Model seeds: 7, 17, 27, 37, and 47

## Results

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Test p95 inference | Test p95 preprocessing plus inference |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.8825 ± 0.0000 | 0.9017 ± 0.0000 | 0.9032 ± 0.0000 | 0.2432 ± 0.0548 ms | 0.9447 ± 0.1519 ms |
| Random Forest | 0.8607 ± 0.0024 | 0.8933 ± 0.0033 | 0.8936 ± 0.0033 | 12.7610 ± 0.4017 ms | 14.1448 ± 1.4158 ms |

The values are the mean and standard deviation across model seeds 7, 17, 27, 37, and 47.

## Why the original result was perfect

The original dataset used one deterministic orientation trajectory for each active motion class. The original audit found 480 test windows with an exact matching training orientation trajectory.

| Original-data check | Logistic Regression | Random Forest |
|---|---:|---:|
| Position-only test accuracy | 0.6167 | 0.5967 |
| Orientation-only test accuracy | 1.0000 | 1.0000 |
| Position plus orientation test accuracy | 1.0000 | 1.0000 |
| Permuted-label mean test accuracy | 0.1960 | 0.1840 |

The safe metadata-only baseline reached 0.1850 accuracy, close to the five-class chance rate of 0.20. The intentionally unsafe identifier-text control reached 1.0000 because the IDs contain class names. Those IDs remain excluded from the actual models.

The corrected generator adds variation in amplitude, speed, duration, start pose, timing, return behavior, noise, drift, sway, device/session effects, and still-class micro-motion. The corrected data has zero exact test-to-training orientation matches and zero exact complete-payload matches.

## Corrected input checks

The model input is 120 time points by seven trial-relative motion channels: position x, y, and z in meters plus normalized quaternion orientation x, y, z, and w. Labels, IDs, timestamps, tracking state, filenames, row order, sequence numbers, and generator seeds are excluded.

| Feature group | Logistic test accuracy | Logistic test macro-F1 | Forest test accuracy | Forest test macro-F1 |
|---|---:|---:|---:|---:|
| Position only | 0.3533 | 0.3460 | 0.3250 | 0.3179 |
| Orientation only | 0.8733 | 0.8732 | 0.9000 | 0.9005 |
| Position plus orientation | 0.9017 | 0.9032 | 0.8950 | 0.8953 |

The corrected label-permutation results were 0.1910 ± 0.0312 for logistic regression and 0.1717 ± 0.0319 for random forest. Safe metadata-only accuracy was 0.1900.

## Interpretation

Logistic regression is the simple linear baseline.
Random forest is the nonlinear tree-based baseline.
The models use the same corrected data, features, and cross-session split.
Orientation remains the main class signal, but the corrected task is no longer perfectly separable.
Later SNN results should use this corrected baseline after the authenticated-window path is stable.

## Timing environment

- Machine model: HP Pavilion Plus Laptop 16-ab1xxx
- Processor: Intel64 Family 6 Model 170 Stepping 4, GenuineIntel
- Operating system: Windows-11-10.0.26200-SP0
- Python: 3.13.14 (CPython)
- Implementation: Python scikit-learn software prototype
- Timing method: time.perf_counter_ns
- Warm-up predictions: 20 per model
- Timed predictions: 600 per model seed
- Timing unit: milliseconds
- Measured boundaries: inference only and preprocessing plus inference

Loading, training, authentication, anomaly detection, logging, and the two-second capture period are excluded. These are laptop/Python measurements on synthetic in-memory windows.

## Provenance

- Base commit recorded during the diagnostic run: 2c11de84bf4e321e81ce34d88dd371a25e7d8cc6
- Corrected configuration SHA-256: 7e9b12fa8679c9fe08e9396b1a9ea0f3c36465afce07f666c6d5817021924846
- Corrected input SHA-256: 752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661
- Original input SHA-256: 0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00
- Corrected implementation and results commit: `e4e0523d9232ded6c7ff266fd5d495a8c8d31fc0`

The 28 Python tests passed in 13.084 seconds and the corrected dataset validation passed for all 1,800 windows. The original `baseline-results.json` and confusion matrices remain as historical evidence. The updated diagnostics are in `baseline-diagnostics.json`, `baseline-diagnostics.md`, and `original-baseline-audit`.
