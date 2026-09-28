# Post-window pipeline benchmark

Synthetic CPU/in-memory comparison. The same binary32-quantized motion, source order, split and models are used within each paired condition.

| Model | Condition | Median (ms) | p95 (ms) | Max (ms) |
|---|---|---:|---:|---:|
| snn_seed_7 | classifier_only | 9.1824 | 10.0035 | 13.2141 |
| snn_seed_7 | authentication_plus_classifier | 17.2948 | 18.7374 | 288.1892 |
| snn_seed_17 | classifier_only | 9.0309 | 10.3146 | 16.0120 |
| snn_seed_17 | authentication_plus_classifier | 16.4914 | 18.3237 | 326.3125 |
| snn_seed_27 | classifier_only | 8.8166 | 9.5808 | 12.0964 |
| snn_seed_27 | authentication_plus_classifier | 15.8243 | 18.4075 | 335.6499 |
| logistic_regression_seed_7 | classifier_only | 1.9340 | 2.4948 | 3.5519 |
| logistic_regression_seed_7 | authentication_plus_classifier | 9.1215 | 11.0993 | 343.8066 |
| random_forest_seed_7 | classifier_only | 13.0567 | 15.6861 | 22.7181 |
| random_forest_seed_7 | authentication_plus_classifier | 20.7229 | 24.1674 | 365.8515 |
| logistic_regression_seed_17 | classifier_only | 1.7993 | 2.2731 | 3.6975 |
| logistic_regression_seed_17 | authentication_plus_classifier | 9.2070 | 10.8945 | 350.9324 |
| random_forest_seed_17 | classifier_only | 13.1251 | 15.4017 | 18.6738 |
| random_forest_seed_17 | authentication_plus_classifier | 20.9737 | 24.2338 | 387.2972 |
| logistic_regression_seed_27 | classifier_only | 1.7412 | 2.1449 | 3.4805 |
| logistic_regression_seed_27 | authentication_plus_classifier | 9.0626 | 10.9162 | 354.6266 |
| random_forest_seed_27 | classifier_only | 14.2539 | 15.9863 | 19.9256 |
| random_forest_seed_27 | authentication_plus_classifier | 20.5187 | 23.8311 | 368.6291 |

Total time is measured directly per window, never assembled from stage percentiles. Preprocessing/tensor creation, inference/output decoding and actual in-memory authentication audit generation are included. Loading, training, capture, network transfer and persistent audit I/O are excluded. Nested component timers add measurement overhead; these are instrumented software measurements.

Session establishment and KDF are separate from recurring windows. They use the existing explicit synthetic correct candidate, not a PUF reliability experiment. Independent credential verification, reconstruction, disjoint replay-state/audit stage instrumentation and durable audit-storage costs remain shared/Will follow-up requirements.

The bad-tag receiver path makes zero preprocessing/classifier calls and preserves sequence state. These are repeated timing observations, not the formal independent Tier-1 attack evaluation.
