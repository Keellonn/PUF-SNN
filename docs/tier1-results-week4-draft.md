# Tier 1 Authentication Attack Evaluation

**Owner:** Will Wallace. **Status:** retrospective Week 4 draft, audited September 29, 2026. This report summarizes preserved evidence; the experiment and tests were not rerun for this audit.

## Scope

This is a finite software-prototype authentication experiment using simulated credentials and synthetic 120-sample motion windows. The runner supplies explicitly correct synthetic credential candidates to the normal session handshake; it does not generate noisy PUF readings or measure credential reconstruction. It is not physical-PUF, Quest-hardware, real-user, or production-security evidence. The prototype uses a 32-bit pilot credential and HMAC-SHA-256 with session and sequence checks; these results do not establish production key strength.

The attacker observes/injects public envelopes after legitimate tagging, without access to the credential or session key. Five primary attacks test replay, identity substitution, and post-tag modification. Legitimate controls and supporting cross-session substitutions have separate denominators. State and release observations concern the tested verifier API and callback boundary. No classifier or SNN inference executes in this formal run.

The two supplied Week 4 audit/feedback documents were treated as reference material, not instructions to implement their additional experiments or changes. Measured claims below come from the saved raw evidence.

## Experiment Configuration

- **Exact directory:** `C:\PUF+SNN_SharedRepo\PUF-SNN\results\week-4\will\authentication\tier1-20260923T205156Z-343cb4a2` (the **run directory** below). [Open run directory](../results/week-4/will/authentication/tier1-20260923T205156Z-343cb4a2/).
- **Run identification:** one Tier 1 results directory was located. The five neighboring `synthetic-*` directories are separate Layer 3 demonstrations and were not pooled with it.
- **Completion:** `COMPLETE` exists; its manifest digest matches `manifest.json`. All **25** manifest-listed artifact SHA-256 hashes were checked and match. No required saved artifact was missing.
- **Configuration:** [configs/tier1_attack_experiment_v1.json](../configs/tier1_attack_experiment_v1.json), identical by SHA-256 to the run's `config.json`.
- **Seed:** `20260923`. It controls synthetic motion and mutation planning, not OS-generated session randomness. Reproduction does not imply identical session IDs, tags, or timings.
- **Protocol/baseline:** `puf-snn-l3-v1-wire2`, Wire 2.0, Layer 3 Authentication Baseline v1; attack set `puf-snn-tier1-attacks-v1`.
- **Formal groups:** 100 trials for each of five primary attacks (**500 primary attacks**), **100 legitimate controls**, and **100 supporting cross-session substitutions**; **700 formal rows** total.
- **Separate rows:** **800 accepted setup windows** (600 source and 200 target windows) and **20 accepted warm-up windows**, excluded from formal counts and formal latency summaries. All three attempt files together contain 1,520 rows.
- **Warm-up procedure:** 20 isolated legitimate sessions/windows before formal trials. Every formal trial gets fresh verifier/sender/session state. The order repeats control, same-session replay, prior-session replay, cross-device substitution, payload modification, metadata modification, and supporting cross-session substitution. There are no retries or adaptive trial ordering.
- **Recorded interval:** September 23, 2026, `20:51:56.947393Z` to `20:52:16.667068Z`.
- **Environment:** Python 3.12.4, MSC v.1940 64-bit AMD64; `Windows-11-10.0.26200-SP0`; host `WillsPC`; Intel64 Family 6 Model 151 Stepping 2, GenuineIntel; 20 logical CPUs. Recorded packages: galois 0.4.11, numpy 2.5.3, jsonschema 4.26.0. These are historical metadata, not measurements of the audit environment. RAM and a commercial CPU model name are not recorded.
- **Timing:** `time.perf_counter_ns`, recorded resolution `1e-7` seconds; p95 uses linear interpolation at sorted index `0.95*(n-1)`. Saved units are ns; reported ms values divide by 1,000,000.
- **Source attribution:** the run manifest records file hashes, **not an execution Git commit or dirty-tree snapshot**. The audit checkout is `40da3a388983030b7b696ce7bf2b801e0ed6903f`. Git associates the runner's addition with `00c0f20c2b06d56392963510928880cde374ba4c`; neither commit is asserted to be the run revision. Exact recorded hashes appear under Reproducibility.

