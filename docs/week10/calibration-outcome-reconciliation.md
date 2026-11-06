# Calibration Outcome Reconciliation and Authentication Security Analysis

**Owner:** Will Wallace
**Week:** 10
**Date:** November 5, 2026
**Status:** Complete - Evidence Provenance Review Pending

This analysis reconciles reconstruction reliability with downstream authentication behavior in the completed Week 9 calibration. The evidence identifies run `week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318`, experiment `week9-shared-noise-calibration-v1`, and authorization `restart-f64a0c5bcd5f496b8189e4dbd13a871d`. Its completion marker records PASS and two finalization validation passes. The earlier interrupted 543-attempt run is a separate historical population and contributes no observations here. Numerical consistency is confirmed; present exact-byte provenance remains qualified as documented in Section 5.

## Calibration Experiment and Reconstruction Outcome Classification
How were the 3,840 authentication attempts classified, and what failure mechanisms account for the 471 unsuccessful reconstructions?

### Experimental structure
The calibration used 24 persistent simulated PUF devices in four groups of six. Each device underwent 20 matched trials at each measurement-noise standard deviation, σ ∈ {0.10, 0.15, 0.20, 0.25}. Conditions are recorded as `s010`, `s015`, `s020`, and `s025`; policies are `single-read-v1` and `majority-3-v1`. Thus,

\[
N_{\mathrm{pairs}}=4\times6\times4\times20=1{,}920,
\qquad N_{\mathrm{attempts}}=2N_{\mathrm{pairs}}=3{,}840.
\]

Each noise-policy cell contains 24 × 20 = 480 attempts. A matched trial shares device, condition, and trial index across policies but contributes two authentication attempts. Single-Read uses one response; Majority-3 votes bitwise over three readings before one reconstruction. The policies share the indexed reading-zero realization, so matched observations are not independent policy samples. Device characteristics and enrollment persist across trials. [E1][ledger] [E2][plan] [E10][context]

This is an independent-read software calibration: ρ=0, common offset zero, manufacturing standard deviation one, and noiseless enrollment. σ denotes abstract additive oscillator-frequency units, not a measured physical-device error probability. The frozen specification reserves correlation contrasts for a separate evaluation; this dataset does not measure correlated-noise attenuation. [E2][config] [E10][spec]

### Classification rules and mechanisms
Reconstruction applies BCH(63,36,t=5) to the first 63 of 64 response bits using public code-offset helper data. The 36-bit message contains a 32-bit credential and four zero padding bits. Raw response disagreement, decoder status, padding validity, and enrolled-credential equality are distinct quantities. The frozen implementation assigns outcomes in this order:

1. **D — Decoder Failure:** `uncorrectable` yields `decoder_failure`, correction count −1, and no exposed candidate.
2. **I — Invalid Credential Format or Padding:** decoding returns a message whose final four bits violate the fixed padding; outcome is `invalid_format_or_padding`.
3. **C — Correct Credential:** a `candidate_valid_format` credential equals the enrolled credential.
4. **W — Valid-Format Incorrect Credential:** a valid-format candidate differs from enrollment.

The final C/W comparison is evaluator-only truth classification; it grants no protocol authority. Unexpected input/backend errors are exceptional cases rather than ordinary D outcomes. None occurred in the completed records. [E3][reconstruct] [E3][bch] [E3][runtime]

The correction radius does not make every reported decoding success correct beyond five enrolled-codeword errors. A nearby incorrect codeword may be returned, and its message may either fail padding or happen to satisfy it. Correct padding establishes structure, not credential equality. Preserved response/reference comparisons support the classifications: C records have 0–5 errors in positions 0–62, while W records have six or seven and report five corrections. Raw candidate messages are omitted, so this is a consistency check rather than a fresh decode or direct padding inspection.

### Complete numerical classification
The following counts were reconfirmed from all saved attempts and agree with the summary. [E1][ledger] [E8][summary]

| Noise σ | Acquisition policy | C | D | I | W | Attempts | Failures |
|---|---|---:|---:|---:|---:|---:|---:|
| 0.10 | Single-Read | 469 | 11 | 0 | 0 | 480 | 11 |
| 0.10 | Majority-3 | 476 | 4 | 0 | 0 | 480 | 4 |
| 0.15 | Single-Read | 431 | 48 | 1 | 0 | 480 | 49 |
| 0.15 | Majority-3 | 465 | 13 | 1 | 1 | 480 | 15 |
| 0.20 | Single-Read | 362 | 110 | 6 | 2 | 480 | 118 |
| 0.20 | Majority-3 | 446 | 34 | 0 | 0 | 480 | 34 |
| 0.25 | Single-Read | 305 | 173 | 1 | 1 | 480 | 175 |
| 0.25 | Majority-3 | 415 | 65 | 0 | 0 | 480 | 65 |
| **Total** | | **3,369** | **458** | **9** | **4** | **3,840** | **471** |

