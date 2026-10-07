# Separate Week 6 observer/GC diagnostic

Four paired noise blocks, four diagnostic modes and six unchanged model conditions.
Each worker/model keeps 30 validation warmups and 60 preselected test-source attempts.
16 fresh timing workers retain all 8,640 natural admission attempts; four additional
fresh processes probe historical trace metadata at 0/5,000/15,000/29,718 retained rows.

## Measured recurring path (conditional on successful admission)

| Block | Mode | Model condition | n | p50 ms | p95 ms | p99 ms | max ms |
|---|---|---|---:|---:|---:|---:|---:|
| 0 | nested_retained_gc_on | forest_motion_forest_anomaly | 60 | 43.5267 | 53.1594 | 55.8678 | 56.5736 |
| 0 | nested_retained_gc_on | logistic_motion_forest_anomaly | 60 | 23.7920 | 31.6487 | 33.1102 | 33.6867 |
| 0 | nested_retained_gc_on | logistic_motion_logistic_anomaly | 60 | 18.1379 | 19.3195 | 124.6937 | 275.5404 |
| 0 | nested_retained_gc_on | snn32_seed17_forest_anomaly | 60 | 34.2898 | 48.3621 | 51.3268 | 53.5870 |
| 0 | nested_retained_gc_on | snn32_seed27_forest_anomaly | 60 | 36.4838 | 48.4852 | 50.3203 | 50.4448 |
| 0 | nested_retained_gc_on | snn32_seed7_forest_anomaly | 60 | 32.7229 | 48.5883 | 52.5565 | 53.7050 |
| 0 | nested_stream_gc_on | forest_motion_forest_anomaly | 60 | 42.5651 | 50.5183 | 54.4425 | 57.3633 |
| 0 | nested_stream_gc_on | logistic_motion_forest_anomaly | 60 | 22.1153 | 32.0488 | 128.4623 | 266.1974 |
| 0 | nested_stream_gc_on | logistic_motion_logistic_anomaly | 60 | 17.5696 | 25.0907 | 25.5641 | 25.7419 |
| 0 | nested_stream_gc_on | snn32_seed17_forest_anomaly | 60 | 33.8340 | 44.8872 | 48.2175 | 49.7440 |
| 0 | nested_stream_gc_on | snn32_seed27_forest_anomaly | 60 | 34.8233 | 47.3768 | 47.9944 | 48.2709 |
| 0 | nested_stream_gc_on | snn32_seed7_forest_anomaly | 60 | 34.3541 | 46.5713 | 48.8689 | 50.2189 |
| 0 | nested_stream_gc_deferred | forest_motion_forest_anomaly | 60 | 38.8663 | 42.1376 | 45.6297 | 50.5417 |
| 0 | nested_stream_gc_deferred | logistic_motion_forest_anomaly | 60 | 20.9306 | 26.4271 | 27.5352 | 27.5974 |
| 0 | nested_stream_gc_deferred | logistic_motion_logistic_anomaly | 60 | 15.9881 | 16.6965 | 18.9177 | 19.0189 |
| 0 | nested_stream_gc_deferred | snn32_seed17_forest_anomaly | 60 | 34.0243 | 47.1989 | 47.6302 | 47.6409 |
| 0 | nested_stream_gc_deferred | snn32_seed27_forest_anomaly | 60 | 33.4507 | 39.4775 | 41.5642 | 42.4608 |
| 0 | nested_stream_gc_deferred | snn32_seed7_forest_anomaly | 60 | 35.6720 | 45.5829 | 47.6600 | 50.0017 |
| 0 | outer_stream_gc_on | forest_motion_forest_anomaly | 60 | 37.2666 | 42.6801 | 47.9836 | 48.1933 |
| 0 | outer_stream_gc_on | logistic_motion_forest_anomaly | 60 | 21.3663 | 23.5196 | 24.0836 | 24.5362 |
| 0 | outer_stream_gc_on | logistic_motion_logistic_anomaly | 60 | 15.9354 | 20.8043 | 119.2497 | 258.6076 |
| 0 | outer_stream_gc_on | snn32_seed17_forest_anomaly | 60 | 34.6403 | 45.9624 | 50.2558 | 55.0809 |
| 0 | outer_stream_gc_on | snn32_seed27_forest_anomaly | 60 | 31.3236 | 43.3587 | 47.0084 | 47.6084 |
| 0 | outer_stream_gc_on | snn32_seed7_forest_anomaly | 60 | 32.6341 | 35.2859 | 35.8091 | 35.9826 |
| 1 | nested_stream_gc_on | forest_motion_forest_anomaly | 60 | 36.1215 | 43.1674 | 43.5542 | 43.6544 |
| 1 | nested_stream_gc_on | logistic_motion_forest_anomaly | 60 | 21.8244 | 24.9055 | 25.1989 | 25.3269 |
| 1 | nested_stream_gc_on | logistic_motion_logistic_anomaly | 60 | 15.8489 | 20.3920 | 22.2541 | 23.2989 |
| 1 | nested_stream_gc_on | snn32_seed17_forest_anomaly | 60 | 34.4879 | 36.3175 | 142.1988 | 284.3644 |
| 1 | nested_stream_gc_on | snn32_seed27_forest_anomaly | 60 | 35.5277 | 39.4440 | 46.0036 | 49.6038 |
| 1 | nested_stream_gc_on | snn32_seed7_forest_anomaly | 60 | 31.4739 | 36.0928 | 37.2181 | 37.2365 |
| 1 | outer_stream_gc_on | forest_motion_forest_anomaly | 60 | 36.9600 | 47.8839 | 134.9258 | 254.3101 |
| 1 | outer_stream_gc_on | logistic_motion_forest_anomaly | 60 | 20.9900 | 22.9980 | 24.6830 | 25.6936 |
| 1 | outer_stream_gc_on | logistic_motion_logistic_anomaly | 60 | 19.4467 | 21.9204 | 23.8797 | 23.8848 |
| 1 | outer_stream_gc_on | snn32_seed17_forest_anomaly | 60 | 31.2583 | 36.4256 | 45.5279 | 46.7839 |
| 1 | outer_stream_gc_on | snn32_seed27_forest_anomaly | 60 | 33.3991 | 35.4738 | 45.1523 | 47.5587 |
| 1 | outer_stream_gc_on | snn32_seed7_forest_anomaly | 60 | 32.3075 | 37.3471 | 41.1901 | 45.7474 |
| 1 | nested_retained_gc_on | forest_motion_forest_anomaly | 60 | 36.1870 | 48.1350 | 49.3852 | 50.3083 |
| 1 | nested_retained_gc_on | logistic_motion_forest_anomaly | 60 | 24.6300 | 29.3852 | 32.6882 | 34.2055 |
| 1 | nested_retained_gc_on | logistic_motion_logistic_anomaly | 60 | 17.4216 | 19.1922 | 121.7621 | 268.9494 |
| 1 | nested_retained_gc_on | snn32_seed17_forest_anomaly | 60 | 31.2294 | 36.0488 | 47.2567 | 47.3045 |
| 1 | nested_retained_gc_on | snn32_seed27_forest_anomaly | 60 | 31.3845 | 44.4339 | 45.2170 | 45.8669 |
| 1 | nested_retained_gc_on | snn32_seed7_forest_anomaly | 60 | 31.0716 | 38.5202 | 44.4489 | 45.1658 |
| 1 | nested_stream_gc_deferred | forest_motion_forest_anomaly | 60 | 41.3563 | 45.1384 | 48.1531 | 51.2865 |
| 1 | nested_stream_gc_deferred | logistic_motion_forest_anomaly | 60 | 23.4170 | 27.6875 | 29.2088 | 29.7317 |
| 1 | nested_stream_gc_deferred | logistic_motion_logistic_anomaly | 60 | 15.7807 | 17.4900 | 20.5022 | 20.6568 |
| 1 | nested_stream_gc_deferred | snn32_seed17_forest_anomaly | 60 | 30.8132 | 32.6904 | 44.5706 | 45.4052 |
| 1 | nested_stream_gc_deferred | snn32_seed27_forest_anomaly | 60 | 31.1103 | 32.4927 | 38.5355 | 46.7169 |
| 1 | nested_stream_gc_deferred | snn32_seed7_forest_anomaly | 60 | 30.6564 | 32.3682 | 38.9046 | 46.7140 |
| 2 | outer_stream_gc_on | forest_motion_forest_anomaly | 60 | 39.2829 | 40.8062 | 41.4551 | 41.6449 |
| 2 | outer_stream_gc_on | logistic_motion_forest_anomaly | 60 | 20.8443 | 22.0781 | 22.3054 | 22.3369 |
| 2 | outer_stream_gc_on | logistic_motion_logistic_anomaly | 60 | 15.8795 | 17.0213 | 20.6659 | 21.1411 |
| 2 | outer_stream_gc_on | snn32_seed17_forest_anomaly | 60 | 31.1087 | 33.5934 | 134.8782 | 277.7514 |
| 2 | outer_stream_gc_on | snn32_seed27_forest_anomaly | 60 | 31.3190 | 34.2807 | 38.4932 | 43.5143 |
| 2 | outer_stream_gc_on | snn32_seed7_forest_anomaly | 60 | 35.2732 | 38.2612 | 41.3042 | 43.8842 |
| 2 | nested_stream_gc_deferred | forest_motion_forest_anomaly | 60 | 36.4836 | 38.6666 | 39.3940 | 39.8440 |
| 2 | nested_stream_gc_deferred | logistic_motion_forest_anomaly | 60 | 21.0602 | 23.2608 | 23.5021 | 23.6731 |
| 2 | nested_stream_gc_deferred | logistic_motion_logistic_anomaly | 60 | 15.9238 | 20.6044 | 21.3991 | 21.4954 |
| 2 | nested_stream_gc_deferred | snn32_seed17_forest_anomaly | 60 | 35.6387 | 37.6359 | 41.9451 | 45.6285 |
| 2 | nested_stream_gc_deferred | snn32_seed27_forest_anomaly | 60 | 30.6833 | 33.1886 | 38.1447 | 44.3647 |
| 2 | nested_stream_gc_deferred | snn32_seed7_forest_anomaly | 60 | 34.2170 | 35.5130 | 39.2157 | 42.0432 |
| 2 | nested_stream_gc_on | forest_motion_forest_anomaly | 60 | 36.6247 | 44.8076 | 48.5472 | 48.7270 |
| 2 | nested_stream_gc_on | logistic_motion_forest_anomaly | 60 | 22.3248 | 24.1976 | 26.8406 | 27.7941 |
| 2 | nested_stream_gc_on | logistic_motion_logistic_anomaly | 60 | 16.6356 | 20.9296 | 22.0168 | 23.3255 |
| 2 | nested_stream_gc_on | snn32_seed17_forest_anomaly | 60 | 34.5854 | 42.5616 | 140.7337 | 281.4617 |
| 2 | nested_stream_gc_on | snn32_seed27_forest_anomaly | 60 | 36.5729 | 39.2782 | 40.1785 | 40.6061 |
| 2 | nested_stream_gc_on | snn32_seed7_forest_anomaly | 60 | 31.1591 | 36.9819 | 40.6193 | 43.8153 |
| 2 | nested_retained_gc_on | forest_motion_forest_anomaly | 60 | 37.3902 | 42.3802 | 49.3758 | 50.4883 |
| 2 | nested_retained_gc_on | logistic_motion_forest_anomaly | 60 | 21.5251 | 24.0313 | 28.3014 | 29.0468 |
| 2 | nested_retained_gc_on | logistic_motion_logistic_anomaly | 60 | 19.1746 | 22.8844 | 26.1822 | 27.5485 |
| 2 | nested_retained_gc_on | snn32_seed17_forest_anomaly | 60 | 32.3404 | 36.0384 | 46.9021 | 47.2678 |
| 2 | nested_retained_gc_on | snn32_seed27_forest_anomaly | 60 | 34.4068 | 36.7555 | 133.1824 | 262.0701 |
| 2 | nested_retained_gc_on | snn32_seed7_forest_anomaly | 60 | 31.7097 | 37.8248 | 46.5263 | 47.0353 |
| 3 | nested_stream_gc_deferred | forest_motion_forest_anomaly | 59 | 37.3993 | 43.4180 | 49.1181 | 49.4881 |
| 3 | nested_stream_gc_deferred | logistic_motion_forest_anomaly | 59 | 25.3398 | 30.9968 | 31.1988 | 31.3169 |
| 3 | nested_stream_gc_deferred | logistic_motion_logistic_anomaly | 59 | 18.0777 | 18.7180 | 20.1883 | 20.2261 |
| 3 | nested_stream_gc_deferred | snn32_seed17_forest_anomaly | 59 | 30.8402 | 33.6248 | 40.4760 | 46.1676 |
| 3 | nested_stream_gc_deferred | snn32_seed27_forest_anomaly | 59 | 31.7537 | 33.3035 | 37.8883 | 43.8299 |
| 3 | nested_stream_gc_deferred | snn32_seed7_forest_anomaly | 59 | 31.7183 | 34.6965 | 43.6670 | 44.2616 |
| 3 | nested_retained_gc_on | forest_motion_forest_anomaly | 59 | 43.0645 | 47.0760 | 49.3278 | 51.8347 |
| 3 | nested_retained_gc_on | logistic_motion_forest_anomaly | 59 | 22.0546 | 31.5753 | 138.7940 | 282.6504 |
| 3 | nested_retained_gc_on | logistic_motion_logistic_anomaly | 59 | 16.6188 | 20.8285 | 20.9029 | 20.9569 |
| 3 | nested_retained_gc_on | snn32_seed17_forest_anomaly | 59 | 31.9974 | 37.1795 | 43.1535 | 44.2130 |
| 3 | nested_retained_gc_on | snn32_seed27_forest_anomaly | 59 | 31.8517 | 44.2338 | 44.7430 | 45.0494 |
| 3 | nested_retained_gc_on | snn32_seed7_forest_anomaly | 59 | 31.9147 | 39.7086 | 46.2687 | 47.9086 |
| 3 | outer_stream_gc_on | forest_motion_forest_anomaly | 59 | 40.3417 | 43.0285 | 48.7760 | 49.6844 |
| 3 | outer_stream_gc_on | logistic_motion_forest_anomaly | 59 | 22.0080 | 23.7771 | 24.2181 | 24.5315 |
| 3 | outer_stream_gc_on | logistic_motion_logistic_anomaly | 59 | 16.3771 | 20.3239 | 21.1049 | 21.7147 |
| 3 | outer_stream_gc_on | snn32_seed17_forest_anomaly | 59 | 32.7360 | 36.9612 | 127.1792 | 248.7115 |
| 3 | outer_stream_gc_on | snn32_seed27_forest_anomaly | 59 | 32.6637 | 36.8108 | 44.8641 | 46.5442 |
| 3 | outer_stream_gc_on | snn32_seed7_forest_anomaly | 59 | 37.4600 | 40.4866 | 44.5777 | 44.9735 |
| 3 | nested_stream_gc_on | forest_motion_forest_anomaly | 59 | 38.8195 | 43.4142 | 44.2619 | 44.4502 |
| 3 | nested_stream_gc_on | logistic_motion_forest_anomaly | 59 | 21.5270 | 23.2605 | 24.3399 | 24.6301 |
| 3 | nested_stream_gc_on | logistic_motion_logistic_anomaly | 59 | 16.5435 | 20.6288 | 21.4140 | 22.2805 |
| 3 | nested_stream_gc_on | snn32_seed17_forest_anomaly | 59 | 36.4820 | 45.3008 | 47.1165 | 47.2668 |
| 3 | nested_stream_gc_on | snn32_seed27_forest_anomaly | 59 | 32.2261 | 35.9505 | 40.2286 | 43.7857 |
| 3 | nested_stream_gc_on | snn32_seed7_forest_anomaly | 59 | 35.1410 | 38.6241 | 161.9322 | 324.6778 |

