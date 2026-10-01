# Formal Pre-HKDF Credential Verifier Evaluation

**Owner:** Will Wallace  
**Week:** 5  
**Status:** Completed

## Scope

This evaluates exact saved simulated Layer 2 evidence from `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/`. Reconstruction was **not rerun**; no PUF response was regenerated. An independent HMAC verifier evaluates the saved candidate. This is a trusted local software pilot using a **32-bit proof-of-mechanism credential**, not production-security evidence.

Only a new evaluation runner, independent auditor, focused tests, config, safe-record schema, this report, and a new results directory were added. BCH, reconstruction, Wire 2, HKDF, confirmation implementation, historical Tier 1 evidence, and sealed Layer 2 artifacts were not changed. No reconstruction alternatives or auth-audit-v2 were implemented. No commit or push was made.

## Source Population

| Saved outcome | Rows | Formal verifier called |
| --- | ---: | ---: |
| Correct valid-format candidate | 56,142 | 56,142 |
| Wrong valid-format candidate / miscorrection | 430 | 430 |
| Decoder failure | 26,447 | 0 |
| Invalid format / padding | 981 | 0 |
| Total | 84,000 | 56,572 |

The cohort contains 20 runs, six devices per run, 120 enrollment identities, seven conditions and 12,000 rows per condition. Every saved source row appears exactly once in the formal attempt records. Decoder and format failures have `not_checked`, zero verifier calls and null verification/composite latency; these are not verifier failures.

Source manifest SHA-256: `082db862432da3d1b523f247035d2ae5d27be3a387317792f6eda8e72960a71b`.
Source attempts SHA-256: `8def501bc44a9ab30b66c50665309be6e7e48d20d55222699bd44b830748866a`.
Source identity: `410cc949953619beeae988c7ff02c14b4f04780a9fa4c6d13d00265742e7929d`.

`COMPLETE`, its manifest hash, all 12 manifest entries, 84,000 rows, 120 unique enrollment bindings and both required nominal regressions were checked before evaluation. The known CRLF/LF checkout issue was explicitly checked using raw hashes and LF hashes computed only in memory. **Every artifact and the manifest matched its raw-byte hash in this evaluation environment; no fallback was needed.** CSV files retain their archived line endings. No source file was rewritten or normalized. `source_integrity.json` records raw, LF and expected hashes and the representation used.

## Verifier Configuration
| Setting | Frozen value |
| --- | --- |
| Experiment version | `credential-verifier-experiment-v1` |
| Output version | `puf-snn-credential-verifier-evaluation-v1` |
| Authentication config | `configs/authentication_v2.json`; `puf-snn-auth-config-v2` |
| Authentication profile | `puf-snn-l3-credential-admission-v1-wire2` |
| Reconstruction binding | `puf-snn-reconstruction-v1` |
| Verifier schema | `puf-snn-credential-verifier-v1` |
| Algorithm | `HMAC-SHA-256`, full 32-byte tag, constant-time comparison |
| Domain | `PUF-SNN/credential-verifier/v1` |
| Nonsecret key identifier | `credential-verifier-v1-formal-001-osrandom` |
| Clock | `time.perf_counter_ns()`, Windows `QueryPerformanceCounter()`, 100 ns reported resolution |
| Warm-up | 200 calls: 100 synthetic passes and 100 synthetic mismatches, alternating |

The existing `InMemoryCredentialVerifierKeyProvider.generate()` generated a fresh independent 32-byte OS-random key. It was not derived from credentials, PUF material, HKDF, simulation seeds or session material, and was never written to config, results, logs or manifests. The warm-up used a separate synthetic enrollment and separately generated key; it consumed no experimental source row. All 120 experimental verifier records were provisioned in memory before timed evaluation, one per trusted enrollment identity, with HMAC tags and no plaintext credential field. Provisioning/tag generation is excluded from timing. Records and tags were never serialized.

Trusted provisioning may read the saved enrolled synthetic credential. Runtime verification receives only the candidate and trusted device/enrollment/reconstruction binding. Archived labels classify rows before invocation; evaluator truth is compared only after the real runtime decision for scoring. Neither truth nor an evaluator label is passed to `verify()` or the session admission path. No receiver reference is substituted for the sender candidate.

