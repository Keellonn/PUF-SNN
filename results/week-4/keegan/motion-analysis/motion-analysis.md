# Motion baseline analysis

All configurations were fixed before evaluation. Session 2 is validation; Session 3 is final comparison, not a tuning loop.

## Fixed-model clean results

| Model | Split | Accuracy | Macro-F1 |
|---|---|---:|---:|
| snn_seed_7 | validation | 0.8433 | 0.8439 |
| snn_seed_17 | validation | 0.8500 | 0.8497 |
| snn_seed_27 | validation | 0.8617 | 0.8618 |
| logistic_regression_seed_7 | validation | 0.8817 | 0.8825 |
| random_forest_seed_7 | validation | 0.8617 | 0.8615 |
| logistic_regression_seed_17 | validation | 0.8817 | 0.8825 |
| random_forest_seed_17 | validation | 0.8600 | 0.8601 |
| logistic_regression_seed_27 | validation | 0.8817 | 0.8825 |
| random_forest_seed_27 | validation | 0.8633 | 0.8632 |
| snn_seed_7 | test | 0.8267 | 0.8274 |
| snn_seed_17 | test | 0.8550 | 0.8552 |
| snn_seed_27 | test | 0.8667 | 0.8673 |
| logistic_regression_seed_7 | test | 0.9017 | 0.9032 |
| random_forest_seed_7 | test | 0.8950 | 0.8953 |
| logistic_regression_seed_17 | test | 0.9017 | 0.9032 |
| random_forest_seed_17 | test | 0.8967 | 0.8968 |
| logistic_regression_seed_27 | test | 0.9017 | 0.9032 |
| random_forest_seed_27 | test | 0.8883 | 0.8888 |

## Feature ablation

Raw relative pose is an explicit unscaled LR control; position+quaternion uses the same seven channels with training-only scaling. RF uses no scaler in either condition. Quaternion+angular velocity has four quaternion plus three radians/second channels; the first velocity is zero. Euler angles are not model features.

| Group | Model | Seed | Validation F1 | Test F1 |
|---|---|---:|---:|---:|
| raw_relative_pose | logistic_regression | 7 | 0.8379 | 0.8637 |
| raw_relative_pose | random_forest | 7 | 0.8615 | 0.8953 |
| raw_relative_pose | logistic_regression | 17 | 0.8379 | 0.8637 |
| raw_relative_pose | random_forest | 17 | 0.8601 | 0.8968 |
| raw_relative_pose | logistic_regression | 27 | 0.8379 | 0.8637 |
| raw_relative_pose | random_forest | 27 | 0.8632 | 0.8888 |
| quaternion_only | logistic_regression | 7 | 0.8537 | 0.8732 |
| quaternion_only | random_forest | 7 | 0.8647 | 0.9005 |
| quaternion_only | logistic_regression | 17 | 0.8537 | 0.8732 |
| quaternion_only | random_forest | 17 | 0.8665 | 0.9038 |
| quaternion_only | logistic_regression | 27 | 0.8537 | 0.8732 |
| quaternion_only | random_forest | 27 | 0.8634 | 0.9003 |
| quaternion_plus_angular_velocity | logistic_regression | 7 | 0.8052 | 0.8367 |
| quaternion_plus_angular_velocity | random_forest | 7 | 0.8465 | 0.8957 |
| quaternion_plus_angular_velocity | logistic_regression | 17 | 0.8052 | 0.8367 |
| quaternion_plus_angular_velocity | random_forest | 17 | 0.8496 | 0.8974 |
| quaternion_plus_angular_velocity | logistic_regression | 27 | 0.8052 | 0.8367 |
| quaternion_plus_angular_velocity | random_forest | 27 | 0.8598 | 0.8939 |
| position_plus_quaternion | logistic_regression | 7 | 0.8825 | 0.9032 |
| position_plus_quaternion | random_forest | 7 | 0.8615 | 0.8953 |
| position_plus_quaternion | logistic_regression | 17 | 0.8825 | 0.9032 |
| position_plus_quaternion | random_forest | 17 | 0.8601 | 0.8968 |
| position_plus_quaternion | logistic_regression | 27 | 0.8825 | 0.9032 |
| position_plus_quaternion | random_forest | 27 | 0.8632 | 0.8888 |

## Nod and still motion

| True class | Test windows | Mean rotation RMS (deg) | Mean position RMS (m) |
|---|---:|---:|---:|
| nod | 120 | 13.5545 | 0.011867 |
| still | 120 | 6.1377 | 0.011585 |

Per-window statistics, predictions, representative correct/incorrect trajectories, feature results, stress results and nod-sweep results are saved separately. Examine whether low-amplitude nods overlap still and whether speed/timing variation changes errors; do not infer realism from synthetic success.

same generator draws and source IDs; only nod intentional rotation/position coefficients and motion-duration range change; noise/drift/sway and return error remain; actual duration is clipped by the original generator

diagnostic synthetic sweep; increasingly ambiguous nominal nod labels are not new independent trials; test results do not choose parameters; no claim of physical execution speed

SNN checkpoints and preprocessing remain frozen during these diagnostics. Feature ablations are conventional-model comparisons, not a new SNN input contract.