## Interpretation and controls

paired-deltas.csv gives RIGHT minus LEFT differences for each source/noise/path pair,
separately by block, phase, condition, decision and reason. Negative values mean the right
mode was faster in those observations. Delta quantiles are not differences of path percentiles.
The contrasts are conditional, not a complete factorial design. Repeated synthetic sources
and model conditions are paired, not independent security/reliability or accuracy samples.

Mode order is position- and adjacent-predecessor-balanced across four blocks. Each mode/block
gets a fresh Python process. Model order is rotated, not completely position-balanced;
frequency, hybrid-core placement, thermal/OS drift and OS/file/backend caches remain uncontrolled.
First warmup per condition is condition-first-use, not fully cold system startup. Loading and
trusted enrollment are outside roots; no decoder/model warmup is hidden before the first root.

Normal-GC modes are references. The deferred-GC mode is diagnostic only; its full cleanup
is reported in each worker's runtime-and-cleanup.json, outside root times. It is not a
deployable 20 ms success claim. No values, slow observations, first uses or refusals are discarded.
Streaming writes EVERY raw trace before dropping it; reloading for analysis happens after
timing and cleanup. Full retained mode owns growing trees across all six conditions.
The shorter worker cohort is not a reproduction of the old 29,718-tree application history.

Root-only mode has no separately timed first-post-window nested span. Compare matched roots
only: fresh, recurring, after-refusal and receiver controls have the same functional boundaries.
Nested stage percentiles must not be added; no no-op timing is subtracted. All clocks and
GC callbacks remain observers, including root-only mode. In-memory audit is included; durable
audit, physical capture/acquisition, network, progress and result I/O are excluded from roots.