Exact HMAC bytes are therefore not bit-for-bit reproducible. The source population, algorithm, decisions and evaluation procedure are reproducible. Latencies and fresh session randomness naturally vary. Python does not guarantee secure erasure of transient bytes.

## Candidate Verification Results

| Population | n | Admitted | Rejected | Admission rate | Rejection rate |
| --- | --- | --- | --- | --- | --- |
| correct | 56,142 | 56,142 | 0 | 100.0% | 0.0% |
| wrong | 430 | 0 | 430 | 0.0% | 100.0% |

Correct candidates: 56,142 true accepts, zero false rejects; true-accept rate 100%, observed false-reject rate 0%. Wrong candidates: 430 rejected before admission, zero admitted; catch rate 100%, observed false-admission rate 0%. Counts are derived from actual structured verifier decisions, independently reconciled against source truth. `anomalies.json` is empty. These are finite observations, not zero population error probabilities.

The formal denominator is exactly **56,572** calls. There are separately 430 integration-verifier calls, 120 positive-control verifier calls and 200 synthetic warm-up calls: 57,322 verifier calls in the evaluation process overall. Integration and warm-up calls do not inflate the formal denominator or its latency statistics. Preflight, report generation and reconciliation do not call the verifier.

## Condition-Level Results
Nominal uses the archived baseline noise SD 0.1 and remains distinct from the sweep SD 0.1 condition.

| Condition | Rows | Decoder failures | Invalid format | Correct | Wrong | Invocations | Correct admitted | Correct rejected | Wrong rejected | Wrong admitted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nominal | 12,000 | 186 | 7 | 11,805 | 2 | 11,807 | 11,805 | 0 | 2 | 0 |
| Sweep SD 0.0 | 12,000 | 0 | 0 | 12,000 | 0 | 12,000 | 12,000 | 0 | 0 | 0 |
| Sweep SD 0.05 | 12,000 | 3 | 0 | 11,997 | 0 | 11,997 | 11,997 | 0 | 0 | 0 |
| Sweep SD 0.1 | 12,000 | 175 | 5 | 11,815 | 5 | 11,820 | 11,815 | 0 | 5 | 0 |
| Sweep SD 0.25 | 12,000 | 4,208 | 113 | 7,610 | 69 | 7,679 | 7,610 | 0 | 69 | 0 |
| Sweep SD 0.5 | 12,000 | 10,552 | 342 | 912 | 194 | 1,106 | 912 | 0 | 194 | 0 |
| Sweep SD 1.0 | 12,000 | 11,323 | 514 | 3 | 160 | 163 | 3 | 0 | 160 | 0 |

Condition-level verification and composite timings appear below; all source outcomes remain separate in `condition_summary.csv`.

## Pre-HKDF Miscorrection Evaluation
All **430** saved miscorrections were reconstituted as `ReconstructionResult` objects from recorded outcome, decoder status, correction count, message bits, candidate bytes, padding validity and failure reason. Saved helper material and trusted enrollment bindings were restored without calling `reconstruct()` or `enroll()`.

Each case used the supported audited `puf_snn.auth.sender.Sender.begin_attempt()` path and a fresh matching audited receiver. The harness would hand an emitted request into `Verifier.begin_session()` and continue the real handshake; every wrong candidate instead returned `credential_verification_failed` before that handoff. “Emitted” means returned P3RQ handed to the receiver in this in-process pilot; no network transport is claimed.

| Instrumented event | Per wrong case | Total over 430 |
| --- | ---: | ---: |
| Credential verifier invocation / mismatch | 1 | 430 |
| P3RQ creation | 0 | 0 |
| P3RQ emission | 0 | 0 |
| Receiver begin-session invocation | 0 | 0 |
| Receiver authorization accepted | 0 | 0 |
| Sender `derive_session_key` | 0 | 0 |
| Receiver `derive_session_key` | 0 | 0 |
| Common module derivation lookup | 0 | 0 |
| `hkdf_extract` | 0 | 0 |
| `hkdf_expand` | 0 | 0 |
| `client_proof` | 0 | 0 |
| `server_proof` | 0 | 0 |
| Pending receiver session construction | 0 | 0 |
| Active receiver session construction / publication | 0 | 0 |
| Sender pending / active transition | 0 | 0 |

