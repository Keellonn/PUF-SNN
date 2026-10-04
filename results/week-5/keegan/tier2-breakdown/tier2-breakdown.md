# Week 5 Tier-2 accounting and held-out breakdown

This is a read-only reporting addendum to the completed historical run. No attack, model, threshold, authentication policy or historical artifact was changed.

## Complete case accounting

All splits: 50,400 planned = 44,899 quality-valid + 5,501 pre-tag blocked cases. Held-out test: 14,956 accepted of 16,800 planned cases.

`construction_failure` means interpolation did not produce a processed window; `quality_failure` means the constructed window failed final canonical/quality validation. Neither means verifier rejection or anomaly detection. A quality-valid construction row's historical `authentication: not_attempted` value records its construction-stage state, not the later delivery result.

| Failure reason | All splits | Held-out test | Boundary |
|---|---:|---:|---|
| `source_gap_exceeds_50_ms` | 3,493 | 1,160 | Before tagging/model input |
| `source_timestamps_not_increasing` | 2,008 | 684 | Before tagging/model input |

The unchanged resampling policy rejects source gaps above 50 ms and non-increasing source timestamps. With the legacy 16,666,667 ns grid, a three-interval gap is 50,000,001 ns and fails that rule. These are recorded data-quality/construction blocks; they were not retried until passing. Final quality failures are counted separately in the accompanying tables.

## Held-out attack and severity breakdown

Counts below are unique cases, not summed over model seeds. Recall is conditional on quality-valid, accepted cases. A failed construction is not an anomaly-model true positive. N/A means there was no eligible case.

| Attack | Severity | Planned | Valid/accepted | Pre-tag blocked | LR recall/FPR mean | RF recall/FPR mean |
|---|---|---:|---:|---:|---:|---:|
| clean | clean | 600 | 600 | 0 | 0.0533 | 0.0294 |
| dropped_samples | high | 600 | 4 | 596 | 1.0000 | 1.0000 |
| dropped_samples | low | 600 | 461 | 139 | 0.5184 | 0.4006 |
| dropped_samples | medium | 600 | 175 | 425 | 0.9429 | 0.9771 |
| frozen_pose | high | 600 | 600 | 0 | 1.0000 | 1.0000 |
| frozen_pose | low | 600 | 600 | 0 | 1.0000 | 1.0000 |
| frozen_pose | medium | 600 | 600 | 0 | 1.0000 | 1.0000 |
| orientation_drift | high | 600 | 600 | 0 | 0.1417 | 0.1306 |
| orientation_drift | low | 600 | 600 | 0 | 0.0600 | 0.0311 |
| orientation_drift | medium | 600 | 600 | 0 | 0.0600 | 0.0539 |
| orientation_jump | high | 600 | 600 | 0 | 1.0000 | 1.0000 |
| orientation_jump | low | 600 | 600 | 0 | 0.8883 | 0.7800 |
| orientation_jump | medium | 600 | 600 | 0 | 1.0000 | 1.0000 |
| orientation_noise | high | 600 | 600 | 0 | 1.0000 | 1.0000 |
| orientation_noise | low | 600 | 600 | 0 | 0.2917 | 0.8989 |
| orientation_noise | medium | 600 | 600 | 0 | 0.9233 | 1.0000 |
| position_drift | high | 600 | 600 | 0 | 1.0000 | 1.0000 |
| position_drift | low | 600 | 600 | 0 | 0.3417 | 0.3567 |
| position_drift | medium | 600 | 600 | 0 | 0.9850 | 0.9961 |
| position_jump | high | 600 | 600 | 0 | 1.0000 | 1.0000 |
| position_jump | low | 600 | 600 | 0 | 1.0000 | 1.0000 |
| position_jump | medium | 600 | 600 | 0 | 1.0000 | 1.0000 |
| position_noise | high | 600 | 600 | 0 | 1.0000 | 1.0000 |
| position_noise | low | 600 | 600 | 0 | 0.8533 | 1.0000 |
| position_noise | medium | 600 | 600 | 0 | 1.0000 | 1.0000 |
| timestamp_jitter | high | 600 | 0 | 600 | N/A | N/A |
| timestamp_jitter | low | 600 | 600 | 0 | 0.0583 | 0.9061 |
| timestamp_jitter | medium | 600 | 516 | 84 | 0.1938 | 1.0000 |

The clean row reports false-positive rate, not attack recall. `detector-breakdown.csv` supplies each seed's detected/missed counts, confidence bounds, target verdict, and the same clean-control FPR (repeated for context, not additional controls). `construction-breakdown.csv` and `failure-reasons.csv` retain all three splits and every blocked case's stage/reason.

## Paired motion-classification degradation

`motion-breakdown.csv` compares each condition with clean predictions for exactly the same eligible source windows. This matters for dropout conditions with only a subset passing quality checks. Positive loss means worse classification; negative loss means improvement. The five-class macro-F1 always uses the fixed label set, including classes with zero support. `motion-detail.json` retains per-class precision/recall/F1/support and full confusion matrices.