## Explicit full-GC heap probes

| Retained old traces | Phase | Probe | Wall ms | Thread CPU ms | Collected objects |
|---:|---|---:|---:|---:|---:|
| 0 | first_full_collection | 0 | 157.1152 | 156.2500 | 0 |
| 0 | repeat_full_collection | 1 | 145.4663 | 140.6250 | 0 |
| 0 | repeat_full_collection | 2 | 143.3500 | 140.6250 | 0 |
| 0 | repeat_full_collection | 3 | 156.4716 | 140.6250 | 0 |
| 0 | repeat_full_collection | 4 | 150.2570 | 156.2500 | 0 |
| 5000 | first_full_collection | 0 | 153.0122 | 140.6250 | 0 |
| 5000 | repeat_full_collection | 1 | 157.1878 | 156.2500 | 0 |
| 5000 | repeat_full_collection | 2 | 155.0078 | 156.2500 | 0 |
| 5000 | repeat_full_collection | 3 | 157.0824 | 156.2500 | 0 |
| 5000 | repeat_full_collection | 4 | 154.3983 | 156.2500 | 0 |
| 15000 | first_full_collection | 0 | 177.7840 | 171.8750 | 0 |
| 15000 | repeat_full_collection | 1 | 180.8319 | 187.5000 | 0 |
| 15000 | repeat_full_collection | 2 | 184.2982 | 187.5000 | 0 |
| 15000 | repeat_full_collection | 3 | 194.3543 | 187.5000 | 0 |
| 15000 | repeat_full_collection | 4 | 193.6964 | 187.5000 | 0 |
| 29718 | first_full_collection | 0 | 229.4958 | 234.3750 | 0 |
| 29718 | repeat_full_collection | 1 | 213.6655 | 218.7500 | 0 |
| 29718 | repeat_full_collection | 2 | 226.8888 | 218.7500 | 0 |
| 29718 | repeat_full_collection | 3 | 212.5651 | 218.7500 | 0 |
| 29718 | repeat_full_collection | 4 | 226.6181 | 218.7500 | 0 |

Each heap dose runs in a fresh process with all frozen models and the complete dataset
resident. Five explicit generation-2 collections are measured: first versus subsequent
collections are separate. Metadata replay is not the original live authentication/application
heap. Full GC may clear free lists as well as scan/collect cycles. These probes test a
possible retained-metadata mechanism; they do not reconstruct historical pause causation.

## Still unresolved

This experiment does not establish Windows scheduling/I/O wait, native allocation stacks,
CPU-cache/power causes or the precise root cause of every historical event. Stage location
and GC overlap alone are not complete attribution. Follow-up OS tracing and evidence-qualified
historical row accounting remain separate checkpoints; raw ETL must not go in public Git.

Diagnostic contrasts on sixty preselected test sources, repeated in four paired noise blocks, not a replacement held-out performance/FRR/security study. Normal-GC modes are references; GC deferral is a counterfactual with separately reported cleanup. All clocks/callbacks and orchestration impose observer costs. Windows scheduling, native allocation, cache, power/core placement and historical single-event root causes remain unresolved without additional evidence. No target-passing, hardware acquisition, Quest, network or durable-audit claim.
