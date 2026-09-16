# Conventional Classification Baselines

This experiment used the synthetic Quest-like dataset.
These results test the pipeline and dont represent real Quest performance yet.

## Dataset

- Training windows: 600
- Validation windows: 600
- Testing windows: 600
- Features per window: 840
- Random seed: 2026

## Results

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Test median inference | Test p95 inference |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 1.0000 | 1.0000 | 1.0000 | 0.2321 ms | 0.3896 ms |
| Random Forest | 1.0000 | 1.0000 | 1.0000 | 14.1423 ms | 21.6515 ms |

## Interpretation

Logistic regression is the simple linear baseline.
Random forest is the nonlinear tree-based baseline.
The models use the same data, features, and cross-session split.
Later SNN results should be compared with these exact baseline results.

## Timing environment

- Machine model: HP Pavilion Plus Laptop 16-ab1xxx
- Processor: Intel64 Family 6 Model 170 Stepping 4, GenuineIntel
- Operating system: Windows-11-10.0.26200-SP0
- Python: 3.13.14 (CPython)
- Implementation: Python scikit-learn software prototype
- Timing method: time.perf_counter_ns
- Warm-up predictions: 20 per model
- Timed predictions: 600 per model
- Timing unit: milliseconds

## Provenance

- Git commit: 4f540a7c9d32035a66d775bedd047756960242de
- Working tree clean before run: True
- Input SHA-256: 0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00
