# Week 6 fresh v2 composite CPU timing

Source commit: `78f499a92f633a4793c776a070058e3a6a9a0b61`

Recorded fresh attempts (including warmup/first use): 3720.

Each of six predeclared conditions has 600 measured single-read attempts and 20 retained
validation warmups. The first warmup is condition-first-use, NOT a fully cold process.
Trusted enrollment has already initialized code algebra, but no decoder/model inference
warmup is hidden before the first condition. First decoder JIT overhead may appear there.

## Direct outer-path summaries

| Condition | Phase | Path | Decision/reason | n | p50 ms | p95 ms | p99 ms | max ms |
|---|---|---|---|---:|---:|---:|---:|---:|
| forest_motion_forest_anomaly | condition_first_use | bad_tag_receiver | reject/invalid_tag | 1 | 1.5252 | 1.5252 | 1.5252 | 1.5252 |
| forest_motion_forest_anomaly | condition_first_use | exact_replay_receiver | reject/duplicate_sequence | 1 | 4.9199 | 4.9199 | 4.9199 | 4.9199 |
| forest_motion_forest_anomaly | condition_first_use | fresh_to_first_window | accept/accepted | 1 | 42.0247 | 42.0247 | 42.0247 | 42.0247 |
| forest_motion_forest_anomaly | condition_first_use | malformed_json_receiver | reject/malformed_message | 1 | 0.1073 | 0.1073 | 0.1073 | 0.1073 |
| forest_motion_forest_anomaly | condition_first_use | post_window_after_refusals | accept/accepted | 1 | 31.8682 | 31.8682 | 31.8682 | 31.8682 |
| forest_motion_forest_anomaly | condition_first_use | post_window_recurring | accept/accepted | 1 | 38.7052 | 38.7052 | 38.7052 | 38.7052 |
| forest_motion_forest_anomaly | condition_first_use | pre_tag_quality_refusal | reject/data_quality_failure | 1 | 1.3344 | 1.3344 | 1.3344 | 1.3344 |
| forest_motion_forest_anomaly | condition_first_use | valid_receiver_after_bad_tag | accept/accepted | 1 | 29.2217 | 29.2217 | 29.2217 | 29.2217 |
| forest_motion_forest_anomaly | measured | bad_tag_receiver | reject/invalid_tag | 599 | 1.4641 | 1.9951 | 2.3740 | 2.8441 |
| forest_motion_forest_anomaly | measured | exact_replay_receiver | reject/duplicate_sequence | 599 | 4.7391 | 7.4808 | 9.0904 | 287.9302 |
| forest_motion_forest_anomaly | measured | fresh_to_first_window | accept/accepted | 599 | 41.9021 | 59.9307 | 65.2019 | 274.6759 |
| forest_motion_forest_anomaly | measured | fresh_to_first_window | reject/failed_reconstruction | 1 | 4.8532 | 4.8532 | 4.8532 | 4.8532 |
| forest_motion_forest_anomaly | measured | malformed_json_receiver | reject/malformed_message | 599 | 0.1009 | 0.1655 | 0.2176 | 1.2999 |
| forest_motion_forest_anomaly | measured | post_window_after_refusals | accept/accepted | 599 | 28.9083 | 39.3474 | 49.7616 | 263.2223 |
| forest_motion_forest_anomaly | measured | post_window_recurring | accept/accepted | 599 | 39.4365 | 52.8523 | 56.6526 | 337.0849 |
| forest_motion_forest_anomaly | measured | pre_tag_quality_refusal | reject/data_quality_failure | 599 | 1.2229 | 1.8468 | 2.2668 | 3.8265 |
| forest_motion_forest_anomaly | measured | valid_receiver_after_bad_tag | accept/accepted | 599 | 29.3665 | 36.9139 | 40.7922 | 46.0745 |
| logistic_motion_forest_anomaly | condition_first_use | bad_tag_receiver | reject/invalid_tag | 1 | 2.3446 | 2.3446 | 2.3446 | 2.3446 |
| logistic_motion_forest_anomaly | condition_first_use | exact_replay_receiver | reject/duplicate_sequence | 1 | 6.5408 | 6.5408 | 6.5408 | 6.5408 |
| logistic_motion_forest_anomaly | condition_first_use | fresh_to_first_window | accept/accepted | 1 | 41.6065 | 41.6065 | 41.6065 | 41.6065 |
| logistic_motion_forest_anomaly | condition_first_use | malformed_json_receiver | reject/malformed_message | 1 | 0.1291 | 0.1291 | 0.1291 | 0.1291 |
| logistic_motion_forest_anomaly | condition_first_use | post_window_after_refusals | accept/accepted | 1 | 23.3739 | 23.3739 | 23.3739 | 23.3739 |
| logistic_motion_forest_anomaly | condition_first_use | post_window_recurring | accept/accepted | 1 | 37.2286 | 37.2286 | 37.2286 | 37.2286 |
| logistic_motion_forest_anomaly | condition_first_use | pre_tag_quality_refusal | reject/data_quality_failure | 1 | 1.7313 | 1.7313 | 1.7313 | 1.7313 |
| logistic_motion_forest_anomaly | condition_first_use | valid_receiver_after_bad_tag | accept/accepted | 1 | 23.9786 | 23.9786 | 23.9786 | 23.9786 |
| logistic_motion_forest_anomaly | measured | bad_tag_receiver | reject/invalid_tag | 599 | 1.5247 | 2.0132 | 2.1388 | 2.4903 |
| logistic_motion_forest_anomaly | measured | exact_replay_receiver | reject/duplicate_sequence | 599 | 6.2809 | 9.2318 | 10.0719 | 223.1532 |
| logistic_motion_forest_anomaly | measured | fresh_to_first_window | accept/accepted | 599 | 26.1044 | 33.3164 | 37.6671 | 334.7859 |
| logistic_motion_forest_anomaly | measured | fresh_to_first_window | reject/failed_reconstruction | 1 | 2.9502 | 2.9502 | 2.9502 | 2.9502 |
| logistic_motion_forest_anomaly | measured | malformed_json_receiver | reject/malformed_message | 599 | 0.1197 | 0.1624 | 0.1929 | 0.4166 |
| logistic_motion_forest_anomaly | measured | post_window_after_refusals | accept/accepted | 599 | 22.0618 | 26.1512 | 29.6956 | 246.6332 |
| logistic_motion_forest_anomaly | measured | post_window_recurring | accept/accepted | 599 | 22.5875 | 30.3028 | 32.8717 | 262.9841 |
| logistic_motion_forest_anomaly | measured | pre_tag_quality_refusal | reject/data_quality_failure | 599 | 1.6995 | 2.1695 | 2.3617 | 2.7324 |
| logistic_motion_forest_anomaly | measured | valid_receiver_after_bad_tag | accept/accepted | 599 | 16.0434 | 21.1681 | 22.6223 | 24.0237 |
| logistic_motion_logistic_anomaly | condition_first_use | bad_tag_receiver | reject/invalid_tag | 1 | 1.3474 | 1.3474 | 1.3474 | 1.3474 |
| logistic_motion_logistic_anomaly | condition_first_use | exact_replay_receiver | reject/duplicate_sequence | 1 | 6.9017 | 6.9017 | 6.9017 | 6.9017 |
| logistic_motion_logistic_anomaly | condition_first_use | fresh_to_first_window | accept/accepted | 1 | 2729.3209 | 2729.3209 | 2729.3209 | 2729.3209 |
| logistic_motion_logistic_anomaly | condition_first_use | malformed_json_receiver | reject/malformed_message | 1 | 0.1790 | 0.1790 | 0.1790 | 0.1790 |
| logistic_motion_logistic_anomaly | condition_first_use | post_window_after_refusals | accept/accepted | 1 | 18.9868 | 18.9868 | 18.9868 | 18.9868 |
| logistic_motion_logistic_anomaly | condition_first_use | post_window_recurring | accept/accepted | 1 | 21.8563 | 21.8563 | 21.8563 | 21.8563 |
| logistic_motion_logistic_anomaly | condition_first_use | pre_tag_quality_refusal | reject/data_quality_failure | 1 | 2.5071 | 2.5071 | 2.5071 | 2.5071 |
| logistic_motion_logistic_anomaly | condition_first_use | valid_receiver_after_bad_tag | accept/accepted | 1 | 10.1307 | 10.1307 | 10.1307 | 10.1307 |
| logistic_motion_logistic_anomaly | measured | bad_tag_receiver | reject/invalid_tag | 599 | 1.5515 | 2.4318 | 3.0621 | 3.3109 |
| logistic_motion_logistic_anomaly | measured | exact_replay_receiver | reject/duplicate_sequence | 599 | 6.3682 | 9.6870 | 12.1546 | 210.8127 |
| logistic_motion_logistic_anomaly | measured | fresh_to_first_window | accept/accepted | 599 | 20.6127 | 31.3187 | 37.4013 | 278.4112 |
| logistic_motion_logistic_anomaly | measured | fresh_to_first_window | reject/failed_reconstruction | 1 | 3.7043 | 3.7043 | 3.7043 | 3.7043 |
| logistic_motion_logistic_anomaly | measured | malformed_json_receiver | reject/malformed_message | 599 | 0.1175 | 0.1872 | 0.2188 | 0.5070 |
| logistic_motion_logistic_anomaly | measured | post_window_after_refusals | accept/accepted | 599 | 17.1304 | 23.5106 | 30.8237 | 218.4561 |
| logistic_motion_logistic_anomaly | measured | post_window_recurring | accept/accepted | 599 | 17.6496 | 27.7629 | 34.1022 | 292.3259 |
| logistic_motion_logistic_anomaly | measured | pre_tag_quality_refusal | reject/data_quality_failure | 599 | 1.7169 | 2.4927 | 3.3937 | 3.6700 |
| logistic_motion_logistic_anomaly | measured | valid_receiver_after_bad_tag | accept/accepted | 599 | 10.6805 | 17.1426 | 21.1686 | 21.6186 |
| snn32_seed17_forest_anomaly | condition_first_use | bad_tag_receiver | reject/invalid_tag | 1 | 1.8269 | 1.8269 | 1.8269 | 1.8269 |
| snn32_seed17_forest_anomaly | condition_first_use | exact_replay_receiver | reject/duplicate_sequence | 1 | 8.5951 | 8.5951 | 8.5951 | 8.5951 |
| snn32_seed17_forest_anomaly | condition_first_use | fresh_to_first_window | accept/accepted | 1 | 56.6979 | 56.6979 | 56.6979 | 56.6979 |
| snn32_seed17_forest_anomaly | condition_first_use | malformed_json_receiver | reject/malformed_message | 1 | 0.0894 | 0.0894 | 0.0894 | 0.0894 |
| snn32_seed17_forest_anomaly | condition_first_use | post_window_after_refusals | accept/accepted | 1 | 32.4513 | 32.4513 | 32.4513 | 32.4513 |
| snn32_seed17_forest_anomaly | condition_first_use | post_window_recurring | accept/accepted | 1 | 47.5312 | 47.5312 | 47.5312 | 47.5312 |
| snn32_seed17_forest_anomaly | condition_first_use | pre_tag_quality_refusal | reject/data_quality_failure | 1 | 0.9817 | 0.9817 | 0.9817 | 0.9817 |
| snn32_seed17_forest_anomaly | condition_first_use | valid_receiver_after_bad_tag | accept/accepted | 1 | 36.9318 | 36.9318 | 36.9318 | 36.9318 |
| snn32_seed17_forest_anomaly | measured | bad_tag_receiver | reject/invalid_tag | 599 | 1.8500 | 1.9959 | 2.1233 | 2.5008 |
| snn32_seed17_forest_anomaly | measured | exact_replay_receiver | reject/duplicate_sequence | 599 | 7.3711 | 8.3679 | 11.7706 | 324.2851 |
| snn32_seed17_forest_anomaly | measured | fresh_to_first_window | accept/accepted | 599 | 55.5374 | 59.3553 | 63.7296 | 372.8408 |
| snn32_seed17_forest_anomaly | measured | fresh_to_first_window | reject/failed_reconstruction | 1 | 3.7359 | 3.7359 | 3.7359 | 3.7359 |
| snn32_seed17_forest_anomaly | measured | malformed_json_receiver | reject/malformed_message | 599 | 0.1458 | 0.1851 | 0.2128 | 0.2325 |
| snn32_seed17_forest_anomaly | measured | post_window_after_refusals | accept/accepted | 599 | 34.7314 | 40.4914 | 45.3025 | 316.5555 |
| snn32_seed17_forest_anomaly | measured | post_window_recurring | accept/accepted | 599 | 47.1784 | 50.5355 | 53.6224 | 359.2428 |
| snn32_seed17_forest_anomaly | measured | pre_tag_quality_refusal | reject/data_quality_failure | 599 | 1.8867 | 2.1492 | 2.2485 | 2.6116 |
| snn32_seed17_forest_anomaly | measured | valid_receiver_after_bad_tag | accept/accepted | 599 | 36.4062 | 38.1582 | 40.3519 | 46.3775 |
| snn32_seed27_forest_anomaly | condition_first_use | bad_tag_receiver | reject/invalid_tag | 1 | 1.6881 | 1.6881 | 1.6881 | 1.6881 |
| snn32_seed27_forest_anomaly | condition_first_use | exact_replay_receiver | reject/duplicate_sequence | 1 | 6.4463 | 6.4463 | 6.4463 | 6.4463 |
| snn32_seed27_forest_anomaly | condition_first_use | fresh_to_first_window | accept/accepted | 1 | 59.4637 | 59.4637 | 59.4637 | 59.4637 |
| snn32_seed27_forest_anomaly | condition_first_use | malformed_json_receiver | reject/malformed_message | 1 | 0.1214 | 0.1214 | 0.1214 | 0.1214 |
| snn32_seed27_forest_anomaly | condition_first_use | post_window_after_refusals | accept/accepted | 1 | 33.6509 | 33.6509 | 33.6509 | 33.6509 |
| snn32_seed27_forest_anomaly | condition_first_use | post_window_recurring | accept/accepted | 1 | 48.1399 | 48.1399 | 48.1399 | 48.1399 |
| snn32_seed27_forest_anomaly | condition_first_use | pre_tag_quality_refusal | reject/data_quality_failure | 1 | 1.5507 | 1.5507 | 1.5507 | 1.5507 |
| snn32_seed27_forest_anomaly | condition_first_use | valid_receiver_after_bad_tag | accept/accepted | 1 | 34.2320 | 34.2320 | 34.2320 | 34.2320 |
| snn32_seed27_forest_anomaly | measured | bad_tag_receiver | reject/invalid_tag | 599 | 1.6929 | 2.1146 | 2.9270 | 3.3379 |
| snn32_seed27_forest_anomaly | measured | exact_replay_receiver | reject/duplicate_sequence | 599 | 4.9154 | 8.5945 | 12.3837 | 324.5220 |
| snn32_seed27_forest_anomaly | measured | fresh_to_first_window | accept/accepted | 599 | 41.6731 | 59.5470 | 67.7996 | 362.8529 |
| snn32_seed27_forest_anomaly | measured | fresh_to_first_window | reject/failed_reconstruction | 1 | 2.6978 | 2.6978 | 2.6978 | 2.6978 |
| snn32_seed27_forest_anomaly | measured | malformed_json_receiver | reject/malformed_message | 599 | 0.1014 | 0.1752 | 0.2040 | 0.2464 |
| snn32_seed27_forest_anomaly | measured | post_window_after_refusals | accept/accepted | 599 | 25.1211 | 38.9728 | 44.9530 | 356.8650 |
| snn32_seed27_forest_anomaly | measured | post_window_recurring | accept/accepted | 599 | 40.2214 | 54.1160 | 59.6622 | 292.8711 |
| snn32_seed27_forest_anomaly | measured | pre_tag_quality_refusal | reject/data_quality_failure | 599 | 1.2773 | 2.1094 | 2.2746 | 2.9642 |
| snn32_seed27_forest_anomaly | measured | valid_receiver_after_bad_tag | accept/accepted | 599 | 26.3367 | 37.5776 | 39.1756 | 42.2513 |
| snn32_seed7_forest_anomaly | condition_first_use | bad_tag_receiver | reject/invalid_tag | 1 | 2.2682 | 2.2682 | 2.2682 | 2.2682 |
| snn32_seed7_forest_anomaly | condition_first_use | exact_replay_receiver | reject/duplicate_sequence | 1 | 5.6092 | 5.6092 | 5.6092 | 5.6092 |
| snn32_seed7_forest_anomaly | condition_first_use | fresh_to_first_window | accept/accepted | 1 | 42.1070 | 42.1070 | 42.1070 | 42.1070 |
| snn32_seed7_forest_anomaly | condition_first_use | malformed_json_receiver | reject/malformed_message | 1 | 0.0808 | 0.0808 | 0.0808 | 0.0808 |
| snn32_seed7_forest_anomaly | condition_first_use | post_window_after_refusals | accept/accepted | 1 | 23.2432 | 23.2432 | 23.2432 | 23.2432 |
| snn32_seed7_forest_anomaly | condition_first_use | post_window_recurring | accept/accepted | 1 | 38.2194 | 38.2194 | 38.2194 | 38.2194 |
| snn32_seed7_forest_anomaly | condition_first_use | pre_tag_quality_refusal | reject/data_quality_failure | 1 | 1.0279 | 1.0279 | 1.0279 | 1.0279 |
| snn32_seed7_forest_anomaly | condition_first_use | valid_receiver_after_bad_tag | accept/accepted | 1 | 31.9799 | 31.9799 | 31.9799 | 31.9799 |
| snn32_seed7_forest_anomaly | measured | bad_tag_receiver | reject/invalid_tag | 599 | 1.8580 | 2.0051 | 2.0556 | 2.4950 |
| snn32_seed7_forest_anomaly | measured | exact_replay_receiver | reject/duplicate_sequence | 599 | 7.4022 | 10.2237 | 12.2450 | 277.8234 |
| snn32_seed7_forest_anomaly | measured | fresh_to_first_window | accept/accepted | 599 | 55.8030 | 60.1001 | 62.8711 | 354.4788 |
| snn32_seed7_forest_anomaly | measured | fresh_to_first_window | reject/failed_reconstruction | 1 | 7.3034 | 7.3034 | 7.3034 | 7.3034 |
| snn32_seed7_forest_anomaly | measured | malformed_json_receiver | reject/malformed_message | 599 | 0.1500 | 0.1886 | 0.2095 | 0.2345 |
| snn32_seed7_forest_anomaly | measured | post_window_after_refusals | accept/accepted | 599 | 34.8505 | 40.5086 | 47.8401 | 293.5287 |
| snn32_seed7_forest_anomaly | measured | post_window_recurring | accept/accepted | 599 | 47.4545 | 51.3985 | 53.9641 | 342.7444 |
| snn32_seed7_forest_anomaly | measured | pre_tag_quality_refusal | reject/data_quality_failure | 599 | 1.9138 | 2.1645 | 2.3187 | 2.7803 |
| snn32_seed7_forest_anomaly | measured | valid_receiver_after_bad_tag | accept/accepted | 599 | 36.5688 | 38.5518 | 40.4533 | 58.3211 |

