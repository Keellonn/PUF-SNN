# Week 6: Current v2 Integration, Composite Timing and Outlier Diagnostics

**Owner:** Keegan Hoyne
**Evidence recorded:** October 5-7, 2026
**Shared reconstruction/authentication owner:** Will Wallace

## Scope and conclusion

This week connected the current independent pre-HKDF admission path to unchanged, frozen motion and anomaly models, then recorded the first instrumented fresh-session and composite post-window CPU timing. Functional boundary checks passed and the saved run reconciles. None of the six complete motion-plus-anomaly conditions meets the provisional 20 ms post-window p95 target in this instrumented environment. Subsequent paired GC/observer controls and bounded Windows scheduling/I/O accounting support collector and ready-delay contributions. Complete causal attribution and isolated tracing overhead remain unestablished; no diagnostic replaces the original target result.

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

The latest saved full Python suite passed 834 tests, including 43 Windows OS accounting/privacy-reporting tests. The earlier 666-test timing-reporting checkpoint included 24 reporting tests. Earlier suites are historical checkpoints, not additional independent test samples.

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

Formal v2 trust/key/enrollment specification, expanded varied Tier-1 trials, controlled reconstruction-reliability alternatives, durable audit performance and approved Quest logger validation remain separate/shared tasks. Baseline nominal FRR, anomaly targets and constrained SNN conclusions stay unchanged. No SNN architecture/anomaly expansion, physical transfer, cross-person/device generalization, production security or hard real-time claim follows.
