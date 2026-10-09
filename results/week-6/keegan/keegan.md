# Week 6: v2 Integration, Stage Accounting and Bounded Quality Optimization

**Owner:** Keegan Hoyne
**Evidence recorded:** October 5-8, 2026; historical runs and October 8 revisions are distinguished below.
**Shared reconstruction/authentication owner:** Will Wallace

## Scope and conclusion

The evaluated software prototype enforces the tested authentication and inference-release policies and offers improved nominal reconstruction reliability in a separate reconstruction-alternatives study, but the original released complete motion-plus-anomaly processing paths do not meet the provisional 20 ms p95 target. Improved reliability belongs to Will's standalone alternatives experiment, not to Keegan's single-read integrated timings.

The October 8 revisions reuse the original timing records for stage accounting, add source-aware Tier-2 uncertainty, and test one exact-arithmetic quality-check candidate against a fresh matched reference. Only the opt-in logistic-motion/logistic-anomaly recurring candidate is below 20 ms p95 in both bounded blocks. Its fresh path, the forest-anomaly candidates, and every original default configuration still miss. The default authentication implementation is unchanged. This is not a blanket low-latency or deployment claim.

Paired GC/observer controls and bounded Windows scheduling/I/O accounting remain preserved. Complete causal attribution and isolated tracing overhead remain unestablished; these diagnostics do not replace direct end-to-end results.

The Week 4/5 datasets, weights, thresholds, accuracy/recall findings and historical known-correct-candidate experiments remain unchanged. These new results do not improve reconstruction reliability, detector recall or SNN accuracy, and are not Quest deployment evidence.

## Current admission-to-inference boundary

`src/python/puf_snn/pipeline_v2.py` performs one simulated noisy response read and one actual BCH reconstruction. The returned candidate passes independent credential verification and trusted local admission before the current HKDF/mutual-confirmation APIs create an active session. It does not compare against enrollment truth to replace a candidate or retry until a read succeeds.

Window authentication verifies binding, integrity, quality and exact ordering before committing audit/sequence state. One at-most-once composite callback receives that exact immutable accepted record, prepares both inputs and runs motion classification plus separate anomaly detection. Refused records invoke no preprocessing or models. Anomaly flags do not rewrite authentication; a consumer exception leaves the event consumed and sequence committed, with incomplete evidence rather than automatic retry.

The protocol, five-minute session policy, quality rules, baseline BCH construction, credential length, model architectures and thresholds were not changed. Integration tests include a controlled wrong-valid-candidate fixture and consumer-failure checks, not estimated attack or miscorrection rates.

## Frozen inputs and functional smoke

`configs/week6_smoke.json` pins the corrected 1,800-window dataset and three existing model manifests. The loader checks their hashes and all 11 local model binaries before deserialization:

- Five motion models: recorded LR/RF seed-7 storage refits and SNN-32 checkpoints for initialization seeds 7/17/27 (historical training seeds 107/117/127).
- Six anomaly detectors: LR/RF seeds 6007/6017/6027, with unchanged validation-selected thresholds and feature definitions.
- SNN-64 stays historical; no training, architecture expansion, threshold selection or storage refit occurred in Week 6.

The smoke preselected one validation source for each of six fixed devices and five classes. All 30 fresh single-read admissions succeeded. Each active session exercised clean acceptance, a quality-valid pre-tag medium position jump, subsequent valid traffic, bad-tag rejection, exact-replay rejection and a 113/120 tracking-valid sender refusal. Totals were 90 accepted composite deliveries and 90 refusal controls, with 450 individual motion forwards, 540 detector forwards and zero model calls on refused windows.

This is functional evidence, not a new accuracy/recall estimate, FRR study or formal Tier-1 evaluation. The recorded line-ending-only amendment fixed the generated attributes file and its hash binding while retaining the original source commit and all six experimental record files unchanged.

## First instrumented timing design and accounting

`configs/week6_timing.json` fixes six conditions before timing: LR motion/LR anomaly, LR motion/RF anomaly, RF motion/RF anomaly and each saved SNN-32 seed with RF anomaly. Detector seed 6007 is fixed. All 11 binaries are checked, but one motion model and one detector execute per accepted timing callback.

