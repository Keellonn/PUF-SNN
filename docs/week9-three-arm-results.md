# Exploratory Three-Arm Pilot Results

**Owner:** Will Wallace  
**Week:** 9
**Status:** Complete

This is a retrospective analysis of the existing exploratory pilot, not a new Week 9 experiment. No experimental execution or implementation change was performed for this report.

## Executive Summary
The October 20, 2026 software pilot compared three ways to obtain the same enrolled credential: one noisy PUF reading, three readings with majority voting, and trusted retrieval of a provisioned credential. Each source fed the same independent credential verifier, admission service, mutual handshake, authenticated-window verifier, and recording-consumer release boundary. The allocation comprised 50 matched trial-condition cells and 150 arm attempts on one simulated device.

Single-Read established 41/50 sessions (82%), Majority-3 established 45/50 (90%), and Stored-Provisioned established 50/50 (100%). All PUF reconstruction failures occurred under independent stress. Majority-3 supplied four additional successful sessions there; the other four conditions produced no observed session failures in either PUF arm. One Single-Read candidate had valid format but the wrong credential. Independent verification rejected it before session-key derivation or consumer release.

Majority-3 increased median acquisition cost from 0.244 to 0.693 ms while retaining one BCH decode per attempt. Across the pilot, 136 authenticated windows led to completed authorized recording releases. These descriptive observations do not establish statistical superiority, adversarial rejection rates, physical PUF security, or SNN performance. Replicated populations, controlled timing, and explicit adversarial tests remain necessary.

## Experimental Design and Trust Assumptions
The [executed configuration][config], [trial plan][plan], [enrollment record][enrollments], and [frozen methodology][frozen-methodology] define three credential sources:

- **Single-Read** (`single-read-v1`): one noisy 64-bit response, BCH(63,36,t=5) reconstruction, independent verification, then downstream authentication.
- **Majority-3** (`majority-3-v1`): three noisy response measurements, bitwise majority voting, one BCH reconstruction, then identical downstream stages.
- **Stored-Provisioned** (`stored-provisioned-v1`): trusted software retrieval of the same enrolled 32-bit credential, with no runtime PUF measurement, BCH decode, or PUF fallback.

In the [frozen stored implementation][stored-source], `StoredCredentialRecord.credential4` is a Python `bytes` value of exactly four bytes. An in-memory mapping indexes records by device, enrollment, and reconstruction identity. Provisioning precedes timing. This is plaintext credential material in trusted process memory; representation redaction and an immutable mapping do not provide secret isolation or secure erasure.

This record is distinct from public BCH helper data and the keyed enrollment tag in the [independent verifier record][credential-verifier]. The verifier uses a separately provisioned 32-byte service key. The trusted receiver registry also contains the enrolled credential for the shared protocol; session keys are derived subsequently during the handshake. Literal credentials, verifier keys, session keys, and authorization capabilities are omitted from the evidence, but public synthetic replay inputs can reconstruct the simulation credential. The control isolates runtime acquisition/reconstruction costs and source failures; it establishes neither extraction resistance nor categorical security superiority. A 32-bit pilot credential is not production-strength cryptographic security.

The sole population/device/enrollment identities are `w8-p000`, `w8-p000-d00`, and `w8-p000-d00-enroll-v1`. The simulator uses 128 ring oscillators, 64 adjacent-pair response bits, manufacturing standard deviation 1.0, and zero enrollment noise. Each condition contains trial indices 0–9; each `trial_id` binds one attempt per arm. All arms share enrollment, credential basis, verifier material, protocol, and a stationary 120-sample sequence-zero window. Each receives fresh authorization, sender, verifier, session, and recording-consumer state.

