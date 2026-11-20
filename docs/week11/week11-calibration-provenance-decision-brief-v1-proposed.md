# Week 11 Calibration Provenance Decision Brief — v1

**Owner:** Will Wallace  
**Week:** 11
**Status:** Complete

## Executive decision summary

**Recommend conditional retention of the numerical calibration and sigma = 0.15**, with explicit disclosure of the unresolved historical audit history. Expected frozen bytes are now present and match both manifests. Their mixed line endings explain the relationship among the three reported hashes, but do not establish how the earlier audit obtained different bytes. No demonstrated numerical consequence has been identified. Before unconditional scientific acceptance, require one separately scoped full saved-evidence audit with compatible frozen source/environment. A newly frozen calibration rerun is **unwarranted on current evidence**; reconsider only if verification exposes a material inconsistency or faculty requires independent replication. This brief records no acceptance or authorization.

## Experiment and evidence identities

Repository-relative aliases used below:

- **B:** `results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/` — successful bundle, experiment `week9-shared-noise-calibration-v1`.
- **R:** `results/week-9/will/calibration-restart-v1/restart-20261028-01/` — operator, audit and postcompletion receipts.
- **S:** `B/source/src/python/puf_snn/` — preserved source, distinct from live `src/python/puf_snn/` and Git blobs.

Original source revision: `6fd13d143fa5c57692851d24d65b62ec3732f98c`; source-set identity: `a888acae484452b4a85c8442c6d5c3d7fa39b555d27b699bd4f0eaf37fbaf5f6`. Completion: `2026-10-29T01:17:43.405641+00:00`. The 24-device, four-sigma, rho=0 run contains 1,920 matched pairs/3,840 policy attempts; the earlier interrupted run is excluded. [E1–E3]

Initial read-only inspection: branch `main`, HEAD `2cca5f4e67101510f4102ea633ab2716b12fd94c`; sole preexisting change ` M docs/research-logs/will.md`. This brief did not exist. All six specifically requested documents exist at their exact named paths. The reconciliation's statement that `docs/week10/shared-noise-calibration-analysis.md` is absent is stale in this checkout; that exact file was read, without substitution. [E4]

## Original discrepancy versus current findings

The Week 10 analysis/reconciliation (November 5) and exception record (November 6) report `S/pipeline_timing.py` as the sole unresolved entry:

- Expected SHA-256 in **both** `B/manifest.json` and `B/source-manifest.json`: `1b9ddc6926877babca9a4bc7453b2ac71ff774f230656127416654ad2f052ba2`.
- Then-observed raw SHA-256: `e204b6c5fb2607714aaf713a224ece5230d17737450e4b096c6472f66b446228`.
- Then-observed LF-normalized SHA-256: `1f0e23de9a17c9e44ee643c70417aa2452f218c016f2eb234ba78ddcc19e80d9`, reported equal to the live-source Git blob at the original revision. [E4]

The historical comparison reported **76 raw matches / 49 LF-normalization-only matches / 1 unresolved** across 126 bundle entries; the 116-source subset was **76/39/1**. It established byte discrepancies in the inspected representation and agreement after normalization for most entries. It did not establish a passing exact-byte audit, substantive code alteration, or invalid numerical results. It is distinct from the October 29 standalone semantic audit, which recorded PASS. The later comparison's exact command/script, audit checkout HEAD/location, complete input-byte inventory and transformation history are not established by the cited records; the reported source revision does not pin that later audit environment. [E3–E4]

Week 11's proposal and research-log summary report recovery of expected bytes and 126/126 and 116/116 agreement. No standalone calibration-investigation report or original reviewer transcript was located in the inspected repository documentation/Week 11 results; the log's review verdict concerns the proposed final specification, not independent calibration certification. [E5]

**Present bounded verification, at the HEAD above:** all 126 manifest members and 116 preserved source files match exactly. `S/pipeline_timing.py` and its live checkout counterpart both contain 23,208 bytes: **411 CRLF and seven lone LF** terminators, yielding the expected digest. In-memory uniform LF gives 22,797 bytes/418 LF and `1f0e23…80d9`; uniform CRLF gives 23,215 bytes/418 CRLF and `e204b6…6228`. Thus all three identities are reproducible representations of the presently preserved text. The original-revision live-source Git blob, HEAD live-source blob, and HEAD bundle-source blob are uniform LF. The bundle path does not exist at the pre-run source revision. Git blob identity is therefore not raw preserved-file identity.