Each condition retains 20 validation warmups and 600 attempts using all test-source windows in fixed order. First use is separated from the other 19 warmups, not represented as fully cold process startup. The run contains 3,720 fresh single-read attempts, 3,720 response reads and 29,718 directly timed root traces.

Every condition admitted 599/600 measured sessions and all 20 warmups; the remaining measured attempt stopped at `reconstruction/failed_reconstruction`. Matching source/noise streams are paired across conditions, so the repeated refusal is not six independent reliability observations. No retries or refusals were hidden. Post-window distributions are conditional on admission; fresh-attempt accounting retains the refusals.

Accepted-path, bad-tag, replay, malformed-JSON, pre-tag quality and subsequent-valid controls reconcile. Rejected traffic produced zero model calls. These controls are not the expanded varied Tier-1 study, and the observed admission fraction does not replace Will's frozen 1.625% nominal FRR result.

### Direct timing results

All values are milliseconds. Each measured accepted row has n=599. LR/RF identifies the motion model / anomaly detector. Complete first, recurring and after-refusal paths include both consumers.

| Condition | Fresh-to-first p50 / p95 / p99 / max | First post-window p95 | Recurring p50 / p95 / p99 / max | After-refusal p95 |
|---|---|---:|---|---:|
| LR / LR | 20.6127 / 31.3187 / 37.4013 / 278.4112 | 27.0020 | 17.6496 / 27.7629 / 34.1022 / 292.3259 | 23.5106 |
| LR / RF | 26.1044 / 33.3164 / 37.6671 / 334.7859 | 29.5842 | 22.5875 / 30.3028 / 32.8717 / 262.9841 | 26.1512 |
| RF / RF | 41.9021 / 59.9307 / 65.2019 / 274.6759 | 52.2101 | 39.4365 / 52.8523 / 56.6526 / 337.0849 | 39.3474 |
| SNN-32 seed 7 / RF | 55.8030 / 60.1001 / 62.8711 / 354.4788 | 51.6710 | 47.4545 / 51.3985 / 53.9641 / 342.7444 | 40.5086 |
| SNN-32 seed 17 / RF | 55.5374 / 59.3553 / 63.7296 / 372.8408 | 51.0221 | 47.1784 / 50.5355 / 53.6224 / 359.2428 | 40.4914 |
| SNN-32 seed 27 / RF | 41.6731 / 59.5470 / 67.7996 / 362.8529 | 54.7558 | 40.2214 / 54.1160 / 59.6622 / 292.8711 | 38.9728 |

The 20 ms p95 target applies to complete post-window paths, not admission totals, receiver-only controls, maxima or hard deadlines. None of the measured complete first/recurring/after-refusal conditions meets it. Historical Week 4 motion-only timings have a different boundary and cannot support a passing claim for these composite paths.

Measured bad-tag receiver-only p95 ranges from 1.9951 to 2.4318 ms across conditions, with zero model calls. Receiver-only controls exclude packet construction/sender sealing. Exact rejected-path counts and p50/p95/p99/max, including the single fresh reconstruction refusal per condition, are retained in `complete-path-latency.csv`; a one-observation refusal group is not a stable latency distribution.

### Timing boundary and conditions

Fresh timing begins before the modeled noisy read and ends after admission refusal or first composite inference. Complete post-window timing includes binary32 conversion, sender binding/quality/HMAC, verifier parsing/HMAC/binding/quality/order and in-memory audit/state commit, at-most-once release, preprocessing and both model consumers. First post-window processing is a directly timed nested span, not a sum or subtraction of percentiles. Model spans include input/tensor handling and decoding/threshold comparison, not only pure forward computation.

Trusted enrollment, endpoint construction, dataset/model loading, physical two-second capture, hardware PUF acquisition, network transport, disk/progress output and durable audit storage are outside the boundary. Replay-state and audit-publication work remain nested within verifier authentication, not fully isolated disjoint costs. Nested HMAC/HKDF/stage percentiles must not be added to their parent totals.

