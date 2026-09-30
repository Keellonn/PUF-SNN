# Week 5 Stream and Anomaly Evaluation

## Scope and denominators

- Test sources: 600; planned paired test cases: 16800.
- Quality-valid evaluated cases: 14956; pre-authentication construction/quality failures: 1844.
- Failed construction is not an authentication rejection or a detector true positive.
- The separate detectors classify documented transformations, not malicious intent or real Quest behavior.

## Frozen motion classifier vulnerability

Mean +/- sample SD across motion seeds 7, 17 and 27. Each transform/severity has at most one case per source; pooled copies are correlated.

| Model | Clean macro-F1 | Pooled quality-valid macro-F1 | Authenticated pooled macro-F1 |
|---|---|---|---|
| logistic_regression | 0.9048 +/- 0.0000 | 0.8112 +/- 0.0000 | 0.8112 +/- 0.0000 |
| random_forest | 0.8936 +/- 0.0042 | 0.8760 +/- 0.0021 | 0.8760 +/- 0.0021 |
| snn | 0.8500 +/- 0.0204 | 0.7452 +/- 0.0118 | 0.7452 +/- 0.0118 |

The intended label stays the original clean-source task. Severe transforms can change or erase the observed task; classification errors are vulnerability measurements, not proof that the corrupted motion has an unambiguous label.

## Separate anomaly detector

Settings are fixed in the saved configuration. Thresholds maximize source-weighted validation F1 subject to clean validation FPR <= 5%; score >= threshold flags a case, and ties prefer the higher threshold. No test result selects a model or threshold.

| Detector | Test precision | Test recall | Test F1 | Clean test FPR | Medium/high recall |
|---|---|---|---|---|---|
| logistic_regression | 0.9970 +/- 0.0000 | 0.7293 +/- 0.0000 | 0.8424 +/- 0.0000 | 0.0533 +/- 0.0000 | 0.8285 +/- 0.0000 |
| random_forest | 0.9985 +/- 0.0001 | 0.8197 +/- 0.0010 | 0.9003 +/- 0.0006 | 0.0294 +/- 0.0019 | 0.8795 +/- 0.0014 |

logistic_regression: mean medium/high recall misses the provisional 90% target. This pooled value does not establish that every transform meets it.

random_forest: mean medium/high recall misses the provisional 90% target. This pooled value does not establish that every transform meets it.

Per-transform/severity counts, five-class confusion matrices, binary confusion counts and paired source-cluster bootstrap intervals are in results.json. Intervals condition on these synthetic devices/sessions; they do not establish cross-device or human generalization. Model-seed SD is reported separately from source uncertainty.

## Authentication boundary

- Real sender/verifier accepts and releases: 14956; fresh synthetic sessions: 150.
- Both branches use the same immutable accepted sensor data; paired motion and anomaly features match exactly before inference.
- Anomaly flags remain downstream results and do not alter authentication acceptance, committed sequence state or at-most-once delivery.
- Batched unauthenticated versus single-window authenticated motion prediction differences: {'motion_logistic_regression_seed7': 0, 'motion_random_forest_seed7': 0, 'motion_snn_seed7': 0, 'motion_logistic_regression_seed17': 0, 'motion_random_forest_seed17': 0, 'motion_snn_seed17': 0, 'motion_logistic_regression_seed27': 0, 'motion_random_forest_seed27': 0, 'motion_snn_seed27': 0}.
- Detector flag differences: {'anomaly_logistic_regression_seed6007': 0, 'anomaly_random_forest_seed6007': 0, 'anomaly_logistic_regression_seed6017': 0, 'anomaly_random_forest_seed6017': 0, 'anomaly_logistic_regression_seed6027': 0, 'anomaly_random_forest_seed6027': 0}; maximum score difference: 2.6645352591e-15.
- Differences are reported, not silently overwritten. Accuracy uses batched unauthenticated predictions and single-window authenticated predictions; this run is not a latency benchmark.

## Limits and saved evidence

- Training weights give each source equal mass, split equally between its one clean case and its constructed transforms. Reported precision/F1 still depend on the synthetic case mixture, not an operational attack prevalence.
- Source jitter/drop metadata are not features. Resampled timestamp disturbances are visible only through effects retained in the motion payload.
- Known-correct synthetic credential candidates isolate the stream boundary. Reconstruction reliability, independent pre-HKDF verification, formal Tier-1 attack rates and durable audit timings are not measured.
- Authentication is run on the held-out test cohort only; training/validation construction success is not reported as measured authentication acceptance.
- No new detector-inclusive matched latency benchmark, human recordings or deployed Quest results are claimed.
- Local models/ binaries are ignored by Git. Their hashes, dependency versions, configuration and reproducible training path are recorded; load only your own trusted model artifacts.
- COMPLETE means this configured stream evaluation finished, not that every Week 5 or shared-system requirement has finished.
