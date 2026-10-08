# Tier 1 v2 Experiment

**Owner:** Will Wallace  
**Week:** 6  
**Status:** Complete — formal evidence independently verified
**Experiment ID:** authentication-v2-tier1-security-evaluation  
**Version:** 1  
**Formal Run:** tier1-v2-formal-001

## Research Objective

The objective of this experiment is to evaluate the security and reliability of our current Authentication-v2 implementation against Tier-1 attacks targeting device authentication, message integrity, session freshness, sequence ordering, and authenticated SNN inference.
Our PUF + SNN architecture uses PUF-derived credential reconstruction and independent verification to establish device-bound authenticated sessions. Once a session is established, sensor windows must satisfy integrity, identity, freshness, and ordering checks before being released to the frozen SNN inference pipeline.
The previous Tier-1 evaluation tested an earlier Wire2 authentication implementation. This experiment extends that work to the current credential-admission Authentication-v2 protocol with larger attack populations, more varied inputs, explicit protocol-state testing, parser-boundary testing, and real frozen inference callbacks.
The primary research questions are,
- Does Authentication-v2 reject replayed, substituted, and modified sensor windows before authenticated release?
- Do rejected packets preserve the receiver's session state, accepted-window count, and expected sequence number?
- Can legitimate communication continue correctly after rejected or out-of-order traffic?
- Does the inference gate prevent rejected packets from invoking preprocessing, SNN inference, or anomaly detection?
- What are the processing-latency distributions associated with legitimate and rejected traffic?

The experiment evaluates the behavior of a finite software implementation under a declared threat model. It is not intended to establish universal protocol security, physical PUF reliability, or robustness against every possible attacker.

## Authentication-v2 Architecture

### Device Credential Reconstruction and Verification

Authentication-v2 begins with device credential reconstruction and independent verification.
The current implementation uses a simulated ring-oscillator PUF containing 128 oscillators arranged into 64 disjoint pairs. The first 63 response bits are used by the existing BCH(63,36,t=5) reconstruction implementation to recover a 32-bit credential.
Each of the six simulated PUF devices has two separately provisioned enrollment generations, with distinct credentials, helper data, enrollment identifiers, and independent credential-verifier records.
For this Tier-1 experiment, each handshake performs,
1. One fresh simulated PUF response reading under noiseless reference conditions
2. One execution of the existing BCH credential-reconstruction implementation
3. Independent credential verification
4. Local credential admission before session-key derivation

The reconstruction result is not fabricated or replaced with the enrolled credential. Credential verification and local admission use the actual implementation.
The noiseless reading policy is intentionally controlled to isolate Authentication-v2 behavior from the separate reconstruction-reliability experiment.
These enrollment generations are experimental fixtures, not evidence of a deployed credential-rotation service.

### Authenticated Session Establishment

Authentication-v2 uses the current credential-admission Wire2 protocol profile:

`puf-snn-l3-credential-admission-v1-wire2`

The protocol uses handshake version 2.0 and authenticated-message version 2.0.
Session establishment includes device credential admission, exchanged nonces, independently derived cryptographic session material, and mutual confirmation.
Session keys are derived using the existing HKDF implementation. The sender and verifier establish matching session material without directly transmitting their derived session keys.
The protocol enforces session lifecycle and resource limits,
- Handshake timeout: 10,000 ms.
- Session time-to-live: 300,000 ms.
- Maximum authenticated windows per session: 10,000.
- Maximum pending sessions: 128.
- Maximum process-issued session identifiers: 10,000.

Each scenario uses fresh sender and verifier endpoints. Additional-device and replacement-session handshakes use the existing endpoint APIs rather than reconstructing the inference pipeline or modifying authenticated session state directly.

### Sensor-Window Integrity and Freshness

Authenticated sensor windows use the existing Wire2 binary representation and HMAC-SHA-256 integrity protection.
The protected data include the device/session context, sequence information, window identifiers, capture timestamps, tracking-quality information, and motion samples.
The current payload format uses binary32 big-endian motion data and payload version 1.0.
Before accepting a sensor window, the verifier performs the applicable representation, device/session lifecycle, authentication, identity-binding, quality, and ordering checks.
Accepted windows must satisfy strict exact-next sequence ordering.
The receiver distinguishes,
- Duplicate sequence numbers
- Stale sequence numbers
- Future sequence gaps
- Invalid authentication tags
- Expired or inactive sessions
- Invalid session or device bindings
- Malformed protocol representations

Rejected packets must not advance the accepted-window count, modify the last-accepted sequence, consume a valid expected sequence, or create authenticated inference authority.
A rejected valid future packet is not automatically buffered for later acceptance. Required missing packets must arrive before the exact original future packet can be submitted again through the planned recovery sequence.

### SNN Inference Gating

The authenticated inference boundary uses the existing `V2InferencePipeline` and `ExactlyOnceClassifierRelease` implementation.
Each accepted sensor window is released through the authenticated classification boundary.
The inference pipeline performs,
1. Accepted-window release
2. Motion/anomaly input preprocessing
3. Frozen SNN motion inference
4. Frozen anomaly-detector inference

Each successfully processed legitimate window is expected to invoke each boundary exactly once.
Rejected windows must produce zero invocations at all four boundaries.
The experiment instruments both the pipeline's existing public call counters and independent pass-through callback-entry counters.
This permits direct verification of whether rejected traffic reaches the inference pipeline rather than inferring successful isolation from a rejection label alone.

## Threat Model and Attack Classes

### Tier-1 Threat Model

The Tier-1 threat model focuses on protocol-level manipulation of public authenticated traffic and the receiver's handling of invalid or improperly sequenced messages.
The attacker can capture, replay, withhold, reorder, or modify transmitted message bytes.
The attacker can also submit malformed messages directly to the receiver's public parsing and verification interfaces.
The attacker does not possess,
- The enrolled device credential
- The independent credential-verifier key
- Derived session keys
- Private enrollment material
- PUF reference responses or helper-data internals
- Local credential-admission authorization handles

Attack mutation functions operate on public packet bytes and explicitly declared mutation parameters.
When a protected field is modified after a packet has been authenticated, the original HMAC tag is preserved rather than regenerated.
The experiment also evaluates legitimately signed future packets that have been withheld or reordered. These cases test receiver ordering and recovery behavior, not an attacker's ability to forge a valid HMAC.
Each primary attack is submitted once in its own planned scenario. All resulting authentication decisions, state changes, inference invocations, and recovery steps are recorded.

### Attack A1

**Attack:** Same-session exact replay.

**Planned attempts:** 1,200.

A previously authenticated and accepted sensor window is captured and submitted again within its original active session.
The replay preserves the exact original packet bytes, including its HMAC, device identity, session identity, sequence number, payload, and metadata.
The attack evaluates whether the verifier rejects an already-consumed sequence number.