Hardware was an HP Pavilion Plus 16-ab1xxx, Intel Core Ultra 7 155H (16 cores/22 logical processors), 31.5 GiB RAM, Windows 11 Home 10.0.26200. Python 3.13.14, NumPy 2.5.3, scikit-learn 1.9.1, Torch 2.14.0+cpu, galois 0.4.11 and joblib 1.6.0 were recorded.

Batch size, native thread pools and Torch intra-op threads were one; Torch inter-op was recorded as 16. GC stayed enabled with thresholds [2000, 10, 10]. Wall timing used monotonic non-adjustable QueryPerformanceCounter with 100 ns reported resolution. Thread CPU used GetThreadTimes, but its clock resolution was not recorded. AC power/heavy apps closed were self-reported. The VTRL Optimized plan was unchanged; CPU frequency, hybrid-core affinity and thermal/background drift were uncontrolled. Conditions ran in fixed order, so the timing differences are not a causal model/hardware ranking.

PUF seed 6767 fixes six manufacturing profiles. Separate `week6-timing-v1` credential and warmup/measured response domains are paired across conditions; verifier keys/handshake nonces use independent OS randomness. The existing 32-bit credential and BCH(63,36,t=5) construction remain unchanged. Secrets, raw responses and helper/enrollment material are not exported.

## Read-only saved-run diagnostics

`src/python/scripts/summarize_week6_timing.py` verified the original completion marker, all 24 artifact hashes, saved quantiles, trace/accounting consistency and every retained outlier. It generated a separate addendum without model loading, response reads, authentication, inference, fitting, threshold selection or new timing.

The addendum contains 168 complete-path rows, 150 root-group summaries/maxima and all 12,621 retained slow/tail observations. Retention is wall time >20 ms OR at least the group's p99; absolute and tail counts overlap and are not added. Many ordinary slow-model observations exceed 20 ms, so this is not a rare-fault-rate estimate.

The largest measured root per condition has 90.30-92.33% recorded GC overlap. GC interval unions are clipped to actual span boundaries; generation-2 overlap is a subset, not an extra duration. The separate largest condition-first-use fresh observation is 2,729.3209 ms, including 2,704.7969 ms in reconstruction. Possible compilation/cache effects were not isolated.

These observations locate activity, not all causes. Benchmark collectors/retained trees and temporary wrappers may themselves affect allocation/heap scanning. Wall/thread-CPU gaps do not prove OS descheduling, and short spans often have zero recorded CPU time. The 1,000 no-op proxy roots had p95 0.0031 ms and max 0.0328 ms, but are not a calibrated overhead correction and were never subtracted. Slow values, admission refusals, first use and maxima remain preserved.

## Completed paired GC and observer controls

The separate `observer-experiment/` result was recorded at
`9f7b737079281f72d183dba2867040c28ec01413`, using source
`f3efeebafc5f5d4f173d7086a84f3e7cbc796ea2` and
`configs/week6_outlier_experiment.json`. Four paired noise blocks compared
nested retained trees, nested streamed trees, root-only streamed observation and
nested streaming with automatic GC temporarily deferred. Six unchanged model
conditions ran in each mode. The 16 fresh timing workers retained all 8,640
one-read admission attempts and 68,952 root records; paired functional signatures
matched and refused windows produced zero model calls.

Four additional fresh processes performed 20 explicit full-GC probes at
0/5,000/15,000/29,718 retained historical metadata rows. Full collection took
143.3500–157.1152 ms at zero rows and 212.5651–229.4958 ms at 29,718 rows.
These are metadata-dose observations, not a reconstruction of the original
application heap or an attribution of every historical pause. Full GC also
has free-list effects; fixed dose order and OS/cache history remain limitations.

GC-deferred workers restored the normal policy and recorded full cleanup outside
window timers: 676.0642–695.9074 ms, collecting 2,856,736–2,886,340 objects.
That delayed work is not free and must not be hidden. The controls support a
collector/measurement contribution, not disabling GC as a production fix,
subtracting overhead from the original results or declaring a passing 20 ms p95.
The matched contrasts and all path distributions are preserved in the diagnostic
report, `paired-deltas.csv`, `path-latency.csv` and each worker's cleanup record.

## Completed Windows scheduling and I/O evidence