**No P3RQ, receiver admission, sender HKDF, receiver HKDF, confirmation, or new pending/active session occurred for any miscorrection.** Every sender ended FAILED, with zero pending and active receiver sessions.

Instrumentation wraps the real sender/receiver imported derivation aliases and the common module lookup, extract/expand, both proof functions, framing, pending/active constructors, receiver entry, and service verification/consumption. Publication and endpoint transitions are also inspected at the operation boundary. Counters increment before invoking the real function, so caught errors do not hide invocations. The positive controls confirm that all relevant counters fire. A focused test deliberately introduces a caught unexpected derivation and confirms the invariant fails. Zero HKDF is explicitly counted, not inferred from missing timing. Instrumentation stores no secret-bearing call arguments or return values.

## Known Nominal Regressions
| Saved regression | One-based source row | Result |
| --- | ---: | --- |
| Seed 2222 / device 3 / attempt 88 | 2789 | `credential_mismatch`; `credential_verification_failed`; all pre-HKDF zero invariants pass |
| Seed 6543 / device 1 / attempt 75 | 7976 | `credential_mismatch`; `credential_verification_failed`; all pre-HKDF zero invariants pass |

Both remain present in the unchanged source and in `integration_miscorrections.jsonl`.

## Positive Integration Controls
**120/120 passed**, one first correct saved candidate per enrollment identity, selected in source row order. Each control had one credential-verifier pass, one P3RQ, one accepted receiver authorization, exactly one key derivation per endpoint, successful mutual confirmation, and one active session at each endpoint. Receiver pending creation was one, receiver active construction/publication one, and final pending count zero. Each control recorded two extracts, two expands, two client-proof function calls and two server-proof function calls (generation plus peer comparison). Total sender derivations were 120 and receiver derivations 120. These controls are separate from the 56,142 correct-candidate denominator and are not included in verifier timing.

## Verification Latency
All values in the following table are **microseconds**, except n. Every sample and outlier is retained. Percentile calculation uses linear interpolation at `(n - 1) * 0.95`. Timing starts immediately before `CredentialAdmissionService.verify()` and ends immediately after it returns, covering record lookup, trusted context validation, key-provider access, HMAC generation, constant-time comparison and structured result construction, plus ordinary call/clock boundary overhead. Candidate parsing and context construction are outside the interval. Reconstruction, JSON parsing, truth comparison, record provisioning, session HKDF, audit/file I/O and serialization are excluded. No instrumentation wrapper is installed around the timed verifier calls.

| Population | n | Mean | Median | p95 | Max |
| --- | --- | --- | --- | --- | --- |
| Nominal | 11,807 | 10.719226 | 10.000000 | 12.500000 | 285.100000 |
| Sweep SD 0.0 | 12,000 | 10.686583 | 10.100000 | 12.205000 | 137.800000 |
| Sweep SD 0.05 | 11,997 | 10.517496 | 10.000000 | 11.800000 | 190.400000 |
| Sweep SD 0.1 | 11,820 | 20.468646 | 21.500000 | 26.900000 | 2060.600000 |
| Sweep SD 0.25 | 7,679 | 27.500768 | 22.700000 | 40.500000 | 848.800000 |
| Sweep SD 0.5 | 1,106 | 31.483544 | 25.700000 | 46.575000 | 720.300000 |
| Sweep SD 1.0 | 163 | 40.679755 | 35.800000 | 56.170000 | 194.900000 |
| correct | 56,142 | 15.328797 | 10.200000 | 25.400000 | 2060.600000 |
| wrong | 430 | 34.789302 | 27.800000 | 50.410000 | 592.100000 |
| all invocations | 56,572 | 15.476715 | 10.200000 | 25.900000 | 2060.600000 |

The sequential run retained saved row order, used default garbage collection and no CPU affinity or real-time scheduling. Condition timings increase later in the run; they are observational measurements confounded with execution order and host scheduling, not evidence that noise SD causes verifier computation cost. The wrong-candidate population is concentrated in later conditions. Do not interpret pooled pass/mismatch latency differences as a controlled timing-side-channel experiment. The maximum verifier sample is 2.0606 ms and is retained.