**Expected rejection reason:** `duplicate_sequence`

**Expected behavior:**

- The original HMAC remains valid
- Session identity remains authenticated
- The packet is rejected because its sequence was already accepted
- The receiver's accepted-count and last-accepted sequence remain unchanged
- No inference callbacks are invoked
- A subsequently submitted valid exact-next packet is accepted

Sequence positions 0 through 4 are included in the planned population.

### Attack A2

**Attack:** Prior-session and expired-session replay.

**Planned attempts:** 1,200.

This attack replays previously valid packets after their original authenticated session has been replaced or expired.
The attack population contains three equally allocated scenarios:
1. **Session replacement — 400 attempts:** Replay a packet from a session that has been replaced by a newly confirmed same-device session.
2. **Expired active session — 400 attempts:** Replay traffic at or after the session deadline while the expired entry remains allocated.
3. **Expired session tombstone — 400 attempts:** Replay traffic after explicit session expiration and cleanup.

**Expected rejection reasons:**

- Replaced session: `inactive_session`.
- Expired session: `expired_session`.

These cases test session lifecycle enforcement before message authentication is reached.
The expiry scenarios use a narrowly scoped simulated monotonic-clock offset to evaluate deadline equality and deadline-plus-1-ms behavior without waiting for the full session TTL.
The experiment does not change cryptographic keys, session timeouts, or stored deadlines.
Recovery requires establishing or using the appropriate new authenticated session. An expired or replaced session is not revived.

### Attack A3

**Attack:** Cross-device identity substitution.

**Planned attempts:** 1,200.

A valid authenticated packet from device A is modified so that its protected device identity identifies a different known and provisioned device B.
The original session identifier, HMAC, and remaining protected data are preserved.
The experiment uses six devices, producing 30 ordered distinct device pairs with 40 attempts per pair.
Both devices have legitimate sessions in the same verifier.

**Expected rejection reason:** `invalid_tag`

Changing the protected device identity without recomputing the HMAC must invalidate authentication before the packet can be accepted.
The experiment also checks that neither device's session state is changed by the rejected packet.
Recovery submits the retained original valid packets for devices A and B, each of which is expected to be accepted once.

### Attack A4

**Attack:** Post-authentication motion-payload modification.

**Planned attempts:** 1,200.

The attacker modifies one bit of an authenticated binary32 motion sample after the original HMAC has been generated.
The experimental variations include,
- 600 position-data modifications
- 600 quaternion-component modifications
- Different sample positions
- Different motion components
- Different mantissa-bit positions

Only one scheduled mantissa bit is modified.
The original HMAC remains unchanged.
The mutation procedure maintains finite floating-point representations and uses a deterministic rule to avoid creating negative zero.

**Expected rejection reason:** `invalid_tag`

The attack evaluates whether even small modifications to protected motion data are rejected before reaching SNN inference.
The retained original packet is submitted afterward to verify that legitimate recovery remains possible.

### Attack A5

**Attack:** Post-authentication protected-metadata modification.

**Planned attempts:** 1,200.

The attacker changes one field inside the authenticated sensor-window representation while retaining the original HMAC.
Six metadata variations are evaluated, with 200 attempts each,
1. Sequence number
2. Window identifier
3. Capture-start timestamp
4. Capture-end timestamp
5. Tracking-valid sample count
6. Tracking-valid parts-per-million value

Only one protected field is changed per attack.

**Expected rejection reason:** `invalid_tag`

The experiment evaluates whether changes to authenticated metadata are detected before the receiver reaches sequence ordering or inference.
The original retained packet is subsequently submitted as the legitimate recovery window.

### Protocol State and Parser Negative Cases

In addition to the five primary attack groups, the experiment includes explicit protocol-state and parser-boundary populations.
**State-machine population:**

Eight state groups are evaluated,
- S1: Invalid-tag future sequence
- S2: Valid-tag future sequence gap
- S3: Invalid exact-next packet
- S4: Duplicate packet after a rejected modification
- S5: Stale packet followed by the valid next packet
- S6: Missing-packet recovery and exact retry of a previously rejected future packet
- S7: Malformed packet followed by a valid exact-next packet
- S8: Cross-session invalid packet followed by valid recovery traffic

Each group contains 120 scenarios.
Across all state groups, the experiment schedules 960 scenarios and 1,080 negative submissions, because S4 contains two negative operations per scenario.
State snapshots are captured before and after every negative submission to verify that rejected traffic does not incorrectly change receiver or sender state.

**Parser-boundary population:**

The experiment includes 28 parser-negative cases, each containing 60 scenarios.
The 1,680 designated negative submissions consist of,
- 24 window-envelope and binary-representation cases
- Four receiver-handshake framing and truncation cases

The parser cases include malformed JSON, duplicate keys, unknown fields, invalid base64, malformed tags, unsupported protocol versions, invalid binary lengths, invalid sample counts, invalid floating-point values, invalid tracking fields, and truncated handshake frames.

Expected first-failure reasons include:

- `malformed_message`
- `invalid_payload_schema`
- `unsupported_protocol_version`

The experiment records whether each malformed submission is rejected at its intended boundary and whether the original legitimate packet or handshake can continue afterward.

### Legitimate Authentication Controls

The experiment schedules 1,200 legitimate authenticated sensor-window submissions.
Each control is constructed through the real sender and verifier APIs.
A valid session is established, any required prefix packets are accepted, and the correctly authenticated exact-next window is submitted.
Expected control behavior includes,
- Authentication acceptance
- Valid device/session identity
- Correct sequence ordering
- Accepted-window count incremented once
- Exactly one authenticated release
- Exactly one preprocessing invocation
- Exactly one SNN motion callback
- Exactly one anomaly-detector callback

A rejected legitimate control remains a rejection in the control population and is not silently retried or replaced.
The resulting valid-message rejection rate measures conditional Layer-3 behavior under controlled successful admission. It is not the PUF reconstruction FRR or the anomaly detector's false-positive rate.

## Experimental Design

### Experimental Configurations

The planned formal experiment includes primary attacks, legitimate controls, state-machine negatives, and parser-boundary negatives,
| Category | Planned Scenarios | Scored/Negative Submissions |
|---|---:|---:|
| A1–A5 primary attacks | 6,000 | 6,000 |
| Legitimate controls | 1,200 | 1,200 |
| S1–S8 state cases | 960 | 1,080 |
| P01–P28 parser cases | 1,680 | 1,680 |
| **Total** | **9,840** | **9,960** |

The larger execution plan also includes setup, recovery, lifecycle, and warmup operations.
Read-only trial-plan compilation produced,
- 23,520 planned setup-window submissions
- 10,200 planned recovery-window submissions
- 11,560 setup-handshake operations
- 1,040 recovery-handshake operations
- 10,640 lifecycle operations
- 34,920 expected successful setup/control/recovery windows
- 66,920 total measured operation rows
- 20 separate warmup scenarios

