# Week 9 Evidence, Resource Feasibility, and Reproducibility

Prepared October 28, 2026, from Tasks 3A–3C and preserved research evidence. This is a retrospective report: no experiment, test, benchmark, replay audit, or model inference was executed for its preparation. THe observed results, source-derived projections, and unresolved questions are distinguished below.

## Executive Summary
The October 20 three-arm authentication pilot preserves 150 completed attempts and numerically reconciled results. Single-Read, Majority-3, and Stored-Provisioned established 41/50, 45/50, and 50/50 sessions respectively. Its 136 authorized releases invoked recording callbacks, not trained models. Independent inspection verified the declared evidence and frozen-source hashes; reconciliation of those saved records is not another experimental execution. [Pilot results][pilot-results]

Two October 21 resource-profiling executions show that caching schema preparation reduced the 150-attempt workflow from 142.875 to 48.734 seconds: a 65.9% observed reduction and approximately 2.93× speedup. All required instance validations remained active. This improved experiment-harness overhead, not PUF acquisition or inference algorithms. Full-scale memory and completion time remain unqualified. [Profiling receipts][resource-baseline] [and comparison][resource-optimized]

Preserved Week 6 research already executed and directly timed simulated Single-Read authentication through saved conventional/SNN/anomaly inference. Keegan’s October 22 controlled comparison additionally supports selected functional-output agreement across quality implementations and recovery policies, without measuring latency or noisy-PUF reliability. These complementary workloads cannot be pooled. Independent experimental reproduction, unresolved provenance records, formal-scale resource qualification, and faculty approval remain outstanding. [Timing evidence][fresh-manifest]; [functional evidence][quality-summary]

## Experiment and Evidence Scope
An attempt is a credential-source/authentication invocation; only a successful establishment creates an active session. Accepted windows can produce composite releases, each invoking preprocessing, motion, and anomaly callbacks. These counts are different denominators. Reconciliation repeats deterministic checks on saved evidence and adds no experimental observations.

| Preserved workload | Allocation and outcomes | PUF source | Downstream consumer and scope |
|---|---|---|---|
| [October 20 three-arm pilot][pilot] | 50 matched cells; 150 arm attempts; 136 sessions/windows/releases | Noisy simulated Single-Read and Majority-3; trusted stored control | Recording callbacks; descriptive authentication outcomes and stage timings |
| October 21 [baseline][resource-baseline] / [optimized][resource-optimized] profiling | One separate 150-attempt bundle per session; two finalization reconciliations each | Same scientific pilot configuration | Recording callbacks; workflow, memory, persistence, and validation overhead |
| [Week 6 initial saved-model timing][fresh-manifest] | 3,720 fresh attempts including warmups; 599/600 measured admissions accepted per model condition | Noisy simulated Single-Read | Actual saved models; six motion/anomaly combinations; fresh and recurring timing |
| [Week 6 matched quality benchmark][quality-timing-manifest] | 1,800 fresh attempts including warmups; four workers; 120/120 measured admissions accepted in block 0 and 119/120 in block 1 per mode/configuration | Noisy simulated Single-Read | Actual saved models; three configurations; matched arithmetic modes and timing boundaries |
| [October 22 quality validation][quality-summary] | 360 admitted sessions; 1,080 accepted windows; 1,080 rejection controls | Controlled correctable Single-Read/Majority-3 fixtures | Actual saved models; functional comparisons, explicitly no timing |
| [October 22 regression][regression] | 1,085 unique selected passing tests | Mixed unit/integration fixtures | Implementation checks; neither another study nor complete repository coverage |

The original pilot’s [source manifest][pilot-source] identifies execution as `83001370f5a65f5d8c6cb55c38bd6f239a6c693a065182b22e1b24575e695153`; its [metadata][pilot-metadata] binds configuration, plan, and environment. Frozen bytes identify this run more precisely than its Git base commit alone. Week 6 timing sources are `78f499a92f633a4793c776a070058e3a6a9a0b61` for the initial run and `bddce50198d68b851f648d45638aa06d9eea152c` for the quality benchmark. October 22’s [execution manifest][quality-manifest] and [source map][quality-source] identify its then-uncommitted additions; the base commit alone is insufficient.

