# Week 6 revision: source-aware historical Tier-2 outcomes

This is an uncertainty/reporting addendum to the completed Week 5 experiment. The saved counts, predictions, models and validation-selected thresholds are unchanged. No attack generation, model loading, inference, training, authentication, timing or recording ran.

## Scope and accounting

The historical experiment used cross-session synthetic windows from six fixed profiles: Session 1 training, Session 2 validation, Session 3 test. Its motion SNN is SNN-64, NOT the SNN-32 in the newer v2 timing study. Its saved authenticated deliveries predate the current v2 independent-credential-verification integration; do not relabel them current-v2 tests.

All splits: **50,400 planned = 44,899 quality-valid + 5,501 pre-tag blocks**. The blocks comprise **3,493 timestamp-gap + 2,008 non-increasing-timestamp cases**. Test only: **16,800 planned = 14,956 quality-valid/accepted + 1,844 pre-tag blocks** (1,160 gap, 684 order). The test contains 600 source windows, each with one clean control and 27 planned transformations. Saved delivery evidence confirms acceptance and identical paired model inputs/predictions for every quality-valid test case.

A pre-tag quality block is a separate outcome: it has no authentication tag, accepted delivery or model prediction. It is not an anomaly true positive, authenticated rejection or detector miss. A missed anomaly is a quality-valid, authenticated transformation which the detector did not flag. The construction record's not_attempted field is an earlier-stage status, not the final delivery decision.

## Frozen-family summary and unmet targets

Family values are arithmetic means of three FIXED detector fits. Shared source bootstrap weights are used for every fit; seeds are not three independent datasets. Intervals are 95% stratified source-bootstrap percentile intervals, conditional on these six profiles, one held-out session and fixed class counts.

| Detector family | All-quality-valid F1 [95% interval] | Medium/high recall [95% interval] | Clean FPR [95% interval] | Observed targets |
|---|---|---|---|---|
| logistic_regression | 84.24% [83.83, 84.66] | 82.85% [82.42, 83.29] | 5.33% [3.83, 7.17] | recall missed; FPR missed |
| random_forest | 90.03% [89.80, 90.26] | 87.95% [87.73, 88.19] | 2.94% [1.78, 4.22] | recall missed; FPR met |

Medium/high recall uses 9,095 quality-valid transformed cases; clean FPR uses 600 clean source controls, NOT 600 new controls per attack or seed. Neither detector family reaches the predeclared 90% medium/high recall target. Logistic also exceeds the 5% clean-FPR limit. These observed criteria and thresholds have not been changed because of test performance.

## Every attack type / severity

This compact table gives quality accounting and fixed-family flag rates. For transformed cases the flag rate is recall among quality-valid accepted cases; for clean it is FPR. Full exact per-seed detections, misses, clean false positives, rejection counts and frozen thresholds are in detector-outcomes.csv (168 rows). All test conditions planned 600 source cases; quality-valid = authenticated accepted.

| Type | Severity | Eligible accepted | Gap blocks | Order blocks | LR rate [95% interval] | RF rate [95% interval] |
|---|---|---:|---:|---:|---|---|
| clean | clean | 600 | 0 | 0 | 5.33% [3.83, 7.17] | 2.94% [1.78, 4.22] |
| dropped_samples | high | 4 | 596 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| dropped_samples | low | 461 | 139 | 0 | 51.84% [47.45, 56.25] | 40.06% [36.04, 44.27] |
| dropped_samples | medium | 175 | 425 | 0 | 94.29% [90.67, 97.37] | 97.71% [96.08, 99.16] |
| frozen_pose | high | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| frozen_pose | low | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| frozen_pose | medium | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| orientation_drift | high | 600 | 0 | 0 | 14.17% [11.50, 17.00] | 13.06% [10.94, 15.39] |
| orientation_drift | low | 600 | 0 | 0 | 6.00% [4.33, 8.00] | 3.11% [2.00, 4.39] |
| orientation_drift | medium | 600 | 0 | 0 | 6.00% [4.17, 7.83] | 5.39% [3.83, 7.06] |
| orientation_jump | high | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| orientation_jump | low | 600 | 0 | 0 | 88.83% [86.33, 91.33] | 78.00% [74.89, 81.00] |
| orientation_jump | medium | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| orientation_noise | high | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| orientation_noise | low | 600 | 0 | 0 | 29.17% [25.83, 32.83] | 89.89% [87.55, 92.06] |
| orientation_noise | medium | 600 | 0 | 0 | 92.33% [90.33, 94.33] | 100.00% [100.00, 100.00]* |
| position_drift | high | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| position_drift | low | 600 | 0 | 0 | 34.17% [30.50, 37.83] | 35.67% [32.22, 39.06] |
| position_drift | medium | 600 | 0 | 0 | 98.50% [97.50, 99.33] | 99.61% [99.11, 99.94] |
| position_jump | high | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| position_jump | low | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| position_jump | medium | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| position_noise | high | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| position_noise | low | 600 | 0 | 0 | 85.33% [82.66, 88.00] | 100.00% [100.00, 100.00]* |
| position_noise | medium | 600 | 0 | 0 | 100.00% [100.00, 100.00]* | 100.00% [100.00, 100.00]* |
| timestamp_jitter | high | 0 | 0 | 600 | N/A | N/A |
| timestamp_jitter | low | 600 | 0 | 0 | 5.83% [4.17, 7.67] | 90.61% [88.33, 92.67] |
| timestamp_jitter | medium | 516 | 0 | 84 | 19.38% [16.08, 22.42] | 100.00% [100.00, 100.00]* |