These are preregistered workload counts; actual completion is reported in Experimental Results.

### Attack Generation and Trial Allocation

Each primary attack group contains 1,200 trials distributed across six simulated devices and two enrollment generations.
For every device/enrollment combination, 100 trials are scheduled.
This produces 12 device-generation cells per primary group.

Primary scenarios vary across,
- Device identity
- Enrollment generation
- Session and nonce identities
- Sequence positions 0 through 4
- Frozen source motion windows
- Attack-specific mutation coordinates
- Session lifecycle states where applicable

A complete deterministic trial plan is generated before formal execution.

The planner uses separate random streams for,
- PUF manufacturing and enrollment
- Controlled PUF readings
- Trial ordering
- Attack mutation choices
- Source-window selection

Protocol nonces, session identifiers, boot identifiers, credentials, and verifier keys use native operating-system randomness rather than public simulation seeds.
The experiment prevents outcome-dependent mutation selection, retries, or modifications to the registered trial population.

### Frozen SNN Models and Sensor Data

The Tier-1 experiment evaluates the existing frozen SNN inference pipeline using the preregistered condition:

`snn32_seed7_forest_anomaly`

The selected model pair consists of:

- **Motion model:** `snn_32_seed_7`
- **Anomaly detector:** `anomaly_random_forest_seed6007`

The source dataset is:

`data/generated/synthetic-windows.jsonl`

The measured test split contains 600 source windows distributed across six devices, five labels, and 20 windows per device/label combination.

The frozen input representation uses,
- Motion input shape: (120, 7)
- Anomaly input shape: (48,)

Actual model inference is performed using the unchanged frozen-model loader and existing preprocessing functions.
The selected model pair is fixed before formal evaluation. The experiment does not retrain models, tune thresholds, regenerate data, or choose a different pair based on attack outcomes.
The frozen loader verifies the complete required bundle, not merely the selected model pair.

### Experimental Controls

The experiment includes several controls to preserve the validity of the measurements.
Each scenario uses fresh authenticated session contexts, while the relevant device profiles and source windows are reused according to the preregistered design.
Attack packets are constructed before timed receiver submission.
For every negative submission, the experiment records the receiver state before and after the attempted operation.
The following properties are checked,
- No unauthorized accepted-window release
- No unexpected sequence-counter advancement
- No alteration of protected session state
- No inference callbacks after authentication rejection
- No duplicate consumption of accepted windows
- Correct handling of the preplanned legitimate recovery sequence

Warmup operations are separated from measured attack/control populations.
The experiment uses real protocol and inference callbacks during formal execution. Dummy callbacks are permitted only in explicitly labeled nonformal implementation tests.
All unexpected decisions are retained as evidence rather than discarded or converted into successful rejections.

### Evaluation Metrics

The experiment measures authentication decisions, protocol-state integrity, inference gating, timing, and evidence completeness.

**Primary attack metrics:**

- Scheduled attack attempts
- Submitted attack attempts
- Accepted attacks
- Rejected attacks
- Execution failures
- Unsubmitted dependent attempts
- Attack acceptance rate
- Attack rejection rate
- Expected versus observed rejection reasons

Attack acceptance and rejection are defined over completed ordinary authentication decisions:

`Attack Acceptance Rate = A / (A + R)`

`Attack Rejection Rate = R / (A + R)`

**Legitimate control metrics:**

- Valid control submissions
- Accepted legitimate windows
- Rejected legitimate windows
- Valid-message rejection rate

**Protocol-state metrics:**

- Accepted-window count before and after injection
- Last-accepted and expected sequence values
- Session lifecycle and deadline preservation
- Sender state preservation
- Recovery acceptance
- Unexpected state changes

**Inference-gating metrics:**

- Accepted-result authority generated
- Authenticated release calls
- Preprocessing calls
- SNN motion inference calls
- Anomaly inference calls
- Consumed-event count changes
- Unauthorized inference invocations

**Latency metrics:**

- Native verifier-authentication latency
- Receiver-to-return processing latency
- Available nested parser, HMAC, preprocessing, inference, audit, and release timing
- Mean, p50, p95, p99 where supported, and maximum latency
- Separate accepted, rejected, setup, recovery, and warmup populations

The experiment uses two-sided 95% Clopper-Pearson intervals for attack acceptance and valid-message rejection.

These intervals describe the planned finite trial populations under binomial assumptions. Shared devices, models, source windows, and session structures introduce dependence that must be disclosed when interpreting the results.

## Implementation and Validation

### Implementation Architecture

The Tier-1 v2 evaluation was implemented as a separate experimental harness built around the existing Authentication-v2 implementation.
Primary files:

- `src/python/puf_snn/tier1_v2.py`
- `src/python/scripts/run_tier1_v2.py`
- `configs/tier1_v2_experiment_v1.json`

Additional evidence schemas:

- `schemas/tier1-v2-attempt-v1.schema.json`
- `schemas/tier1-v2-trial-plan-v1.schema.json`
- `schemas/tier1-v2-summary-v1.schema.json`

The runner handles,
- Strict configuration validation
- Deterministic trial-plan compilation
- Real PUF reconstruction and credential admission
- Session establishment and lifecycle orchestration
- Public-byte attack generation
- Safe protocol-state observation
- Real inference callback instrumentation
- Per-operation timing collection
- Evidence generation and reconciliation
- Source and artifact integrity verification

The existing Authentication-v2 protocol, credential verifier, BCH reconstruction, PUF model, and inference-gating behavior were not modified to implement the new attack harness.
A small change to `pipeline_timing.py` moved two frozen-model imports into their respective functions without changing timing calculations or protocol behavior.

### Protocol and Security Validation

The implementation includes all five registered primary attack groups, eight protocol-state groups, and 28 parser-negative cases.
Deterministic validation tests exercise the expected first-failure reasons and verify that mutation helpers operate only on public packet material.
Additional checks cover,
- Exact replay-byte preservation
- Invalid authentication tags
- Protected device-identity substitution
- Protected motion and metadata modifications
- Duplicate, stale, and future sequence handling
- Session replacement and expiry behavior
- Protocol-state preservation after rejection
- Correct recovery of legitimate traffic
- Malformed binary and JSON representations
- Truncated handshake messages
- Exact accepted-window release behavior
- Inference callback counts
- Recovery and interruption accounting

The harness records ordinary unexpected acceptances or rejection-reason mismatches as findings.
Infrastructure exceptions and incomplete observations are recorded separately and cannot be reclassified as valid security rejections.

### Automated Testing

The initial harness implementation passed 22 new automated tests.