A separate reference process and Windows-traced process each retained 540 fresh
attempts and 4,320 application-root timings. Their functional signatures matched,
with zero model calls on rejected windows and no training or threshold selection.
Capture source was `624807b9095b7be41f7c3bbe7d18a31d50f95478`.
All 27 saved native markers, clock brackets, zero final-header event/buffer-loss
counts and scoped process/thread lifetimes were checked. Export-relative clock
uncertainty was 31.1 microseconds; native accounting uses exact validated QPC ticks.

The public evidence at `windows-os-evidence/` was recorded at
`b91088a60cd88e7cea66bf01ceb297efce23543f`, with reporting source
`8ba6a711e205fe962a125cffea92c1909725cb94`. Its manifest SHA-256 is
`058507ddc3166abc7bd9a87065a1f8b9a7e5f97162fedd39ddb2561c95110b4a`.
All 4,320 traced roots have complete scheduling coverage and reconciled disjoint
wall-time partitions. The report retains 2,106 distinct slow/tail/maxima records,
144 groups and all eight roots above 100 ms. GC overlaps 2,160 roots; measured
ready-but-not-dispatched time occurs in 2,639. One root overlaps scoped main-thread
file operations; none overlaps the scoped disk or hard-fault intervals. This is
scoped observation, not proof of no cached/metadata/other-thread I/O or blocking.

Four long cases have 286.4601–432.8645 ms GC overlap, about 90–98% of those roots.
A different 142.4030 ms case has only 0.3193 ms GC but 56.1910 ms ready delay.
The largest root is a 3,735.7236 ms first-condition-use admission/first-window
path, including 3,690.2300 ms reconstruction and 274.7025 ms GC inside that stage.
Two roughly 102–107 ms SNN cases have less than 1 ms GC and about 9.6–12.5 ms
ready delay; their remaining execution is not fully explained. The eight-case
table and all nested-stage records preserve these distinctions rather than
assigning every outlier to GC.

The CSwitch v5 full native schema remains unavailable. A 24,495-event prefix
cross-check exposed an erroneous 0/1 interpretation of opaque byte13 in the
initial review. Its actual zero/nonzero export rendering was checked, the failed
review/extraction preserved, and byte13 excluded from accounting; its native
wait-mode meaning was not claimed. Known scheduling fields, validated lifetimes
and same-CPU ISR/DPC intervals support the bounded accounting, not complete
schema or causal validation.

The sanitized export verifies eight artifact hashes and the completion binding.
It contains numeric durations/counts and approved project labels, not raw ETL,
kernel payloads, absolute clocks, OS IDs, addresses, private paths or IRP tokens.
The saved ETL and recovery evidence remain private; exporting the report required
no new recording, ETL scan, model loading or timing. COMPLETE means the filtered
accounting export finished, not that every causal question is resolved.

Reference precedes traced in fixed order, so their observed differences do not
isolate tracing overhead. Allocation stacks, cache/frequency/thermal effects,
dependency-specific waits and other-thread activity remain unresolved. New
tracing cannot retroactively prove OS causes for earlier untraced roots.
`complete_causal_attribution_established` and `tracing_overhead_isolated` remain
false. No original timing, refusal, first-use observation or target was replaced.

## Tests, evidence and provenance

The latest saved full Python suite passed 964 tests in 100.599 seconds at the quality-benchmark source checkpoint. The 834-test Windows OS checkpoint, including 43 accounting/privacy-reporting tests, is historical. The earlier 666-test timing-reporting checkpoint included 24 reporting tests. Earlier suites are historical checkpoints, not additional independent test samples.