Research logs provide chronology and researcher attribution. Execution receipts, records, and source identities determine the narrower claims in this report.

## Resource Optimization
Observed: both October 21 sessions were accepted by the profiler. The authoritative sidecars are `tmp/week8-three-arm-resource-profile-v1/first-20261021-01/` and `tmp/week8-three-arm-resource-profile-v1/cachecmp-20261021-01/`. Their [baseline][baseline-worker] and [optimized][optimized-worker] worker summaries preserve the following counters.

| Metric, 150 attempts per execution | Baseline | Optimized |
|---|---:|---:|
| Total session/workflow wall time | 142.875 s | 48.734 s |
| Schema-definition checks | 459 | 5 |
| Required instance validations | 459 | 459 |
| Inclusive schema self-check time | 97.799 s | 1.073 s |
| Inclusive finalization time | 71.528 s | 8.050 s |
| Sampled peak private bytes | 1,501,810,688 | 1,502,896,128 |

The observed saving is 94.141 seconds, or 65.9%; the runtime ratio is approximately 2.93×. Finalization fell approximately 88.7%. These are **two descriptive profiling executions**, not replicated performance distributions. Instrumentation, operating-system activity, compilation, and cache state affect their durations. [Benchmark interpretation][schema-report]

The [process-local cache][schema-cache] retains up to 16 successfully prepared validators, keyed by exact schema bytes and validator class. Schema self-checking establishes that a definition conforms to its meta-schema; instance validation checks each configuration, plan, attempt, or summary against that definition. Every public call still reads current schema bytes and performs instance validation. Only successful parsing, self-checking, and validator preparation are reused. The 459 instance validations include 450 attempt checks across append and two reconciliations, plus nine other checks.

Both memory counters are approximately 1.502 decimal GB, or 1.399 GiB, with a slight increase after optimization. Windows private commitment is not resident working set; sampled maxima are not guaranteed instantaneous peaks. No memory reduction is demonstrated. Inclusive timers overlap: self-checks nest inside validation, and reconciliation/internal audit nest inside finalization. They must not be added. The [profiler report][profiler-report] explains those measurement limits.

This cache preserves evidence checks and improves harness efficiency. It does not demonstrate faster PUF acquisition, sensor-window authentication, or model inference.

## 4 — Scaling and Validation Requirements

Proposed, not executed or approved: the unchanged [formal configuration][formal-config] allocates 20 populations × 6 devices × 50 trials × 5 conditions × 3 arms: 30,000 matched cells and **90,000 attempts**. Formal execution remains disabled. The following counts are source-derived under successful uninterrupted completion, not formal measurements.

| Work | Original experiment | Additional two-pass finalization |
|---|---:|---:|
| PUF readings / replay measurements | 120,000 | 240,000 |
| BCH decodes | 60,000 | 120,000 |
| Stored retrievals | 30,000 | None rerun as experimental retrievals |
| Enrollment/reference readings | 120 | 240 |
| Reconciliation passes | — | 2 |

Each standalone audit would add another 120,000 replay measurements, 60,000 decodes, and 120 reference readings, plus record validation and integrity checks. Replay verifies existing attempts; it does not enlarge reliability denominators. The [resource plan][resource-plan] supplies the derivation and separates these operations from execution.

Projection: extrapolating the original 924,808-byte ledger by attempt count gives approximately 555 MB of JSONL. The October 21 ledger sizes imply approximately 561 MB instead. Allowing for the plan and relatively fixed supporting artifacts gives a central evidence-bundle estimate of **approximately 0.6 GB**, not a storage guarantee. It excludes adequate reserve for analysis outputs, caches, profiler logs, backups, filesystem allocation, and retained incomplete runs. Outcome-dependent row lengths can change the estimate; serialized bytes do not determine Python heap size.