*Small cohorts (<30 eligible sources) and/or degenerate empirical intervals are flagged, not evidence of certain detection. High dropped_samples has only four eligible sources: all four were flagged by each fit. Its [100%,100%] bootstrap interval cannot reveal unseen misses. 31 of 2,000 draws contain no eligible case and are explicitly undefined, not retried. High timestamp_jitter has zero eligible cases: recall and its interval are N/A, not 100% or zero. Defined/undefined draw counts and degeneracy flags are saved for every rate.

## Motion degradation is a separate objective

motion-degradation.csv has 252 rows: all 28 conditions x nine frozen motion fits. Each transformed condition is compared with clean predictions from exactly its eligible source subset. Clean-minus-transformed accuracy loss has a source-paired 95% bootstrap interval. Clean/transformed macro-F1 and its loss are descriptive points, using the fixed five-class label set; this report does not claim an F1 interval. Existing full confusion matrices remain in the historical breakdown. A classification error can choose the wrong motion action; an anomaly flag indicates suspect sensor semantics, not a failed HMAC. Legitimate low-amplitude nod/still ambiguity is a separate execution-variation analysis, not automatically an anomaly-detector failure. This report neither changes that interpretation nor claims an SNN advantage over conventional baselines.

## Source-aware uncertainty protocol

Fixed reporting settings: PCG64 seed 7027, 2,000 draws; 2.5th/97.5th percentiles with NumPy's linear quantile method. Resample source windows with replacement within each fixed profile/session/motion-class stratum (30 strata, 20 sources each). This saved dataset has exactly one window per source trial; a dataset with multiple windows per trial must use a revised trial-level cluster protocol rather than this script.

For a sampled source, one multiplicity applies jointly to ALL its derivatives, quality outcomes, matched clean prediction and detector/motion fits. For each draw, aggregate source contributions before dividing: e.g. medium/high recall is summed flagged eligible medium/high cases divided by summed eligible medium/high cases. Thus the pooled cases are not resampled as independent messages. Clean FPR uses the same resampled source weights. Paired accuracy loss sums clean-correct minus transformed-correct over eligible derivatives.

source-cohort.csv gives the canonical source-column mapping; bootstrap-source-weights.csv preserves every integer multiplicity for replay. The matrix hash uses little-endian uint16 C-order bytes. Bootstrap draws are statistical resampling, not new experiments, security trials or model fits. Undefined ratios have no eligible denominator and are omitted only from that metric's percentile calculation, with counts reported; no replacement draws are generated to force eligibility.

These intervals assume exchangeable independently generated source trials within fixed strata. They handle dependence of derivatives and paired fits, not uncertainty across new devices, people, sessions or independently generated populations. There is only one held-out session per fixed profile: no cross-session-population or hardware generalization interval is estimable here. Systematic synthetic-generator artifacts, shared profile effects and training variation are outside these conditional intervals. Prior binomial intervals remain historical supplementary conditional descriptions, not evidence that all pooled transformed messages were independent.

## Preservation and remaining work

The pinned manifest, completion marker, nine saved input artifacts and source code hashes are checked before and after reporting. Recomputed detector counts/rates and every motion confusion matrix/F1 reconcile with the frozen results. Original threshold calibration, generation parameters and train/test splits are unchanged. This addendum does not re-audit generator cues through new data: metadata exclusion and source/split rules remain the recorded design.

This completes the saved Tier-2 source-aware reporting revision only. It does not complete the narrow current-v2 stage measurements/one-bottleneck optimization, majority-3/correlated-noise integration, provisioned-credential control, release manifest, paper evaluation or hardware/institutional approval requirements.