### Evidence verification

`reconciliation.json` reports `passed=true`, 700 scheduled/formal rows, 800 setup rows, 3,500 verifier audit records, 1,500 matched window audits, 1,000 session establishments, and 1,000 terminal session controls. It records `unexpected_behavior=false`, zero state-mutation violations, and zero payload-release violations. `manifest.json` embeds the same reconciliation. The before/after baseline snapshots are byte-identical and record 32 checked baseline files with no historical mismatches.

Read-only calculations independently checked scheduled trial IDs/order, unique attempt IDs, every formal/setup window-to-audit join, expected/observed decisions and reasons, latency agreement, complete before/after state snapshots, release callback outcomes, envelope/digest consistency, retained original tags, and exact recorded byte mutations. All 1,000 entries in `session-audit-map.json` join their establishment and terminal events. All seven summary/latency CSVs listed below agree with recalculations from saved rows/audits, including Wilson bounds and linearly interpolated p95. Warm-up acceptance was checked separately. This is internal consistency and integrity evidence, not third-party attestation.

Exact saved files used: `COMPLETE`, `manifest.json`, `metadata.json`, `config.json`, `plan.md`, `trial-plan.json`, `attempts.schema.json`, `attempts.jsonl`, `setup_attempts.jsonl`, `warmup_attempts.jsonl`, `audit.jsonl`, `sender/audit.jsonl`, `warmup/audit.jsonl`, `warmup/sender/audit.jsonl`, `session-audit-map.json`, `reconciliation.json`, `baseline-manifest.json`, `baseline-before.json`, `baseline-after.json`, `attack_summary.csv`, `control_summary.csv`, `supporting_summary.csv`, `variant_summary.csv`, `reason_summary.csv`, `latency_summary.csv`, `endpoint_latency_summary.csv`, and `audit-io.json`. Warm-up audit files were hash-verified; detailed window/audit joining concerned the formal/setup population.

## Primary Attack Results

Each row below means: **100/100 attacks were rejected in this experiment (100% observed rejection)**. Every primary group had 0/100 accepted attacks (**0% observed acceptance**), with the expected reason in all 100 trials. Latencies are verifier authentication latency in **milliseconds**, with 100 nonmissing values per row.

| Attack | Property tested | Trials | Accepted | Rejected | Observed reason | Observed rejection rate | Median latency | p95 latency | Max latency |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|
| Same-session replay | Freshness / duplicate sequence | 100 | 0 | 100 | `duplicate_sequence` | 100% | 2.825900 | 3.085100 | 3.356300 |
| Prior-session replay | Active-session binding | 100 | 0 | 100 | `inactive_session` | 100% | 0.892900 | 1.041710 | 3.787100 |
| Cross-device substitution | Integrity of protected device identity | 100 | 0 | 100 | `invalid_tag` | 100% | 0.906750 | 1.104675 | 1.218100 |
| Post-tag motion-payload modification | Motion-payload integrity | 100 | 0 | 100 | `invalid_tag` | 100% | 0.907450 | 1.039085 | 1.125800 |
| Post-tag protected-metadata modification | Protected sequence integrity | 100 | 0 | 100 | `invalid_tag` | 100% | 0.912950 | 1.088285 | 2.250200 |

Sources: all 700 lines of `attempts.jsonl`, selecting `is_primary=true`; cross-checked against `attack_summary.csv`, `reason_summary.csv`, and `latency_summary.csv`. Combined primary counts are 0 accepted and 500 rejected; no pooled heterogeneous-attack security interval is claimed.

