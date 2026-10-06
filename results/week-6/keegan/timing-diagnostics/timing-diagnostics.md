# Saved Week 6 v2 timing and outlier addendum

Benchmark source commit: `78f499a92f633a4793c776a070058e3a6a9a0b61`. Results commit: `a4a9e2548fd30ee2383923dbd0de6cd5c45c587f`.

This is a read-only analysis of the completed instrumented run. It performs no new timing, response reads, authentication, model loading/inference, fitting or threshold selection. Original files remain unchanged.

## Complete-path comparison (measured accepted attempts only)

| Condition | n | Fresh-to-first p95 ms | First post-window p95 ms | Recurring p50 / p95 / p99 / max ms | After-refusal p95 ms | All three post-window p95 <=20 ms? |
|---|---:|---:|---:|---|---:|---|
| logistic_motion_logistic_anomaly | 599 | 31.3187 | 27.0020 | 17.6496 / 27.7629 / 34.1022 / 292.3259 | 23.5106 | no |
| logistic_motion_forest_anomaly | 599 | 33.3164 | 29.5842 | 22.5875 / 30.3028 / 32.8717 / 262.9841 | 26.1512 | no |
| forest_motion_forest_anomaly | 599 | 59.9307 | 52.2101 | 39.4365 / 52.8523 / 56.6526 / 337.0849 | 39.3474 | no |
| snn32_seed7_forest_anomaly | 599 | 60.1001 | 51.6710 | 47.4545 / 51.3985 / 53.9641 / 342.7444 | 40.5086 | no |
| snn32_seed17_forest_anomaly | 599 | 59.3553 | 51.0221 | 47.1784 / 50.5355 / 53.6224 / 359.2428 | 40.4914 | no |
| snn32_seed27_forest_anomaly | 599 | 59.5470 | 54.7558 | 40.2214 / 54.1160 / 59.6622 / 292.8711 | 38.9728 | no |

The 20 ms software-prototype p95 target applies to directly measured complete post-window paths, including both consumers. It does not apply to admission totals, receiver-only controls, maxima or hard real-time deadlines. These instrumented CPU observations do not establish uninstrumented/headset latency or a causal advantage of one model; condition order, CPU frequency and core placement were uncontrolled.

## Accounting and denominators

All 3,720 fresh attempts and 29,718 root traces reconcile. Each condition has 20 retained validation warmups and 600 test-source attempts. First use is separate from the other 19 warmups. Admission failures stay in the fresh-attempt denominator; post-window timings are conditional on successful admission. Rejected traffic has zero model calls.

The same source/noise streams are paired across conditions. The repeated failure is not six independent reliability observations, and this run is not an FRR or formal Tier-1 study. Every refused admission is tabulated in reconciliation.json. Existing Tier-2 recall/FPR and historical Week 4 timing results are separate experiments.

## Retained slow/tail observations

An observation is retained if wall time is >20 ms OR at least the p99 of its condition/phase/path/decision/reason group. Counts overlap and must not be added. With tiny groups, the maximum is retained even if fast; with slow model paths, many ordinary observations exceed 20 ms. This is not an estimate of a rare-fault rate.

outlier-summary.csv gives every group's denominator and absolute/tail/GC counts. retained-outlier-detail.csv lists every retained observation. group-maxima.csv keeps all root-group maxima, including rejection controls and first use. complete-path-latency.csv includes all direct roots and directly timed first-post-window spans, with p50/p95/p99/max. Original nested spans and raw trees remain in fresh-v2-timing.

## Largest measured root observation in each condition

| Condition | Path | Wall ms | GC overlap ms | GC / wall | Largest nested stage |
|---|---|---:|---:|---:|---|
| logistic_motion_logistic_anomaly | post_window_recurring | 292.3259 | 269.0324 | 92.03% | verifier_authentication_total |
| logistic_motion_forest_anomaly | fresh_to_first_window | 334.7859 | 306.6628 | 91.60% | first_post_window_total |
| forest_motion_forest_anomaly | post_window_recurring | 337.0849 | 306.6364 | 90.97% | verifier_authentication_total |
| snn32_seed7_forest_anomaly | fresh_to_first_window | 354.4788 | 320.1000 | 90.30% | first_post_window_total |
| snn32_seed17_forest_anomaly | fresh_to_first_window | 372.8408 | 337.6541 | 90.56% | first_post_window_total |
| snn32_seed27_forest_anomaly | fresh_to_first_window | 362.8529 | 335.0327 | 92.33% | first_post_window_total |

The largest retained condition-first-use fresh path is 2729.3209 ms in logistic_motion_logistic_anomaly, with 2704.7969 ms in reconstruction. This is a separate first-use observation, not part of measured p95. Backend compilation/cache effects are possible but were not separately isolated.

## What the GC evidence does and does not show

GC overlap is the union of recorded GC intervals clipped to the actual root or named stage. Duplicate/overlapping intervals are not double-counted. Generation-2 overlap is reported separately and is already contained in total GC overlap; do not add it again. Nested-stage durations overlap too and cannot be summed into end-to-end latency. Nested exception flags from a parser/quality function can be caught by the normal rejection path; they are retained and are not automatically labeled benchmark failures. An uncaught outer-span exception is not a completed observation.

Large measured maxima coincide with substantial GC activity. This is an observed contributor/location, not proof that GC explains all latency or that all GC originates in application code. The benchmark's collectors, retained trace trees and temporary wrappers may themselves affect allocations and heap scanning; that contribution was not isolated. No-op observer timings are not a calibrated correction and are never subtracted.

Wall/thread-CPU gaps do not distinguish scheduling, waiting, worker work, allocation or clock granularity. Many short spans have zero recorded thread-CPU time; the original metadata did not record its clock resolution. GC remains enabled, and timing/progress output and disk writes are outside the measured roots. Durable application audit storage, physical acquisition and network transport are still excluded.

## Remaining causal work (not completed by this addendum)

A separately declared diagnostic experiment must isolate collector/retention effects and GC pauses before attributing the historical maxima to application latency. Scheduling/power, allocation and cache causes remain unresolved without direct measurements. Any diagnostic repeats must preserve this run, keep the same models/thresholds/admission policy and retain refusals; do not remove slow values or disable GC merely to manufacture a passing p95.

Expanded varied Tier-1 evaluation, controlled reconstruction improvements, precise trust/key specification, durable audit performance and approved Quest logger validation remain separate/shared work. No SNN architecture or anomaly-model expansion follows from this report.