Earlier implementation validation also recorded,
- 237 authentication regression tests passed.
- 50 reconstruction regression tests passed.

Following the restoration of frozen model artifacts and installation of the compatible PyTorch environment, the October 7 real-artifact preflight executed 126 targeted tests.

| Test Suite | Passed |
|---|---:|
| `test_pipeline_v2.py` | 27 |
| `test_pipeline_timing.py` | 28 |
| `test_frozen_pipeline.py` | 22 |
| `test_tier1_v2.py` | 25 |
| `test_pipeline_timing_reporting.py` | 24 |
| **Total** | **126** |

All 126 targeted tests passed with zero failures, errors, skips, or blocked tests.
The separate full formal trial plan was also compiled without running attack measurements.
Compilation confirmed all registered group counts, scenario identities, mutation allocations, setup operations, recovery operations, and execution-order assignments.
These validation results establish implementation readiness for review but are not formal attack-performance results.

### Real-Artifact Feasibility Validation

A separate nonformal feasibility run was executed using the restored frozen dataset and real model artifacts.

Before model loading, the following integrity checks passed,
- 12/12 restored dataset/model payload files verified
- 66/66 files in the complete frozen artifact inventory verified
- All three historical artifact completion markers present
- Frozen dataset and model manifest hashes matched their pinned values

The unchanged frozen-model loader successfully loaded the required models and selected the declared SNN/anomaly pair.

The nonformal real-artifact experiment contained,
- 75 scenarios
- 360 operation rows
- Coverage of A1–A5
- Coverage of S1–S8
- Coverage of P01–P28
- Legitimate authentication controls
- Session lifecycle and recovery operations

Observed feasibility results,
- 120 accepted windows invoked release, preprocessing, motion inference, and anomaly inference exactly once
- 70 rejected window submissions invoked none of these four boundaries
- Four additional malformed-handshake submissions were evaluated separately
- 30/30 evidence reconciliation checks passed
- No declared reason, state, inference-count, or recovery discrepancies were observed

The retained nonformal evidence reported:

`evidence_complete: true`

`expected_behavior_observed: true`

However, the package intentionally retains the NONFORMAL `INCOMPLETE` marker and cannot be promoted into the formal experiment.
The complete feasibility invocation took approximately 20.401 seconds.
Based on the compact validation workload, a cautious 30–90 minute planning range was estimated for the full formal experiment.
This range is a runtime estimate rather than a measured formal performance result.

### Formal Preflight and Source Provenance

Formal execution used isolated local commit **0d088079d025e50411c8a752b32507bbb87d5d5b**, whose parent is the original repository HEAD **9384644a182700afa8f180a81f495acf278185af**. Its only committed additions are the four restored historical supporting documents. The original main branch, index, and history were preserved; those four files remain untracked and unchanged there.

The isolated checkout preserved exact original source/artifact bytes, including hash-significant Windows line endings. Its Git tree was clean and identical to the committed tree before execution. The supported formal_preflight verified the current source manifest, unchanged protocol baseline, frozen config hashes, all 66 artifacts, complete plan, and unused output path. All 12 dataset/model payload hashes passed within that inventory. All 428 relevant regression tests passed with no failures, errors, or skips, and pip check reported no broken requirements. The real frozen bundle and registered model pair loaded successfully; input shapes and all source-window representations passed preflight.

The committed registered config intentionally retains null execution pins. Only the authorized external run-specific config resolved execution_source_commit and source_manifest_path; no self-referential source edit was made. The resolved plan digest is **cd2c26dd87689e4c1192843cded2166ba7e7c0692e24843387ef462fc302cd96**. Preflight retained 9,840 measured scenarios, 66,920 measured operations, and 20 separate warmup scenarios.

The source manifest covers 185 files. The historical plan's original design-time hashes remain unchanged, while the execution manifest pins the current specification at **81d48649db98812f2d62592e3bc4bf0e60419ff0434e39f3888d9b7247a918e7**. The plan itself remains **a8bb71144f8a07056cd1326d755b5e8c7599ae417e3f96445a94fdf08f9a4851**. A complete-history Git bundle and independently hash-verified exact-byte ZIP preserve the actual local execution source.

Evidence: [verification/preflight.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/preflight.json), [verification/model-preflight.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/model-preflight.json), [verification/test-results.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/test-results.json), [verification/source-snapshot-verification.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/source-snapshot-verification.json), and [source_manifest.json](../results/week-6/will/authentication/tier1-v2-formal-001/source_manifest.json).

## Experimental Results

All results in this section come from tier1-v2-formal-001. The retained runner reconciliation passed 31/31 checks; a separate process regenerated the summary and CSVs and independently checked raw state, authority, callbacks, source-record hashes and allocations. No measurement was restarted or replaced. Historical nonformal results above remain separate.

### Tier-1 Attack Rejection Results

The formal run completed on October 8, 2026 (America/New_York), using the isolated execution source identified below. All 6,000 primary attacks were submitted once. Each group recorded zero accepted attacks and 1,200 rejected attacks; there were zero execution errors and zero unsubmitted attempts in every group. Rates use completed authentication decisions, A + R = 1,200 per group.

| Group | Scheduled | Submitted | Accepted | Rejected | Acceptance rate | Rejection rate | Observed reason |
|---|---|---|---|---|---|---|---|
| A1 | 1200 | 1200 | 0 | 1200 | 0.0000% | 100.0000% | duplicate_sequence: 1,200 |
| A2 | 1200 | 1200 | 0 | 1200 | 0.0000% | 100.0000% | inactive_session: 400; expired_session: 800 |
| A3 | 1200 | 1200 | 0 | 1200 | 0.0000% | 100.0000% | invalid_tag: 1,200 |
| A4 | 1200 | 1200 | 0 | 1200 | 0.0000% | 100.0000% | invalid_tag: 1,200 |
| A5 | 1200 | 1200 | 0 | 1200 | 0.0000% | 100.0000% | invalid_tag: 1,200 |

Expected and observed reasons matched for 6,000/6,000 primary submissions (100%). A2 retained 400 replacement, 400 expired-live, and 400 expired-cleanup cases; the expiry cases split equally between deadline equality and +1 ms. A4 retained 600 position and 600 quaternion mutations, and A5 retained 200 mutations of each of its six protected fields. Each primary group and the control group used all 600 test windows twice. No acceptance was reclassified using an anomaly prediction.

Evidence: [attempts.jsonl](../results/week-6/will/authentication/tier1-v2-formal-001/attempts.jsonl), [attack_summary.csv](../results/week-6/will/authentication/tier1-v2-formal-001/attack_summary.csv), [reason_summary.csv](../results/week-6/will/authentication/tier1-v2-formal-001/reason_summary.csv), and [independent raw-evidence analysis](../results/week-6/will/authentication/tier1-v2-formal-001/verification/independent-analysis.json).