The saved two-sided 95% Wilson rejection interval for **each** 100/100 primary group is **96.3006501793% to 100%**, using `z=1.959963984540054`. These are conditional descriptive binomial reference intervals. Fresh state per trial does not establish independent, identically distributed outcomes from a real attacker or hardware population: code, seed, fixture family, and fixed ordering are shared.

**Supporting result, separate from the five primary groups:** cross-session substitution was rejected 100/100 times with `invalid_tag` (100% observed rejection; 0% acceptance). Its saved Wilson rejection interval is also 96.3006501793% to 100%; median/p95/max verifier latency is **0.908000 / 1.073065 / 1.186300 ms**. Both devices first have accepted sequence-0 setup windows; the mutation replaces A's protected session ID with B's active session ID and updates the redundant envelope `key_id`, retaining the tag and A's device ID. State snapshots remain equal and callback count is zero in all 100 cases. This case is not a same-device replacement-session replay.

## Legitimate Control Results

The formal controls accepted **100/100 valid windows (100% observed acceptance)** and rejected **0/100**, giving **0% observed valid-message false-rejection rate**. Each used a correctly tagged sequence-0 message in a fresh active session, with valid quality and device/session binding. All had authentication/order `pass/pass`, one exact-payload callback, accepted count 0 to 1, and last accepted sequence null to 0.

Verifier latency, n=100: **median 2.828100 ms; p95 3.119715 ms; maximum 3.193400 ms**. The saved Wilson interval is for **acceptance**, 96.3006501793% to 100%. Its complementary FRR interval is **0% to 3.6993498207%**, reproducibly derived by subtracting the saved acceptance bounds from 1; that FRR interval is not a separately saved CSV field.

This conditional valid-message Tier 1 FRR is **not Layer 2 PUF reconstruction FRR**. Correct credential candidates are supplied; reconstruction failures and miscorrections never enter this control denominator. The 800 setup accepts and 20 warm-up accepts do not enlarge the formal control denominator.

## Attack Details

The runner's current bytes match its recorded historical SHA-256, so its fixture/mutation semantics can be inspected without executing it. Saved original/submitted envelopes independently confirm the operations. For every primary rejection, the complete recorded session-state snapshot remains unchanged and the attempted release returns `acceptance_required` with zero callbacks. The snapshots cover session lifecycle, accepted count, last accepted sequence, deadline, owner, terminal information, and active-device mappings; audit logging itself does change.

### Same-session replay

Starting state: `sim-tier1-A` has an active session and an already accepted, correctly tagged sequence-0 window; accepted count is 1, last accepted is 0, and the expected next sequence is 1. The attacker resubmits the complete envelope byte-for-byte, including the original tag. The expected defense is duplicate detection after valid HMAC verification. All 100 observations have authentication `pass`, order `duplicate`, and reason `duplicate_sequence`. Accepted count stays 1 and last accepted stays 0, so expected next sequence remains 1. No payload is released.

### Prior-session replay

Starting state: A's original sequence-0 window was accepted during setup. Normal authenticated replacement then closes that session with a `session_replaced` tombstone and activates a new session for A, with accepted count 0 and last accepted null. The attacker replays the unchanged old envelope. The expected defense is inactive-session lookup, before HMAC/order processing. All 100 observations report `inactive_session`, authentication `not_checked`, and order `not_checked`. The old tombstone and new active session remain unchanged; the new session still expects sequence 0. Closed-session count/sequence fields are null in the snapshots, not zero. No payload is released. This population uses replacement, not session expiration.

### Cross-device substitution

Starting state: independently provisioned A and B each have an active session and an accepted sequence-0 setup window. The attacker changes only the protected device identifier from equal-length `sim-tier1-A` to registered `sim-tier1-B`, retaining A's session ID and original tag. HMAC covers the changed identity bytes. All 100 observations report `invalid_tag`, authentication `fail`, and order `not_checked`; both sessions retain accepted count 1 and last accepted 0. No payload is released. This demonstrates post-tag identity substitution rejection, not a wrong-device PUF reconstruction experiment or a correctly re-tagged wrong-owner attack.

