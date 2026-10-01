# Tier 1 Authentication Attack Evaluation

**Owner:** Will Wallace
**Week:** 5
**Status:** Complete

## Experiment Configuration

The Tier 1 authentication experiment was originally executed on September 23, 2026. During Week 5, I audited the preserved evidence, reconciled the raw results, verified the manifest and completion records, and converted the existing experiment into a formal results report.

The experiment contained five primary attack groups with 100 trials per attack, plus 100 legitimate controls and 100 supporting cross-session substitutions.

- Primary attacks: 500 trials
- Legitimate controls: 100 trials
- Supporting substitutions: 100 trials
- Total formal trials: 700
- Separate setup windows: 800
- Separate warm-up windows: 20
- Experiment seed: 20260923
- Authentication baseline: `puf-snn-l3-v1-wire2`
- Wire format: Wire 2.0
- Attack set: `puf-snn-tier1-attacks-v1`

The formal run is stored at:

`results/week-4/will/authentication/tier1-20260923T205156Z-343cb4a2/`

The saved `COMPLETE` marker, `manifest.json`, and `reconciliation.json` all passed verification. All 25 manifest-listed artifact hashes matched their preserved files.

This experiment used synthetic software-generated motion windows and supplied-correct credential candidates. It did not evaluate noisy PUF reconstruction, physical PUF hardware, real Quest traffic, or classifier/SNN inference.

## Primary Attack Results

Each primary attack group contained 100 trials. All five primary groups produced 0 accepted attacks and 100 rejected attacks, giving 500/500 observed primary attack rejections.

| Attack | Trials | Accepted | Rejected | Observed Reason | Rejection Rate | Median Latency | p95 Latency | Maximum Latency |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| Same-session replay | 100 | 0 | 100 | `duplicate_sequence` | 100% | 2.8259 ms | 3.0851 ms | 3.3563 ms |
| Prior-session replay | 100 | 0 | 100 | `inactive_session` | 100% | 0.8929 ms | 1.0417 ms | 3.7871 ms |
| Cross-device substitution | 100 | 0 | 100 | `invalid_tag` | 100% | 0.9068 ms | 1.1047 ms | 1.2181 ms |
| Post-tag motion-payload modification | 100 | 0 | 100 | `invalid_tag` | 100% | 0.9075 ms | 1.0391 ms | 1.1258 ms |
| Post-tag protected-metadata modification | 100 | 0 | 100 | `invalid_tag` | 100% | 0.9130 ms | 1.0883 ms | 2.2502 ms |

A separate supporting cross-session substitution population was also rejected 100/100 times with `invalid_tag`.

For each group with 100/100 expected outcomes, the saved two-sided 95% Wilson interval was approximately 96.30% to 100%. These are finite experimental observations and are not evidence of universal attack rejection.

## Legitimate Control Results

All 100/100 legitimate control windows were accepted.

- Accepted: 100
- Rejected: 0
- Observed valid-message false-rejection rate: 0%
- Median verifier latency: 2.8281 ms
- p95 verifier latency: 3.1197 ms
- Maximum verifier latency: 3.1934 ms

The saved Wilson interval for the valid-message acceptance proportion was approximately 96.30% to 100%.

This Tier 1 control result applies only to Layer 3 traffic supplied with a correct credential candidate. It does not include Layer 2 PUF reconstruction failures and should not be confused with the Layer 2 reconstruction FRR.

## Attack Details

### Same-session replay

Starting state: `sim-tier1-A` has an active session and an already accepted, correctly tagged sequence-0 window; accepted count is 1, last accepted is 0, and the expected next sequence is 1.

The attacker resubmits the complete envelope byte-for-byte, including the original tag. The expected defense is duplicate detection after valid HMAC verification.

All 100 observations have authentication `pass`, order `duplicate`, and reason `duplicate_sequence`.

Accepted count stays 1 and last accepted stays 0, so expected next sequence remains 1. No payload is released.

### Prior-session replay

Starting state: A's original sequence-0 window was accepted during setup. Normal authenticated replacement then closes that session with a `session_replaced` tombstone and activates a new session for A, with accepted count 0 and last accepted null.

The attacker replays the unchanged old envelope. The expected defense is inactive-session lookup before HMAC or ordering processing.

All 100 observations report `inactive_session`, authentication `not_checked`, and order `not_checked`.

The old tombstone and new active session remain unchanged, and the new session still expects sequence 0. No payload is released.

This population uses authenticated session replacement rather than session expiration.

### Cross-device substitution

Starting state: independently provisioned A and B each have an active session and an accepted sequence-0 setup window.

The attacker changes only the protected device identifier from `sim-tier1-A` to `sim-tier1-B`, retaining A's session ID and original authentication tag.

Because the device identity is included in the authenticated bytes, the modified message no longer matches the original HMAC.

All 100 observations report `invalid_tag`, authentication `fail`, and order `not_checked`.