## Interpretation boundaries

Fresh timing starts before the modeled response read and ends after refusal or the first
composite inference. The source motion window is already loaded: physical capture is excluded.
Recurring/after-refusal full-window paths include binary32 conversion, sender binding/quality/HMAC,
receiver parser/HMAC/quality/sequence/audit commit, at-most-once conversion/preprocessing and both models.
Receiver-only paths exclude packet construction and sender sealing; pre-tag refusal is not an HMAC rejection.

The provisional 20 ms p95 target applies ONLY to complete post-window paths, including the anomaly
consumer here. It does not apply to fresh admission totals, receiver-only timings, maxima or hard deadlines.
Assess each recorded condition separately: no blanket meets-target claim, especially for random forest.

Motion-consumer timing includes normalization/tensor construction/prediction decoding, not only forward compute.
Credential verification, local admission, confirmation, serialization, HMAC and in-memory audit calls have
nested spans. Current replay-state checks/publication remain inside verifier authentication, not isolated
disjoint stages. Native HKDF values are nested in challenge/confirmation; never add nested percentiles.

All warmups, natural admission failures, slow values and maxima are retained. Paired noise streams and
sources are reused across conditions: 3,600 measured attempts are not 3,600 independent reliability trials.
Functional bad-tag/replay/malformed/quality controls are NOT formal varied Tier-1 evaluation.