### Post-tag motion-payload modification

Starting state: A has already accepted the original sequence-0 window and expects sequence 1. The attacker XORs one planned mantissa bit (0 through 22) of one binary32 position component in one of the 120 samples; all other authenticated bytes and the original tag are retained. Across the population, all three position components and all 23 eligible mantissa-bit positions occur. The expected defense is HMAC failure before quality/order processing. All 100 observations report `invalid_tag`, authentication `fail`, and order `not_checked`. Accepted count stays 1 and last accepted stays 0. No payload is released. These are specific single-bit position mutations, not exhaustive motion-field corruption.

### Post-tag protected-metadata modification

Starting state: A has already accepted sequence 0 and expects sequence 1. The attacker changes only the protected 64-bit sequence number **0 to 1** and retains the original tag. All 100 observations report `invalid_tag`, authentication `fail`, and order `not_checked`, as expected from HMAC integrity checking before ordering. Accepted count stays 1, last accepted stays 0, and expected next sequence remains 1. No payload is released. The modified value is the next expected sequence, **not a high/future gap**; this formal group must not be labeled a high-sequence poisoning evaluation.

## State-Safety Results

### A. Experimentally measured in the formal Tier 1 run

- All **500 primary** and **100 supporting** rejections preserve their complete immediate before/after state snapshots. All 600 have zero state-mutation violations. Same-session replay specifically preserves expected next sequence 1; payload/metadata changes do not advance it; old-session replay does not change the replacement session's active state.
- All **600 rejected formal attempts** actually attempt `release_accepted`, return `acceptance_required`, and record **zero callbacks** and no released payload. The 100 formal controls release exactly one matching authenticated window each.
- The callback is `released.append`, not a classifier. `payload_reached_inference=False` is assigned unconditionally by the runner because it does not instantiate inference. Thus the measured result is **no accepted-payload release for rejected traffic in the tested path**, not direct measurement of zero SNN invocations in an end-to-end deployment.
- Each attack fixture ends after its formal submission and cleanup. Independent controls show valid traffic works in fresh sessions; they do **not** measure a valid continuation after rejection in the same fixture. High/future sequence gaps, stale sequence below last accepted, malformed messages, failed confirmation, and expiration are not separate formal attack populations here. An old *session* replay is measured, but it is distinct from a stale *sequence* in an active session.

### B. Tested in unit/integration tests only

The following claims come from inspection of existing test assertions and saved passing output, not new execution or formal-population results. [tests/auth/test_verifier.py](../tests/auth/test_verifier.py) uses a shared `check()` helper asserting unchanged session status and no accepted payload/bytes on rejection:

- `test_duplicate` and `test_stale`: duplicate and stale sequence rejection with preserved session status.
- `test_gap_and_late_missing_no_automatic_reconsideration`: sequence 2 is rejected while 0 is expected; sequence 0 then succeeds; 2 is rejected while 1 is expected; 1 then 2 succeed. A gap does not advance state or automatically queue/reconsider the rejected window.
- `test_u64_max_is_gap_without_wrap`: correctly tagged sequence `2**64-1` is rejected as `future_sequence_gap` without changing state.
- `test_invalid_tag_high_sequence_cannot_poison`: sequence 999999 with an invalid tag is rejected without state mutation, then valid sequence 0 succeeds. `test_stale_tag_on_protected_mutations` separately exercises sequence 999999 and other changed protected fields with the original tag.
- `test_malformed_inputs_leave_state`: malformed input variants leave session status unchanged.
- `test_replacement_new_sequence_zero_old_cannot_reset`: an old-session packet is rejected after replacement, and valid sequence 0 in the new session succeeds.

