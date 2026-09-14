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

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Test p95 inference |
|---|---:|---:|---:|---:|
| Logistic Regression | 1.0000 | 1.0000 | 1.0000 | 0.5417 ms |
| Random Forest | 1.0000 | 1.0000 | 1.0000 | 22.4288 ms |

## Interpretation

Logistic regression is the simple linear baseline.
Random forest is the nonlinear tree-based baseline.
The models use the same data, features, and cross-session split.
Later SNN results should be compared with these exact baseline results.