| Condition | Sigma | Rho | Uniform common offset C | Noise interpretation | Matched cells | Attempts S/M/Stored |
|---|---:|---:|---|---|---:|---|
| `independent_nominal` | 0.10 | 0.00 | 0 | Independent | 10 | 10/10/10 |
| `independent_stress` | 0.25 | 0.00 | 0 | Independent, greater magnitude | 10 | 10/10/10 |
| `common_control` | 0.10 | 0.00 | −1 or +1; observed 4/6 cells | Uniform common-mode plus independent noise | 10 | 10/10/10 |
| `differential_rho50` | 0.10 | 0.50 | 0 | Differential correlated | 10 | 10/10/10 |
| `differential_rho90` | 0.10 | 0.90 | 0 | Differential correlated | 10 | 10/10/10 |
| **Total** | — | — | — | — | **50** | **50/50/50 = 150** |

The [frozen noise model][noise-source] combines oscillator-specific shared disturbance `sigma*sqrt(rho)*Z` with independent per-reading disturbance `sigma*sqrt(1-rho)*E`. Stochastic marginal magnitude is preserved across rho at sigma=0.10; stress instead uses sigma=0.25. Single-Read and Majority-3 separately measure the same indexed first reading; Majority-3 makes two additional measurements. Common aliases nominal's noise identity at the same trial index, and their preserved response observations agree. It is not independent replication. Stored repetitions are noise-independent workload controls.

A uniform common-mode offset cancels in a pairwise frequency comparison: `(f_i+C)−(f_j+C)=f_i−f_j`. Differential oscillator disturbances can change that difference and therefore response ordering. Here `rho` is the modeled fraction of stochastic oscillator-noise variance shared across readings, not a directly measured binary response-error correlation coefficient. The frozen simulator rejects any common-offset-induced ordering change caused by floating-point rounding rather than treating it as a physical effect.

Six arm permutations cycle with condition/device offsets, then trial blocks are deterministically shuffled. Master/schedule seeds are 2026101901/2026101902; measurement randomness is indexed independently of policy. Handshake entropy remains OS-random and unmatched. No retries occurred.

## Reconstruction Reliability
The [attempt records][attempts] preserve **C**: correct credential; **D**: decoder-declared failure; **I**: invalid format/padding; and **W**: wrong valid-format credential. These partition completed PUF reconstructions. Success is C/n; reconstruction false-rejection rate (FRR) is (D+I+W)/n. W is a reconstruction failure despite passing format validation. Condition labels below abbreviate the exact names in Section 2.

| Condition | Arm | Attempts | C | D | I | W | Success | Reconstruction FRR |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Nominal | Single-Read | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| Nominal | Majority-3 | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| Stress | Single-Read | 10 | 1 | 6 | 2 | 1 | 10% | 90% |
| Stress | Majority-3 | 10 | 5 | 5 | 0 | 0 | 50% | 50% |
| Common | Single-Read | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| Common | Majority-3 | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| Rho 0.50 | Single-Read | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| Rho 0.50 | Majority-3 | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| Rho 0.90 | Single-Read | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| Rho 0.90 | Majority-3 | 10 | 10 | 0 | 0 | 0 | 100% | 0% |
| **All conditions** | **Single-Read** | **50** | **41** | **6** | **2** | **1** | **82%** | **18%** |
| **All conditions** | **Majority-3** | **50** | **45** | **5** | **0** | **0** | **90%** | **10%** |

Every condition-arm row sums to exactly 10. All observed PUF reconstruction failures occurred in independent stress. Single-Read performed 50 readings and 50 runtime decodes; Majority-3 performed 150 readings and 50 decodes. Stored retrieval succeeded 10/10 per condition, 50/50 overall, with no unavailable or malformed result. Stored reconstruction and decode durations are inapplicable/null, not BCH successes or measured zero-cost reconstructions.

## Independent Verification and Admission Accounting
Reconstruction, credential verification, local admission, session activation, window acceptance, and recording release are successive stages, not interchangeable success definitions.