Both sessions retain accepted count 1 and last accepted sequence 0. No payload is released.

This demonstrates rejection of post-tag device-identity substitution. It is not a wrong-device PUF reconstruction experiment and does not test an attacker capable of generating a valid new tag.

### Post-tag motion-payload modification

Starting state: A has already accepted the original sequence-0 window and expects sequence 1.

The attacker XORs one planned mantissa bit from one binary32 position component in one of the 120 samples. All other authenticated bytes and the original tag are retained.

Across the 100-trial population, all three position components and all 23 eligible mantissa-bit positions are represented.

The expected defense is HMAC failure before quality or ordering processing.

All 100 observations report `invalid_tag`, authentication `fail`, and order `not_checked`.

Accepted count stays 1 and last accepted stays 0. No payload is released.

These are controlled single-bit motion mutations rather than exhaustive corruption of every possible motion field.

### Post-tag protected-metadata modification

Starting state: A has already accepted sequence 0 and expects sequence 1.

The attacker changes only the protected 64-bit sequence number from 0 to 1 while retaining the original authentication tag.

All 100 observations report `invalid_tag`, authentication `fail`, and order `not_checked`.

Accepted count stays 1, last accepted remains 0, and expected next sequence remains 1. No payload is released.

The modified value is the next expected sequence, not a high/future sequence gap. Therefore, this group should not be described as a formal high-sequence poisoning experiment.

## State-Safety Results

Across the 500 primary attack rejections and 100 supporting substitution rejections, all 600 rejected formal attempts preserved their recorded verifier state.

No rejected attempt:

- advanced the accepted sequence number,
- changed accepted-count state,
- replaced or activated a session,
- modified the expected next sequence,
- or produced an accepted-payload release.

All 600 rejected attempts reached the accepted-payload release guard and were denied with zero release callbacks.

The 100 legitimate controls each produced one accepted payload release.

The formal Tier 1 runner used a collector callback at the release boundary rather than an actual classifier or SNN. Therefore, the formal result demonstrates that rejected traffic did not cross the accepted-payload release boundary. Separate integration tests provide evidence that classifier calls are also blocked after authentication failure.

High/future sequence poisoning, stale active-session sequences, malformed inputs, and selected valid-after-rejection recovery cases were exercised in unit or integration tests rather than as separate 100-trial formal populations.

### Accepted legitimate control

A representative legitimate control was accepted with:

- Decision: `accept`
- Reason: `accepted`
- Authentication: `pass`
- Ordering: `pass`
- Sequence: 0
- Previous last accepted sequence: null
- New last accepted sequence: 0
- Accepted count transition: 0 to 1
- Payload release callbacks: 1
- Verifier authentication latency: 2.7556 ms

The accepted payload matched the authenticated source payload.

### Same-session replay rejection

A representative same-session replay was rejected with:

- Decision: `reject`
- Reason: `duplicate_sequence`
- Authentication: `pass`
- Ordering: `duplicate`
- Submitted sequence: 0
- Expected sequence: 1
- Last accepted sequence before rejection: 0
- Last accepted sequence after rejection: 0
- Accepted count remained: 1
- Payload release callbacks: 0
- Release result: `acceptance_required`
- Verifier authentication latency: 3.0680 ms

This example demonstrates that a byte-for-byte valid replay can pass authentication but still fail the freshness/ordering check without changing verifier state.

### Invalid-tag rejection after payload modification

A representative motion-payload mutation changed one bit in a binary32 position value while retaining the original authentication tag.

The attempt was rejected with:

- Decision: `reject`
- Reason: `invalid_tag`
- Authentication: `fail`
- Ordering: `not_checked`
- Accepted count unchanged: 1
- Last accepted sequence unchanged: 0
- Payload release callbacks: 0
- Release result: `acceptance_required`
- Verifier authentication latency: 0.9469 ms

Because authentication failed, ordering was never evaluated and the modified payload was never accepted.

## Interpretation

The implemented historical verifier rejected the tested replay, substitution, and post-tag modification cases in this finite software experiment.

All 500 primary attacks and 100 supporting substitutions matched their expected reason codes without observed accepted-state mutation or accepted-payload release.

The separate 100 legitimate controls demonstrate successful valid-message processing under the experiment's supplied-correct-credential conditions.

HMAC and state checks perform different roles:

- An unchanged same-session replay passes HMAC but fails duplicate detection.
- An old replaced-session replay is rejected by session-lifecycle lookup before HMAC processing.
- Changed protected device identity, motion payload, and sequence bytes fail HMAC verification before ordering checks.

The different rejection paths also explain the observed timing differences. Early-exit paths such as inactive-session lookup and invalid-tag rejection generally complete faster than valid traffic or duplicate replay processing.

These measurements do not independently isolate the cost of every individual internal check and should not be interpreted as a causal stage-by-stage performance decomposition.