Every row satisfies C+D+I+W=N and D+I+W=failures. Globally,

\[
3{,}369+458+9+4=3{,}840,\qquad458+9+4=471,
\]

\[
\widehat{\mathrm{FRR}}_{\mathrm{reconstruction}}
=\frac{D+I+W}{N}=\frac{471}{3{,}840}=12.265625\%.
\]

| Failure mechanism | Count | Percentage of 471 failures | Percentage of 3,840 attempts |
|---|---:|---:|---:|
| Decoder failure | 458 | 97.240% | 11.927% |
| Invalid format/padding | 9 | 1.911% | 0.234% |
| Valid-format incorrect credential | 4 | 0.849% | 0.104% |

Decoder-declared failure dominates the observed composition; only 13 unsuccessful attempts returned decoded messages. Increasing σ increases total failures for each policy, although sparse I/W counts are not monotonic. Majority-3 records 118/1,920 failures versus Single-Read's 353/1,920: 226 fewer D, seven fewer I, and two fewer W outcomes. These aggregate comparisons describe the equally allocated sweep, not a deployment noise distribution or a renewed operating-point selection.

**Reconstruction finding:** all 471 failures are classified without overlap; the four structurally valid incorrect candidates require a downstream correctness boundary beyond BCH and padding.

## Authentication-Stage Progression and Outcome Accounting
How did the four reconstruction categories progress through credential verification, session admission, session establishment, and authenticated sensor-window release?

### Architecture and trust boundaries
The implemented sequence is **PUF acquisition → BCH reconstruction → independent credential verification → admission authorization → session establishment and mutual confirmation → authenticated-window verification → authorized release**. Reconstruction proposes a credential; it does not authenticate identity. D/I terminate in `Sender.begin_attempt` before the credential admission service is called. [E5][pipeline] [E5][session]

The independent verifier checks candidate and enrollment bindings, record support/enabled status, and an HMAC-SHA-256 comparison tag calculated with a separate verifier key. A passing comparison permits an opaque local authorization handle. The service's live table binds that handle to the verified candidate, attempt, request, and challenge transcript; a caller-created lookalike has no authority. Authorization is an intermediate permission, not session activation. [E4][credential]

The receiver consumes authorization before HKDF-based key derivation. The sender must claim the unchanged bound candidate before its derivation. HKDF uses the credential, server nonce, and transcript context; it does not increase the credential's entropy. Client and server HMAC confirmation proofs, protocol checks, and deadlines precede activation. The pipeline additionally checks coherent sender/receiver activation. [E5][session] [E5][pipeline]

An active sender constructs a protected window. The stateful receiver checks encoding, device/session status, expiry and limits, session-key HMAC, identity/key binding, quality, and sequence order. Acceptance commits state and creates the verifier-bound result eligible for release. This per-window integrity check differs from the earlier enrollment-credential comparison. The release gate requires the exact committed result and records an event as consumed before preprocessing; callback failure does not restore delivery eligibility. [E6][sender] [E6][verifier] [E6][gate]

### Complete stage-transition matrix
| Reconstruction category | Attempts | Verifier accepted | Verifier rejected | Verifier not reached | Admission authorized | Active sessions | Completed releases |
|---|---:|---:|---:|---:|---:|---:|---:|
| C | 3,369 | 3,369 | 0 | 0 | 3,369 | 3,369 | 3,369 |
| D | 458 | 0 | 0 | 458 | 0 | 0 | 0 |
| I | 9 | 0 | 0 | 9 | 0 | 0 | 0 |
| W | 4 | 0 | 4 | 0 | 0 | 0 | 0 |
| **Total** | **3,840** | **3,369** | **4** | **467** | **3,369** | **3,369** | **3,369** |

Acceptance means `verification_outcomes=["verified"]`; explicit rejection means `["credential_mismatch"]`. Not reached requires an empty list and zero verification calls. Admission authorization requires `[true]` in `authorization_outcomes` and `["authorized"]` in `admission_outcomes`. The four W attempts instead record `[false]` and `["refused"]`; 467 D/I attempts never reach authorization. Active sessions require `establishment.session_active=true` and both endpoint-active flags. Completed release additionally requires its completion counter and callback evidence, rather than window acceptance alone. [E1][ledger] [E7][runtime]