| Change | Commit |
|---|---|
| Current v2 connector and composite inference | `178738f63a7d80379b084cd664d3daa81f431078` |
| Frozen loader and smoke implementation | `7d07a4f7f2de58b64ae17f98aa9c1478a9803f14` |
| Smoke evidence and explicit LF/hash amendment | `fa8cbf1e958c049c54261b0d5652a90251ef3bae` |
| Fresh timing implementation/instrumentation | `78f499a92f633a4793c776a070058e3a6a9a0b61` |
| First instrumented timing evidence | `a4a9e2548fd30ee2383923dbd0de6cd5c45c587f` |
| Read-only timing/GC reporting implementation | `a238d70d075276f3c3f10f58044fdb4bb90ae585` |
| Reconciled timing diagnostic evidence | `cc8c86c5122ec74d4744ba41a715133b53bf342b` |
| GC/observer controls | `fb7a99563b559f3f182122ed35a4916b5501880d` |
| Paired diagnostic runner | `f3efeebafc5f5d4f173d7086a84f3e7cbc796ea2` |
| Paired controls and cleanup evidence | `9f7b737079281f72d183dba2867040c28ec01413` |
| Windows profile and clock support | `ec5db19aafcf95362c620bee6a6bd88c404dcaa0` |
| Fixed traced workload and native reader | `624807b9095b7be41f7c3bbe7d18a31d50f95478` |
| Sanitized OS accounting/reporting and tests | `8ba6a711e205fe962a125cffea92c1909725cb94` |
| Sanitized Windows evidence | `b91088a60cd88e7cea66bf01ceb297efce23543f` |

Evidence is under `results/week-6/keegan/frozen-model-smoke/`, `fresh-v2-timing/`, `timing-diagnostics/`, `observer-experiment/`, `windows-os-evidence/` and `test-evidence/`. Methods are in `docs/week6-end-to-end.md`, `docs/week6-outlier-diagnostics.md` and `docs/week6-windows-os-evidence.md`. Run manifests retain source/configuration/input hashes, environment, commands, seed domains and execution flags; COMPLETE binds each manifest.

- Dataset SHA-256: `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`.
- Corrected smoke manifest SHA-256: `36d472679416943a332f16c6349911e803c57c911165ecb19321a84f69175ec0`.
- Fresh timing manifest SHA-256: `10135c6e3849015c6afcfb96c91d9bc25bdeabdbdc1da2531b1ec65501403b50`.
- Diagnostic manifest SHA-256: `492d1ca1df348b9ebd78f425479ab45e3ae1066463e38d62649148cb8401423c`.

### Recorded commands (completed runs; do not rerun into these directories)

```powershell
python src/python/scripts/run_week6_smoke.py --config configs/week6_smoke.json --output results/week-6/keegan/frozen-model-smoke
python -u src/python/scripts/benchmark_week6_v2.py --config configs/week6_timing.json --output results/week-6/keegan/fresh-v2-timing --power ac --background heavy_apps_closed
python src/python/scripts/summarize_week6_timing.py --input results/week-6/keegan/fresh-v2-timing --output results/week-6/keegan/timing-diagnostics
python -m unittest discover -s tests -p 'test_pipeline_timing_reporting.py' -v
python src/python/scripts/summarize_week6_os_evidence.py --private-accounting <private-accounting-directory>
python -m unittest discover -s tests -p 'test_windows_os_*.py' -v
python -m unittest discover -s tests -v
```

### Frozen-input handoff

An exact ZIP containing the generated dataset and 11 frozen binaries, with original repository-relative paths, a hash index and verification/install helper, was prepared for trusted transfer to Will. These local inputs are Git-ignored; a clone alone does not supply them. The helper verifies all 12 payload files against the pinned repository manifests before copying and refuses conflicting existing targets. No credentials, verifier keys, raw responses or helper material are included. Preparation is complete; receipt/verification by Will is not established here.

## Remaining work and limitations

The original timing experiment, separately declared paired GC/observer controls and bounded Windows evidence review are complete and preserved. Every new large root has an evidence-qualified account, including explicit unknown residuals; this is not complete causal isolation. Tracing overhead, allocation/cache/power causes and dependency-level waits are not fully established. Disabling GC, hiding cleanup or dropping slow values solely to pass a target is not a result.

Will's actual [v2 protocol specification](../../../docs/authentication-v2-protocol-spec.md), [expanded Tier-1 report](../../../docs/week6-tier1-v2-experiment.md) and [standalone reconstruction-alternatives report](../../../docs/week6-reconstruction-alternatives-experiment.md) are now in the repository. Their raw formal result directories are absent from this checkout, so their numerical results are identified as documented rather than independently recomputed here.