Post-window distributions are conditional on successful admission; natural admission refusals remain
in fresh-attempt totals. Model conditions run in fixed order, so thermal/background drift is not
eliminated by pairing source/noise streams. This is not a causal hardware comparison.

## Outlier evidence, not invented diagnoses

The per-condition outliers-*.jsonl files retain every >20 ms observation, group p99 tail and maximum,
with full stage trees, GC overlap, thread CPU and wall gaps. Disk/progress output is outside each span.
A wall/thread-CPU gap can reflect waiting, worker work or descheduling; it does not prove OS scheduling.
GC overlap does not prove that GC caused all delay. Allocation/cache/frequency/OS causes are unmeasured
and explicitly unresolved. Further causal profiling is required before explaining every large outlier.

Instrumentation uses temporary wrappers and GC callbacks. overhead.json records a no-op proxy, not a
calibrated correction; no subtraction or claim of uninstrumented application latency is made.
Read machine start/end snapshots and self-reported AC/background conditions in environment.json.
Power plan is recorded, not changed; hybrid-core placement and CPU frequency are uncontrolled.

Instrumented, single-process CPU software prototype with loaded synthetic windows, six fixed simulated PUF profiles and paired repeated sources/noise streams. Not hardware response acquisition, physical two-second motion capture, network transport, durable audit, an independent FRR/security study, real-time guarantee or Quest/cross-device/person generalization. Enrollment, loading, endpoint construction, result/progress I/O and orderly shutdown are outside the timed boundary. All nested spans include observer overhead. Outlier location/GC overlap/CPU gaps do not establish causation.

No training, selection, architecture expansion, reconstruction-policy or protocol change.