### Protocol State and Parser Rejection

All 1,080 state-negative submissions across 960 scenarios were rejected with their registered reasons. S4 contributed two negatives in each of its 120 scenarios.

| Group | Scenarios | Submitted / rejected | Observed reasons |
|---|---|---|---|
| S1 | 120 | 120 / 120 | invalid_tag: 120 |
| S2 | 120 | 120 / 120 | future_sequence_gap: 120 |
| S3 | 120 | 120 / 120 | invalid_tag: 120 |
| S4 | 120 | 240 / 240 | duplicate_sequence: 120; invalid_tag: 120 |
| S5 | 120 | 120 / 120 | stale_sequence: 120 |
| S6 | 120 | 120 / 120 | future_sequence_gap: 120 |
| S7 | 120 | 120 / 120 | malformed_message: 120 |
| S8 | 120 | 120 / 120 | invalid_key_id: 60; invalid_tag: 60 |

All 28 parser cases completed 60/60 expected rejections, giving 1,680/1,680 in total: 1,440 window-envelope/binary cases and 240 receiver-handshake cases. Observed parser reasons were 1,200 malformed_message, 420 invalid_payload_schema, and 60 unsupported_protocol_version. The state/parser expected-reason match rate was 2,760/2,760 (100%). No parser refusal was counted as an infrastructure failure.

Before/after comparisons found zero rejected-state changes, zero accepted-window authority violations, and zero unauthorized inference invocations. Checks included accepted count, last accepted and expected next sequence, session identity/lifecycle/deadline, sender state, and consumed-event state; only the explicitly excluded derived elapsed-deadline flag could vary. Handshake parser refusals preserved the appropriate pending state.

All 10,200 distinct planned recovery windows were accepted, and all 1,040 recovery-handshake operations completed successfully. There were zero recovery rejections, errors, or unsubmitted steps. S6 filled the missing sequence range and retried the exact retained future packet; this demonstrates the registered explicit recovery, not automatic buffering or retransmission. Recovery counts use distinct operation rows, avoiding double-counting shared S4 recovery references.

Evidence: [state_safety.jsonl](../results/week-6/will/authentication/tier1-v2-formal-001/state_safety.jsonl), [parser_negative.jsonl](../results/week-6/will/authentication/tier1-v2-formal-001/parser_negative.jsonl), [recovery.jsonl](../results/week-6/will/authentication/tier1-v2-formal-001/recovery.jsonl), [reconciliation.json](../results/week-6/will/authentication/tier1-v2-formal-001/reconciliation.json), and [verification/independent-analysis.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/independent-analysis.json).

### Legitimate Authentication Results

All 1,200/1,200 legitimate controls were accepted (100% acceptance); 0/1,200 were rejected (0% valid-message rejection). No control had an execution error or remained unsubmitted. Every accepted control advanced its session's accepted count exactly once, set the expected next sequence consistently, and consumed one authenticated event.

The broader measured workload also accepted 23,520 setup windows and 10,200 recovery windows, for 34,920 measured accepted windows. The 20 accepted warmup windows are separate. These results characterize Layer-3 behavior under the registered noiseless reference-condition admission fixture; they do not measure noisy reconstruction FRR or anomaly-classifier accuracy.

Evidence: [controls.jsonl](../results/week-6/will/authentication/tier1-v2-formal-001/controls.jsonl), [control_summary.csv](../results/week-6/will/authentication/tier1-v2-formal-001/control_summary.csv), [setup.jsonl](../results/week-6/will/authentication/tier1-v2-formal-001/setup.jsonl), and [verification/independent-analysis.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/independent-analysis.json).

### SNN Inference Gate Results

The public pipeline counters and independent callback-entry observations agreed for every submitted window. Each successfully consumed window had one accepted-window release, one preprocessing invocation, one SNN invocation, and one anomaly-detector invocation.

| Population | Windows | Release | Preprocessing | SNN | Anomaly |
|---|---|---|---|---|---|
| Measured setup, control, and recovery accepts | 34,920 | 34,920 | 34,920 | 34,920 | 34,920 |
| Measured rejected windows | 8,520 | 0 | 0 | 0 | 0 |
| Separate warmup accepts | 20 | 20 | 20 | 20 | 20 |

The 240 malformed-handshake submissions also produced zero calls at all four boundaries. There were zero callback/public-counter discrepancies, zero rejected accepted-result authorities, and zero repeated or missing consumption transitions. All accepted formal windows recorded the required real model identities, snn_32_seed_7 and anomaly_random_forest_seed6007. Across measured windows and warmups, each processing boundary was invoked 34,940 times.

These observations establish the measured gating behavior. They do not convert the implementation's at-most-once delivery guarantee into guaranteed successful inference after arbitrary downstream failures.

Evidence: per-operation calls_delta, callback_entry_delta, state snapshots and authority flags in the raw streams, independently recomputed in [verification/independent-analysis.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/independent-analysis.json).

### Authentication and Processing Latency

All values below are actual formal measurements in milliseconds, with no outliers removed. Native verifier time excludes accepted release and inference. Receiver-to-return time directly measures the receiver call and includes downstream processing when accepted. The following role/group aggregates were recomputed from raw rows; the registered variant/reason/clock strata remain in [latency_summary.csv](../results/week-6/will/authentication/tier1-v2-formal-001/latency_summary.csv) and [summary.json](../results/week-6/will/authentication/tier1-v2-formal-001/summary.json). Expiry fixtures remain separate from real-clock observations.

**Native verifier authentication**

| Population | n | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Maximum (ms) |
|---|---|---|---|---|---|---|
| Legitimate controls | 1,200 | 4.9431 | 5.1700 | 5.9924 | 7.3466 | 176.2541 |
| Setup windows | 23,520 | 5.4087 | 5.2096 | 6.7859 | 7.2888 | 194.3588 |
| Recovery windows | 10,200 | 4.9671 | 5.1078 | 6.0798 | 7.2774 | 196.3410 |
| A1 duplicate replay | 1,200 | 5.1175 | 5.0202 | 5.5935 | 7.4108 | 172.3032 |
| A2 replaced session | 400 | 1.4906 | 1.4368 | 1.8459 | 1.9700 | 2.2265 |
| A2 expiry equality (simulated) | 400 | 1.2622 | 1.3976 | 1.7094 | 1.8751 | 2.3139 |
| A2 expiry +1 ms (simulated) | 400 | 1.2611 | 1.4101 | 1.6531 | 1.8768 | 2.1249 |
| A3 device substitution | 1,200 | 2.1469 | 1.4244 | 1.7471 | 2.0464 | 178.1672 |
| A4 payload modification | 1,200 | 1.9267 | 1.4306 | 1.7256 | 1.9482 | 206.1934 |
| A5 metadata modification | 1,200 | 1.4782 | 1.4320 | 1.7491 | 1.9158 | 165.0544 |
| S1–S8 state negatives | 1,080 | 2.3206 | 1.4440 | 5.2183 | 6.6008 | 7.9520 |
| P01–P24 window parser negatives | 1,440 | 0.2795 | 0.1105 | 1.4024 | 1.5662 | 2.7079 |