### Downstream execution and instrumentation
| Separately measured stage | Recorded count |
|---|---:|
| Outer `establishment` / `admission_request` method entries | 3,840 / 3,840 |
| Independent verification / authorization-service calls | 3,373 / 3,373 |
| Session requests emitted | 3,369 |
| Receiver / sender HKDF invocations | 3,369 / 3,369 |
| Completed four-step mutual handshakes | 3,369 |
| Active sessions | 3,369 |
| Window-sealing / verification calls | 3,369 / 3,369 |
| Accepted authenticated sequence-zero windows | 3,369 |
| Recorded authorized releases | 3,369 |
| Release entries / completions | 3,369 / 3,369 |
| Each recording callback's invocations / completions | 3,369 / 3,369 |

All C attempts completed these stages; no post-verification attrition occurred. All 471 unsuccessful attempts recorded zero HKDF, handshake, window, and release operations. There were no window rejections, callback exceptions, infrastructure faults, or instrumented exception spans. The four-step handshake records acceptance at receiver challenge, sender confirmation, receiver confirmation, and sender activation. [E1][ledger] [E7][capture]

The outer `admission_request` counter wraps `Sender.begin_attempt`, which also handles reconstruction refusals. Its 3,840 entries therefore cannot be interpreted as 3,840 emitted requests or authorizations. `establishment.request_emitted` supplies the narrower request count. Similarly, runtime `authorized_release_count` is derived from window acceptance, while `release_count` counts records appended during consumer preparation. Actual completion is separately corroborated by `release_completions` and `callbacks.{preprocessing,motion,anomaly}.{invocations,completions}`. [E7][runtime] [E7][capture]

The supplied consumer records identifiers and returns `recording-consumer-v1`; its motion/anomaly callbacks are probes. Consequently, these are completed authenticated recording deliveries, not demonstrated trained SNN classification or model-accuracy outcomes. [E7][consumer]

## Independent Verification of Four Incorrect Credentials
What happened to the four valid-format incorrect credentials, and did independent verification prevent unauthorized session establishment and release?

### Significance and individual inventory
A decoded BCH candidate can satisfy padding while differing from enrollment. Neither decoder success nor correct padding establishes authenticated identity. The evaluator detects equality/mismatch using enrollment truth, whereas the independent verifier recomputes an enrollment-comparison HMAC over identifiers and the candidate, then uses `hmac.compare_digest`. It does not authorize based on the evaluator's W label. This separation makes explicit mismatch refusal a meaningful execution observation. [E3][runtime] [E4][credential]

Each supplied identifier was located directly in the ledger. Lines are one-based; trial and execution indices are zero-based. [E1][ledger]

| Event | Device / population | Noise σ | Policy | Trial index | Execution index | Ledger line |
|---|---|---:|---|---:|---:|---:|
| W1 | `w9c-p000-d04` / `w9c-p000` | 0.20 | Single-Read | 10 | 326 | [327][w1] |
| W2 | `w9c-p003-d05` / `w9c-p003` | 0.25 | Single-Read | 0 | 791 | [792][w2] |
| W3 | `w9c-p003-d03` / `w9c-p003` | 0.15 | Majority-3 | 2 | 2,436 | [2,437][w3] |
| W4 | `w9c-p003-d04` / `w9c-p003` | 0.20 | Single-Read | 0 | 2,765 | [2,766][w4] |

- **W1 policy-attempt ID:** `cc35e7844093e9379a7392fbc4a62592e0ec94b1f8196cff8c2e85017c838dc1`  
  **Matched trial ID:** `f3638601f3d72bc5f252c5ad85d54fde77542445a1cdb0227d1b9a28212fbf09`
- **W2 policy-attempt ID:** `c20a1cbcb867cbd7bb15faae7bb181a242bc9b72634144de1f220fd101f4ec65`  
  **Matched trial ID:** `95b87e05d0452287217b75d94b7ac68466055ff3e3b7fe5bc2e152aa636e80ee`
- **W3 policy-attempt ID:** `f1e86157bf0baca065f4249fece7bf0dfae593a1dc8c60bd1ea8388ecdcd3153`  
  **Matched trial ID:** `967d655bfafe101b1b6c6d75cb83409a43e998ec1d95938b1f50e6f4be378e8b`