| Motion family | Clean macro-F1 mean | All quality-valid macro-F1 mean |
|---|---:|---:|
| logistic_regression | 0.9048 | 0.8112 |
| random_forest | 0.8936 | 0.8760 |
| snn | 0.8500 | 0.7452 |

## Calibration and frozen decisions

Training uses Session 1 only, with equal total source weights and equal clean/transformed mass per source. The LR scaler is fitted on weighted training only. Session 2 chooses the maximum source-weighted F1 threshold subject to clean FPR <= 5%; ties use the higher threshold and scores equal to it are flagged. Session 3 is used only after freezing these choices. This addendum loads the saved thresholds; it does not select new ones.

| Detector | Frozen threshold | Validation clean FP / n | Test clean FP / n | Test FPR | Test <=5% |
|---|---:|---:|---:|---:|---|
| anomaly_logistic_regression_seed6007 | 0.543110 | 30/600 | 32/600 | 0.0533 | False |
| anomaly_logistic_regression_seed6017 | 0.543110 | 30/600 | 32/600 | 0.0533 | False |
| anomaly_logistic_regression_seed6027 | 0.543110 | 30/600 | 32/600 | 0.0533 | False |
| anomaly_random_forest_seed6007 | 0.906311 | 21/600 | 19/600 | 0.0317 | True |
| anomaly_random_forest_seed6017 | 0.905451 | 24/600 | 17/600 | 0.0283 | True |
| anomaly_random_forest_seed6027 | 0.907794 | 19/600 | 17/600 | 0.0283 | True |

logistic_regression: mean F1 0.8424; mean clean test FPR 0.0533; mean medium/high recall 0.8285.

random_forest: mean F1 0.9003; mean clean test FPR 0.0294; mean medium/high recall 0.8795.

Neither detector reaches the predeclared 90% medium/high recall target. Logistic regression also exceeds the 5% clean test FPR target. The random forest is promising but does not meet the full criterion. Test results do not justify lowering a threshold or changing an attack's severity.

## Uncertainty, variation and cue controls

Per-condition detector recall and clean FPR use two-sided 95% Clopper-Pearson binomial intervals, separately for each fixed model. There is one case per source in each condition. These intervals assume exchangeable independent source trials; shared simulated device/session profiles limit that assumption. They are conditional descriptive intervals, not evidence of cross-device, cross-person or real-world generalization. All-pass/zero-pass rates retain finite uncertainty; zero eligible cases have no interval.

Paired accuracy-loss intervals use 400 source-paired bootstrap resamples with reporting seed 7017 (PCG64). The clean and transformed predictions stay paired; the same resampling indices are used across models for a condition. This is conditional on the subset that passed construction. Very small cohorts can produce degenerate percentile intervals; consult counts and do not interpret them as population certainty.

The fixed clean dataset, attack-generation seed 5007, motion seeds 7/17/27, detector seeds 6007/6017/6027, and uncertainty seed have separate roles. Changing a model seed does not regenerate motion. Seed means are repeated fits on the same cases, not independent datasets or three times as many test trials. Logistic regression uses deterministic lbfgs; its configured random_state does not create independent fitting variation. Zero seed SD describes identical outcomes, not a reliability guarantee.

Identifiers, labels, splits, severity, attack magnitudes, raw jitter/drop indices, tracking flags and construction outcomes are not detector inputs. Clean and attacked windows undergo the same canonical binary32 conversion and relative-pose feature path. Jitter/drop is resampled onto the original grid, so the detector cannot see discarded source timing directly. However exact frozen-pose repeats can be an artificial cue, and transformation labels do not establish malicious intent. These controls reduce obvious leakage but do not prove artifact-free detection on physical Quest data.

## Authentication evidence and limitations

The saved delivery evidence reconciles 14,956 distinct accepted events across 150 synthetic sessions, each with 9 motion and 6 detector calls. Paired inputs match; motion predictions and anomaly flags match; maximum score difference is 2.6645352591003757e-15. The verifier sequence was committed before model calls. This is at-most-once event release, not guaranteed callback completion.

Quality-valid pre-tag anomalies authenticate because the legitimate sender tags them. The anomaly decision stays downstream; it does not rewrite authentication or roll back state. This historical run used known-correct synthetic credential material and predates Will's new pre-HKDF gate. Reading it does not validate the updated gate, noisy reconstruction availability, or fresh end-to-end v2 timing. Detector-inclusive latency, durable audit I/O, approved human recordings and Quest deployment remain outside this addendum.

## Provenance and generated files

Historical evaluation source commit: `40da3a388983030b7b696ce7bf2b801e0ed6903f`. Dataset SHA-256: `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`.

The new manifest lists exactly the historical inputs checked, their byte hashes, this reporting code's hashes, reporting settings and environment. Unused joblib files are neither loaded nor required. Historical source hashes describe the old run and are not replaced by today's updated authentication code. The original run and manifest are unchanged.
