# Bounded exact-quality arithmetic comparison

Only quality arithmetic changes between isolated workers. The default v2 path is unchanged.
Two AB/BA paired noise blocks; three predeclared frozen configurations; 120 measured and
30 validation warmup admissions per configuration/mode/block. All failures and first uses retained.

## Direct accepted totals (conditional on successful admission)

| Block | Mode | Configuration | Phase / path | n | p50 ms | p95 ms | p99 ms | max ms |
|---|---|---|---|---:|---:|---:|---:|---:|
| 0 | reference_fraction | logistic_motion_forest_anomaly | measured / fresh_to_first_window | 120 | 33.4373 | 45.0540 | 47.3576 | 48.4475 |
| 0 | reference_fraction | logistic_motion_forest_anomaly | measured / post_window_recurring | 120 | 29.3808 | 40.9905 | 44.4152 | 46.3546 |
| 0 | reference_fraction | logistic_motion_logistic_anomaly | measured / fresh_to_first_window | 120 | 27.5512 | 34.6154 | 38.3127 | 357.8313 |
| 0 | reference_fraction | logistic_motion_logistic_anomaly | measured / post_window_recurring | 120 | 21.7873 | 27.4285 | 28.3976 | 30.2832 |
| 0 | reference_fraction | snn32_seed7_forest_anomaly | measured / fresh_to_first_window | 120 | 44.6388 | 52.6902 | 57.5718 | 62.8287 |
| 0 | reference_fraction | snn32_seed7_forest_anomaly | measured / post_window_recurring | 120 | 39.3152 | 46.5381 | 48.3202 | 55.0178 |
| 0 | candidate_dyadic | logistic_motion_forest_anomaly | measured / fresh_to_first_window | 120 | 21.5541 | 31.0356 | 35.2531 | 36.5154 |
| 0 | candidate_dyadic | logistic_motion_forest_anomaly | measured / post_window_recurring | 120 | 18.5179 | 25.0066 | 28.1944 | 35.9363 |
| 0 | candidate_dyadic | logistic_motion_logistic_anomaly | measured / fresh_to_first_window | 120 | 16.9821 | 22.2278 | 25.1668 | 334.6179 |
| 0 | candidate_dyadic | logistic_motion_logistic_anomaly | measured / post_window_recurring | 120 | 11.3977 | 14.2551 | 14.6007 | 14.7113 |
| 0 | candidate_dyadic | snn32_seed7_forest_anomaly | measured / fresh_to_first_window | 120 | 28.7303 | 37.7728 | 40.9676 | 44.9913 |
| 0 | candidate_dyadic | snn32_seed7_forest_anomaly | measured / post_window_recurring | 120 | 26.2252 | 32.1141 | 37.4021 | 37.8880 |
| 1 | candidate_dyadic | logistic_motion_forest_anomaly | measured / fresh_to_first_window | 119 | 26.0857 | 35.0740 | 39.8133 | 44.2887 |
| 1 | candidate_dyadic | logistic_motion_forest_anomaly | measured / post_window_recurring | 119 | 20.5644 | 28.9934 | 32.2455 | 33.9667 |
| 1 | candidate_dyadic | logistic_motion_logistic_anomaly | measured / fresh_to_first_window | 119 | 18.2412 | 23.4115 | 26.1416 | 35.8083 |
| 1 | candidate_dyadic | logistic_motion_logistic_anomaly | measured / post_window_recurring | 119 | 12.1987 | 15.3827 | 17.5056 | 17.7962 |
| 1 | candidate_dyadic | snn32_seed7_forest_anomaly | measured / fresh_to_first_window | 119 | 39.0046 | 49.9577 | 56.6905 | 355.3507 |
| 1 | candidate_dyadic | snn32_seed7_forest_anomaly | measured / post_window_recurring | 119 | 32.5475 | 40.8279 | 50.0594 | 52.0476 |
| 1 | reference_fraction | logistic_motion_forest_anomaly | measured / fresh_to_first_window | 119 | 35.5990 | 48.2380 | 79.2610 | 98.9675 |
| 1 | reference_fraction | logistic_motion_forest_anomaly | measured / post_window_recurring | 119 | 30.7899 | 41.3853 | 46.3709 | 48.6078 |
| 1 | reference_fraction | logistic_motion_logistic_anomaly | measured / fresh_to_first_window | 119 | 25.7871 | 31.3079 | 36.1394 | 39.4958 |
| 1 | reference_fraction | logistic_motion_logistic_anomaly | measured / post_window_recurring | 119 | 20.8554 | 25.1534 | 29.8900 | 30.3449 |
| 1 | reference_fraction | snn32_seed7_forest_anomaly | measured / fresh_to_first_window | 119 | 46.5814 | 68.1923 | 71.0508 | 362.1873 |
| 1 | reference_fraction | snn32_seed7_forest_anomaly | measured / post_window_recurring | 119 | 40.0425 | 48.6062 | 51.4827 | 53.0702 |