- **W4 policy-attempt ID:** `46ef3376b7de9c785cdc02bde7857fe49564e6ca4f88ecffe966cfdce2501d05`  
  **Matched trial ID:** `fa03606652a3406c94ee1bbdb5c4764dd874c2308df183a2573f9a6bfa63aed3`

### Verified rejection progression
All four reconstruction objects record `classification="W"`, `outcome="candidate_valid_format"`, `decoder_status="decoded"`, and `corrections=5`. Saved first-63 error counts are respectively 7, 6, 7, and 6. A five-correction candidate cannot be the enrolled codeword at those distances under the frozen decoder invariant; the W truth label and independent mismatch result agree. No raw credentials or keys are needed for this inventory.

| Recorded field or stage | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| `verification_outcomes` | `credential_mismatch` | `credential_mismatch` | `credential_mismatch` | `credential_mismatch` |
| `authorization_outcomes` / `admission_outcomes` | false / refused | false / refused | false / refused | false / refused |
| Session request emitted | No | No | No | No |
| Receiver / sender HKDF calls | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Active session | No | No | No | No |
| Accepted windows | 0 | 0 | 0 | 0 |
| Authorized / unauthorized releases | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Recording callbacks invoked | 0 | 0 | 0 | 0 |

The first two table rows abbreviate single-element lists. Every event also records `authorization_diagnostics=["credential_mismatch"]`, empty handshake/window-verification lists, and establishment rejection at `credential_admission` with reason `credential_verification_failed`. The instrumented handle-present Boolean is false, so no admission capability was issued. [E7][capture]

These four observations support the tested verifier boundary: incorrect but well-formed candidates were explicitly refused before session establishment. The 467 D/I cases instead record no verifier decision. Reconstruction unreliability therefore caused legitimate access failure without observed unauthorized progression. Four correct refusals do not establish resistance to arbitrary adversarial credentials, physical-PUF attacks, or production-strength impersonation.

## Numerical Reconciliation and Security Invariant Evaluation
Can every attempt be accounted for exactly once, and what authentication security properties are supported by the recorded execution?

### Terminal and stage-specific partitions

| Mutually exclusive terminal outcome | Attempts |
|---|---:|
| Successful authenticated release and recording delivery | 3,369 |
| BCH decoder failure | 458 |
| Invalid credential format or padding | 9 |
| Incorrect credential rejected by verifier | 4 |
| **Total** | **3,840** |

Thus 3,840=3,369+458+9+4 and 471=458+9+4. The four verifier rejections are already W failures within 471; adding them again would count the same attempts twice. Multiple earlier stage observations belong to one original `policy_attempt_id`.

Verification partitions as 3,369 accepted + four rejected + 467 not reached. Admission partitions as 3,369 authorized + four refused + 467 not reached. There are 3,369 active sessions and 471 attempts without activation; all active sessions produce one accepted window and completed recording delivery. Accordingly, 3,369 deliveries + 471 attempts without release recover the original population. [E1][ledger] [E8][summary]

The relevant rates have different denominators,
\[
\begin{aligned}
\text{Reconstruction FRR}&=471/3{,}840=12.265625\%,\\
\text{Verifier refusal among reached candidates}&=4/3{,}373\approx0.118589\%,\\
\text{Verifier refusal per original attempt}&=4/3{,}840\approx0.104167\%.
\end{aligned}
\]

The saved `admission_failure_rate` equals `(attempts-authorized_admissions)/attempts`. It includes non-arrivals at admission, so its 471-failure aggregate interpretation does not imply 471 explicit refusals. Similarly, equality of reconstruction and session failure rates here reflects the observed absence of downstream attrition, not equivalence of their definitions. [E8][aggregate]