### Timing Interpretation

Verifier latency was measured separately for each formal attack and control group.

The five primary attack groups had median verifier latency ranging from approximately 0.89 ms to 2.83 ms.

Same-session replay was slower than most invalid-tag attacks because the replay still passes HMAC verification and reaches the ordering check.

Prior-session replay is rejected earlier because the referenced session is already inactive.

For 100 legitimate controls:

- Sender preparation median: 2.21375 ms
- Sender preparation p95: 2.44996 ms
- Sender preparation maximum: 2.50200 ms
- Verifier median: 2.82810 ms
- Verifier p95: 3.11972 ms
- Verifier maximum: 3.19340 ms

The paired sender-preparation plus verifier-authentication latency for legitimate controls was:

- Median: 5.10435 ms
- p95: 5.30207 ms
- Maximum: 5.45950 ms

These values are Layer 3 software timing only.

They exclude:

- PUF acquisition,
- noisy credential reconstruction,
- independent credential verification added later in Week 5,
- network transport,
- motion preprocessing,
- classifier/SNN inference,
- and persistent audit-storage overhead.

Attack-side paired sender-plus-verifier totals were not recorded and should not be treated as zero.

### Documentation Reconciliation

Week 5 did not create a new Tier 1 attack population. Instead, the preserved September 23 experiment was audited and formally reported.

The saved raw evidence agrees with the expected attack behavior documented in the Tier 1 experiment plan.

The primary reporting gap before Week 5 was not missing attack execution, but missing formal presentation of:

- observed accepted/rejected counts,
- reason-code distributions,
- finite-sample uncertainty,
- per-attack latency,
- state-safety behavior,
- audit examples,
- and reproducibility information.

The historical Tier 1 experiment belongs to the frozen Layer 3 Authentication Baseline v1.

The current repository now contains the newer authentication-v2 credential-admission implementation. Therefore, these Tier 1 results must remain attributed to the preserved historical v1 experiment and should not be described as a fresh evaluation of the current v2 source.

The formal experiment used 100 trials per attack group. Whether a later study should expand to at least 1,000 trials per group remains a faculty/scope decision.

## Limitations

- Only 100 trials per primary group, one experiment seed, one deterministic implementation/fixture family, and a fixed group order were evaluated. The saved Wilson intervals do not establish hardware or attacker-population independence, universal security, or proof against all attacks.
- The experiment is synthetic software only. It includes no physical PUF, no actual noisy credential reconstruction, no real Quest traffic, and no real-user or physical-device performance evaluation.
- The supplied credential is a proof-of-mechanism pilot credential and should not be interpreted as production-strength secret material.
- Timing is workstation/Python software timing and should not be generalized to Quest hardware, FPGA implementation, embedded deployment, or network timing.
- No full acquisition-to-inference latency was measured in this experiment.
- Mutation coverage is intentionally narrow: one device-identity substitution pattern, single-bit position mutations, and sequence modification from 0 to 1.
- The prior-session replay population uses authenticated session replacement rather than expiration.
- The attacker does not possess the session key and therefore cannot generate a valid replacement HMAC.
- High/future sequence injection, stale active-session sequences, malformed input, and selected valid-after-rejection recovery behavior were tested separately rather than as formal 100-trial populations.
- Accepted-payload release blocking is measured formally, but the formal attack runner does not execute a real classifier or SNN.
- These results do not establish rate limiting or comprehensive denial-of-service resistance.
- Historical provenance is primarily file-hash based. The experiment does not record an exact execution Git commit or complete historical source archive.
- Matching manifests and hashes demonstrate consistency of the preserved experiment evidence, not independent third-party authenticity.
- The historical Tier 1 run is Git-ignored and should be preserved separately. It must not be overwritten by a current-profile rerun.

## Reproducibility

Primary preserved experiment directory:

`results/week-4/will/authentication/tier1-20260923T205156Z-343cb4a2/`

Important raw evidence:

- `attempts.jsonl`
- `setup_attempts.jsonl`
- `warmup_attempts.jsonl`
- `audit.jsonl`
- `sender/audit.jsonl`
- `session-audit-map.json`

Important summaries:

- `attack_summary.csv`
- `control_summary.csv`
- `supporting_summary.csv`
- `variant_summary.csv`
- `reason_summary.csv`
- `latency_summary.csv`
- `endpoint_latency_summary.csv`

Integrity and provenance:

- `config.json`
- `plan.md`
- `trial-plan.json`
- `metadata.json`
- `reconciliation.json`
- `baseline-manifest.json`
- `baseline-before.json`
- `baseline-after.json`
- `manifest.json`
- `COMPLETE`

Repository configuration used by the historical experiment:

`configs/tier1_attack_experiment_v1.json`

The command recorded for the original experiment was:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/run_tier1_attacks.py --config configs/tier1_attack_experiment_v1.json