Remaining Will/shared work is reconciliation of the 1.625% versus 0.9833% reconstruction baselines, fresh majority-3 integration and correlated-noise evaluation, the provisioned-random-credential control, key-custody/security-role review, consolidated Tier-1 experiment metadata and full shared release-evidence closure. Durable audit timing and approved Quest logger validation remain unmeasured. Frozen anomaly targets and constrained SNN conclusions stay unchanged. No model expansion, physical transfer, cross-person/device generalization, production security or hard real-time claim follows.



## October 8 feedback revisions: new results

### Stage accounting without another original benchmark

The [stage-accounting report](stage-accounting/stage-accounting.md) reconciles all 29,718 original roots, their directly measured totals and each exclusive nanosecond partition. It retains 3,720 attempts, separate refusal outcomes and the paired 599/600 measured admissions per condition. These use one read and BCH(63,36,t=5), not majority-3. Successful-path quantiles condition on admission; failed attempts remain in the refusal tables.

The primary tables cover LR/LR, LR/RF and the predeclared SNN-32 seed-7/RF condition, with all original configurations retained. Parsing, HMAC, receiver quality, preprocessing, motion, anomaly and in-memory audit have measured boundaries. Binding/sequence/locks/state remain a labeled receiver remainder; handshake spans locate session work but do not independently isolate every HKDF/key-confirmation operation. Inclusive stages overlap and their percentiles must never be added to infer total p95.

Will's 5.1700 ms median is a documented accepted native-verifier measurement, including mutex, parsing, binding, HMAC/quality/order and audit/state work, excluding release/inference. Historical bad-tag p95 0.9814 ms is a different early-return path and harness, not an interchangeable estimate.

### One bottleneck: exact quaternion-quality arithmetic

In the original LR/LR first-window table, receiver quality has p50 4.5545 ms versus 0.0162 ms for HMAC calculation. Sender serialization also includes quality checks. This justified one controlled arithmetic optimization, not another model search.

The opt-in dyadic candidate replaces Fraction arithmetic with exact integer arithmetic for finite binary32 values, preserving component/norm bounds, quaternion sign continuity and quality-check order. It does not cache quality decisions, bypass validation, weaken HMAC or change admission/sequence policy. It has 26 focused equivalence/boundary tests; default adoption requires authentication-owner review.

The [bounded benchmark](quality-benchmark/quality-benchmark.md) used four fresh workers in two AB/BA blocks, three predeclared frozen configurations and 120 measured plus 30 validation-warmup attempts per configuration/mode/block. All 1,800 attempts, 15,126 roots and 768 sustained windows reconcile. Public input/output/state signatures match, and rejected windows invoke no models. Block 0 admitted 120/120 measured attempts per configuration/mode; block 1 admitted 119/120. The mirrored refusal is one paired noise case, not six independent failures.

| Configuration | Recurring reference p95, blocks 0 / 1 (ms) | Recurring candidate p95, blocks 0 / 1 (ms) | Fresh candidate p95, blocks 0 / 1 (ms) |
|---|---:|---:|---:|
| LR motion / LR anomaly | 27.4285 / 25.1534 | 14.2551 / 15.3827 | 22.2278 / 23.4115 |
| LR motion / RF anomaly | 40.9905 / 41.3853 | 25.0066 / 28.9934 | 31.0356 / 35.0740 |
| SNN-32 seed 7 / RF anomaly | 46.5381 / 48.6062 | 32.1141 / 40.8279 | 37.7728 / 49.9577 |

These direct totals are conditional on 120 and 119 accepted attempts per block respectively. Candidate effects are compared with these new matched references, not the old laptop percentiles. Not every paired window is faster; SNN block-1 paired p95 delta is +0.2890 ms. Two reused-source blocks provide descriptive evidence, not a robust population-level timing interval.

Receiver-quality p50 falls from approximately 5.0-5.6 ms to 0.60-0.77 ms across these matched worker tables. Other stage timings vary as well, so the complete reduction is not attributed solely to arithmetic. SNN motion and forest anomaly inference retain meaningful costs.