This demonstrates recovery of the **expected byte sequence**, and supports newline conversion as an explanation of the hash relationship. It does **not** prove that conversion caused the historical observation, identify who/what transformed a copy, or authenticate an uninterrupted chain of custody. Present agreement cannot retrospectively certify that audit.

## Scientific impact and unresolved uncertainty

Static dependency tracing used preserved source, without executing it. [E6]

- **Simulation inputs/PUF generation — reasonably supported unaffected:** `shared_noise_calibration_v1.enrollment_material` uses device manufacture, reference generation and indexed seed domains; runtime uses `correlated_noise_v1.CorrelatedResponseReader`. Neither calls `pipeline_timing.py` functions. No changed input or response is demonstrated.
- **Reconstruction/FRR — reasonably supported unaffected:** runtime calls `pipeline_v2` acquisition/reconstruction and classifies C/D/I/W; analysis counts every non-C outcome as failure. Saved reports reconcile C=3,369, D=458, I=9, W=4. At .15, S/M failures are 49/480 and 15/480. These are preserved findings, not new calculations here. [E2–E4]
- **Bootstrap — reasonably supported unaffected:** `shared_noise_calibration_analysis_v1.bootstrap_devices` uses recorded device counts, `Random`, and `majority3_auth_analysis_v1.percentile`, not `pipeline_timing.quantile`. Saved 10,000 whole-device draws yield the descriptive Delta interval [3.333, 11.250] percentage points; no bootstrap was recomputed here.
- **Seven gates — numerical compliance supported; certification remains conditional:** `candidate_gates` evaluates coverage/correctness, baseline region, M region, minimum benefit, informative counts, uncertainty and heterogeneity. None uses latency. Coverage includes validation/integrity requirements; numerical gate booleans alone cannot resolve provenance.
- **Sigma selection — demonstrated in saved receipts:** .10 fails baseline, benefit, counts and uncertainty; .15/.20/.25 pass all seven; `select_candidates` chooses the lowest qualifying value, .15. At .15 the reported benefit is 7.083 percentage points. The prospective rules were researcher-authorized before execution, not demonstrated faculty-approved thresholds. [E1–E2]
- **Timing — no demonstrated effect from this discrepancy:** calibration uses `three_arm_auth_runtime_v1.Capture`, inheriting `majority3_auth_runtime_v1.Capture` and its `perf_counter_ns` spans. Its summaries use the separate analysis percentile routine. `pipeline_timing.py` contains functional wrappers used by other studies, so its name alone proves nothing; those wrappers are not the traced calibration capture path. Timing remains host-dependent, descriptive and not exactly reproducible.
- **Historical execution reproducibility — incompletely established:** historical completion/two-pass and standalone PASS receipts support the recorded execution, but present hashing is not replay or independent reproduction. The missing audit-history chain remains unknown; OS-random protocol bytes and durations are not seed-reproducible.
- **Formal provenance/acknowledgment — still outstanding:** inherited `source_paths()` includes every package Python file, including `pipeline_timing.py`. Exact hashes gate execution and audit even when functions are unused. Claims that the file is irrelevant to certification, that present matching completes acknowledgment, or that a rerun repairs historical custody are contradicted by these requirements. [E6–E7]

## Contemporaneous versus reconstructed evidence

- **Before execution:** `B/source/docs/week9-shared-noise-study-specification.md`, frozen config/plan/source, `R/checkout-verification.json` (01:10:06 UTC), and run-bound approval-v2 (01:10:52 UTC) preserve requirements and identities before the 01:10:58 launch. The authorization basis expressly disclaims a faculty signature. [E1, E3]
- **Successful execution/finalization:** `B/metadata.json`, enrollments, attempts, summary, validation, selection (01:16:59 UTC), manifests and completion marker preserve outcomes and recorded checks.
- **Postcompletion:** `R/standalone-audit*.json` (01:19:07–01:19:39 UTC), postcompletion analysis receipt (01:19:40 UTC), and final verification (01:22:14 UTC) record later audit/reanalysis and zero new scientific samples. They are not pre-execution requirements.
- **Later investigations:** Week 10 comparisons/exception, Week 11 proposal/log and this brief's static hash checks interpret preserved records. They are not contemporaneous execution evidence. [E4–E5]

## Minimum corrective action