Source-established risks: the [writer/auditor][writer] retains complete nested attempt records. Internal finalization audit parses another complete record graph while the first remains live; plans, schedules, identity sets, summaries, and temporary byte buffers also require memory. Repeated source hashing and per-row write/flush/fsync persist after schema caching. Hash-input bytes describe logical work, not necessarily physical disk traffic. There is no automatic interrupted-run resume; a late failure can retain nearly complete output and require repeated work in a new run.

Unmeasured: full-scale peak private memory and completion/finalization time. Multiplying pilot wall time or memory by the allocation ratio is not a qualified estimate. Successful 150-attempt profiling establishes neither RAM fit nor sustained execution feasibility. The leading resource question is whether finalization, especially the second record graph, fits a selected workstation’s private-memory budget with adequate operating-system headroom.

## Evidence Provenance and Reproducibility
The October 20 bundle contains 150 preserved completed attempts**, 95 matching evidence-manifest members, 87 matching frozen source members, and a completion marker matching its manifest hash. Task 3B independently checked these static identities. Task 1’s [numerical report][pilot-results] records agreement across 4,540 group-summary leaf values; Task 3B additionally checked 135 group count fields without discrepancy. These are independent checks of existing bytes and arithmetic, not reruns or independent experimental samples. Primary anchors are the [attempts][pilot-attempts], [summary][pilot-summary], [manifest][pilot-manifest], [source manifest][pilot-source], and [completion marker][pilot-marker].

The [original validation receipt][pilot-validation] describes one reconciliation: 200 replay measurements, 100 replay BCH decodes, and one reference reading. The completion marker records two passes; frozen control flow therefore entails 400/200/2 validation operations at successful finalization. Original experimental work remains 200 PUF readings, 100 runtime decodes, and 50 stored retrievals. A later standalone audit is researcher-reported in the [accounting addendum][validation-report]; no separate output receipt was located. Its additional 200/100/1 is source-derived conditional accounting, not independently recorded execution.

Preserved execution, verified hashes, numerical reconciliation, built-in finalization, an independently run functional test suite, and an independent experimental reproduction are different evidence levels. Neither developer test receipts nor source checkout alone establishes the latter. Separate independent experimental reproduction of the October 20 pilot or October 22 saved-model workload was **not established**. The [handoff manifest][handoff] explicitly records no cross-person or fresh-environment reproduction. Earlier scoped clean-environment checks concern other source boundaries, as explained in [release readiness][release-readiness].

Three limitations remain unresolved. First, the historical `pipeline_timing.py` fingerprint question lacks the original conflicting receipt and expected/observed hash pair. Present frozen-file agreement does not resolve its history. Second, [current source][writer] still requires `docs/week8-three-arm-auth-tests.patch`, absent at that path but present under [docs/archive/][archived-patch]. This is a likely execution/audit blocker from static inspection, not a failure executed during these audits. Third, no primary receipt for the reported ARM64 attempt at commit `295f92081d17fa02f5844c836415dbc09e6da132` was located. Its claimed stopping point remains unverified; no qualifying functional or experimental reproduction output was found.

Task 3B found the frozen synthetic dataset and all 11 saved-model binaries hash-correct in the audited workspace against the [input configuration][frozen-config] and [artifact pins][model-hashes]. This does not establish availability elsewhere. PUF metadata records Python 3.12.4; Keegan’s handoff specifies Windows x64/Python 3.13.14 and an [observed dependency lock][dependency-lock]. Exact source representation matters: line endings can change raw hashes despite matching text. Seeds reproduce simulation inputs and schedules; OS-random keys, nonces, session IDs, and timing remain unmatched. Historical evidence must not be rewritten to disguise these differences.

## PUF/SNN Integration
The implemented chain is: **simulated PUF → BCH reconstruction → independent credential verification → authorization → session establishment → authenticated-window verification → controlled release → preprocessing → motion classification → anomaly detection**. The [connector][pipeline], [Wire-2 delivery interface][integration], and [frozen-model adapter][frozen-models] separate credential authority, payload authority, and consumer behavior.