### Security invariant evaluation
| Property and expected behavior | Evidence fields inspected | Observed result and assessment | Limitation |
|---|---|---|---|
| Reconstruction failure isolation: D/I must not verify, admit, or release | `verification_outcomes`, `admission_outcomes`, operation/release counters | All 467 terminate at reconstruction; zero downstream successes. Supported. | Saved execution observations only. |
| Independent W rejection: wrong candidates must be explicitly refused | Verification calls/outcomes and authorization diagnostics | All four reached verification and returned `credential_mismatch`. Supported. | Four observed candidates, not an attack population. |
| No unauthorized admission | `authorization_outcomes`, `admission_outcomes` | Zero of 471 unsuccessful attempts authorized; four refused, 467 not reached. Supported. | Capability objects/table state are omitted. |
| Key/session gating | HKDF/handshake counts, `establishment`, `endpoint_state` | Zero of 471 unsuccessful attempts recorded HKDF or activation. Supported. | Internal capability consumption is source-supported, not separately logged. |
| Authorized release enforcement | Window authentication/acceptance, active flags, release and callback counters | Zero releases without recorded active/accepted state; zero per-attempt duplicates or unauthorized releases. Supported. | No independent global event/payload-identity audit. |
| Successful-path completion | Accepted verification through callback-completion fields | All 3,369 C attempts complete every stage; zero unexplained attrition. Supported. | Recording callbacks are not trained inference. |

### Scope of the security finding
Zero unauthorized releases means zero among 3,840 original attempts, including all 471 failures; 3,369 protected windows were actually tested. Failed attempts were not supplied adversarial windows. Existing replay, forged-tag, sequence, and cross-session defenses are implementation properties, not evidence those attacks were exercised here. HKDF invocation counts do not expose key values or independently prove key equality. The 32-bit pilot credential has limited entropy, which HKDF cannot remedy.

**Bounded finding:** the saved simulated execution supports isolation of the observed reconstruction failures and completion of the correct-credential path. It supplies neither a general cryptographic security proof nor physical-device or comprehensive adversarial validation.

## Evidence, Reproducibility, and Outstanding Limitations
Paths below are relative to the repository root. Define **B** as `results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318`, **R** as `results/week-9/will/calibration-restart-v1/restart-20261028-01`, and **S** as `B/source/src/python/puf_snn`.

| Evidence | Authoritative files and locations | Claims supported |
|---|---|---|
| E1 | [B/attempts.jsonl][ledger]; W lines 327, 792, 2437, 2766 | Individual identities, classifications, stage decisions, instrumentation, callbacks. |
| E2 | [B/trial-plan.json][plan], [config.json][config], [metadata.json][metadata], [enrollments.json][enrollments] | Schedule/denominators, run identity, ρ=0 design, preserved reference responses. |
| E3 | [S/reconstruction/credential.py][reconstruct] lines 117–162; [bch.py][bch] lines 130–149; [calibration runtime][runtime] lines 68–74 | Decode/padding decisions, decoder invariants, evaluator C/D/I/W order. |
| E4 | [S/auth/credential_verifier.py][credential] lines 290–380, 397–430 | Independent comparison; local issuance and binding/consumption rules. |
| E5 | [S/pipeline_v2.py][pipeline] lines 145–174, 201–239; [S/auth/session.py][session] lines 239–277, 356–445, 548–629 | Early termination, request/HKDF prerequisites, mutual confirmation and activation. |
| E6 | [S/auth/sender.py][sender] lines 238–296; [verifier.py][verifier] lines 170–295, 364–389; [binary_window.py][binary]; [S/integration.py][gate] lines 163–199 | Window construction/authentication, state checks, committed-result release and at-most-once gate. |
| E7 | [Three-arm instrumentation][capture] lines 40–95; [base capture and recording consumer][consumer] lines 71–110, 153–178; [calibration runtime][runtime] lines 77–110 | Counter meanings, handle-present diagnostics, callback completions and recording-only execution. |
| E8 | [B/summary.json][summary], [selection.json][selection]; [R/analysis.json][analysis], [device-results.csv][devices]; [summary implementation][aggregate] lines 357–372 | Aggregate numerical agreement and failure-rate definitions. |
| E9 | [B/CALIBRATION_VALIDATED.json][marker], [validation.json][validation]; [R/standalone-audit.json][audit], [final-verification.json][final], [postcompletion receipt][post] | Historical completion/audit status; count reconciliation and zero reported unauthorized releases. |
| E10 | [Current Week 9 report][report]; [frozen study specification][spec]; [existing Week 10 analysis][context] | Methodological context and complementary operating-point analysis. |
| E11 | [B/manifest.json][manifest], [source-manifest.json][source-manifest] | Recorded byte identities and present integrity qualifications. |

The requested shorter context path, `docs/week10/shared-noise-calibration-analysis.md`, is absent; the existing document is `docs/week10/week10-shared-noise-calibration-analysis.md`. It was consulted without alteration. The ledger and frozen implementation take precedence over contextual reports.