**Receiver-to-return processing**

| Population | n | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Maximum (ms) |
|---|---|---|---|---|---|---|
| Legitimate controls | 1,200 | 19.1071 | 19.4579 | 23.1507 | 40.7158 | 189.5738 |
| Setup windows | 23,520 | 20.6648 | 19.6070 | 37.1010 | 40.8137 | 265.3652 |
| Recovery windows | 10,200 | 18.7552 | 19.2320 | 24.1348 | 40.5966 | 207.4851 |
| A1 duplicate replay | 1,200 | 5.1599 | 5.0633 | 5.6545 | 7.4972 | 172.3427 |
| A2 replaced session | 400 | 1.5343 | 1.4784 | 1.8924 | 2.0384 | 2.2857 |
| A2 expiry equality (simulated) | 400 | 1.3002 | 1.4357 | 1.7671 | 1.9455 | 2.3871 |
| A2 expiry +1 ms (simulated) | 400 | 1.3022 | 1.4504 | 1.6974 | 1.9833 | 2.8506 |
| A3 device substitution | 1,200 | 2.1873 | 1.4652 | 1.8012 | 2.1250 | 178.2066 |
| A4 payload modification | 1,200 | 1.9671 | 1.4715 | 1.7821 | 2.0124 | 206.2492 |
| A5 metadata modification | 1,200 | 1.5189 | 1.4724 | 1.8019 | 2.0159 | 165.0983 |
| S1–S8 state negatives | 1,080 | 2.3561 | 1.4875 | 5.2628 | 6.6612 | 8.0699 |
| P01–P24 window parser negatives | 1,440 | 0.2940 | 0.1237 | 1.4171 | 1.5814 | 2.7320 |

For the 240 handshake-parser refusals, receiver-call mean/p50/p95/p99/maximum were 0.0824 / 0.0767 / 0.1204 / 0.1506 / 0.1613 ms. These calls have no native window-verifier latency. The 20 separate warmup receiver calls had mean 23.3868 ms, p50 23.9059 ms, p95 25.6664 ms, and maximum 25.6801 ms; p99 was not reported because n < 100.

**Nested processing spans for the 1,200 legitimate controls**

| Observed span | n | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Maximum (ms) |
|---|---|---|---|---|---|---|
| Preprocessing | 1200 | 2.3984 | 2.5460 | 2.9208 | 4.5102 | 14.4399 |
| SNN motion inference | 1200 | 7.0567 | 6.7420 | 8.0496 | 19.2804 | 177.1868 |
| RF anomaly inference | 1200 | 4.2545 | 4.4516 | 5.0626 | 8.8259 | 14.9112 |
| Accepted release and consumers (inclusive) | 1200 | 14.1371 | 14.2340 | 16.9642 | 33.2165 | 184.0606 |

Nested spans overlap their enclosing receiver/release spans. Their separately calculated percentiles must not be added. Normal setup/recovery handshakes and explicit lifecycle operations have no latency values in this registered formal harness; no timings are fabricated for them. Setup/recovery *windows* and the A2 lifecycle-conditioned replay calls are reported above.

Control receiver p95 was 23.1507 ms and maximum was 189.5738 ms. The largest measured receiver observation across the tabulated window populations was 265.3652 ms in setup traffic. Long-tail observations remain in the raw timing traces; unmeasured background load is not assigned as their cause. The complete CLI invocation took 1,618.341 seconds, including preflight, loading, orchestration, evidence writing and finalization. That wall time is not a per-window latency metric. These are instrumented local Windows CPU software measurements, not physical Quest 3 or FPGA performance.

Evidence: [timing_traces.jsonl](../results/week-6/will/authentication/tier1-v2-formal-001/timing_traces.jsonl), [latency_summary.csv](../results/week-6/will/authentication/tier1-v2-formal-001/latency_summary.csv), [verification/independent-analysis.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/independent-analysis.json), and [verification/formal-invocation.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/formal-invocation.json).

### Statistical Confidence and Reliability

For each primary group separately, attack acceptance was 0/1,200. The preregistered two-sided 95% equal-tailed Clopper–Pearson interval is **0–0.3069346%**; the complementary attack-rejection interval is **99.6930654–100%**. Legitimate-control rejection was also 0/1,200, with the same **0–0.3069346%** interval. The zero-event upper probability is 1 − 0.025^(1/1200) = 0.003069346108100284. There were no execution errors or unsubmitted attempts to exclude or reinterpret as rejections.

These are pointwise binomial intervals, not simultaneous guarantees across attack groups. Zero observed acceptance does not establish zero underlying attack-success probability. Six simulated devices, twelve enrollment fixtures, reused test windows, fixed models, one implementation, and one machine introduce dependence and restrict generalization. Fresh sessions/nonces do not remove those dependencies. The control interval concerns conditional Layer-3 valid-message rejection, not noisy PUF reconstruction or semantic anomaly false positives.

Intervals and denominators are retained in [attack_summary.csv](../results/week-6/will/authentication/tier1-v2-formal-001/attack_summary.csv), [control_summary.csv](../results/week-6/will/authentication/tier1-v2-formal-001/control_summary.csv), and the independent analysis; the latter separately recomputed beta-quantile endpoints and checked the zero-event closed form.

## Security Analysis

### Authentication and Device Binding

A3 rejected all 1,200 substitutions of another known device's protected identity with invalid_tag while preserving both legitimate sessions and their recovery paths. This supports integrity of the evaluated protected device identity under the original session key. It does not demonstrate physical device attestation, resistance to credential guessing, or protection after trusted-process or key compromise. The simulated PUF and local credential-admission assumptions remain part of the boundary.

### Replay and Freshness Protection

A1 rejected every same-session replay at duplicate_sequence even though its retained HMAC remained valid. A2 rejected 400 replaced-session packets at inactive_session and 800 expired-session packets at expired_session before HMAC verification. The state cases additionally exercised stale packets and valid future gaps. No rejected replay advanced receiver ordering state.

Expiry equality and +1 ms observations used the registered clock proxy, not five minutes of real elapsed waiting. These results support session/sequence freshness in this workload; authenticated capture timestamps are not checked against receiver wall-clock age.

### Message Integrity