Propose **one full audit of B against its exact frozen source in a compatible recorded environment**, covering artifact/source hashes, imported-source identity, plan/coverage, deterministic reading/vote/decoder replay, summary/selection, consumed authorization and completion identities. Preserve original evidence; retain a separately dated audit receipt and bounded work accounting. One standalone pass entails 7,680 replay readings, 3,840 decodes and 24 enrollment references, adding zero scientific samples. This is proposed future verification, not authorized or performed here. [E3, E6–E7]

The live source set has four mismatches: `docs/week9-shared-noise-study-specification.md`, `src/python/puf_snn/integration.py`, `src/python/puf_snn/source_quality.py`, and `src/python/puf_snn/trial_ledger.py`; 112 other entries match. The repository venv cannot currently launch because its referenced native Python 3.12 executable is unavailable. Identify compatible frozen source/environment first; do not bypass validators, normalize historical files or reseal evidence. Static hashing here used only an available interpreter's standard library.

Keep five decisions separate: **faculty scientific acceptance** disposes of the scientific limitation; **full evidence/source audit** supplies technical validation; **researcher selection acknowledgment** is a genuine named, dated, hash-bound attestation outside B after validation; **final methodology freeze** requires adoption, implementation/review and resource qualification of the Week 11 proposal; **final execution authorization** is separately issued against that completed freeze. None has been created or implied by this brief. [E5, E7]

## Evidence references and anchors

- **E1 — Prospective contract:** `B/source/docs/week9-shared-noise-study-specification.md`, SHA-256 `f5a12c19e9228860b901e9abb0eee4c16aa4dbaa785bbea32fa4b5e31b244b23`; `B/config.json`, `B/trial-plan.json`; `R/approval-v2.json`, `R/authorization-basis.json`. Live context: [Week 9 specification](../week9-shared-noise-study-specification.md).
- **E2 — Outcomes/choice:** `B/attempts.jsonl`, `B/summary.json`, `B/selection.json`; [Week 9 results](../week9-shared-noise-calibration-results.md). Selection raw-file SHA-256 `424a43f99a200f150dda42b85fffb030a73a69976e53f44f2ac8763ecd531d41`; internal canonical selection identity `7cd3f25b3abfe8472d38841f744134cf88981a5d2771a7cc9de4b15463e819c6` is a different digest type.
- **E3 — Validation/lifecycle:** `B/validation.json`, `B/CALIBRATION_VALIDATED.json`; `R/checkout-verification.json`, `execution-invocation.json`, `standalone-audit.json`, `standalone-audit-start.json`, `standalone-audit-process.json`, `postcompletion-analysis-receipt.json`, `final-verification.json`. Present raw manifest hash `18998ac06762e6a77ce9406754e82b97767433f33b4a7774c9f1106fb961f7fa`; marker hash `0fc4ab9ba7a736878a539a1d241a285847f5495bced22ab9d9f9931d4e71f62c`.
- **E4 — Historical comparison:** [exception](../week10/calibration-provenance-exception.md), [analysis](../week10/shared-noise-calibration-analysis.md), [reconciliation](../week10/calibration-outcome-reconciliation.md), especially their integrity sections. Their findings remain historical statements, not present measurements.
- **E5 — Week 11 investigation/review summaries:** [final-study proposal](week11-final-correlated-noise-study-specification-v1-proposed.md), repository assessment and decision/adoption sections; [research log](../research-logs/will.md), historical provenance and independent-review sections. The preexisting modified log is contextual, not an independent audit receipt.
- **E6 — Preserved dependency/validator source:** `S/experiments/{shared_noise_calibration_v1,shared_noise_calibration_runtime_v1,shared_noise_calibration_analysis_v1,shared_noise_calibration_evidence_v1,correlated_noise_v1,three_arm_auth_runtime_v1,majority3_auth_runtime_v1,majority3_auth_analysis_v1,majority3_auth_evidence_v1}.py`; `S/pipeline_v2.py`, `S/puf/{device,acquisition,ro_puf}.py`, `S/reconstruction/credential.py`, `S/pipeline_timing.py`; `B/manifest.json`, `B/source-manifest.json`.
- **E7 — Current workflow:** `src/python/puf_snn/experiments/shared_noise_calibration_provenance_v2.py` (`record_acknowledgment`, `selection_status`) and `shared_noise_calibration_evidence_v1.py` (`source_hashes`, `audit_evidence`); both match their frozen entries. No workflow was invoked.