## Archived Reconstruction + Verification Composite Latency
This is **archived reconstruction + current verification composite latency**, not fresh end-to-end timing. For each valid-format source row, its archived reconstruction nanoseconds were added to that row's newly measured verification nanoseconds first. Statistics were then computed from these paired sums; separate percentiles were never added. All values below are **milliseconds**, except n.

| Population | n | Mean | Median | p95 | Max |
| --- | --- | --- | --- | --- | --- |
| Nominal | 11,807 | 1.179027 | 1.048800 | 2.273100 | 16.634400 |
| Sweep SD 0.0 | 12,000 | 0.174622 | 0.156000 | 0.261500 | 1.264800 |
| Sweep SD 0.05 | 11,997 | 0.864484 | 0.904800 | 1.959740 | 4.618000 |
| Sweep SD 0.1 | 11,820 | 1.134081 | 1.026950 | 2.152310 | 8.749400 |
| Sweep SD 0.25 | 7,679 | 1.294676 | 1.115200 | 2.188010 | 6.786800 |
| Sweep SD 0.5 | 1,106 | 1.367315 | 1.171500 | 2.301975 | 5.755400 |
| Sweep SD 1.0 | 163 | 1.368028 | 1.172500 | 2.265770 | 4.105200 |
| correct | 56,142 | 0.906200 | 0.946400 | 2.054495 | 16.634400 |
| wrong | 430 | 1.380065 | 1.184200 | 2.318890 | 4.229800 |
| all invocations | 56,572 | 0.909802 | 0.948500 | 2.056900 | 16.634400 |

Decoder and invalid-format rows do not have a verifier/composite sample. Their archived reconstruction-only durations are reported separately below (milliseconds); no verification cost is invented for them.

| Population | n | Mean | Median | p95 | Max |
| --- | --- | --- | --- | --- | --- |
| decoder_failure | 26,447 | 1.117078 | 0.951600 | 1.926570 | 7.975500 |
| invalid_format_or_padding | 981 | 1.336314 | 1.155800 | 2.215800 | 4.285700 |

## Statistical Uncertainty
Two-sided 95% Wilson score intervals use `z = 1.959963984540054`:

| Decision proportion | Observed | Percentage | Two-sided 95% Wilson interval |
| --- | ---: | ---: | --- |
| Correct-candidate admission | 56,142 / 56,142 | 100% | 99.993158% to 100% |
| Wrong-candidate rejection | 430 / 430 | 100% | 99.114548% to 100% |

For zero observed wrong admissions, the complementary Wilson interval for admission has an upper bound of **0.885452%** (0.00885452218221916 as a proportion), not zero. The analogous correct-candidate false-reject upper bound is **0.00684193%**. These are complements of the requested two-sided 95% Wilson intervals, not separately calculated one-sided bounds. They do not establish universal security or zero population false-admission/false-reject probability.

The sample is a saved, selected synthetic miscorrection population with repeated attempts sharing enrollment/device/run identities. The Wilson calculation uses a binomial working model; independence and population representativeness are not established. These intervals describe finite-sample uncertainty under that model, not a deployment-security guarantee.

## Evidence Integrity and Reconciliation
Independent reconciliation reread saved source rows and safe output records without importing the verifier, reconstruction or simulator. It checked,
- `84,000 = 56,142 + 430 + 26,447 + 981` and `56,572 = 56,142 + 430`
- All 84,000 one-based source locators exactly once, with exact original condition and enrollment identity
- Exactly one verifier call per valid-format row and zero calls/null timing for all decoder/format failures
- Decisions against archived enrollment truth, separate 430-case and 120-case integration populations, exact counters, and both nominal regressions
- Per-attempt composite pairing, every condition/pooled summary and Wilson interval, recalculated independently
- Exact allowed attempt/integration fields and absence of forbidden secret-bearing keys. All 84,000 attempt records also passed the JSON Schema
- Before/after raw SHA-256 equality for **547 protected files**, including every pre-existing result file and all `puf_snn` Python implementation files; the pre-existing result file set was unchanged. The original preflight snapshot was checked separately as well
- Runtime reconstruction/BCH guard count **zero**. No reconstruction or PUF simulator was run