| Contribution | Implementation / test basis | Preserved execution boundary |
|---|---|---|
| Acquisition and reconstruction | Single-Read/Majority-3 acquisition, BCH and format checks; pipeline/reconstruction fixtures | October 20 noisy three-arm authentication; Week 6 noisy Single-Read; October 22 controlled fixtures |
| Verification, authorization, handshake | Independent candidate verification, local admission, HKDF and mutual confirmation; credential/session tests | Real authentication code in all three integration workloads |
| Window integrity, replay and release | HMAC, identity/session binding, exact-next ordering, verifier-owned acceptance and at-most-once gate; refusal/release tests | October 20 positive windows; Week 6/October 22 also exercise refusal controls |
| Preprocessing | Accepted binary32 payload to finite 120×7 motion and 48-feature anomaly inputs; interface tests | Actual feature preparation in Week 6/October 22; recording callback in October 20 |
| Motion and anomaly inference | Saved conventional/SNN-32 models and frozen anomaly thresholds; loader/model tests | Actual saved-model inference in Week 6/October 22; recording callbacks in October 20 |

Thus October 20’s 136 recording releases are not 136 SNN inferences. Conversely, Week 6 already demonstrates complete simulated Single-Read authentication through saved-model inference with direct timing. October 22 extends functional integration to both acquisition policies using correctable fixtures; it supplies neither noisy-RO reliability nor latency evidence. No unified three-arm saved-model performance study is established.

The handoff must preserve exact accepted-payload binding and consumed-event handling. Rejected traffic invokes no models; callback failure leaves evidence incomplete without automatic redelivery or rollback. Labels/splits are excluded from model inputs, and anomaly flags do not retroactively alter authentication. These finite software checks do not establish physical PUF security, deployed key custody, or general model accuracy.

## Keegan’s Functional and Timing Evidence
The [October 22 protocol][quality-config] uses 30 validation windows, three model combinations, two acquisition policies, and two arithmetic modes: **360 sessions**. The [saved records][quality-cells] and [summary][quality-summary] support 180 arithmetic comparison pairs and 180 downstream recovery-policy pairs, 1,080 accepted windows, and 1,080 rejected controls. Both pair counts refer to comparisons among existing sessions, not additional sessions. Task 3B found no recorded pair mismatches in decisions/reasons, model-input fingerprints, motion predictions, anomaly scores/flags, call counts, release counts, or session state.

The configurations are logistic motion/logistic anomaly, logistic motion/forest anomaly, and SNN-32 seed 7/forest anomaly. Controlled response fixtures exercise real voting, decoding, verification, and release, but do not measure noisy-PUF reliability. All admissions succeed; broader admission-failure coverage comes from separate tests. The [differential tests][quality-equivalence] include deterministic consumer probes, which must not be relabeled as trained-model predictions. Functional agreement is bounded to the recorded cases and does not itself establish speedup or universal equivalence.

The [regression receipt][regression] records **1,085 selected passing tests, including 73 focused tests**, not 1,158. The [reproduction guide][reproduction-guide] identifies the focused 26 + 28 + 6 + 13 methods and repeated-run overlap. Root discovery excludes non-package `experiments`, `tier1`, and `tools`; this is not complete historical-suite validation. The [validation decision][keegan-validation] retains unchanged defaults, with exact-integer quality arithmetic as an optional serial research implementation.

Observed performance comes from the separate Week 6 matched quality benchmark. The following direct accepted-path p95 values use logistic motion and logistic anomaly detection; both saved estimators use the predeclared seed-7/6007 identities. Task 3C independently recomputed the selected raw-trace quantiles. [Primary timing CSV][quality-timing-csv]; [benchmark interpretation][quality-timing-report]

| Block | Accepted n per mode/path | Reference recurring | Integer recurring | Reference fresh-to-first | Integer fresh-to-first |
|---|---:|---:|---:|---:|---:|
| 0: reference then candidate | 120 of 120 planned | 27.4285 ms | 14.2551 ms | 34.6154 ms | 22.2278 ms |
| 1: candidate then reference | 119 of 120 planned | 25.1534 ms | 15.3827 ms | 31.3079 ms | 23.4115 ms |