Saved evidence: [results/week-4/keegan/test-evidence/full-python-suite.txt](../results/week-4/keegan/test-evidence/full-python-suite.txt), lines 131, 134, 136, 140, 143, 147, 148, and 152 mark these tests `ok`; lines 359 and 361 record 322 tests and `OK`. That historical suite output is not a fresh certification of the current checkout and does not identify an exact generating command/environment.

[tests/auth/test_classifier_integration.py](../tests/auth/test_classifier_integration.py), `SharedEndToEndTests.reject_without_delivery`, explicitly checks zero classifier-stub calls and unchanged session state after failed delivery. Cases include modified payload, invalid HMAC, exact replay, future gap, unknown device/session, low quality, and malformed input. A positive test delivers exact authenticated payload once. [results/week-4/keegan/test-evidence/classifier-integration-tests.txt](../results/week-4/keegan/test-evidence/classifier-integration-tests.txt) records all 12 tests passing. This is stronger evidence about an actual classifier wrapper than the formal run's collector callback, but remains integration-test evidence.

Therefore, selected high/future-sequence poisoning and valid-after-rejection behavior are supported by tests; they are not 100-trial formal Tier 1 findings. These assertions do not establish universal desynchronization resistance, durability across restarts, or invalid-traffic rate limiting.

## Audit Examples

Locations below are **one-based JSONL line numbers**, relative to the exact run directory above. These are representative first occurrences, not latency extremes. Packet-supplied identity fields on a failed HMAC are observations, not authenticated identity claims.

### Accepted legitimate control

- `attempts.jsonl:1`, trial `trial-00000`; corresponding **`audit.jsonl:2`**, event `07a5ff1ec1fb706960e2dbcafdc1f528:2`, recorded UTC `2026-09-23T20:52:01.241425Z`.
- Device `sim-tier1-A`; session `7198373ea8874e386abec232a37a0492`; window `trial-00000.source-window`; sequence 0; identity authenticated `true`.
- Decision/reason `accept/accepted`; authentication/order `pass/pass`; audit expected sequence 0, last accepted null to 0, lifecycle `ACTIVE` to `ACTIVE`. Linked attempt snapshots show accepted count 0 to 1 and unchanged deadline `20880937000000` ns; one exact-payload callback.
- `latency_ns.verifier_auth=2755600` (**2.755600 ms**). The other audit latency fields (reconstruction, session establishment, KDF, sender preparation/HMAC, audit I/O) are null in this window record; null is not zero or a claim that the stage was measured here.

### Same-session replay rejection

- `attempts.jsonl:2`, trial `trial-00001`; corresponding **`audit.jsonl:6`**, event `3085eb2707e93b1f5369b3831b6063c7:3`, recorded UTC `2026-09-23T20:52:01.258431Z`.
- Device `sim-tier1-A`; session `a7e33a5a549ae4733dc77f00c95c1252`; window `trial-00001.source-window`; sequence 0; identity authenticated `true`.
- Decision/reason `reject/duplicate_sequence`; authentication `pass`, order `duplicate`; expected sequence 1, last accepted 0 to 0, lifecycle `ACTIVE` to `ACTIVE`. Linked snapshots retain accepted count 1 and deadline `20880953000000` ns; zero callbacks and release error `acceptance_required`.
- `latency_ns.verifier_auth=3068000` (**3.068000 ms**); all other latency fields in this audit record are null.

### Invalid-tag rejection after payload modification

- `attempts.jsonl:5`, trial `trial-00004`; corresponding **`audit.jsonl:23`**, event `8e4d649516d338ad1ed6736c3bcc1c7e:3`, recorded UTC `2026-09-23T20:52:01.325430Z`.
- Observed device `sim-tier1-A`; session `d1b88a18a192622ed107d7e004320de4`; window `trial-00004.source-window`; sequence 0; identity authenticated `false`.
- The linked attempt records zero-based sample 51, position component 2, mantissa bit 15, authenticated-byte offset 2122: word `3e104cf6` becomes `3e10ccf6`, with the original tag retained.
- Decision/reason `reject/invalid_tag`; authentication `fail`, order `not_checked`; lifecycle `ACTIVE` to `ACTIVE`. Audit expected/last-accepted fields and authenticated-byte digest are null because identity was not authenticated. The **separate trusted fixture snapshots** show accepted count 1, last accepted 0, and deadline `20881015000000` ns unchanged; zero callbacks and `acceptance_required`.
- `latency_ns.verifier_auth=946900` (**0.946900 ms**); all other latency fields in this audit record are null.