Automatic GC stays enabled. Final explicit cleanup is reported separately: 231.3012/235.5045 ms in reference workers and 245.8145/261.7698 ms in candidate workers. Same-session 64-window burst rates range from 30.876-61.203 windows/s for reference and 39.179-99.632 for candidate. Burst rates include assertions, signatures and evidence writes, exclude admission/loading/final cleanup, and are unpaced closed-loop capacity rather than a sensor-arrival/backpressure study. Worker-wide mixed workload capacity separately includes cleanup.

Coarse working set is approximately 662-664 MB after loading and 716 MB before/after cleanup; private commit is approximately 2.045-2.096 GB. These are resource snapshots, not stage peaks or evidence of a memory improvement. Core placement, frequency, thermals and background load were not fully controlled.

The two-second acquisition window is additional. Physical PUF/sensor acquisition, transmission and durable audit storage are excluded; in-memory audit and timing-observer work are included. No cleanup cost is claimed to disappear.

### Tier-2 source-aware uncertainty, unchanged predictions

The [source-aware report](tier2-source-uncertainty/tier2-source-uncertainty.md) reconciles all 50,400 planned cases, including 44,899 quality-valid cases and 5,501 pre-tag blocks (3,493 excessive gaps; 2,008 non-increasing timestamps). Held-out test has 600 sources, 16,800 planned derivatives/controls, 1,844 quality blocks and 14,956 authenticated deliveries.

The same source-bootstrap weight applies to each source's clean record, attack/severity derivatives and frozen model-seed predictions. There are 2,000 stratified draws, seed 7027, conditional on six fixed profiles, five classes and the held-out session. Model seeds are not independent datasets. The 168 detector and 252 motion condition rows retain detected/missed counts, quality blocks, clean FPR and paired motion degradation.

| Detector family, mean over frozen fits | F1 [source-bootstrap 95% interval] | Medium/high recall [interval] | Clean FPR [interval] |
|---|---|---|---|
| Logistic | 0.8424 [0.8383, 0.8466] | 82.85% [82.42%, 83.29%] | 5.33% [3.83%, 7.17%] |
| Forest | 0.9003 [0.8980, 0.9026] | 87.95% [87.73%, 88.19%] | 2.94% [1.78%, 4.22%] |

Neither meets the unchanged 90% medium/high point-recall target; logistic also exceeds the 5% clean-FPR target. Orientation drift is a prominent weakness. Zero-eligible conditions remain N/A; four eligible high-dropout cases and degenerate intervals are not broad evidence of perfect detection. Undefined bootstrap samples are recorded rather than retried.

Quality blocks occur before tagging/inference and are neither detector successes nor misses. Legitimate low-amplitude nod/still ambiguity is a different objective: infrequent anomaly flags on legitimate small nods are not automatically an anomaly failure. Neither SNN outperforms conventional motion baselines. The historical Tier-2 authentication run predates the current v2 admission gate and is not relabeled as a new v2 security experiment.

### Revision provenance and submission materials

| Revision | Source commit | Evidence commit |
|---|---|---|
| Saved stage accounting | 7921261fc6ff690b9c8e1b9f66907d3424e2ae4a | f11f491b92f48b21ea4541911a6100ba96c09f4e |
| Source-aware Tier-2 uncertainty | c5e982baef8f892e42c4719c695d22c3b9dc4a63 | 2b1d2100bd6aa1ca0e3121657e4e657f2ee93a46 |
| Exact quality candidate | 18bf6e5e18e538c0cd6501a89c19e7ea04af5bb8 | Focused/full test evidence in that commit |
| Paired quality comparison | bddce50198d68b851f648d45638aa06d9eea152c | 2c84cf8394bd444188291e254bbf1ddde3cc8661 |

The [feedback consolidation](../../../docs/week6-feedback-consolidation.md) maps requirements, claims, test categories and remaining ownership. The [evaluation draft](../../../docs/paper-evaluation-draft.md), [preliminary brief](../../../docs/preliminary-results-brief.md) and [release-evidence index](../../../docs/week6-release-evidence.md) are reporting artifacts, not new experiments. Original manifests remain unchanged. The index pins the experimental snapshot, ignored payloads and recorded run manifests but does not declare the missing shared formal evidence or hardware authorization complete.