| Stage or outcome | Single-Read | Majority-3 | Stored |
|---|---:|---:|---:|
| Total attempts | 50 | 50 | 50 |
| Independent verifier not reached | 8 | 5 | 0 |
| Independent verifier reached | 42 | 45 | 50 |
| Credential verification passed | 41 | 45 | 50 |
| Explicit verifier refusals | 1 | 0 | 0 |
| Authorized admissions | 41 | 45 | 50 |
| Explicit admission-service refusals | 1 | 0 | 0 |
| Established sessions | 41 | 45 | 50 |
| Failed establishment attempts | 9 | 5 | 0 |
| Accepted windows | 41 | 45 | 50 |
| Authorized recording releases | 41 | 45 | 50 |

**Condition-level authentication-stage accounting.** Each row contains 10 completed attempts from the [original records][attempts]. V calls/refusals count actual independent-verifier invocations/explicit refusals; completed admissions are authorized local admissions. Release entries/completions and callback invocations/completions are recorded separately. Callback counts apply to each of preprocessing, motion, and anomaly, not their sum.

| Condition | Arm | Attempts | V calls | V refusals | Completed admissions | Sessions | Accepted windows | Authorized release entries/completions | Callbacks invocations/completions, each type | Unauthorized-release violations |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|
| Nominal | Single-Read | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Nominal | Majority-3 | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Nominal | Stored | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Stress | Single-Read | 10 | 2 | 1 | 1 | 1 | 1 | 1/1 | 1/1 | 0 |
| Stress | Majority-3 | 10 | 5 | 0 | 5 | 5 | 5 | 5/5 | 5/5 | 0 |
| Stress | Stored | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Common | Single-Read | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Common | Majority-3 | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Common | Stored | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Rho 0.50 | Single-Read | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Rho 0.50 | Majority-3 | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Rho 0.50 | Stored | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Rho 0.90 | Single-Read | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Rho 0.90 | Majority-3 | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| Rho 0.90 | Stored | 10 | 10 | 0 | 10 | 10 | 10 | 10/10 | 10/10 | 0 |
| **All arms/conditions** | — | **150** | **137** | **1** | **136** | **136** | **136** | **136/136** | **136/136** | **0** |

An adversarial unauthorized-release attempt denominator was **not measured in any condition-arm cell**. The recorded zero violations do not supply that denominator or an adversarial rejection rate. These condition-level counts reconcile to the aggregate stage and release tables; callbacks remain recording functions.

Eight Single-Read attempts (six D, two I) and five Majority-3 attempts (five D) stopped during reconstruction. They have no verifier call and must not be counted as explicit verifier refusals. Their establishment reason is `failed_reconstruction`. Under the methodology's all-attempt definition, admission/session failure rates are 9/50, 5/50, and 0/50; those include upstream source failures. No authorized admission failed later establishment, and no policy refusal was recorded.

The sole W candidate is [attempts.jsonl line 110][wrong-attempt], execution index 109: Single-Read, independent stress, trial index 8, trial ID `29a4434ed5cbec339cc0e96ea79e1d9263466c9e7e6440a4332627c24f2b236b`. The decoder reported `decoded` with valid candidate format, but actual independent verification returned `credential_mismatch`; admission was `refused`. Establishment returned `credential_verification_failed`, with no emitted request, zero sender/receiver HKDF calls, inactive endpoints, no accepted window, and no consumer release.

These outcomes are directly recorded. The [frozen sender control flow][session-source] and [pipeline establishment path][pipeline-source] explain the ordering: D/I stop before credential verification; refused admission stops before request emission and handshake. Runtime truth classification distinguishes C from W without granting authority. Consequently, decoder completion alone is not evidence of a correct or admitted credential.

## Matched Reliability Comparison
The comparison joins original records by `trial_id`, retaining the same condition/device/trial identity. Difference means Majority-3 session success minus Single-Read session success, in percentage points (pp).