Compare candidate against its NEW matched reference, not against historical laptop percentiles.
Per-block results are descriptive; two reused-source noise blocks do not supply a robust population CI.
Paired deltas are candidate minus reference for identical inputs/outcomes, not differences of percentiles.
Rejects/fresh admission failures have separate rows and denominators. Never add stage p95s for a total.

## Sustained same-session processing

| Block | Mode | Configuration | Planned / completed | Closed-loop windows/s |
|---|---|---|---:|---:|
| 0 | reference_fraction | logistic_motion_logistic_anomaly | 64 / 64 | 61.203 |
| 0 | reference_fraction | logistic_motion_forest_anomaly | 64 / 64 | 46.364 |
| 0 | reference_fraction | snn32_seed7_forest_anomaly | 64 / 64 | 35.967 |
| 0 | candidate_dyadic | logistic_motion_logistic_anomaly | 64 / 64 | 99.632 |
| 0 | candidate_dyadic | logistic_motion_forest_anomaly | 64 / 64 | 82.964 |
| 0 | candidate_dyadic | snn32_seed7_forest_anomaly | 64 / 64 | 43.088 |
| 1 | candidate_dyadic | snn32_seed7_forest_anomaly | 64 / 64 | 39.179 |
| 1 | candidate_dyadic | logistic_motion_forest_anomaly | 64 / 64 | 59.067 |
| 1 | candidate_dyadic | logistic_motion_logistic_anomaly | 64 / 64 | 72.761 |
| 1 | reference_fraction | snn32_seed7_forest_anomaly | 64 / 64 | 30.876 |
| 1 | reference_fraction | logistic_motion_forest_anomaly | 64 / 64 | 49.673 |
| 1 | reference_fraction | logistic_motion_logistic_anomaly | 64 / 64 | 60.697 |

The 64-window burst reuses the final PLANNED admission. If it fails, report N/A; do not retry
or replace that attempt. Bursts use 64 distinct same-profile preselected test windows. Automatic GC
stays enabled; closed-loop throughput includes assertions, signatures and evidence writes but
excludes admission, loading and final cleanup. Worker-wide mixed workload capacity includes cleanup
and is reported separately: it is NOT recurring-only throughput. This is unpaced capacity, not a
sensor-arrival/backpressure study. Coarse working-set/private-commit snapshots are not stage peaks.

## Stage and interpretation boundaries

Worker tables retain the SAME nested timers and per-root exclusive partition as the historical
stage analysis. Sender serialization still includes quality; receiver quality is separately timed.
Binding/sequence/locks/state and handshake/HKDF/confirmation remainders remain explicitly unisolated.
Full in-memory audit calls are included; durable audit storage is not. Motion and anomaly consumer
timings include their own scaling/normalization/dispatch work. Public input/output fingerprints are
computed after roots; storing references inside callbacks is observer overhead in both modes.

The wire comparison neutralizes ONLY the 16 fresh random session-ID bytes in a post-timer COPY;
all other authenticated header/payload bytes remain in that hash. Actual packets/HMAC bindings
are untouched. Random session IDs and cryptographic tags are not expected to match across workers.

The provisional 20 ms boundary is complete post-window processing, not receiver-only, crypto-only
or motion-only timing. Report any observed bounded-cohort attainment with its sample size and
conditions, without declaring deployment qualification. Keep the original architecture's unmet
target and historical evidence visible. The physical TWO-SECOND acquisition window is additional
and excluded: these numbers are not total event-to-decision latency.

This tests one shared application bottleneck; it cannot remove SNN or forest inference costs.
Seed 7 was predeclared, not chosen for speed; other SNN seeds remain historical evidence.
No fresh majority-3/correlated-noise study, conventional-key control, new security trial, model
search, threshold adjustment, OS tracing or default authentication change occurred.

Paired bounded software arithmetic comparison, not a new independent held-out accuracy/FRR/security study or production adoption. Two blocks reuse 120 test sources across modes/models and 64 further preselected same-profile windows for unpaced closed-loop session reuse. Single-read baseline BCH(63,36,t=5), 32-bit pilot credential; NOT integrated majority-3. GC remains enabled. All roots include observer costs; streamed evidence is outside root timers but inside closed-loop throughput. Physical PUF/sensor acquisition, the two-second motion acquisition window, network, durable audit, enrollment/loading and evidence I/O are excluded from root latency. No hard deadline, Quest, cross-device/person generalization or isolated Windows/cache/power causality claim.