Seven focused evaluator tests passed before evaluation (final run: 0.641 s; initial run: 1.180 s), with no failures, errors, skips or warnings. They cover real synthetic pass/rejection integration, caught derivation detection, reconstruction guards, outlier/percentile calculation, Wilson uncertainty, output-field rejection and independent audit detection of invocation/composite/locator/label tampering. No general auth suite or reconstruction test suite was run during this task.

`validation.json` records the test and schema checks. `reconciliation.json` records independent PASS. `manifest.json` hashes every preceding file in the new evidence directory, including an exact report copy, safe schema, config, metadata and integrity snapshots. `COMPLETE` references the manifest and reconciliation hashes and is written **last**. The manifest cannot hash itself or the subsequently written COMPLETE marker; COMPLETE closes that chain. No valid COMPLETE is written on failure. The initial evaluation metadata deliberately retains its pre-sealing status; final completion authority is `COMPLETE` plus the manifest/reconciliation chain.

The existing virtual environment required execution outside the restricted sandbox to access its installed interpreter. No package or dependency was installed or upgraded. Actual runtime was Python 3.12.4, Windows 11 AMD64, with `NUMBA_CPU_NAME=generic` preserved from the repository workflow; no codec operation was invoked.

## Security Interpretation
Layer 2 reconstruction can produce valid-format wrong candidates beyond its correction radius. A valid padding/message shape alone does not establish that the enrolled credential was recovered.
The independent verifier checks whether a candidate matches the trusted enrolled HMAC record, with its trusted device/enrollment/reconstruction/key binding. This experiment observed successful detection of all 430 saved miscorrections, including the two nominal regressions.
The supported session path permits HKDF only after successful credential admission. Every saved wrong candidate stopped before either endpoint derived session material. The positive controls show that legitimate candidates still reach both derivations and mutual confirmation. This establishes the tested local control-flow invariant for this finite saved cohort; it does not establish physical device provenance or cryptographic security beyond the pilot's assumptions.

## Limitations
- Only a 32-bit credential; HKDF does not add credential entropy
- Captured confirmation traffic still permits traffic-based offline guessing of credentials
- Verifier service-key compromise with records permits offline credential search; the reference registry and existing research fixtures retain their original sensitive-material assumptions
- A trusted co-located process shares the local admission service and has access to transient secrets. This is not malicious-process isolation, protected key custody, remote attestation or a remote authorization token
- Synthetic PUF and saved/selected reconstruction population; no physical PUF was tested
- Finite sample size, repeated enrollment identities and nonrandom condition order limit statistical and latency interpretation
- No production-security claim, universal-security claim or zero population error-probability claim
- Confirmation behavior, Wire 2 and old generic audit-v1 vocabulary remain unchanged. No auth-audit-v2 was needed; external safe counters provide this experiment's detailed evidence
- Composite timing combines archived reconstruction measurements with current verifier measurements and is not a fresh end-to-end benchmark

## Evidence Paths
- Source: `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/`.
- New sealed evidence: `results/week-5/will/credential-verifier/credential-verifier-v1-formal-001/`.
- Config: `configs/credential_verifier_experiment_v1.json`.
- Runner: `src/python/scripts/run_credential_verifier_experiment.py`.
- Independent auditor: `src/python/scripts/audit_credential_verifier_experiment.py`.
- Safe schema: `schemas/credential-verifier-attempt-v1.schema.json`.
- Focused tests: `tests/experiments/test_credential_verifier_experiment.py`.
- Report: `docs/credential-verifier-formal-results-week5.md`; identical evidence copy: `formal_results.md`.

Run commands from repository root (the formal output directory is exclusive and cannot be reused),
```powershell
$env:PYTHONPATH = 'src/python'
$env:NUMBA_CPU_NAME = 'generic'
.\.venv\Scripts\python.exe -B -W default -m unittest tests.experiments.test_credential_verifier_experiment
.\.venv\Scripts\python.exe -B src/python/scripts/run_credential_verifier_experiment.py --preflight
.\.venv\Scripts\python.exe -B src/python/scripts/run_credential_verifier_experiment.py --evaluate
python -B src/python/scripts/audit_credential_verifier_experiment.py
# After report and validation evidence are present:
python -B src/python/scripts/audit_credential_verifier_experiment.py --seal
```