| Condition | Pairs | Both succeeded | Both failed | Only Single-Read | Only Majority-3 | Single-Read success | Majority-3 success | Difference |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Nominal | 10 | 10 | 0 | 0 | 0 | 10/10 (100%) | 10/10 (100%) | 0 pp |
| Stress | 10 | 1 | 5 | 0 | 4 | 1/10 (10%) | 5/10 (50%) | +40 pp |
| Common | 10 | 10 | 0 | 0 | 0 | 10/10 (100%) | 10/10 (100%) | 0 pp |
| Rho 0.50 | 10 | 10 | 0 | 0 | 0 | 10/10 (100%) | 10/10 (100%) | 0 pp |
| Rho 0.90 | 10 | 10 | 0 | 0 | 0 | 10/10 (100%) | 10/10 (100%) | 0 pp |
| **Aggregate** | **50** | **41** | **5** | **0** | **4** | **41/50 (82%)** | **45/50 (90%)** | **+8 pp** |

Every additional Majority-3 success occurred under independent stress, at indices 0, 3, 4, and 8. Both succeeded at index 9; both failed at 1, 2, 5, 6, and 7. The aggregate difference is four additional sessions in 50 matched cells. These are observed differences, not established population effects. One population/device does not supply independent device-population replication; the three readings and repeated controls cannot serve as replacement independent units. No formal significance test or confidence interval is claimed.

## Authentication and Release Boundary
| Recorded boundary | Single-Read | Majority-3 | Stored | Total |
|---|---:|---:|---:|---:|
| Established sessions | 41 | 45 | 50 | 136 |
| Submitted/accepted windows | 41/41 | 45/45 | 50/50 | 136/136 |
| Rejected submitted windows | 0 | 0 | 0 | 0 |
| Authorized release entries/completions | 41/41 | 45/45 | 50/50 | 136/136 |
| Callback invocations/completions, each type | 41/41 | 45/45 | 50/50 | 136/136 |
| Recorded `model_calls`, each type | 41 | 45 | 50 | 136 |
| Unauthorized-release violations | 0 | 0 | 0 | 0 |

Callback types are preprocessing, motion, and anomaly: 136 invocations and completions each, or 408 across the three types, within 136 composite releases. Motion/anomaly callbacks were recording functions, not trained-model inference. These counts validate neither SNN accuracy nor inference latency. The 14 failed establishments submitted no window and invoked no release.

All 136 release entries followed accepted authenticated windows; all completed. No dedicated adversarial unauthorized-release attempts or independently identified attack denominator are present. The violation counter is not an unauthorized-attempt counter.

Zero unauthorized-release violations were observed in the pilot's recorded paths. This experiment does not establish an adversarial unauthorized-release rejection rate.

## Stage-Level Processing Overhead
The [frozen instrumentation][runtime-source] records `perf_counter_ns` spans, converted here to milliseconds (ns/1,000,000). The [frozen quantile function][analysis-source] linearly interpolates sorted samples at `(n−1)*p` (type 7). The table reports per-attempt spans; authorization-exclusive subtracts its immediate verification child. Other listed spans are inclusive.