## Interpretation

The implemented historical verifier rejected the tested replay, substitution, and post-tag modification cases in this finite software experiment. All 500 primary attacks and 100 supporting substitutions matched their expected reason codes, without observed accepted-state mutation or accepted-payload release. The separate 100 legitimate controls demonstrate successful valid-message processing under the experiment's supplied-correct-credential conditions.

HMAC and state checks perform different roles: an unchanged same-session replay passes HMAC but fails duplicate detection; an old replaced-session replay is rejected by lifecycle lookup before HMAC; changed protected identity, motion, and sequence bytes fail HMAC before ordering. Faster median rejection latency for early-exit cases is consistent with those recorded paths; these data do not separately time HMAC verification versus each state check or establish a causal stage-cost decomposition.

### Timing interpretation

For 100 formal controls, sender preparation median/p95/max is **2.213750 / 2.449960 / 2.502000 ms**; its included HMAC-generation timing is **0.012000 / 0.016410 / 0.059700 ms**. Per-window `total_layer3_ns = sender_prepare_ns + verifier_auth_ns` has median/p95/max **5.104350 / 5.302070 / 5.459500 ms**. HMAC must not be added again; total percentiles are calculated from paired per-window totals, not sums of percentile values.

For the 600 formal rejected attempts (including support), verifier median/p95/max is **0.918950 / 2.907740 / 3.787100 ms**. These pooled figures describe this particular mixture of attack paths. Attack sender preparation, sender HMAC, and paired Layer 3 total fields are **null for all 600**, deliberately excluded by the saved plan. Their absence is not a zero measurement or evidence of end-to-end rejected latency.

`endpoint_latency_summary.csv` separately includes formal fixtures **and setup**, excludes warm-up, and is not a 700-formal-row summary. Sender session establishment has n=1,000, median/p95/max **0.202350 / 0.265310 / 0.474500 ms**. Sender KDF has n=1,000, **0.005400 / 0.006300 / 0.072800 ms**; verifier KDF has n=1,000, **0.011600 / 0.014700 / 0.091200 ms**. The endpoint verifier population has 1,500 windows and a **30.388200 ms** maximum; the endpoint sender-preparation population has 900 windows and a **31.721000 ms** maximum. Those setup-inclusive maxima are retained, not silently substituted for formal maxima or discarded as outliers.

The saved plan defines verifier timing as returned `verifier_auth_ns`, not an external timer. Setup, mutation, harness hashing/validation, release, and disk writes are outside it. `audit-io.json` records batch-only I/O (700 batches per formal endpoint and 20 per warm-up endpoint); it cannot supply a per-window audit-I/O latency by assumption. Reconstruction, independent credential verification, capture/network transport, preprocessing/classification, and a full accepted/rejected authentication-plus-inference pipeline are not measured by these formal totals. No performance-target verdict is recorded (`performance_target_verdict=null`).

### Documentation reconciliation