Reconciliation uses read-only JSON parsing and in-memory counts keyed by attempt identity and condition/policy. The preceding investigations checked schedule positions, unique identities, complete pairs, saved response distances, and stage spans. Final synthesis reconfirmed all classifications, downstream patterns, eight summary cells, and four W identities. Summaries agree with ledger counts; historical receipts report successful validation. No simulation, decode, protocol session, or cryptographic recomputation was performed for this document. This is evidence reconciliation, not independent experimental reproduction.

### Historical integrity qualification
Present hashing finds 76 exact raw-byte matches among 126 bundle-manifest entries, 49 matching only after in-memory CRLF-to-LF conversion, and one unresolved mismatch: `S/pipeline_timing.py`. The 116-entry source manifest gives 76 raw matches, 39 LF-only matches, and the same unresolved file. Uniform LF/CRLF conversion does not recover that file's recorded digest. The manifest and completion marker themselves reproduce historical hashes only after in-memory newline conversion. [E11][manifest] [E9][final]

Historical PASS receipts establish what was recorded at completion; they do not establish a new passing exact-byte audit of this checkout. Parsed numerical agreement remains valid as a separate finding. No file was repaired, normalized on disk, repinned, or resealed. The mismatch's original byte identity remains unresolved.

### Evidence visibility
Direct observations comprise persisted decisions, instrumented calls, endpoint flags, and callback counts. Control-flow inspection supports the meaning of those observations, including capability consumption and cryptographic checks. The ledger omits raw candidate credentials/messages, keys, capability objects, full protected envelopes, and complete session/event identities. Consequently, padding bits, cryptographic tags, capability-table contents, and global cross-event identity cannot be independently reconstructed and verified from those fields alone. Derived authorization/release diagnostics are not independent sensors. These limits qualify security inference without changing the complete parsed-record accounting.

## 6. Research Conclusions
The basic reconciliation questions are resolved numerically, 471 unsuccessful reconstructions comprised of 458 decoder failures, nine padding failures, and four valid-format incorrect credentials. Decoder-declared failure accounts for 97.24% of failures; the remaining decoded messages show why decoder success and structural validity cannot substitute for enrollment correctness.

All 467 D/I attempts stopped before independent verification. All four W candidates reached that boundary and were explicitly refused before authorization, request emission, HKDF, or active-session establishment. None of the 471 unsuccessful attempts recorded protected-window release. Conversely, all 3,369 correct reconstructions completed verification, admission, mutual confirmation, accepted sequence-zero window verification, and recording delivery. Every original attempt belongs to exactly one terminal category.

The calibration therefore supports correct enforcement of the tested authentication boundary while distinguishing reliability loss from unauthorized access. It does not demonstrate universal attack resistance, production credential strength, physical-PUF security, or trained SNN inference. Exact-byte provenance review remains pending. This outcome accounting complements the earlier Week 10 operating-point justification by explaining the mechanisms and downstream consequences behind reconstruction FRR; it neither repeats selection nor represents completion of the future correlated-noise evaluation.

[ledger]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/attempts.jsonl
[w1]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/attempts.jsonl#L327
[w2]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/attempts.jsonl#L792
[w3]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/attempts.jsonl#L2437
[w4]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/attempts.jsonl#L2766
[plan]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/trial-plan.json
[config]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/config.json
[metadata]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/metadata.json
[enrollments]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/enrollments.json
[reconstruct]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/reconstruction/credential.py
[bch]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/reconstruction/bch.py
[runtime]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/experiments/shared_noise_calibration_runtime_v1.py
[credential]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/auth/credential_verifier.py
[pipeline]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/pipeline_v2.py
[session]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/auth/session.py
[sender]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/auth/sender.py
[verifier]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/auth/verifier.py
[binary]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/auth/binary_window.py
[gate]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/integration.py
[capture]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/experiments/three_arm_auth_runtime_v1.py
[consumer]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/experiments/majority3_auth_runtime_v1.py
[summary]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/summary.json
[selection]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/selection.json
[analysis]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/analysis.json
[devices]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/device-results.csv
[aggregate]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/experiments/three_arm_auth_evidence_v1.py
[marker]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/CALIBRATION_VALIDATED.json
[validation]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/validation.json
[audit]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/standalone-audit.json
[final]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/final-verification.json
[post]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/postcompletion-analysis-receipt.json
[report]: ../week9-shared-noise-calibration-results.md
[spec]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/docs/week9-shared-noise-study-specification.md
[context]: week10-shared-noise-calibration-analysis.md
[manifest]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/manifest.json
[source-manifest]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source-manifest.json