| Arm | Stage | n | Median ms | p95 ms | Maximum ms | Measurement boundary |
|---|---|---:|---:|---:|---:|---|
| Single-Read | PUF acquisition | 50 | 0.244150 | 0.278500 | 0.443300 | `acquire_response`, including reading/validation |
| Majority-3 | PUF acquisition | 50 | 0.693100 | 1.052205 | 1.331100 | `acquire_response`, including three readings/voting |
| Stored | Credential retrieval | 50 | 0.005550 | 0.007465 | 0.020000 | Provider `get_credential` |
| Majority-3 | Majority voting | 50 | 0.028450 | 0.043910 | 0.052500 | `majority_vote3`, inside acquisition |
| Single-Read | BCH decode | 50 | 1.166500 | 2.534285 | 3.333500 | `BCHCodec.decode` |
| Majority-3 | BCH decode | 50 | 1.105450 | 2.602940 | 2404.131900 | `BCHCodec.decode` |
| Single-Read | Reconstruction | 50 | 1.207350 | 2.583925 | 3.376000 | `reconstruct`, including BCH/format checks |
| Majority-3 | Reconstruction | 50 | 1.162200 | 2.658115 | 2404.179800 | `reconstruct`, including BCH/format checks |
| Single-Read | Independent verification | 42 | 0.036250 | 0.046135 | 0.061500 | Admission service `verify` |
| Majority-3 | Independent verification | 45 | 0.035500 | 0.045560 | 0.056500 | Admission service `verify` |
| Stored | Independent verification | 50 | 0.024250 | 0.031620 | 0.038000 | Admission service `verify` |
| Single-Read | Local authorization, inclusive | 42 | 0.050750 | 0.065160 | 0.083200 | `authorize_with_outcome`, includes verification |
| Majority-3 | Local authorization, inclusive | 45 | 0.049300 | 0.062060 | 0.082300 | Same boundary |
| Stored | Local authorization, inclusive | 50 | 0.034650 | 0.043310 | 0.052600 | Same boundary |
| Single-Read | Local authorization, exclusive | 42 | 0.014200 | 0.021670 | 0.034400 | Authorization minus verification child |
| Majority-3 | Local authorization, exclusive | 45 | 0.013700 | 0.017160 | 0.025800 | Same subtraction |
| Stored | Local authorization, exclusive | 50 | 0.010250 | 0.012340 | 0.014600 | Same subtraction |
| Single-Read | Establishment, all attempts | 50 | 1.969400 | 3.503625 | 3.963000 | Entire `establish` invocation |
| Majority-3 | Establishment, all attempts | 50 | 2.384850 | 4.317310 | 2405.540100 | Entire `establish` invocation |
| Stored | Establishment, all attempts | 50 | 0.391550 | 0.490005 | 0.924700 | Entire `establish_stored` invocation |
| Single-Read | Establishment, successful only | 41 | 2.000400 | 3.172800 | 3.963000 | Same total, conditional on active session |
| Majority-3 | Establishment, successful only | 45 | 2.536000 | 4.511360 | 2405.540100 | Same total, conditional on active session |
| Single-Read | First authenticated window | 41 | 8.457400 | 10.737700 | 11.689400 | Sealing, verification, and recording release |
| Majority-3 | First authenticated window | 45 | 8.426900 | 9.551980 | 11.069700 | Same directly measured window block |
| Stored | First authenticated window | 50 | 5.685150 | 8.170665 | 35.586500 | Same directly measured window block |

Stored's success-only establishment equals its all-attempt result. Acquisition/reconstruction include failed PUF attempts; Single-Read verification includes the rejected W candidate. Success-only establishment has a selected survivor denominator. Missing stages are null, never zero-cost observations: Stored has no acquisition/BCH/reconstruction, and Single-Read has no voting span. Overlapping spans and separate p95 values must not be added to estimate total latency.

Majority-3 performs three readings instead of one, but both PUF arms decode once. Its median acquisition is approximately 2.84 times Single-Read; stored retrieval is approximately 0.0056 ms. Reconstruction and authorization medians vary modestly between PUF arms without establishing intrinsic speed differences. All-attempt establishment medians are approximately 1.969, 2.385, and 0.392 ms respectively.

The first measured BCH decode, Majority-3/Common trial 1 at execution index 1, took **2404.1319 ms (2.4041319 s)**. Its establishment took **2405.5401 ms**. Retaining this observation yields Common/Majority-3 p95 values of 1323.537830 ms for reconstruction and 1325.147025 ms for establishment. Aggregate mean establishment is 50.793402 ms for Majority-3, versus 2.201366 ms for Single-Read and 0.412102 ms for Stored. Compilation/cache first-use effects are plausible explanations, not isolated or conclusively established causes. No outlier was removed or replaced.