All 2,400 A4/A5 payload and protected-metadata modifications were rejected at invalid_tag with their original tags retained. Together with A3, these observations support the implemented HMAC boundary for the specific public-byte mutations. Representation failures were reported separately by the parser population. The experiment does not establish payload confidentiality, a cryptographic forgery bound, or benign semantics for legitimately authenticated motion.

### Protocol State Enforcement

The 1,080 state negatives and 1,680 parser negatives matched their expected reasons without protected-state corruption. All scheduled recoveries completed. Strict exact-next ordering therefore preserved the retained legitimate continuations exercised here. Packet loss remains an availability concern because the sender advances on sealing and the receiver neither buffers future packets nor supplies automatic transport recovery. Resource exhaustion, concurrency, crashes, and persistent-state recovery were not formal populations in this run.

### Inference Boundary Protection

Rejected windows produced zero release, preprocessing, SNN, and anomaly invocations, while all 34,920 measured accepted windows produced one invocation at each boundary. Independent callback counts, public counters, accepted-result authority, and consumed-event transitions corroborated the rejection labels. No anomaly prediction was used to excuse an authentication acceptance. Guarantees remain limited to the supported trusted-process pipeline and its at-most-once event consumption.

### Security and Performance Tradeoffs

Early parser, lifecycle, and invalid-tag exits avoided downstream model execution. A1 replays reached later ordering checks and therefore exercised more verifier work than early rejections. Accepted controls incurred both authentication and real inference: median native verifier time was 5.1700 ms, compared with 19.4579 ms for receiver-to-return processing. Those are separately measured distributions, not additive timing components.

The observed tails preclude inferring a hard latency bound from the median. Instrumentation, audit work, GC-enabled execution, and local machine conditions are part of the measured software condition. No protocol tuning, reduced population, model replacement, or reconstruction alternative was used to obtain these outcomes.

## Experimental Limitations

The Tier-1 v2 experiment evaluates a controlled software implementation of Authentication-v2 rather than a physical hardware deployment.

The study focuses on selected protocol-level attacks and receiver-state behavior. It does not evaluate all possible attack strategies or prove universal security.

Key methodological limitations include,
- PUF credential admission is evaluated under controlled noiseless reference conditions
- The experiment does not measure noisy PUF reconstruction FRR
- Six simulated PUF device profiles are reused across the attack population
- Two enrollment generations per device do not represent independent physical devices
- The same 600 frozen test windows are reused according to the planned schedule
- Fresh sessions and nonces do not make all attacks statistically independent
- The model pair and inference implementation remain fixed throughout the experiment
- Tier-2 adversarial motion attacks and semantic model robustness are outside this evaluation
- Credential compromise, attacker possession of session keys, and unrestricted cryptographic forgery are outside the primary attack model
- Network transport behavior, real wireless conditions, and hardware timing are not evaluated
- Clock-offset expiration cases simulate deadline boundaries rather than waiting for real elapsed session expiry
- Real inference latency measurements reflect the local software environment, not Meta Quest 3 hardware execution

The study also distinguishes authentication success from anomaly-detection behavior.
A correctly authenticated sensor window may still receive an anomaly classification. Conversely, an incorrectly admitted attack must be reported as an authentication failure even if the downstream anomaly detector flags it.
The formal study's confidence intervals must be interpreted alongside the dependence introduced by reused device profiles, source records, and shared implementation conditions.

## Conclusions and Recommendations

### Primary Findings

The complete registered experiment produced 6,000/6,000 primary rejections with zero accepted attacks, 1,200/1,200 legitimate-control acceptances, and 2,760/2,760 expected state/parser rejections. All 10,200 recovery windows and 1,040 recovery handshakes completed successfully. Rejected traffic produced no state, authority, or inference-gating violations. All 66,920 measured operation rows and 60 warmup rows reconciled; no execution failures or unsubmitted operations occurred.

Control receiver latency had mean 19.1071 ms, p50 19.4579 ms and p95 23.1507 ms. Each group's 0/1,200 attack acceptances has a descriptive two-sided 95% Clopper–Pearson upper endpoint of 0.3069346%, subject to the stated dependence limitations.

### Authentication-v2 Security Assessment

The evaluated software implementation exhibited the registered replay, protected-byte integrity, lifecycle, sequence-state, parser, recovery, and inference-gating behavior. Evidence completeness and expected security behavior both passed, as separate verdicts. This is finite implementation evidence rather than a universal security proof. The 32-bit research credential, offline-guessing exposure of captured confirmations, co-located trust boundary, simulated PUF, and absence of encryption/forward secrecy remain unchanged limitations.

### Recommended Protocol Improvements

No protocol repair was required by an observed violation in this run. Before production-oriented use, prioritize a separately specified higher-entropy credential/key design, protected key custody and process boundaries, and a defined network loss/recovery policy. Evaluate capture-time freshness and crash-safe session/audit persistence under explicit threat models. Any such change requires a new version and fresh evaluation; these recommendations were not implemented in the frozen experiment.

### Future Research

Extend evaluation to independent device populations, physical PUF/XR measurements, noisy admission, transport loss/reordering, resource exhaustion, concurrency, and crash recovery. Broaden parser/property-based testing and examine latency tails with dedicated system measurements. Evaluate any reconstruction-reliability improvement in a separate versioned integration study. The completed Reconstruction Alternatives Experiment remains unchanged, and neither majority voting nor stronger BCH was integrated into this run.

## Reproducibility and Evidence

### Experiment Configuration and Environment

- **Experiment:** authentication-v2-tier1-security-evaluation, version 1.
- **Formal run:** tier1-v2-formal-001; completed October 8, 2026 (America/New_York).
- **Protocol profile:** puf-snn-l3-credential-admission-v1-wire2.
- **Original main HEAD:** 9384644a182700afa8f180a81f495acf278185af.
- **Actual execution source:** 0d088079d025e50411c8a752b32507bbb87d5d5b, a detached isolated local provenance commit; it was not pushed and is not the original main HEAD.
- **Registered config:** configs/tier1_v2_experiment_v1.json.
- **Actual resolved config:** [config.json](../results/week-6/will/authentication/tier1-v2-formal-001/config.json); exact invocation is retained in [verification/formal-invocation.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/formal-invocation.json).
- **Authentication/frozen configs:** configs/authentication_v2.json and configs/week6_smoke.json, unchanged.
- **Model condition:** snn32_seed7_forest_anomaly; SNN snn_32_seed_7 plus anomaly_random_forest_seed6007.

Execution used Windows 11 (build 26200), Python 3.12.4, PyTorch 2.14.0+cpu, NumPy 2.5.3, SciPy 1.18.1, galois 0.4.11, numba 0.67.0, scikit-learn 1.9.1, joblib 1.6.0, jsonschema 4.26.0, and threadpoolctl 3.7.0. The CPU reported Intel64 Family 6 Model 151 with 20 logical processors. Execution was serial, CPU/eval, batch size one, with torch and native pools limited to one thread and GC enabled. QueryPerformanceCounter resolution was 100 ns. The existing High performance power plan was observed, not changed; background load was not measured.