Fresh-to-first directly includes a simulated read, reconstruction, verification/authorization, handshake, first-window protection/verification, release, preprocessing, and both models. Recurring timing processes another window on an established session without another reconstruction or handshake. Each condition has 30 validation warmups; measured fresh sessions are not cold process startup. The first-use observations remain separately visible. Source/noise streams are matched within block, while actual cryptographic values differ. Quantiles are conditional on accepted admission; failures retain separate denominators.

Only optimized logistic/logistic recurring processing meets the provisional 20 ms p95 target in both bounded blocks. Optimized SNN-32 seed 7/forest recurring p95 is 32.1141/40.8279 ms, with fresh-to-first 37.7728/49.9577 ms; those paths do not meet that target. None implies a hard deadline or SNN algorithm speedup. The [earlier six-configuration timing run][fresh-timing-csv] is another distinct benchmark, not the matched reference to subtract here.

The software measurements exclude two-second sensor collection, physical PUF acquisition, external transport, enrollment, endpoint construction, model loading, and durable evidence storage. In-memory audit and instrumentation remain included. The [worker environment][timing-environment] records Windows 11, an HP Pavilion Plus/Core Ultra 7 155H, 31.5 GiB RAM, Python 3.13.14, CPU Torch 2.14.0+cpu, and enabled GC. Core/frequency/thermal/background effects and complete outlier causation remain uncontrolled. These values must not be added to October 20 stage timings or October 21 workflow seconds.

## Outstanding Scientific and Reproducibility Questions
Every next action below is proposed work, not existing authorization.

| Issue | Current Evidence | Missing Evidence | Why It Matters | Proposed Next Action |
|---|---|---|---|---|
| Formal-scale peak memory | Small-run private-byte samples; retained/duplicated graphs in source | Qualified finalization peak and headroom | Memory exhaustion could invalidate completion | Seek approval for a bounded resource-qualification method and explicit host budget |
| Independent compatible host | Frozen inputs correct locally; environment pins/handoff available | Investigator-host receipt and actual comparable execution | Availability and checkout are not reproduction | Verify complete frozen handoff/environment before separately authorized execution |
| Historical source provenance | Current frozen hashes agree | Original timing-source discrepancy receipt/hash pair; ARM64 attempt record | Provenance history cannot be silently closed | Recover primary records or retain explicit unresolved status |
| Required-source-path discrepancy | Absent old patch path; archived file present | Reviewed resolution and subsequent validation | Current execution/audit may stop before work | Address in a separately authorized source-maintenance task; preserve old manifests |
| Unified three-arm trained-model latency | Single-read timing and controlled two-policy functionality | Consistent noisy three-arm saved-model timing | Existing workloads answer different questions | Define one reviewed workload/boundary before proposing measurement |
| Physical Quest/PUF measurements | Software simulation and synthetic motion | Qualified hardware/capture/transport evidence | No physical timing/security generalization follows | Determine hardware and collection prerequisites under applicable approvals |
| Correlated-noise statistics | Exploratory pilot and proposed allocation/methodology | Approved estimands, population-aware uncertainty, completed analysis | Repeated reads/controls are dependent | Obtain faculty methodology review and freeze the analysis plan |
| Faculty approval and execution controls | Formal mode disabled | Methodology approval, resource qualification, frozen identities, separate execution approval | A proposed allocation is not permission to run | Keep formal gates disabled until prerequisites and explicit authorization are documented |

## Faculty-Facing Conclusions
The project has demonstrated a working software connection between simulated PUF authentication and protected motion processing. The original three-arm pilot distinguishes credential acquisition, reconstruction, verification, and release outcomes; its numerical results agree with preserved records. Separate Week 6 executions show that single-read simulated authentication can proceed through actual saved conventional, SNN, and anomaly inference, with the complete software path measured directly. The pilot’s recording callbacks and these trained-model executions answer different questions.

Two optimizations also have distinct evidence. Schema caching reduced pilot-scale experiment-processing overhead while retaining record validation and two-pass reconciliation. Optional exact-integer quality arithmetic reduced selected complete-window latency in a separate matched benchmark. Only the logistic/logistic recurring configuration met the provisional 20 ms p95 target in both blocks; fresh-session and SNN/forest results remained above it. These findings do not establish deployment deadlines or faster SNN algorithms.