The profile is a cold-process run with zero harness warmup, not a new process for every session. First-window timings concern each fresh session, not recurring-window throughput. Enrollment, provisioning, endpoint setup, shared-noise preparation, template construction, and model loading are excluded. Instrumentation adds overhead; prior process/package caches and OS variation remain possible influences. These workstation measurements separate setup from window processing and provide no complete real-inference latency estimate. The historical resource/schema-cache benchmark is a separate experiment and supplies no per-authentication measurement here.

## Evidence Reconciliation and Provenance
The authoritative bundle is `results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/`, abbreviated **B**. Historical semantics come from `B/source/`, rather than current HEAD.

| Provenance field | Value |
|---|---|
| Original run ID | `week8-three-arm-auth-v1-nonformal-20261020-001` |
| Executed source ID | `83001370f5a65f5d8c6cb55c38bd6f239a6c693a065182b22e1b24575e695153` |
| Canonical configuration digest | `f08c74bbc1e44e8a73dfc8038580df9c9a91acdf3fc6da1bce643f58472166ce` |
| Canonical trial-plan digest | `74a07b7b06edee5dd58b9ad594fe70d00859ea1c4bceeaec2fb6bac52821a016` |
| Original attempts | 150 completed; 50 matched cells |
| Integrity checks | All 95 manifest members and 87 source members match; completion-marker manifest hash matches |
| Numerical reconciliation | Exact agreement across 4,540 group-level summary leaf values |

The 4,540-value finding was reconfirmed by independent in-memory calculations against [summary.json][summary]: all fields of its 15 condition-arm groups, including counts, rates, callbacks, all-attempt/success-only establishment statistics, and inclusive/exclusive stage statistics. It does not mean 4,540 independent observations or a full historical replay. Manifest checks used [manifest.json][manifest], [source-manifest.json][source-manifest], and [NONFORMAL_VALIDATED.json][marker]; no evidence was regenerated. Quantiles followed the frozen implementation. [Metadata][metadata] records Windows 11, CPython 3.12.4, galois 0.4.11, and numba 0.67.0; CPU/load/cache characterization is incomplete.

The original execution included uncommitted implementation files. Its frozen source ID therefore identifies the executed snapshot more precisely than Git base commit `d4e27abe42b7ac8ccd59f5c024c9ab3ca351bc53` alone. The previously raised historical `pipeline_timing.py` provenance mismatch remains unresolved historical context. Presently available frozen bytes and manifest hashes agree, but that agreement does not establish why the earlier mismatch was reported, repair its provenance history, or prove it false. The underlying historical discrepancy record was not located among the consulted files.

The [original validation receipt][validation] reports 200 experimental PUF readings and 100 runtime BCH decodes separately from one validation pass: 200 replay measurements, 100 replay decodes, and one reference reading. Two successful finalization passes entail 400 replay measurements, 200 replay decodes, and two reference readings. These finalization totals follow from frozen control flow; replay adds no statistical samples. The [validation-accounting addendum](week8-evidence-validation.md) explains the historical receipt's one-pass scope. No replay was run for this report.