- The supplied repository audit's Tier 1 counts, reasons, and verifier median/p95/max values agree with the raw evidence. The supplied research feedback's statement that formal results are still needed is addressed by reporting this existing run; it is not evidence that the run is absent.
- [docs/puf-tier1-attacks.md](puf-tier1-attacks.md) describes methods and expected outputs, not this run's measured table. [docs/research-logs/will.md](research-logs/will.md) likewise describes implementation and leaves formal analysis under “Plans for next week.” Their stated configuration/reason expectations agree with the run; the reporting gap is omitted numerical evidence, not a conflicting outcome count.
- Broad references to inference must be qualified: the formal runner tests the release boundary, while classifier-call assertions live in separate integration tests. Protected metadata here is sequence 0 to 1, not high/future-sequence poisoning. Prior-session replay means authenticated replacement, not expiration.
- The saved plan expressly justifies 100/group as a bookkeeping/order pilot, **not a power calculation**. Feedback asks for at least 1,000 or a justified smaller initial count; whether this pilot justification is sufficient remains a research-review decision.
- Current baseline/versioning has drifted. Direct hash comparison finds **two missing baseline files and five baseline hash mismatches**; the historical snapshots remain internally intact. The experiment-specific plan is also missing from current `docs/`, while its saved `plan.md` survives. Current Tier 1 schema bytes differ from the saved schema, although parsing both JSON files produces equal objects. Byte-hash mismatch alone must not be described as a demonstrated semantic change.

## Limitations

- Only 100 trials per primary group, one seed, one deterministic implementation/fixture family, and a fixed group order were evaluated. The saved Wilson bounds do not establish hardware/attacker population independence, universal security, or proof against all attacks.
- Synthetic software only: no physical PUF, no actual noisy reconstruction in this run, no real Quest traffic, and no real-user robustness or physical-device performance claim. The pilot credential is not a production-strength long-term secret.
- Timing is workstation/Python timing, includes retained slow observations, and must not be generalized to Quest, FPGA, embedded deployment, or network behavior. There is no full inference-pipeline timing in this run and no formal target verdict.
- Mutation coverage is narrow: one device-ID replacement, single position mantissa-bit changes, and sequence 0 to 1. Session replay is replacement-based. The attacker does not know the session key.
- High/future sequence injection, stale active-session sequence, malformed input, and valid-after-rejection recovery have selected unit/integration tests rather than formal 100-trial populations. Release callback blocking is measured formally; classifier-stub blocking is tested separately. These results do not establish rate limiting or comprehensive denial-of-service resistance.
- Historical provenance is file-hash based; no exact execution Git revision/dirty-tree state is saved, and the output directory does not contain a complete historical source archive. Matching manifest hashes demonstrate consistency within the preserved evidence, not independent authenticity.
- The run is Git-ignored. This audit does not establish an external backup location. Existing evidence is preserved in place; no archive, baseline update, or replacement experiment was created.

## Reproducibility

Use only the run directory identified above for these numerical results. The authoritative configuration/plan/schema copies are `config.json`, `plan.md`, `trial-plan.json`, and `attempts.schema.json`; raw formal evidence is `attempts.jsonl`. Use `setup_attempts.jsonl` and `warmup_attempts.jsonl` separately. Join window rows to `audit.jsonl` using `audit_event_id` and session endpoints through `session-audit-map.json`; sender timing comes from `sender/audit.jsonl`. Reconciliation is `reconciliation.json`. Summaries are the seven `*_summary.csv` files enumerated under Experiment Configuration. `manifest.json` hashes artifacts; `COMPLETE` hashes that manifest. Preserve both baseline snapshots and `baseline-manifest.json`.

Recorded SHA-256 values:

- `manifest.json` (referenced by `COMPLETE`): `c49efb9cd4627f8084cff24ed93331055b2baed54d0e45fe7b4d1d88e31541e2`.
- Configuration: `aaecc3326f5e5725651f45178594ef1dbb01e037af7ee6fb0ca08a5256761da9`.
- Baseline manifest: `1035a63dde8b2ead202293f98f0b6a3b458021537bd378611856441627d368b7`.
- Both baseline snapshots: `ec38f41a2dfe1b9c0dc938e8250593d506bbdbfada3d0067935166bea111cedd`.
- `attempts.jsonl`: `4ab11312941e7060e099250b843f5db1311d270585118aa7630b56e66a66475c`.
- `audit.jsonl`: `b23f630495226bafbef140808e82537c44adde309ec8e1ab16a6b9469aa71be2`.
- `src/python/scripts/run_tier1_attacks.py`: `01e233e605c500f2b32befc745f8a0923c3fc2f5c8723f78a5dde086d4477101` (current bytes match).
- `run_tier1.ps1`: `8b0b6f26d19814dff4ca47993b5cc25a534515ef7cd1f8acf06698d5231866fa` (current bytes match).
- `schemas/tier1-attempt-v1.schema.json`: `5473465150a7459aa8c0093c4393679291146e7376826770342baad3ea028243` (saved `attempts.schema.json` matches; current schema bytes do not).
- `tests/tier1/test_tier1.py`: `7518520e457dc62f9326fe05c7b337063b88425d9e513c99d78807535309d99a` (current bytes match).
- `docs/tier1-attack-experiment-plan.md`: `185b1544ccc8032670da58288d4c48034aab13f09a19e18bbe5248b1c09e529b` (saved `plan.md` matches; current source path is absent).

All 32 historical baseline source hashes are retained in `baseline-before.json`, `baseline-after.json`, `baseline-manifest.json`, and `metadata.json`. Direct comparison with the current checkout finds these missing baseline paths: `docs/authentication-v1.md` and `docs/layer3-final-status-and-tier1-handoff.md`. Current hashes differ for `schemas/auth-audit-v1.schema.json`, `schemas/authenticated-window-v2.schema.json`, `src/python/puf_snn/auth/audit.py`, `src/python/puf_snn/auth/session.py`, and `src/python/puf_snn/auth/verifier.py`. Consequently, the current checkout does not satisfy the historical runner's baseline check. The check was inspected and its hashes compared directly; the runner was not invoked. The first-add commit is not a verified byte-exact substitute for the recorded historical baseline.

The recorded original command in `metadata.json` is reproduced **for provenance only; it was not executed for this audit**:

```text
C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe -B src/python/scripts/run_tier1_attacks.py --config configs/tier1_attack_experiment_v1.json
```

For a read-only numerical spot-check from the repository root, this standard-library snippet reads saved evidence and prints hashes/counts/latencies without importing the runner, performing authentication, or writing results:

```python
from pathlib import Path
import collections, hashlib, json, math, statistics

run = Path("results/week-4/will/authentication/tier1-20260923T205156Z-343cb4a2")
load = lambda name: json.loads((run / name).read_text(encoding="utf-8"))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = load("manifest.json")
assert sha(run / "manifest.json") == load("COMPLETE")["manifest_sha256"]
assert all(sha(run / name) == expected
           for name, expected in manifest["files"].items())
rows = [json.loads(line) for line in
        (run / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(rows) == load("reconciliation.json")["formal_rows"] == 700
for kind in dict.fromkeys(row["attack_type"] for row in rows):
    group = [row for row in rows if row["attack_type"] == kind]
    values = sorted(row["verifier_auth_ns"] for row in group)
    index = 0.95 * (len(values) - 1)
    lo, hi = math.floor(index), math.ceil(index)
    p95 = values[lo] + (values[hi] - values[lo]) * (index - lo)
    outcomes = collections.Counter((row["actual_decision"], row["actual_reason"])
                                   for row in group)
    print(kind, len(group), dict(outcomes), "median/p95/max ms:",
          statistics.median(values) / 1e6, p95 / 1e6, max(values) / 1e6)
```

**Rerun assessment:** no evidence-integrity or numerical discrepancy found requires rerunning this historical experiment. A separately authorized future evaluation could expand trial counts, formalize high/future/stale/malformed and continuation populations, or measure an inference pipeline under a new explicitly versioned baseline. Such work would answer additional questions, not repair or overwrite this completed run. No experiment, tests, authentication implementation, historical baseline, evidence file, or research-log entry was modified or regenerated for this report.