The CLI ran from 05:41:44.330039 to 06:08:42.670960 UTC (01:41:44–02:08:42 EDT), exiting 0 after 1618.341 seconds. The scenario-loop environment observations span 05:42:20.260781–06:02:53.293759 UTC. These process/loop durations include work outside receiver timing. Exact start/end machine metadata is in [metadata.json](../results/week-6/will/authentication/tier1-v2-formal-001/metadata.json).

### Source Code and Formal Results

The existing harness, runner, tests and schemas remain unchanged:

- src/python/puf_snn/tier1_v2.py
- src/python/scripts/run_tier1_v2.py
- tests/tier1/test_tier1_v2.py
- schemas/tier1-v2-attempt-v1.schema.json
- schemas/tier1-v2-trial-plan-v1.schema.json
- schemas/tier1-v2-summary-v1.schema.json

**Final evidence directory:** results/week-6/will/authentication/tier1-v2-formal-001/.

**Formal trial-plan digest:** cd2c26dd87689e4c1192843cded2166ba7e7c0692e24843387ef462fc302cd96.

**Resolved configuration canonical digest:** bc90905e5f9fb3462a945d9bbf249d8f13e62737390bc20d60bd50753e071c83.

**Source manifest:** [source_manifest.json](../results/week-6/will/authentication/tier1-v2-formal-001/source_manifest.json); SHA-256 d1367398222037dc9f6bc92c1b5d4610f68a6e0513b02b61bbb74e6ba31892b3.

**Frozen artifact manifest:** [artifact_manifest.json](../results/week-6/will/authentication/tier1-v2-formal-001/artifact_manifest.json); SHA-256 a28b242ef1099193665d25d1ef5b03cfbb9452669cf5033ee648654fef3bd66f. All 66 required files verified before loading, during formal preflight, and after execution. Selected identities and authoritative bundle pins are:

| Artifact | SHA-256 |
|---|---|
| Dataset: synthetic-windows.jsonl | 752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661 |
| SNN: seed-7/model-state.pt | 112f434cc79817da8c254947fb68a23e69a0d8734199c7f3166b681c11028fe6 |
| Anomaly: anomaly_random_forest_seed6007.joblib | 441572d3500737df9bb1bf38031b64fc4a9f4a490094e6bf652bbefc92cd717b |
| SNN bundle manifest | ccf13e7d7c3b199676e8a847394cc1d5a1c4d70939fa2f94d8efd84ab0470779 |
| Conventional bundle manifest | 456b21cf1c4ed74dbc52294857b2d9c607d9cdd6efeb753b2679b95b9df100ed |
| Anomaly bundle manifest | 8c053eadacf67c97f4d886a8116df17f185afb818d2e25439090fb7d7275f13e |

**Recoverable execution source:** [complete-history Git bundle](../results/week-6/will/authentication/tier1-v2-formal-001/verification/execution-source.bundle), SHA-256 7abdfe2cb8f4e32c980a848b29c926ebd55830938cb704b384f331fa2f3a8314. The [exact-byte source ZIP](../results/week-6/will/authentication/tier1-v2-formal-001/verification/execution-source-bytes.zip) has SHA-256 a9af23d5fa0129b05c4d8b77d6f6c57ffa1428bc75934d674e77687d8d16eca1. Its 188 files include all 185 execution-manifest entries and the three additional historical supporting documents. Archive contents and bundle recoverability were independently checked.

To recover the source, clone the local bundle, select the recorded execution commit, and restore the ZIP's exact source bytes before verifying the source manifest. Git line-ending conversion alone may not reproduce every pinned byte hash. Frozen dataset/model payloads remain at their original repository paths and must independently match artifact_manifest.json. A future execution requires its own authorized fresh identity and run-specific provenance; the retained formal directory must not be reused. Native OS randomness means future public session traffic will differ even with the same nonsecret schedule.

### Evidence Integrity and Supporting Documentation

The formal package contains 26 original files. Its original evidence manifest and COMPLETE marker were preserved byte-for-byte during an exclusive transfer from the isolated clone. All copied original hashes matched. Supplemental preflight, invocation, source-recovery and independent analysis files are under verification/ and have a separate [verification manifest](../results/week-6/will/authentication/tier1-v2-formal-001/verification/verification-manifest.json); they are not silently added to or represented as covered by the runner's original manifest.

- **Formal execution status:** COMPLETE; no INCOMPLETE marker remains.
- **Evidence completeness:** true; all 66,980 operation identities reconcile, including 66,920 measured rows and 60 warmup rows.
- **Expected behavior observed:** true; no observed reason, state, authority, gating or recovery violation.
- **Formal reconciliation:** [reconciliation.json](../results/week-6/will/authentication/tier1-v2-formal-001/reconciliation.json), 31/31 checks passed.
- **Independent reconciliation:** [verification/independent-reconciliation.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/independent-reconciliation.json); regenerated summary and all five CSVs match exactly, source/artifact pins and completion-marker closure verify.
- **Independent raw analysis:** [verification/independent-analysis.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/independent-analysis.json); zero source-record hash or source-allocation discrepancies, execution failures, unsubmitted operations, state findings, authority findings, callback discrepancies, or expected-reason mismatches.
- **Original evidence manifest:** [manifest.json](../results/week-6/will/authentication/tier1-v2-formal-001/manifest.json), SHA-256 098ebcf6488e7d2b5c2054200bab289e5428c859904108059d0437612c137177.
- **Formal completion anchor:** [COMPLETE](../results/week-6/will/authentication/tier1-v2-formal-001/COMPLETE), which pins that manifest and separately records the expected-behavior verdict.
- **Transfer check:** [verification/transfer-verification.json](../results/week-6/will/authentication/tier1-v2-formal-001/verification/transfer-verification.json); all original evidence files matched their isolated-source hashes.

COMPLETE records methodological completion, not universal security. All raw decisions, public wire traffic, native audits, timing traces and recovery rows remain retained. No historical evidence, registered parameter, protocol behavior, model, or dataset was changed. The two finalized research documents remain uncommitted for review; nothing was pushed.

Historical supporting documents remain unchanged and untracked in the original repository:

- docs/week6-tier1-v2-experiment-plan.md
- docs/week6-tier1-v2-implementation-validation.md
- docs/week6-tier1-v2-real-artifact-preflight.md
- docs/week6-tier1-v2-final-local-review.md

The Authentication-v2 specification remains at docs/authentication-v2-protocol-spec.md. The completed Reconstruction Alternatives Experiment and prior research hours were preserved.