The current [methodology](week8-three-arm-auth-methodology.md) and [research log](research-logs/will.md#week-8-three-arm-authentication-pilot-and-resource-optimization) provide context, not replacements for frozen evidence. The bundle lacks archived test-execution receipts. `Week 8 Research Feedback.txt` was not found in the accessible locations searched and was not used as evidence.

## Scientific Interpretation and Limitations
**Reliability and cost.** The observed Majority-3 advantage is confined to independent stress in this pilot. Additional readings increased acquisition cost while preserving a single decode. Stored demonstrates the contribution of source acquisition/reconstruction under trusted-storage assumptions; it does not establish a hardware security ordering.

**Correlation.** At rho=0.50 and 0.90, sigma=0.10, both PUF arms succeeded 10/10. Single-Read also succeeded 10/10 at nominal noise, leaving no observed nominal reliability benefit whose attenuation could be measured. Shared differential disturbance may reduce voting's benefit, but quantifying that mechanism requires operation near a failure boundary and replication.

**Security boundary.** One observed wrong valid-format candidate was rejected before session-key derivation. This supports the tested failure path, not protection against arbitrary attackers. Zero violations among the recorded legitimate release paths provide no adversarial rejection-rate estimate.

**Generality and timing.** One simulated population/device, idealized enrollment, a 32-bit pilot credential, synthetic stationary motion, and recording callbacks bound the conclusions. Timing is descriptive of this instrumented workload/environment, including first-use effects and conditional survivors. Neither percentages nor latency should be generalized to physical Quest, FPGA, or ASIC PUF implementations, production key security, or trained-model performance.

## Remaining Work and Formal-Study Connection
The pilot motivates a controlled differential correlated-noise study with repeated simulated populations/devices and conditions near a reconstruction failure boundary. Prerequisites include population-aware uncertainty and paired estimands, controlled timing replication with explicit cold/warmed and recurring-window protocols, actual inference-call measurements, and explicit adversarial unauthorized-release testing with identified denominators. Full-study runtime, storage, and peak-memory feasibility, frozen source/configuration/environment records, test receipts, and researcher/faculty approval remain necessary. The historical provenance question also remains open. The proposed 90,000-attempt study is neither executed nor authorized by this retrospective report.

## Appendix A. Condition-Level Timing

Each timing cell is **n; median ms; p95 ms**, computed from [original attempt spans][attempts] and cross-checked against the corresponding [historical summary group][summary]. Condition names use the abbreviations in Section 3. All boundaries and the linear-interpolation quantile method follow Section 7 and the frozen instrumentation. Acquisition is inclusive `acquire_response` for PUF arms; Stored instead measures `get_credential`. Reconstruction includes BCH and format checks. Verification measures the actual `verify` call; local authorization is inclusive `authorize_with_outcome` and includes verification. Establishment is the directly measured total for **all attempts**, including failures; overlapping columns must not be added.

| Condition | Arm | Acquisition/retrieval: n; median; p95 | Reconstruction: n; median; p95 | Independent verification: n; median; p95 | Local authorization, inclusive: n; median; p95 | Total establishment: n; median; p95 |
|---|---|---|---|---|---|---|
| Nominal | Single-Read | 10; 0.238250; 0.370355 | 10; 1.277900; 2.844045 | 10; 0.035450; 0.054615 | 10; 0.050850; 0.079465 | 10; 2.055200; 3.896085 |
| Nominal | Majority-3 | 10; 0.698500; 1.082480 | 10; 1.868900; 2.776975 | 10; 0.034550; 0.047500 | 10; 0.047550; 0.069160 | 10; 3.117150; 4.534890 |
| Nominal | Stored | 10; 0.005600; 0.006685 | 0; N/A; N/A | 10; 0.025100; 0.031620 | 10; 0.035600; 0.043110 | 10; 0.392600; 0.495340 |
| Stress | Single-Read | 10; 0.245600; 0.254965 | 10; 1.039950; 2.681560 | 2; 0.036050; 0.039515 | 2; 0.048100; 0.054220 | 10; 1.632850; 3.080130 |
| Stress | Majority-3 | 10; 0.672450; 1.036005 | 10; 1.088950; 2.061600 | 5; 0.034900; 0.043800 | 5; 0.047600; 0.059780 | 10; 2.143850; 3.458780 |
| Stress | Stored | 10; 0.005350; 0.005800 | 0; N/A; N/A | 10; 0.024350; 0.030675 | 10; 0.034550; 0.042355 | 10; 0.390050; 0.449945 |
| Common | Single-Read | 10; 0.251150; 0.267730 | 10; 1.626350; 2.261760 | 10; 0.036150; 0.042560 | 10; 0.050400; 0.061420 | 10; 2.429150; 3.118320 |
| Common | Majority-3 | 10; 0.704500; 1.197900 | 10; 1.406200; 1323.537830 | 10; 0.038400; 0.045780 | 10; 0.053550; 0.062870 | 10; 2.688800; 1325.147025 |
| Common | Stored | 10; 0.006100; 0.007255 | 0; N/A; N/A | 10; 0.024700; 0.035390 | 10; 0.034900; 0.049630 | 10; 0.402150; 0.729310 |
| Rho 0.50 | Single-Read | 10; 0.244250; 0.265890 | 10; 1.385200; 1.998310 | 10; 0.037950; 0.045565 | 10; 0.052050; 0.062825 | 10; 2.269300; 2.792695 |
| Rho 0.50 | Majority-3 | 10; 0.693850; 0.731855 | 10; 1.877700; 2.180940 | 10; 0.037250; 0.040225 | 10; 0.051900; 0.055320 | 10; 3.100800; 3.413555 |
| Rho 0.50 | Stored | 10; 0.005400; 0.006980 | 0; N/A; N/A | 10; 0.024150; 0.026365 | 10; 0.034350; 0.036860 | 10; 0.381600; 0.412405 |
| Rho 0.90 | Single-Read | 10; 0.245550; 0.317995 | 10; 1.129700; 1.894775 | 10; 0.035750; 0.042280 | 10; 0.049650; 0.057020 | 10; 1.892350; 2.641240 |
| Rho 0.90 | Majority-3 | 10; 0.706800; 0.851380 | 10; 1.074650; 2.063760 | 10; 0.035200; 0.041560 | 10; 0.048650; 0.056285 | 10; 2.318350; 3.413000 |
| Rho 0.90 | Stored | 10; 0.005550; 0.014420 | 0; N/A; N/A | 10; 0.023950; 0.028900 | 10; 0.034450; 0.039800 | 10; 0.392700; 0.417690 |

Stored reconstruction has n=0 and inapplicable durations, not zero processing cost. Verification/authorization timings are conditional on reaching those stages: Stress/Single-Read includes one accepted and one refused candidate (n=2); Stress/Majority-3 includes five accepted candidates (n=5). Acquisition/reconstruction and all-attempt establishment retain upstream failures. Success-only establishment remains separately reported in Section 7; no recurring-window timing is implied.

The **2404.1319 ms first-use BCH decode** remains included in Common/Majority-3 reconstruction and its **2405.5401 ms establishment**. With ten observations and the frozen interpolation rule, the p95 interpolates between the two largest values, giving this maximum substantial weight. Consequently, condition-level reconstruction/establishment p95 values are **1323.537830/1325.147025 ms**, despite medians of **1.406200/2.688800 ms**. This is the same preserved first-use observation discussed in Section 7, not a separate trial or a cleaned timing estimate; compilation/cache attribution remains plausible rather than established.

[attempts]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/attempts.jsonl
[wrong-attempt]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/attempts.jsonl#L110
[summary]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/summary.json
[plan]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/trial-plan.json
[config]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/config.json
[enrollments]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/enrollments.json
[metadata]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/metadata.json
[manifest]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/manifest.json
[source-manifest]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source-manifest.json
[validation]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/validation.json
[marker]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/NONFORMAL_VALIDATED.json
[frozen-methodology]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/docs/week8-three-arm-auth-methodology.md
[stored-source]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/auth/stored_credential.py
[credential-verifier]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/auth/credential_verifier.py
[noise-source]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/experiments/correlated_noise_v1.py
[session-source]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/auth/session.py#L239
[pipeline-source]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/pipeline_v2.py#L202
[analysis-source]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/experiments/majority3_auth_analysis_v1.py#L13
[runtime-source]: ../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/experiments/three_arm_auth_runtime_v1.py