Independent checks verified evidence/source hashes and reconciled saved numerical outputs and selected timing quantiles. They did not independently repeat the experiments. Keegan’s controlled comparison supports agreement of recorded model and protocol outputs on its declared cases, without universal equivalence or new reliability claims.

Formal-scale peak memory and completion time, independent execution on a compatible host, historical provenance questions, physical-device behavior, and unified three-arm trained-model timing remain unverified. Before formal experiments, faculty should review the statistical methodology, resolve or explicitly retain provenance limitations, qualify resource budgets and the reproduction handoff, freeze source/configuration/environment identities, and separately authorize execution. No proposed follow-up in this report is presented as approved.

[pilot-results]: week9-three-arm-results.md
[pilot]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/
[pilot-attempts]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/attempts.jsonl
[pilot-summary]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/summary.json
[pilot-manifest]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/manifest.json
[pilot-source]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source-manifest.json
[pilot-metadata]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/metadata.json
[pilot-marker]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/NONFORMAL_VALIDATED.json
[pilot-validation]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/validation.json
[validation-report]: week8-evidence-validation.md
[resource-baseline]: ../tmp/week8-three-arm-resource-profile-v1/first-20261021-01/summary.json
[resource-optimized]: ../tmp/week8-three-arm-resource-profile-v1/cachecmp-20261021-01/summary.json
[baseline-worker]: ../tmp/week8-three-arm-resource-profile-v1/first-20261021-01/pair-1/summary.json
[optimized-worker]: ../tmp/week8-three-arm-resource-profile-v1/cachecmp-20261021-01/pair-1/summary.json
[schema-report]: week8-schema-validation-optimization-benchmark.md
[schema-cache]: ../src/python/puf_snn/experiments/majority3_auth_v1.py
[profiler-report]: archive/week8-three-arm-resource-profiler-v1.md
[resource-plan]: archive/week8-three-arm-formal-resource-feasibility-plan-v1.md
[formal-config]: ../configs/three_arm_auth_v1.json
[writer]: ../src/python/puf_snn/experiments/three_arm_auth_evidence_v1.py
[archived-patch]: archive/week8-three-arm-auth-tests.patch
[fresh-manifest]: ../results/week-6/keegan/fresh-v2-timing/manifest.json
[fresh-timing-csv]: ../results/week-6/keegan/fresh-v2-timing/path-latency.csv
[quality-timing-manifest]: ../results/week-6/keegan/quality-benchmark/manifest.json
[quality-timing-csv]: ../results/week-6/keegan/quality-benchmark/direct-path-latency.csv
[quality-timing-report]: ../results/week-6/keegan/quality-benchmark/quality-benchmark.md
[timing-environment]: ../results/week-6/keegan/quality-benchmark/workers/block-0-candidate_dyadic/environment-start.json
[quality-summary]: ../results/week-8/keegan/quality-validation-20261022-001/summary.json
[quality-manifest]: ../results/week-8/keegan/quality-validation-20261022-001/manifest.json
[quality-source]: ../results/week-8/keegan/quality-validation-20261022-001/source-hashes.json
[quality-cells]: ../results/week-8/keegan/quality-validation-20261022-001/cells.jsonl
[quality-config]: ../configs/week8_quality_validation.json
[quality-equivalence]: week8-quality-equivalence.md
[keegan-validation]: week8-keegan-validation.md
[regression]: ../results/week-8/keegan/regression-20261022-001/summary.json
[reproduction-guide]: week8-keegan-reproduction.md
[handoff]: ../results/week-8/keegan/handoff-20261022-002/manifest.json
[release-readiness]: week7-release-readiness.md
[frozen-config]: ../configs/week6_smoke.json
[model-hashes]: ../results/week-8/keegan/quality-validation-20261022-001/frozen-input-hashes.json
[dependency-lock]: ../requirements/week7/win-amd64-cp313-observed-hashed.txt
[pipeline]: ../src/python/puf_snn/pipeline_v2.py
[integration]: ../src/python/puf_snn/integration.py
[frozen-models]: ../src/python/puf_snn/frozen_pipeline.py
