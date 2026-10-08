# Week 6 saved-data stage-accounting revision

Original benchmark: `78f499a92f633a4793c776a070058e3a6a9a0b61`; original results: `a4a9e2548fd30ee2383923dbd0de6cd5c45c587f`.

This is reporting of unchanged saved evidence, not a new timing or reliability experiment. All original hashes, admission/control counts and direct/inclusive quantiles were checked. No models, response reads, authentication, fitting, threshold selection, ETL scan or recording ran.

## Current integrated conclusion

The evaluated baseline software pipeline enforced the tested admission and inference-release policies, but none of its complete motion-plus-anomaly post-window configurations met the provisional 20 ms p95 target. Reconstruction alternatives are a separate experiment; improved reliability is not demonstrated by these single-read integrated timings.

## Directly measured totals

Primary SNN seed 7 is the first SNN checkpoint in the original predeclared condition list, not selected for favorable latency. All three seeds and the forest-motion comparison remain in the machine-readable evidence and comparison table below.

| Condition | Accepted n | Fresh first-window p50 / p95 / p99 / max ms | Recurring p50 / p95 / p99 / max ms | Recurring p95 <=20 ms |
|---|---:|---|---|---|
| logistic_motion_logistic_anomaly | 599 | 20.6127 / 31.3187 / 37.4013 / 278.4112 | 17.6496 / 27.7629 / 34.1022 / 292.3259 | no |
| logistic_motion_forest_anomaly | 599 | 26.1044 / 33.3164 / 37.6671 / 334.7859 | 22.5875 / 30.3028 / 32.8717 / 262.9841 | no |
| snn32_seed7_forest_anomaly | 599 | 55.8030 / 60.1001 / 62.8711 / 354.4788 | 47.4545 / 51.3985 / 53.9641 / 342.7444 | no |
| forest_motion_forest_anomaly | 599 | 41.9021 / 59.9307 / 65.2019 / 274.6759 | 39.4365 / 52.8523 / 56.6526 / 337.0849 | no |
| snn32_seed17_forest_anomaly | 599 | 55.5374 / 59.3553 / 63.7296 / 372.8408 | 47.1784 / 50.5355 / 53.6224 / 359.2428 | no |
| snn32_seed27_forest_anomaly | 599 | 41.6731 / 59.5470 / 67.7996 / 362.8529 | 40.2214 / 54.1160 / 59.6622 / 292.8711 | no |

These are directly measured totals. Do not add stage medians or percentiles. Fresh timing includes modeled response generation, one reconstruction attempt, verification/admission, session establishment and the first full window. Recurring timing does not repeat session setup.

## Primary configurations: nested measured boundaries

Values are p50 / p95 milliseconds. Inclusive rows overlap their children and are NOT additive. All accepted measured rows have the same 599 successful attempts per condition.

### logistic_motion_logistic_anomaly

| Measured boundary | p50 / p95 ms |
|---|---|
| Reconstruction | 2.5245 / 3.8214 |
| Independent credential verification (recorded calls) | 0.0409 / 0.0636 |
| Whole admission/session setup (inclusive) | 3.3089 / 4.9485 |
| First complete post-window processing (inclusive) | 17.2492 / 27.0020 |
| Binary32 adapter | 1.0924 / 1.8044 |
| Sender sealing including serialization/quality/HMAC/audit (inclusive) | 5.2328 / 8.8606 |
| Receiver parsing | 1.6147 / 3.7874 |
| Receiver HMAC calculation only | 0.0162 / 0.0287 |
| Receiver quality check | 4.5545 / 7.1978 |
| Complete receiver authentication (inclusive) | 6.4172 / 10.9944 |
| Shared preprocessing | 3.3057 / 5.2088 |
| Motion consumer including normalization/decoding | 0.4359 / 0.7712 |
| Anomaly consumer including threshold | 0.3486 / 0.5710 |

### logistic_motion_forest_anomaly

| Measured boundary | p50 / p95 ms |
|---|---|
| Reconstruction | 2.7018 / 3.6368 |
| Independent credential verification (recorded calls) | 0.0455 / 0.0665 |
| Whole admission/session setup (inclusive) | 3.5300 / 4.6335 |
| First complete post-window processing (inclusive) | 22.6095 / 29.5842 |
| Binary32 adapter | 1.0718 / 1.3892 |
| Sender sealing including serialization/quality/HMAC/audit (inclusive) | 5.1050 / 6.5517 |
| Receiver parsing | 1.5759 / 4.5004 |
| Receiver HMAC calculation only | 0.0163 / 0.0257 |
| Receiver quality check | 4.4111 / 5.6835 |
| Complete receiver authentication (inclusive) | 6.1423 / 9.0781 |
| Shared preprocessing | 3.2149 / 4.3129 |
| Motion consumer including normalization/decoding | 0.4636 / 0.7236 |
| Anomaly consumer including threshold | 5.8616 / 7.7460 |

### snn32_seed7_forest_anomaly

| Measured boundary | p50 / p95 ms |
|---|---|
| Reconstruction | 7.2211 / 7.9045 |
| Independent credential verification (recorded calls) | 0.0633 / 0.0794 |
| Whole admission/session setup (inclusive) | 8.3122 / 9.0633 |
| First complete post-window processing (inclusive) | 47.5227 / 51.6710 |
| Binary32 adapter | 1.3599 / 1.4829 |
| Sender sealing including serialization/quality/HMAC/audit (inclusive) | 6.3619 / 6.6689 |
| Receiver parsing | 2.0684 / 5.9449 |
| Receiver HMAC calculation only | 0.0255 / 0.0357 |
| Receiver quality check | 5.4380 / 5.7207 |
| Complete receiver authentication (inclusive) | 7.7090 / 11.6150 |
| Shared preprocessing | 4.8754 / 5.1885 |
| Motion consumer including normalization/decoding | 17.7986 / 19.0508 |
| Anomaly consumer including threshold | 8.3814 / 8.8913 |

## Disjoint per-observation accounting

For each serial span, exclusive duration = its duration minus its direct child durations. Children must be contained, non-overlapping siblings. Exclusive categories sum exactly to the direct root for each observation. Category percentiles do not sum to the total percentile. Unisolated remainders include wrapper/observer overhead and are not pure application timings.

stage-accounting.csv includes every condition/phase/path/decision/reason/category, presence counts and p50/p95/p99/max. per-observation-accounting.csv retains the integer-nanosecond partition for every root. A zero for an absent stage means it was outside that path, not a measured zero-cost operation.

| Primary recurring condition | Measured in-memory audit p50 / p95 ms | Unisolated receiver binding/sequence/state remainder p50 / p95 ms |
|---|---|---|
| logistic_motion_logistic_anomaly | 0.0852 / 0.1494 | 0.0799 / 0.1458 |
| logistic_motion_forest_anomaly | 0.0865 / 0.1245 | 0.0822 / 0.1163 |
| snn32_seed7_forest_anomaly | 0.1219 / 0.1580 | 0.1202 / 0.1519 |

Session establishment/key confirmation can likewise be located in the recorded handshake spans and exclusive session remainder. Credential-verification/admission/audit children are removed from that remainder, but HKDF and confirmation computation are not separately isolated. The recorded native HKDF durations lack span boundaries and are not injected into the partition.

## Admission configuration, denominators and pairing

The 599/600 admissions per measured condition use six fixed simulated PUF profiles, seed 6767, 128 adjacent-paired oscillators, 63 selected bits, BCH(63,36,t=5), a 32-bit pilot credential and one response read/one decode. Majority-3 was not integrated in this run; no retry-until-success or enrolled-credential substitution was used. The same one reconstruction refusal recurs across paired conditions and is not six independent failure observations.

Fresh quantiles are reported separately for accepted and refused outcomes in direct-path-latency.csv. The accepted table excludes admission failures by conditioning, not by deleting them: all 600 measured attempts per condition remain in admission-accounting.csv and reconciliation.json. First-use and 19 other warmups remain separate; first use is not a fully cold process.

All model conditions use the same predeclared source/noise streams and timing-wrapper protocol, but run in fixed order: thermal/background/CPU drift is not isolated. Receiver-only bad-tag/replay controls exclude sender sealing and return before accepted release/inference. They are not identical execution paths to accepted full-window processing. GC-deferral and Windows-traced experiments are separate diagnostic cohorts, not interchangeable measurements in this table.

## What the 5.17 ms figure means

Will's docs/week6-tier1-v2-experiment.md reports native verifier p50 = 5.1700 ms for 1,200 legitimate controls, versus receiver-to-return p50 = 19.4579 ms. This addendum records that DOCUMENTED cross-experiment context; it does not independently recompute Will's raw Tier-1 measurements. The verifier's native timer starts before mutex acquisition and ends after parsing, binding, HMAC/quality/order checks and audit/state commit on the accepted path, excluding accepted release and model inference. The saved external authentication wrapper has a different boundary/observer cost.

Historical bad-tag p95 = 0.981 ms is an earlier early-rejection benchmark, not the accepted verifier median and not a matched estimate of current complete-path cost. The original current-run bad-tag receiver distributions are retained below; their direct totals still exclude sender sealing.

| Condition | Current measured bad-tag receiver n | p50 / p95 / p99 / max ms |
|---|---:|---|
| logistic_motion_logistic_anomaly | 599 | 1.5515 / 2.4318 / 3.0621 / 3.3109 |
| logistic_motion_forest_anomaly | 599 | 1.5247 / 2.0132 / 2.1388 / 2.4903 |
| snn32_seed7_forest_anomaly | 599 | 1.8580 / 2.0051 / 2.0556 / 2.4950 |

## Coverage gaps and next bounded experiment

1. Sequence checking, locking and state publication are not individually timed. Keep the receiver remainder labeled unisolated; add narrow consistent instrumentation only if separate values are required.
2. Measured audit calls are not the whole audit-related system cost and do not include durable persistence.
3. Shared preprocessing and consumer-specific normalization have different boundaries; preserve them.
4. Review typical measured stages and choose one bottleneck; this report performs no optimization or new timing. Any optimized comparison must retain frozen models, thresholds, protocol checks, failures and full totals, and include cleanup time, sustained throughput and memory/resource behavior.

## Scope and limitations

The two-second motion acquisition window remains visible but is NOT timed here. Processing p95 is not total event-to-decision latency. Physical sensor/PUF acquisition, network transmission, durable audit storage, loading/enrollment and evidence/progress I/O remain excluded. All saved measurements include observer effects, enabled automatic GC, fixed condition order and uncontrolled CPU frequency/core placement. GC overlap is not sole-cause proof. No real Quest, cross-device/person, production-security, hard-real-time or optimized-latency claim follows. Historical partial benchmarks remain historical.
