# Authentication-v2 Tier-1 Security Evaluation v1

**Status:** Design and preregistration specification only; no new attack results.  
**Plan date:** October 6, 2026 (America/New_York).  
**Experiment ID:** `authentication-v2-tier1-security-evaluation`; **version:** `1`.  
**Owner:** Will Wallace. **Proposed first run:** `tier1-v2-formal-001`.

## 1. Experiment identity and source baseline

The inspected branch is `main`; HEAD is `78f499a92f633a4793c776a070058e3a6a9a0b61` (`Add fresh v2 composite timing runner and instrumentation`). HEAD equals the implementation baseline of [Authentication v2 Protocol and Trust Specification](authentication-v2-protocol-spec.md), which was read in full. There are **no intervening commits and no working-tree differences in `src`, `tests`, or `configs` against that baseline**. No authentication, credential-admission, session, verifier, integration, inference, or timing behavior changed after the specification baseline in this checkout.

At inspection, `docs/research-logs/will.md` was modified and these documents were untracked: `docs/authentication-v2-protocol-spec.md`, `docs/week6-start-current-repo-audit.md`, and `docs/week6-v2-protocol-spec-prep.md`. They are existing user work, not changes made for this plan. Git's ownership check required a command-local `safe.directory` option; no global Git setting was changed. No applicable `AGENTS.md` was found in the workspace/parent paths or the target documentation directory.

Exact-byte SHA-256 anchors at design time:

| File | SHA-256 |
|---|---|
| `docs/authentication-v2-protocol-spec.md` | `2f6dc6b3a3dd74d8952ae1daeea4aec2d435c433e093ef031e7ff0cad3c943f9` |
| `configs/authentication_v2.json` | `b0ee45b8a3ee5cf6c4c25813e876847303ada4209abc4632bce903a331cf0f60` |
| `configs/week6_smoke.json` | `2b880104269800e654e4841644a0c7b6fcaad096ea25dc2970fc79126ce04d90` |
| `configs/week6_timing.json` | `6610693c4e4bd3105ba29344a937d471001846118ec65ca4038c161e58be5dfe` |

The next implementation commit necessarily differs from this design baseline. Before formal execution, record the exact committed runner/config/schema/plan revisions and re-audit any intervening protocol changes. Do not substitute this design HEAD for the execution HEAD. Preserve byte hashes as well as commits, particularly because the specification is currently untracked. No formal source freeze or commit is performed in this task.

Authority order for this experiment is current executable source, current tests, current v2 specification, current configuration, historical Tier-1 source/evidence, then other documentation. Historical names containing `wire2` do not imply current credential-admission v2.

## 2. Motivation and faculty traceability

Historical Tier 1 evaluated the earlier `puf-snn-l3-v1-wire2` path: five primary groups of 100, 100 controls, and 100 supporting substitutions. It remains a separate, preserved experiment. This plan supplements that evidence with current-v2 admission, varied packets and session contexts, explicit state/recovery populations, parser boundaries, actual frozen inference callbacks, and exact binomial intervals.

The newest supplied faculty direction was checked directly in `C:/Users/wwall/Downloads/Week 5 Research Feedback.txt` (SHA-256 `48752a30c184cd683461c0ecacd8662dbbe3393586acdb588ac899b36b05876f`). It asks for at least 1,000 varied trials per primary type if practical, exact binomial intervals for attack acceptance and valid-message rejection, future-sequence/invalid-next/duplicate-after-reject cases, malformed parser cases, and classifier-call instrumentation. The external feedback is not in Git; [the Week 6 starting audit](week6-start-current-repo-audit.md), sections 10–11, records the same provenance. The old report's suggestion that expansion remains wholly undecided is superseded for this new study. Faculty did not name a particular exact interval: this plan chooses two-sided 95% Clopper–Pearson, not historical Wilson.

## 3. Research questions

1. **RQ1:** Does the evaluated current-v2 implementation reject observed replay, device substitution, and post-tag payload/metadata modifications before accepted-window release?
2. **RQ2:** Do rejected attempts preserve accepted-count, last-accepted, expected-sequence, session identity, and deadline state?
3. **RQ3:** Do malformed or state-conflicting packets prevent the explicitly retained legitimate continuation from being accepted under strict exact-next ordering?
4. **RQ4:** Are preprocessing, motion, anomaly, and accepted-release invocations zero for each authentication-rejected packet, with one of each for each successfully processed legitimate window?
5. **RQ5:** What are the verifier and receiver-to-return latency distributions for the declared accepted/rejected populations and rejection reasons?

These are finite implementation questions. They do not evaluate physical PUF uniqueness, noisy reconstruction FRR, credential guessing, semantic anomaly detection accuracy, model robustness, network deployment, or universal security.

## 4. Current-v2 evaluation boundary

Use the audited `auth.sender.Sender`, `auth.verifier.Verifier`, `auth.binary_window`, `integration.ExactlyOnceClassifierRelease`, and `V2InferencePipeline`. The frozen profile is `puf-snn-l3-credential-admission-v1-wire2`: handshake 2.0, authenticated message 2.0, payload 1.0, binary32 big-endian, and full HMAC-SHA-256. Use `configs/authentication_v2.json` unchanged: 10,000 ms handshake timeout, 300,000 ms session TTL, 10,000 windows/session, 128 pending and 10,000 process-issued session IDs. No old `window_message`/`inference_gate` route is used.

Every scenario gets a fresh verifier and a fresh primary sender; provision the second device in that same verifier when needed. Construct **one pipeline before any activation**. The constructor requires fresh endpoints and exact audited endpoint types. Its `establish` method permits one attempt. Additional-device and replacement handshakes therefore call the existing endpoint methods through a small harness orchestration helper; they must not construct another pipeline on a used verifier or call `pipeline.establish` twice. The original pipeline's receiver/gate continues to process envelopes for the verifier; the harness separately owns all sender references. No sender pointer swap or new authenticator is needed.

### Controlled admission, not another reconstruction study

Use six simulated RO-PUF devices (128 oscillators, adjacent pairs, 64-bit response, manufacturing SD 1, no aging) from `configs/puf_baseline.json`. Create two separately provisioned enrollment generations per device, with distinct enrollment IDs, credentials, helper data, and credential-verifier records. These generations are isolated fixtures, **not a runtime rotation service** and not additional independent physical devices.

For each handshake, acquire exactly one fresh simulated response at the configuration's **reference conditions** (environmental offset 0, measurement-noise SD 0), then call the real `reconstruct` once. This deliberately controlled Layer-3 fixture is chosen in advance to exercise successful admission without conditioning on outcomes from noisy `.1` reads. It is not the nominal noisy-read timing population. Do not manufacture a `ReconstructionResult`, insert the enrolled credential as a runtime candidate, retry a failed reconstruction, or weaken the decoder. Credential verification and both independent HKDF calls remain real.

Use OS-generated four-byte research credentials and independent `InMemoryCredentialVerifierKeyProvider.generate` keys; retain provisioning only in memory. A failed controlled admission is retained as a setup failure, with the dependent preplanned attempts unexecuted and the run incomplete. It is not replaced by a newly successful session. No 84,000-attempt reconstruction or 430-candidate verifier study is rerun.

### Attacker and injection boundaries

Primary mutation functions receive only public source envelopes, declared mutation parameters, and public device/session identifiers. They receive no credential, key, enrollment reference response, or admission handle. Post-tag mutations preserve the original tag. Same-session and lifecycle replays preserve the entire original envelope.

Window attacks enter `pipeline.process_envelope(bytes)`, which calls the actual verifier and accepted-release path. Parser cases deliberately inject raw bytes there; malformed input need not be constructible through the sender. Handshake truncation cases enter `Verifier.begin_session` or `Verifier.confirm_session` with real local setup state. A valid-tag future packet is obtained by sealing legitimate consecutive packets and withholding earlier ones, not by supplying a key to the attacker or modifying sender counters.

## 5. Primary attack groups: frozen definitions

Each group has **1,200 scored attack attempts**, 6,000 total. Setup packets, warmups, state/parser cases, and recovery messages are not primary attack trials. One primary trial means one designated malicious submission into a fresh scenario, not 1,200 repeated calls against one mutated packet.

Notation: `P(s,k)` is an immutable envelope sealed normally for session `s`, sequence `k`; `N` ranges over 0–4. All prefixes below are actually sealed, accepted, and released through the real pipeline, never assigned into verifier state. `E=accepted_count` is expected-next; `last=null` at E=0, otherwise E−1. Attack snapshots are taken **after packet construction and lifecycle preparation**, immediately before submission. All ordinary rejections below should mint no accepted Window or accepted-result authority, leave replay state unchanged, and produce release/preprocessing/motion/anomaly deltas `(0,0,0,0)`.

### A1. Same-session exact replay — 1,200

- **Property:** no second acceptance of an already consumed sequence in an active session.
- **Initial state/source:** accept `P(s,0)..P(s,N)`; retain the exact bytes of `P(s,N)`. The receiver has E=N+1, last=N; the sender has next=N+1. No other traffic intervenes.
- **Operation:** resubmit `P(s,N)` byte-for-byte with its original tag, key ID, payload, and metadata.
- **Expected defense:** parse, active-session lookup, HMAC, owner/key-ID binding, and quality pass; ordering returns `duplicate_sequence`. Authentication=`pass`; identity authenticated=true; ordering=`duplicate`.
- **State/inference:** count remains N+1, last remains N, deadline and sender next unchanged; no release or model calls.
- **Recovery:** seal and submit one valid `P(s,N+1)`; expect `accepted`, count N+2, last N+1 and one call at each inference boundary.
- **Variation:** all 12 device/enrollment cells, 1,200 fresh sessions/nonces/tags, five sequence positions (240 each), all 600 test source windows (twice/group), variable prefix windows.

### A2. Prior/expired-session replay — 1,200

- **Property:** traffic from replaced or expired sessions cannot consume an active session's sequence state.
- **Initial state/source:** accept `P(old,0)..P(old,N)` and retain `P(old,N)`. Assign 400 trials to each lifecycle variant below.
- **Replacement (400):** perform a fresh admitted/confirmed same-device handshake on the same verifier; old becomes `CLOSED/session_replaced`, new is ACTIVE at E=0. Replay exact old bytes. Expect `inactive_session` at lifecycle lookup, before HMAC.
- **TTL without cleanup (400):** present the old packet at/after its recorded receiver deadline, with its active entry still allocated. Expect `expired_session` at deadline check. Entry remains ACTIVE and its count N+1, last N, deadline unchanged. Rejection is not cleanup.
- **TTL after cleanup (400):** run `expire_due_sessions` at/after the deadline before the attack snapshot; old is EXPIRED. Replay exact old bytes. Expect `expired_session` at terminal-state lookup; tombstone unchanged. Terminal `accepted_count`/`last_accepted` are unavailable, not zero; retain their separate preclosure ledger values.
- **HMAC/identity:** the captured tag was valid when issued, but receiver authentication=`not_checked` in all three variants; identity authenticated=false; ordering not reached. Never report an observed HMAC pass for these early exits.
- **Recovery:** replacement variant sends new-session sequence 0. Expiry variants first finish explicit cleanup (if necessary), then establish a new legitimate same-device session and submit sequence 0. Old-session traffic is never expected to recover an expired session. Each recovery window must be accepted once.
- **Variation:** fresh old/new session contexts, N=0–4, source windows, device/enrollment cells; for each expiry subtype use 200 cases at exact equality and 200 at deadline+1,000,000 ns.

**Expiry clock fixture:** avoid hundreds of five-minute waits. In a serial, narrowly scoped harness context, replace only the audited verifier module's `time` reference with a proxy whose `monotonic_ns` is the real monotonic clock plus a fixed forward offset, while `perf_counter_ns` remains real. Compute the offset before the attack; the equality subcase uses a fixed deadline value for all verifier monotonic samples during that call. Do not mutate `_Active.deadline`, change TTL, patch cryptography, or label this real elapsed expiration. For the live-entry subtype, take after-snapshot before cleanup; then tombstone the expired entry under the same fixture. Restore the module before the new recovery handshake. There is no revival of an old session by restoring the clock. Record clock mode/offset and report simulated-expiry timing separately. Existing TTL-equality tests establish this test-seam precedent; restoration and unchanged state are implementation checks.

### A3. Cross-device substitution — 1,200

- **Property:** integrity of the protected device identity under a valid source session's key.
- **Initial state/source:** known enabled devices A and B, each with a normally admitted active session in the same verifier. A has accepted 0..N−1 (none when N=0); B has E=0. Seal but withhold `P(A,N)` and `P(B,0)`.
- **Operation:** replace only the LP16 device string in A's authenticated bytes with B's equal-width provisioned pseudonym; keep A's SID, sequence, all other protected bytes, wrapper key ID, and original tag. Both devices must be known: an unknown-device early rejection would test a different condition.
- **Expected defense:** lookup reaches A's active SID; HMAC over altered bytes fails with `invalid_tag` before owner binding. Authentication=`fail`, identity=false, ordering not reached. Do not expect `device_session_mismatch` without a valid replacement tag.
- **State/inference:** both sessions and both senders unchanged by injection. A remains E=N; B remains E=0. Sender next values already became N+1 and 1 when packets were sealed.
- **Recovery:** submit retained original A,N and B,0, once each. Expect two separately recorded acceptances with one release/preprocessing/motion/anomaly call each.
- **Variation:** all 30 ordered distinct device pairs (40 trials each), both enrollment generations, fresh session pairs, N=0–4 and all source windows. Pseudonyms `t1v2-d0`..`t1v2-d5` have equal width.

### A4. Post-tag motion-payload modification — 1,200

- **Property:** integrity of the binary32 motion samples.
- **Initial state/source:** session at E=N after accepted prefix 0..N−1; seal and retain a valid exact-next `P(s,N)`.
- **Operation:** change one binary32 mantissa bit (bit 0..22) in one selected sample; 600 position and 600 quaternion-component cases. Preserve tag and every other byte. Use byte mutation, not a sender re-seal or quality-enforcing `encode_window` on the changed quaternion.
- **Representation constraint:** chosen changed float must remain finite and not negative zero. If the planned bit would produce negative zero, scan the remaining mantissa bits cyclically for the first legal changed word; record requested and actual bit. This is a deterministic representation rule, not outcome-based attack tuning. Representation is prechecked outside timing; mutated quality need not pass because HMAC precedes quality.
- **Expected defense:** parser passes; HMAC fails `invalid_tag`; authentication=`fail`, identity=false, ordering not reached. Count stays N; last and sender next unchanged by injection. Four inference deltas zero.
- **Recovery:** submit the untouched retained P(s,N) once, expected acceptance, E=N+1, last=N.
- **Variation:** all 120 sample positions, all three position/four orientation components within their respective subgroups, all 23 mantissa-bit positions, different underlying values, devices/enrollments/sessions/sequences/windows/tags. Report actual coverage after the negative-zero rule.

### A5. Post-tag protected-metadata modification — 1,200

- **Property:** integrity of metadata inside authenticated binary A.
- **Initial state/source:** E=N, prefix 0..N−1 accepted; seal and retain P(s,N).
- **Operation:** exactly one protected field changes, in six equal variants of 200: sequence N→N+1; one window-ID ASCII character; capture start +1 ns; capture end +1 ns; tracking-valid count (120→119, otherwise +1); tracking-valid PPM XOR 1. Window-ID replacement selects the first character and maps `a`→`b`, any other legal first character→`a`, preserving width. Leave all other bytes and tag untouched.
- **Expected defense:** representation valid; `invalid_tag` before quality/order. Authentication=`fail`, identity=false, ordering not reached; E=N and last unchanged, zero inference calls. A metadata mutation may be semantically inconsistent, but that is not the first failure under the stale tag.
- **Recovery:** retained original P(s,N) accepted once. Sender next remains N+1 during attack and during submission of retained recovery.
- **Variation:** six fields, their existing source values, five sequence positions, all windows and device/enrollment/session contexts. Do not call outer JSON `key_id`, encoding, algorithm, labels, or split identifiers HMAC-protected metadata; the former are wrapper constraints and the latter are not protocol fields.

## 6. Trial variation, seed strategy, and dependence

### Exact allocation

For each primary group and the control group, enumerate `(device d=0..5, enrollment generation g=0..1, t=0..99)`: 12 cells ×100 =1,200. Define stable local index `r=100*(2*d+g)+t`. Sequence N=`t mod 5`, giving 240 observations at each N. Trial IDs encode group,d,g,t and are unique across the run. Per group, use every one of each device's 100 frozen test windows exactly once in each enrollment generation, with a predeclared permutation. Source device IDs are dataset strata; sender IDs are the separate provisioned pseudonyms. Keep their mapping in the trial plan, never in model features.

For A2, assign lifecycle variants by `r mod 3`; within each of the two expiry variants alternate equality/+1 ms. For A3, generate an independently shuffled list containing each other device 20 times per (d,g) cell. For A4, shuffle a list of 600 position and 600 quaternion assignments; within each subgroup independently shuffle balanced sample, component, and bit lists, with residual counts assigned in ascending value order. For A5, shuffle six labels repeated 200 times. These separate permutations avoid relying on a single identical mutation or accidental shared modulo schedule. Report all cross-tabulations; balance of individual dimensions does not imply a full factorial.

Map d to sorted dataset device IDs. A secondary device uses generation g, and a replacement session keeps the original device/enrollment generation. A3 replacement choices are the other five device indices in ascending order before their repeated list is shuffled. S8 selects the next device cyclically `(d+1) mod 6`. For state/parser subvariant quotas, construct the stated repeated labels in table order and shuffle with that case's mutation stream; assign them to ascending `(d,g,t)` slots. Source windows for these smaller populations come from the appropriate device's independent case/generation permutation; consume the first 10 (state) or five (parser) slots per cell. These rules freeze smaller-cohort selection without needing the missing dataset at design time.

State groups each have 120 scenarios: every device/generation cell ×10, E=`2+(t mod 5)`. Parser groups each have 60 scenarios: every device/generation cell ×5, N=`t`. Each scenario uses fresh sessions. Sample/index/offset choices vary according to the parser table and mutation stream. Fixed constants such as magic and sample-count are deliberately repeated boundary values, not claims of 60 independent parser grammars.

### Randomness contract

| Stream | Configured seed / source | Purpose |
|---|---|---|
| PUF/device | 6767 | `week2-v1:6767:{d}:manufacturing` and `...:enrollment`, compatible with six baseline profile generation domains |
| Controlled PUF read | 2026100601 | Fresh reference-condition read per handshake, distinct setup/phase/scenario/sender-role domain |
| Session/trial planning | 2026100602 | Shuffle scenario execution order and fixture assignments; **does not seed protocol nonces** |
| Attack mutation | 2026100603 | Variant quotas, sample/components/bit schedules and parser mutation choices |
| Window selection | 2026100604 | Test-window permutations and prefix/recovery source selection |
| Model/input sampling | none | One fixed frozen model pair; deterministic batch-size-one evaluation of planned inputs; no training or random prediction sampling |
| Credential, verifier key, boot ID, SID, client/server nonces | OS `secrets` provider | Native supported randomness, no global patch or exported secret seed |

Use `random.Random` with `seed(identity_string, version=2)` as in `run_week6_smoke.rng_for`. Non-PUF domains are `tier1-v2-v1:{stream}:{seed}:{phase}:{group}:{d}:{g}:{t}:{role}` with literal field order, decimal integers, and ASCII separators. `role` distinguishes source, replacement, second device, prefix index and recovery index. Record full nonsecret stream IDs and Python version; materialize the complete schedule before any formal observation so later execution ordering does not consume planning streams differently. Credentials have no published seed. Use OS entropy directly; never derive credentials from a logged PUF/read/mutation seed.

Warmups use a separate `phase=warmup` and 20 distinct validation windows. Measured source windows are the 600 test records sorted by `(device_id,label,window_id)` before permutation, with six devices ×five labels ×20 windows. Verify disjoint validation/test window IDs and the pinned dataset hash; do not regenerate missing data in this task or silently replace it with synthetic fixtures. For any required prefix/recovery source, use the appropriate device's prepermuted test list cyclically from the scenario source position plus the operation ordinal. Recovery authenticity, not prediction correctness, is the outcome.

### What remains dependent

1,200 is the number of designated packet submissions, not 1,200 independent devices, users, motion recordings, credentials, or model draws. Six device profiles, twelve enrollment materials, 600 windows, fixed models, one implementation, and one machine are reused. Fresh sessions/nonces vary tags but do not make underlying windows or devices independent. Within a state scenario, all steps and recoveries are explicitly dependent; between groups, sources are reused. Report marginal coverage and counts by device, generation, N, variant, source window and session. A binomial model provides the requested conventional interval, with its independence/equal-probability assumptions disclosed; it is not a design-based guarantee over arbitrary attackers or device populations. Never multiply sample size by prefix packets, model callbacks, repeated sources, or recovery steps.

## 7. Legitimate controls

Plan **1,200 scored valid exact-next windows**, allocated identically to primary groups, each in its own fresh scenario. Establish a real admitted session, process 0..N−1 as setup, then seal and submit N once. Expected result=`accept/accepted`, HMAC/identity/order pass, E=N→N+1, last→N, one accepted Window and one release, preprocessing, motion callback and anomaly callback.

Control packet construction occurs outside the receiver timer, just as for attacks. Save sender preparation/HMAC measurements separately if present. Source values and quality must meet the current sender contract; no amplitude, predicted class, anomaly-score or PUF-success selection is permitted. A control that reaches the verifier and is rejected stays in the 1,200 control schedule and the completed control rejection denominator. Do not retry it. Its isolated scenario prevents a rejection from turning subsequent scored controls into cascade gaps. A setup/construction exception or refusal prevents that planned valid-message submission and is a retained incomplete-scenario status, not an ordinary valid-message rejection or a replacement trial. Report setup failures separately.

Control error rate is **conditional Layer-3 valid-message rejection under controlled successful admission**, not reconstruction/admission FRR and not semantic anomaly false-positive rate. An anomaly flag leaves authentication acceptance unchanged.

## 8. State-poisoning/desynchronization populations

Eight groups ×120 scenarios = **960 scenarios**. Every group begins at E in 2..6, last=E−1, after a real accepted prefix. All sender-generated packets required below are sealed and retained before the attack snapshot; sender next is explicitly recorded. No writes to `next_to_send` or verifier counters are allowed. State rows are one per negative submission: S4 has two, so **1,080 designated state-negative rows**, not 960. Recovery/setup rows are separate.

For each negative step, both replay fields and deadline/lifecycle remain unchanged, accepted count does not increase, sender state/next does not change, and four inference deltas must be zero. For every recovery window accepted at k, count increases by one, last becomes k, and each inference delta is one. These assertions are evaluated per step, not merely at the end of a scenario.

| ID / population (120 scenarios each) | Exact negative traffic and first reason | Before → after rejection | Required recovery, once per listed packet |
|---|---|---|---|
| S1 invalid-tag future | Retain P(E); replace its sequence with 2^63 (60) or 2^64−1 (60), retain original tag: `invalid_tag` | (E,E−1)→same; sender next E+1 | Original P(E) accepts; count E+1, last E |
| S2 valid-tag future | Seal P(E)..P(E+g), g=1,2,3 (40 each); withhold missing prefix; submit P(E+g): `future_sequence_gap` | Same receiver pair; sender next E+g+1 | Submit retained P(E), accepts. Remaining withheld packets are intentionally not part of this recovery; record their planned disposition, close fixture afterward |
| S3 invalid exact-next | Retained P(E): 60 cases XOR one tag bit (varied bit 0..255); 60 cases finite position mantissa change with old tag: `invalid_tag` | Same receiver pair; sender next E+1 | Untouched P(E) accepts |
| S4 duplicate after rejection | Submit tag-corrupted P(E): `invalid_tag`; then retained, previously accepted P(E−1): `duplicate_sequence` | Separate before/after snapshots for both; (E,E−1) remains unchanged twice; sender next E+1 | Untouched P(E) accepts |
| S5 stale then next | Submit retained P(E−2): `stale_sequence` | Same receiver pair; sender next E+1 after preparing P(E) | P(E) accepts |
| S6 gap/missing/retry | Seal P(E)..P(E+g), g=1,2,3 (40 each); submit P(E+g): `future_sequence_gap` | Same receiver pair; sender next E+g+1 | Submit P(E)..P(E+g−1) in order; then resubmit the exact former future P(E+g). All g+1 accept. No automatic buffering/reconsideration is assumed |
| S7 malformed then next | Retain P(E); truncate its envelope at one predeclared interior byte (nonempty, excluding complete trailing whitespace): `malformed_message` | Same pair; sender next E+1 | Complete P(E) accepts |
| S8 cross-session invalid then valid | Both A and B active; A at E, B at 0. Seal A,E and B,0. In 60 cases replace protected A SID and wrapper key ID with B SID, keep A tag: `invalid_tag`. In 60 cases change **only wrapper key ID** to B: `invalid_key_id` after HMAC passes | Both sessions unchanged; A/B sender next E+1/1 | Original A,E and B,0 each accept once |

For S2/S6, authentication passes, identity is true, order=`gap`, missing_start=E, missing_end=E+g−1, missing_count=g. S4's second step and S5 have HMAC pass and authenticated identity. S8 wrapper-only variants have HMAC pass but identity false and order not checked: key ID does not select the verification key. S1/S3/S4 first/S8 protected-SID variants have HMAC fail, identity false, and order not checked; S7 has HMAC not checked.

The S6 final resubmission is a specifically predeclared recovery step of a valid reordered packet, not retry-until-success. No recovery failure is retried. If a preceding step unexpectedly accepts and changes the state, preserve that result and perform the predeclared remaining traffic once if the endpoint is usable; record any resulting reason mismatch without adapting expected-next or changing the packet. Stop an incomplete endpoint, record unexecuted dependents, and retain the run.

This population answers whether rejected traffic advances/corrupts expected-next and whether the documented continuation remains usable. It does not claim successful transport repair for a missing packet that was never retained.

## 9. Parser and protocol-boundary populations

**28 cases ×60 scenarios =1,680 designated negative submissions**: 24 window-envelope/binary cases (1,440) and four receiver-handshake truncation cases (240). These are separate from primary denominators. Window scenarios start with a real active session, prefix 0..N−1 accepted, and a withheld valid P(N). For each negative, assert state/counter deltas zero; afterward submit original P(N) once and expect acceptance and four inference calls of one each. Store exact changed offsets/widths, public input hash and size; calculate offsets from LP16 identifier lengths, never from a fixed fixture's absolute positions.

`MM=malformed_message`, `IPS=invalid_payload_schema`, `UPV=unsupported_protocol_version`. All listed window negatives fail representation parsing **before lookup/HMAC/identity/quality/order**; HMAC=`not_checked`, identity=false, order=`not_checked`. Each row below defines exactly one mutation, except where an explicit internal split is declared. Base64 and JSON are otherwise valid when testing binary fields; keep original tag.

| ID | Raw injection into `process_envelope` | Exact expected reason / suballocation |
|---|---|---|
| P01 | Cut UTF-8 JSON envelope inside a token; vary cut offset | MM; 60 |
| P02 | Remove a required colon/comma in otherwise complete JSON | MM; 60, 30 each |
| P03 | Duplicate a JSON key with identical value | MM; 20 at each of outer/protected/authentication object levels |
| P04 | Add an unknown field | MM; 20 at each object level |
| P05 | Replace protected encoding with `puf-snn-binary32-le-v2` | MM; 60 |
| P06 | Replace algorithm with `HMAC-SHA256` | MM; 60 |
| P07 | Replace one base64 alphabet character with `!` | MM; 60, varied positions |
| P08 | Append one excess `=` to canonical base64 | MM; 60; strict decode and/or re-encoding identity rejects |
| P09 | Truncate tag to 62 hex chars or extend to 66 | MM; 30 each |
| P10 | Replace one selected tag character with uppercase `A` or nonhex `g` | MM; 30 each; guarantees actual uppercase/nonhex even if original tag was digits-only |
| P11 | Change one byte of `P3AW` magic | MM; 60, cycle four byte positions |
| P12 | Change protocol-major or authenticated-message-major 2→3 | UPV; 30 each |
| P13 | Change payload-major version 1→2 | IPS; 60 |
| P14 | Truncate binary A | MM; 30 remove one final byte, 30 remove 39 final bytes; base64/JSON rebuilt canonically |
| P15 | Alter declared payload length 4683→4682 or 4684 while retaining bytes | MM; 30 each |
| P16 | Encode fixed sample count 120 as little-endian `78 00` rather than `00 78` | IPS; 60 |
| P17 | Change sample count to 119 or 121, retain sample bytes | IPS; 30 each |
| P18 | At selected sample position i, encode index `(i+1) mod 120` | IPS; 60, varied i |
| P19 | Replace one pose word with negative zero `80000000`, +infinity `7f800000`, or NaN `7fc00000` | IPS; 20 each, varied sample/component |
| P20 | Set one tracking-valid byte to 2 | IPS; 60, varied sample |
| P21 | Change payload header `01 00 3c` to `01 00 3b` | IPS; 60 |
| P22 | Prefix BOM or inject invalid UTF-8 byte `ff` into JSON | MM; 30 each |
| P23 | Change key ID to 31 hex chars or insert uppercase `A` | MM; 30 each |
| P24 | Append one binary zero after final sample, retaining declared length | MM; 60 |

There is no generic endian marker in a float. Byte-reversing a finite F32 can produce another valid finite F32 and would then fail the unchanged HMAC (`invalid_tag`), not necessarily the parser. P16 deliberately chooses an unambiguously invalid big-endian constant; P05 covers the wrapper string. Do not claim all little-endian-looking values can be recognized or relabel a validly encoded changed float as malformed. Outer JSON key order is accepted; it is not a negative case. Do not use ordinary JSON dictionaries to construct duplicate-key tests.

Handshake populations use the existing audited endpoints, real reconstructed/admitted requests and proofs, and the same real inference gate constructed before activation:

| ID / 60 each | Injection and state | Expected result/state preservation | Recovery |
|---|---|---|---|
| P25 | `begin_session`: truncate a valid P3RQ frame without updating its U32 length; sender PENDING with live bound handle, receiver has no pending/active session | REFUSAL, local `last_reason=malformed_message`; no pending/active allocation, no receiver HKDF, no handle consumption | Resubmit untouched original request with the same live handle, finish normal confirmation, then accepted sequence 0 |
| P26 | `begin_session`: truncate request body within its nonce and reframe with matching shortened length | Same as P25; body parser fails MM before admission | Same as P25 |
| P27 | `confirm_session`: truncate valid P3CF frame without updating frame length; receiver PENDING | REFUSAL/MM; pending retained, no new activation or window state; sender remains PENDING because refusal is not forwarded in this injection scenario | Submit retained original P3CF, deliver returned P3OK to sender, then sequence 0 accepts |
| P28 | `confirm_session`: remove final proof byte and reframe consistently | REFUSAL/MM; proof-length parse fails before comparison; pending retained | Same as P27 |

For P25/P26 vary truncation length 1..16; for P27 vary 1..16; P28 specifically removes one byte. Use each existing pending attempt only for its planned malformed injection and recovery; no retries of a failed recovery. Do not claim the sender could continue after receiving and acting on a P3NO—it is intentionally not forwarded in these receiver-boundary tests. All malformed handshake calls have zero release/preprocessing/motion/anomaly invocations. Report receiver-call duration rather than a nonexistent `VerificationResult.verifier_auth_ns`. Record the successful recovery handshake transitions separately from its first window. Sender-only challenge/final-confirmation corruption, resource-exhaustion and concurrency stress remain existing unit-test coverage, outside this finite parser population.

## 10. Expected-reason matrix and check precedence

Order is: representation → known/enabled device → session state/deadline/count limit → HMAC → owner/enrollment binding → wrapper key ID → authenticated identity/state coherence → quality → duplicate/stale/gap → late deadline checks → audit/state/accepted-result commit. Compare the exact expected reason with the observed reason and preserve differences.

| Attack/condition | First failing check; exact reason | HMAC observed expectation | Identity authenticated? | Sequence comparison reached? | Expected protected state change | Inference/release |
|---|---|---|---|---|---|---|
| A1, S4 duplicate step | Duplicate; `duplicate_sequence` | pass | yes | yes | none | 0 each |
| A2 replaced old session | Lifecycle; `inactive_session` | not_checked (historically valid) | no | no | none; existing tombstone retained | 0 each |
| A2 expired ACTIVE | Initial deadline; `expired_session` | not_checked (historically valid) | no | no | none; still ACTIVE until cleanup | 0 each |
| A2 expired tombstone | Lifecycle; `expired_session` | not_checked (historically valid) | no | no | none | 0 each |
| A3 known other device | HMAC; `invalid_tag` | fail | no | no | neither session changes | 0 each |
| A4/A5, S1/S3/S4 first step | HMAC; `invalid_tag` | fail | no | no | none | 0 each |
| S2/S6 valid future | Exact-next gap; `future_sequence_gap` | pass | yes | yes | none; missing range audit only | 0 each |
| S5 stale | Stale; `stale_sequence` | pass | yes | yes | none | 0 each |
| S8 protected SID+wrapper swap | HMAC with B's selected key; `invalid_tag` | fail | no | no | A/B unchanged | 0 each |
| S8 wrapper key-ID-only swap | Key-ID consistency; `invalid_key_id` | pass | no | no | A/B unchanged | 0 each |
| S7; P01–P11, P14–P15, P22–P24 | Envelope/binary parse; `malformed_message` | not_checked | no | no | none | 0 each |
| P12 | Version parser; `unsupported_protocol_version` | not_checked | no | no | none | 0 each |
| P13, P16–P21 | Payload representation; `invalid_payload_schema` | not_checked | no | no | none | 0 each |
| P25–P28 | Frame/body parser; `malformed_message` | not_checked; no confirmation comparison | no | no | no allocation/activation; existing pending retained where applicable | 0 each |
| Control and expected valid recovery | No failing check; `accepted` | pass | yes | yes/pass | count+1, last=submitted k; deadline unchanged | 1 each |

P10 is a malformed **tag representation**, not an `invalid_tag` HMAC failure. Audit growth and elapsed observation time are permitted on rejection; replay state, deadline, lifecycle and inference authority are not. Enrollment IDs are locally bound, not fields the attack can rewrite on the wire. No signed wrong-owner or signed bad-quality packet is claimed in this primary threat model; those privileged fixtures remain unit tests. Unexpected `unknown_device`, `unknown_session`, `device_session_mismatch`, `data_quality_failure`, or any other reason is retained verbatim and investigated, not remapped to `invalid_tag`.

## 11. Safe state snapshot design

Proposed snapshot type (explicit allowlist; no recursive object serialization):

```text
StateSnapshot = {
  sessions: [{ session_alias, session_id_hex, owner_device_id, enrollment_generation,
    state: ACTIVE|PENDING|CLOSED|EXPIRED|FAILED|null,
    accepted_count: integer|null, last_accepted: integer|null,
    expected_sequence: integer|null, deadline_ns: integer|null,
    deadline_elapsed: boolean|null, terminal_reason: string|null,
    terminal_time_ns: integer|null,
    last_observed_active: {accepted_count,last_accepted,event_id}|null }],
  active_session_ids: [hex SID], pending_session_ids: [hex SID],
  senders: [{sender_alias,device_id,state,session_id_hex|null,next_to_send}],
  calls: {release,preprocessing,motion,anomaly},
  consumed_event_count, consumed_event_ids_sha256,
  sender_incomplete: [{sender_alias,value}], verifier_incomplete
}
```

Use public `session_status`, `active_session_ids`, `tombstones`, sender `state/session_id/next_to_send`, pipeline `calls/consumed_event_ids`, and allowlisted audit snapshots. Derive owner from successful establishment audit and trusted scenario mapping, not an unverified packet claim. `expected_sequence=accepted_count` only for an ACTIVE entry with coherent counter/last relation. An expired-but-not-cleaned entry is ACTIVE with `deadline_elapsed=true`; a tombstone has null live counters/deadline, never invented zeros. `last_observed_active` is explicitly evaluator history, not a claim that the tombstone stores counters.

Current APIs expose status for a known pending SID but do not enumerate pending IDs. A harness-only read-only observer may take `tuple(verifier._pending.keys())` under `verifier._lock`; it returns only public SID bytes. Never return dictionary values, keys, transcripts or admission objects. This narrow observation adapter needs tests and source binding, not a protocol/API change. P3CH parsing supplies the known public SID for pending snapshots; request-negative cases should have an empty pending-ID set. Capture every involved source/target/old/new session, not just the pipeline sender's SID.

`calls.release` is the separately measured invocation count of the real verifier release boundary; `consumed_event_count` is a different metric. A rejected event is not minted as accepted: a temporary observer of the real `verify_window` return records only `accepted_window_present`, `authenticated_bytes_present`, result/event ID and native timing before returning the **unchanged exact object**. These booleans must be false on rejected windows. Never serialize the result object itself. For ordinary rejection, compare snapshots excluding evaluator time/derived elapsed flag and audit growth; predeclared clock changes/lifecycle operations occur before the before-snapshot. Deadline comparisons still use the exact stored value.

Do not export credentials, candidate messages, helper bits, reference/noisy PUF responses, verifier keys/tags/records, session keys, authorization handles, object `__dict__`, locals, arbitrary exception messages, or hashes of short credentials. Published simulated-generation seeds are research fixture provenance, not a claim of provisioning secrecy.

## 12. Inference-call instrumentation

Formal callback condition is fixed before results: **`snn32_seed7_forest_anomaly`**, motion `snn_32_seed_7`, anomaly `anomaly_random_forest_seed6007`. This is one existing `pipeline_timing.CONDITIONS` entry, chosen to exercise the SNN motion path and a real conventional anomaly detector. This study does not compare models or select one by attack outcomes. No claim that this condition meets 20 ms is made.

Load the unchanged `FrozenModelBundle` through `load_frozen_bundle(ROOT, week6_smoke_config)`, then `one_model_bundle` for the declared pair. Use `attacks.evaluation.prepare_model_inputs` for the real (120,7) motion and (48,) anomaly inputs. One selected bundle callback invokes one underlying motion model or anomaly model; avoid loading all models into a single callback and calling that many forwards “one model invocation.” The loader currently requires and checks all historical bundle binaries before deserializing any; retain that contract even though only one pair is evaluated.

Measure cumulative public `pipeline.calls` before/after every operation and calculate deltas. Each accepted event calls preprocessing once, then motion once, then anomaly once. Preprocessing prepares both inputs; count that as one composite preprocessing invocation, not two. Wrap the **real** callbacks with pass-through entry counters, independent of the pipeline counters, and require agreement. Instrument `Verifier.release_accepted` through a restoring, pass-through wrapper and count entry invocations for the current scenario; also record consumed-event-set growth. Do not infer zero calls just from a rejection label. Rejected events use normal `process_envelope`; do not deliberately call the release API on them during the measured formal flow, which would manufacture a nonzero release-attempt count. Existing guard tests cover that separate misuse.

Reuse `TimingCapture`/`instrument_pipeline` for stage observations, including `accepted_release_and_consumers`; count wrappers must compose with them, not replace behavior or consume a result twice. They are temporary process-wide patches: run serially, restore in `finally`, and never execute concurrently with another benchmark. Count entry even if a callback throws. Conversion/preprocessing failure, motion failure, or anomaly failure is an execution failure after possible committed acceptance/consumption, not a rejection or permission to replay. Preserve partial deltas and mark incomplete.

For **every** accepted setup, control or recovery, verify one consumed event and four call deltas of one. For every rejected attempt, all four zero, consumed set unchanged, and no accepted payload returned. The public audit row carries authentication/identity/order evidence absent from a rejected `WindowOutcome`; join by `event_id`, never infer authenticated identity from a parsed device field. Spy/dummy models may be used in runner unit tests only, labeled nonformal. They cannot satisfy formal completeness if artifacts are missing.

## 13. Metrics, exceptions, and exact confidence intervals

For every primary family and each declared variant report scheduled count, submitted count, completed accepted A, completed rejected R, execution/infrastructure failures F, and not-submitted count U. Completed means an ordinary authentication decision with complete required observation, including any required downstream processing; retain the raw verifier decision separately if downstream processing fails.

- Attack acceptance rate = A/(A+R); attack rejection rate = R/(A+R), reported as counts and percentages.
- Control valid-message rejection rate = R_control/(A_control+R_control), with raw accepted/rejected counts.
- State and parser populations: per-case/scenario/step counts and reasons, state-mutation violations, nonzero-inference violations, no-accepted-payload violations, recovery attempted/completed/accepted/rejected/failed/not-submitted. No pooling into the five primary rates.
- Every scheduled scored operation satisfies scheduled=A+R+F+U; submitted=A+R+submitted_failures. A setup failure is F for that setup operation; its unsubmitted scored dependents are U with a reference to the failure, not multiple fabricated verifier rejections.
- Preserve raw authentication accept/reject totals also for failed downstream operations, in separate `authentication_decision_counts`; these do not silently disappear behind the execution-status classification.
- Missing observations, timing/counter instrumentation failures, audit failure/incomplete flags, unexpected exceptions, `internal_error`, model failure, source/artifact drift, and evidence I/O failure make the formal run incomplete. Do not treat them as protective attack rejections. Persist safe partial state/timing and sanitized error category/stage. Never dump exception arguments or traceback locals.
- An ordinary unexpected accept, different rejection reason, or valid-control rejection is a finding. It remains in A/R; do not abort before writing it or change the denominator. Continue other fresh scenarios when the endpoint/evidence remains usable. Missing dependent recovery after a failed endpoint remains explicit.

### Interval definition

Use **two-sided 95% equal-tailed Clopper–Pearson**, alpha=0.05, separately for attack acceptance x=A and control rejection x=R_control. For n>0:

```text
L = 0                       if x=0, else BetaQuantile(0.025; x, n-x+1)
U = 1                       if x=n, else BetaQuantile(0.975; x+1, n-x)
```

For n=0 rate and bounds are null. Rejection-rate intervals may additionally be reported as `[1-U,1-L]` from attack-acceptance bounds. Use the same method for explicit per-variant proportions, always with their own n; these are pointwise, not simultaneous intervals. Store method/alpha/tails/estimand/n/x in machine-readable summaries, unrounded probabilities in JSON, and clearly rounded percentages in CSV/report. Numerical tests must include x=0,x=n and interior x; at x=0, U=`1-0.025^(1/n)`. For 0/1,200 accepted attacks the planned mathematical upper endpoint is approximately 0.307% (an illustration, **not an observed result**).

These are exact under the binomial model, not an assertion that shared sources/sessions establish independent identically distributed trials. Report the dependencies in section 6 adjacent to intervals. Do not use the rule of three, Wilson, a one-sided bound, or a bootstrap as an unlabeled replacement for the requested interval. Partial-run proportions/intervals, if generated, are labeled incomplete descriptive evidence with F/U and planned n visible; they cannot be represented as the formal completed population.

## 14. Timing methodology

Use real `perf_counter_ns` for elapsed duration, integer ns in raw records, ms in summaries. Reuse `TimingCapture`, `instrument_pipeline`, `quantile`/`latency_statistics`; add arithmetic mean and the reporting n rather than another timer framework. No attack is repeated merely to increase timing n.

1. **Native verifier latency:** `VerificationResult.verifier_auth_ns`, joined to its audit event; includes lock wait, parsing, lookup, HMAC/quality/order where reached, allocation, audit and state publication. It excludes subsequent release/preprocessing/models. The pass-through result observer collects it without another verification call.
2. **Receiver path latency:** directly measure one `pipeline.process_envelope` call; includes verifier work and, if accepted, actual release and both models. For handshake negatives measure only the specified receiver API call; native window verifier latency is null. Never invent a sender+receiver attack total from an earlier packet's sealing time.
3. **Nested spans:** parser, HMAC calculation, quality, audit operations, release, preprocessing and consumers using the current timing wrappers. Sequence checks and commit stay within verifier timing; they are not newly claimed disjoint stages. Native verifier and wrapper timing differ slightly in boundaries/observer overhead; retain both without adding them.

Packet preparation, mutation, snapshots, audit-copy/join, recovery preparation, writing/flushing JSONL/CSV, assertions, progress output, dataset/model loading, enrollment/reconstruction/handshake setup and shutdown are outside the window receiver-path timer. In-memory audit inside the actual methods remains included. This is not capture-to-inference, durable audit, network, hardware, or fresh-admission timing; the separate Week 6 timing study owns that broader question. Save source sender timings if available, labeled preparation only; sender HMAC is nested in sender preparation.

Before measured scenarios, run 20 valid sequence-0 warmup scenarios on distinct validation windows with the same chosen model pair and instrumentation. Retain them in `warmup.jsonl`; the first is labeled first-use. These warm shared code/model paths, not every parser branch. Do not remove the first measured sample of each negative variant or pretend all rejected branches are fully warmed. No measured windows are warmups and no warmups enter primary/control denominators.

Run one CPU process, one orchestration thread, batch size one, torch and native threadpools limited to one, models in eval mode, GC enabled with no forced per-trial collection. Record Python/package/backend versions, OS/CPU, timers/resolution, thread settings, power plan and background-load report, start/end machine conditions, model-load/warmup policy, execution order and controlled-clock mode. Do not change power policy or authentication timeouts for speed. Randomize whole scenario order using the frozen planning stream; never reorder steps within a scenario.

For each family/variant/outcome/reason/clock-mode and for controls report n, mean, median/p50, p95, maximum, and p99 when n>=100; set p99 null with `insufficient_n` otherwise. Quantiles use linear interpolation at q*(n−1), matching `pipeline_timing.quantile`. Retain every latency/outlier in raw data. For unexpected accepted attacks, report their timings in their actual acceptance stratum. Keep recovery/setup/warmup distributions separate. Preserve nested wall/thread-CPU/GC evidence for slow observations but do not infer unmeasured causes or subtract an overhead estimate. No new security or latency pass threshold is introduced.

## 15. Proposed configuration (design only)

Proposed path: **`configs/tier1_v2_experiment_v1.json`**. Do not create it in this design task. The following is the exact initial field/value proposal; case IDs resolve to the versioned mutation/scenario definitions above. Reject unknown fields, duplicate JSON keys, booleans used as integers, altered fixed counts, unsupported profile, and unresolved execution pins for formal mode. A separate test fixture may downscale unit tests; no small-run result may receive this formal identity.

```json
{
  "config_version": "puf-snn-tier1-v2-config-v1",
  "experiment_id": "authentication-v2-tier1-security-evaluation",
  "experiment_version": 1,
  "run_id": "tier1-v2-formal-001",
  "plan_path": "docs/week6-tier1-v2-experiment-plan.md",
  "design_baseline_commit": "78f499a92f633a4793c776a070058e3a6a9a0b61",
  "execution_source_commit": null,
  "source_manifest_path": null,
  "protocol_profile": "puf-snn-l3-credential-admission-v1-wire2",
  "auth_config": "configs/authentication_v2.json",
  "auth_config_sha256": "b0ee45b8a3ee5cf6c4c25813e876847303ada4209abc4632bce903a331cf0f60",
  "puf_config": "configs/puf_baseline.json",
  "admission_fixture": "one_fresh_reference_condition_read_then_real_reconstruction",
  "frozen_config": "configs/week6_smoke.json",
  "frozen_config_sha256": "2b880104269800e654e4841644a0c7b6fcaad096ea25dc2970fc79126ce04d90",
  "model_condition": "snn32_seed7_forest_anomaly",
  "device_count": 6,
  "enrollment_generations_per_device": 2,
  "primary_groups": ["A1", "A2", "A3", "A4", "A5"],
  "primary_trials_per_group": 1200,
  "control_trials": 1200,
  "trials_per_device_generation_cell": 100,
  "sequence_positions": [0, 1, 2, 3, 4],
  "state_groups": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
  "state_scenarios_per_group": 120,
  "parser_groups": ["P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08", "P09", "P10", "P11", "P12", "P13", "P14", "P15", "P16", "P17", "P18", "P19", "P20", "P21", "P22", "P23", "P24", "P25", "P26", "P27", "P28"],
  "parser_scenarios_per_group": 60,
  "variation_contract": "tier1-v2-balanced-scenarios-v1",
  "measured_source_split": "test",
  "window_selection": "all_600_by_device_permuted_twice_per_primary_or_control_group",
  "seeds": {"puf": 6767, "controlled_read": 2026100601, "trial": 2026100602, "mutation": 2026100603, "window": 2026100604},
  "secret_and_protocol_randomness": "os_secrets_unmodified",
  "expiry_fixture": "receiver_monotonic_proxy_equality_or_plus_1ms",
  "timing": {"warmup_controls": 20, "warmup_split": "validation", "repetitions_per_submission": 1, "batch_size": 1, "native_threads": 1, "torch_threads": 1, "gc_enabled": true, "quantiles": "linear_q_times_n_minus_1", "p99_min_n": 100},
  "confidence_interval": {"method": "clopper_pearson", "confidence": 0.95, "sides": 2},
  "attempt_schema": "puf-snn-tier1-v2-attempt-v1",
  "output_root": "results/week-6/will/authentication",
  "execution_failure_policy": "retain_partial_no_complete_no_retry"
}
```

`execution_source_commit` and `source_manifest_path` are explicitly unresolved provenance pins for the later committed implementation, **not experiment tuning knobs**. Resolve them in a run-specific config copied outside the committed source: pin the clean implementation commit and a preflight source manifest of the committed tree. This avoids a commit containing its own hash. Pin this plan, runner, schemas, authentication/reconstruction/integration/timing sources, relevant tests, package lock/requirements, PUF/auth/frozen configs, and specification in that source manifest. A current config hash pins all unchanged authentication values; do not copy independent mutable TTL/window-limit options into the new config. Run ID/output changes are provenance changes; any population, artifact, mutation, model or interval change requires a dated plan/config version amendment before formal observations, not editing a completed run.

## 16. Proposed attempt, trial-plan and summary schemas

Create in the next task, not now: `schemas/tier1-v2-attempt-v1.schema.json`, `schemas/tier1-v2-trial-plan-v1.schema.json`, and `schemas/tier1-v2-summary-v1.schema.json`. JSON Schema draft 2020-12; all structural objects use `additionalProperties:false`. Encode U64 sequences as exact JSON integers in Python; any JavaScript reader must use lossless parsing or decimal display strings, never round 2^64−1. Null means unavailable/not applicable, not measured zero. Required fields include:

```text
AttemptV1 {
  schema_version: const puf-snn-tier1-v2-attempt-v1,
  experiment_id, experiment_version, run_id, config_sha256, trial_plan_sha256,
  trial_id, scenario_id, step_index, execution_index,
  phase: measured|warmup,
  role: primary_attack|legitimate_control|state_negative|parser_negative|
        setup_window|recovery_window|setup_handshake|recovery_handshake|lifecycle,
  attack_group: A1..A5|S1..S8|P01..P28|control|null,
  attack_variant, injection_boundary, parent_attack_trial_id|null,
  seed_ids: {trial,mutation,window,controlled_read},
  device_index, device_id, enrollment_generation, session_trial_index,
  source_session_alias|null, target_device_id|null, target_session_alias|null,
  source: {dataset_sha256,record_id|null,record_sha256|null,split|null,
           packet_id|null,sequence_number|null,window_id|null},
  submitted: {packet_id|null,byte_length|null,sequence_number|null},
  mutation: {category,field|null,operation,byte_offset|null,width|null,
             sample_index|null,component|null,requested_bit|null,actual_bit|null,
             before_hex|null,after_hex|null},
  expected: {result,reason,hmac,identity_authenticated,order,
             replay_state_change,release,preprocessing,motion,anomaly},
  execution_status: completed|execution_failure|not_submitted,
  observed: {result: accept|reject|null,reason:string|null,stage:string|null,
             authentication:pass|fail|not_checked|null,identity_authenticated:boolean|null,
             order:pass|duplicate|stale|gap|not_checked|null,
             missing_start|null,missing_end|null,missing_count|null,
             authenticated_bytes_sha256:string|null,
             accepted_window_present:boolean|null,authenticated_bytes_present:boolean|null},
  event_id|null, audit_event_ids:[],
  state_before:StateSnapshot|null, state_after:StateSnapshot|null,
  calls_delta:{release,preprocessing,motion,anomaly}|null,
  callback_entry_delta:{preprocessing,motion,anomaly}|null,
  consumed_event_delta:integer|null,
  latency_ns:{verifier_native|null,receiver_path|null,sender_prepare|null,sender_hmac|null},
  trace_id|null, clock_mode:real|expiry_equality|expiry_plus_1ms, clock_offset_ns|null,
  recovery:{required_step_ids:[],attempted_step_ids:[],complete:boolean},
  violations:[], error:{category,stage,dependency_trial_id|null}|null,
  notes:[]
}
```

IDs/paths/notes use bounded, harness-owned strings, never arbitrary exception contents. Device/sequence/source fields are planned or observed identifiers; they do not assert identity authentication. Outcome values preserve runtime `accept/reject` vocabulary. State definitions are exactly section 11; accepted-count/last before/after are available there and flattened into CSV, not independently recomputed duplicate JSON fields. For handshake/lifecycle operations without `VerificationResult`, accepted-window presence and window authentication fields are null; refusal proof status is separately described by stage/reason.

Each receiver input has a `packet_id=sha256(exact bytes)`. `traffic.jsonl` contains allowlisted public wire messages `{packet_id,boundary,bytes_b64}` once per unique packet; no enrollment or local-admission objects. This permits exact forensic checking of JSON duplicates/truncation, retained tags and replay equality even though fresh OS randomness makes a later run byte-different. Source/submitted records refer to these IDs. Packet hashes are **not** verifier-authenticated hashes: keep the audit's authenticated-A hash separate. Public handshake proofs remain public protocol material with the specification's offline-guessing limitation, not exported keys.

Recovery steps are full AttemptV1 rows in `recovery.jsonl`, with their own expected/observed result/reason/state/calls/timing and parent/scenario links. Parent rows list predeclared step IDs; offline summaries derive final recovery attempted/result/reason/state from linked rows. Do not rewrite attack rows after recovery. Explicit `not_submitted` rows account for blocked steps; nullable observed values must not masquerade as rejections.

The trial plan freezes all scenario IDs, group/variant assignments, device/enrollment/sequence/source choices, mutation schedules, ordered setup/negative/recovery operations, expected results/reasons, logical session aliases, and execution order before evaluation. Runtime-generated public SIDs are bound to those aliases in metadata/evidence, not invented as deterministic trial seeds. Source-dependent byte offsets are computed and recorded before injection. Include scheduled counts by role/group/variant and an exact plan digest. No need to mutate the plan after receiving an outcome.

SummaryV1 contains experiment/run/source/config/plan identities; completion/evidence status; scheduled/submitted/A/R/F/U counts; raw authentication counts; rates with exact interval metadata; reason cross-tabs (expected vs actual); variant/device/source/sequence coverage; latency strata; invariant-violation counts with trial IDs; recovery accounting; and explicit limitations. It references raw rows rather than embedding secret or model objects. Reconciliation is a separate versioned document of check names, observed/expected counts, discrepancies and outcome-verdict flags.

## 17. Proposed runner architecture

New entry point **`src/python/scripts/run_tier1_v2.py`**; supporting scenario/planning/summary logic in **`src/python/puf_snn/tier1_v2.py`** if needed. Do not import or modify the historical runner's execution flow, v1 baseline check, fake candidate helper, Wilson summaries or collector release logic.

1. `validate_config_and_source`: strict config/schema validation, execution commit and hash checks, untouched protocol baseline, fresh scoped output path. Validate all artifact hashes/COMPLETE inputs before model deserialization, enrollment or attacks.
2. `compile_trial_plan`: deterministic nonsecret schedule with the fixed populations and all dependent steps. Check balance and uniqueness; write/hash before the first formal attempt. Preflight material/input representation failures stop before formal mode, not shrink the plan.
3. `load_inputs_and_callbacks`: reuse frozen loader, `one_model_bundle`, real preprocessing and callbacks. No training, checkpoint/threshold search, or custom replacement data. Cache loaded models across fixtures.
4. `make_enrollments`: native PUF helpers, two generation fixtures/device, OS credentials/independent verifier key provider, current helper/record/store/service/registry types. Do not reuse timing `make_materials` unmodified: it deliberately assumes nominal noisy reads and timing-specific seeded credentials.
5. `make_scenario`: fresh audited endpoints and one pipeline; required registry entries and locally shared service. Acquire/read/reconstruct once per handshake, use `pipeline.establish` for the initial normal activation and the same actual endpoint calls for additional handshakes. Log safe phase outcomes, not reconstruction objects. A new verifier per scenario keeps issued-ID and retained audit/result-map growth bounded without modifying limits.
6. `prepare_packets_and_mutation`: preconstruct valid packets with normal sender, retain missing/old packets, mutate public bytes only, verify representation invariants without executing verifier decisions, cache exact source/submitted bytes in the traffic ledger. Do not use a test module as the formal implementation dependency.
7. `snapshot_safe_state` and `observe_operation`: snapshots outside timers; pass-through result observation; `capture.measure` around the actual one API call; read audit by event ID, state, call deltas and safe timing afterward. Write an observation before checking expectation failures. No extra verification just to get the full result.
8. `run_recovery`: issue exactly the planned retained/next/new-session steps; do not re-seal a retained sequence or repair state manually. Capture each step and the parent relation. Unexpected outcomes are data.
9. `emit_evidence`: append-only exclusive JSONL, UTF-8/LF and finite JSON numeric values, safe schema allowlists and unique IDs. Export each endpoint's new public audit records with scenario/sender labels; audit event IDs remain native. No disk/progress I/O inside timed spans.
10. `summarize_and_reconcile`: reread persisted rows, regenerate counts, exact intervals, latency and reason/recovery tables, validate expected plan coverage and hash closure. Separate methodological completion from whether security expectations held.
11. `finalize_manifest`: close/flush writers, rehash sources/artifacts, retain INCOMPLETE on any failure; otherwise write final manifest and its COMPLETE anchor per section 19. Close remaining sessions through supported lifecycle methods outside timers; never drop terminal evidence.

Reuse `TimingCapture`, `instrument_pipeline`, `latency_statistics`/`quantile`, `one_model_bundle`, and frozen-path/hash utilities. **Do not call `run_timed_attempt`, `reconcile_timing`, or `validate_timing_config`** for these populations: their fixed eight paths, six conditions, 600 attempts and assertion-based stopping are a different experiment. The new harness needs its own population/exception accounting around the shared instrumentation. This is orchestration and evidence implementation, not a duplicated composite model pipeline.

## 18. Formal result directory and evidence package

Proposed new root: **`results/week-6/will/authentication/tier1-v2-formal-001/`**, exclusively created. If it exists, fail; do not overwrite, resume, replace or relabel it. A later attempt uses a new run ID with an explicit relation to the incomplete predecessor. Preserve all historical directories untouched.

| File | Purpose |
|---|---|
| `plan.md`, `config.json`, `trial-plan.json` | Exact frozen plan, resolved configuration, enumerated schedule |
| `attempts.jsonl` | 6,000 scheduled primary attack rows |
| `controls.jsonl` | 1,200 scheduled control rows |
| `state_safety.jsonl` | 1,080 negative steps across 960 state scenarios |
| `parser_negative.jsonl` | 1,680 designated parser calls |
| `setup.jsonl`, `recovery.jsonl`, `warmup.jsonl` | Separate actual/setup-dependent rows and all unexecuted statuses; never primary/control denominators |
| `traffic.jsonl` | Deduplicated exact public wire inputs addressed by SHA-256 |
| `audit.jsonl` | Native allowlisted sender/verifier audit rows with scenario/endpoint linkage; all relevant setup, decision and terminal rows |
| `timing_traces.jsonl` | Per-operation existing timing-span/GC/CPU traces, phase and row linkage |
| `summary.json` | Versioned raw counts, rates/intervals, coverage, violations, limitations and verdicts |
| `attack_summary.csv`, `control_summary.csv` | Counts/rates/intervals for primary families/variants and controls |
| `reason_summary.csv`, `latency_summary.csv`, `recovery_summary.csv` | Expected/observed reasons, declared timing strata and exact dependent recovery accounting; include population/group columns for state/parser rows |
| `metadata.json` | Environment, command, source identities, randomness policy, clocks, model condition, start/end time and incomplete failure categories |
| `source_manifest.json` | Exact execution sources/tests/configs/schema/plan hashes and commit; design-baseline relationship |
| `artifact_manifest.json` | Input dataset and model manifests/normalization/checkpoints/thresholds/features/COMPLETE hashes with relative paths |
| `reconciliation.json` | Persisted-data coverage, joins, counts, hashes and invariant findings |
| `manifest.json`, `COMPLETE` or `INCOMPLETE` | Final evidence hash closure and completion anchor, or explicit partial-run status |
| `.gitattributes` | Fix result text to LF before hashes, as existing Week 6 runners do |

No second archive of keys/enrollments, separate duplicate packet blobs, or model retraining outputs belong here. No synthetic “results” or COMPLETE marker is written during design/implementation. Copy input manifests/plan by bytes when freezing; never edit historical manifests to match a new newline representation.

## 19. Reconciliation and completeness

The planned measured logical scenarios are 6,000 primary +1,200 controls +960 state +1,680 parser =**9,840**. Designated scored/negative rows are **9,960**, because S4 contributes an additional 120 negative steps. There are **10,200 planned recovery-window submissions**: primary 7,200 (two per A3, one per other primary), state 1,320 (S6 has g+1, S8 has two, others one), parser 1,680 (including first windows after handshake recovery). Additional recovery-handshake/lifecycle and setup rows are enumerated by the planner; they are not extra attack trials. Twenty valid warmup scenarios are separate. Prefix packet counts and all setup/recovery operation IDs must be materialized before execution; no after-the-fact denominator inferred solely from whichever rows happened to be written.

The defined prefixes yield **23,520 setup-window submissions**: 14,400 in primary scenarios (3,600 each for A1/A2 and 2,400 each for A3/A4/A5), 2,400 before scored controls, 3,840 in state scenarios and 2,880 in window-parser scenarios. Thus expected successful setup+control+recovery traffic totals **34,920 accepted windows**, plus 20 warmups. These are planned workload counts, not observations; handshake/lifecycle operations add evidence rows but no model calls. All count projections must agree with the compiled plan.

Two distinct verdicts are required:

- **Evidence complete:** every scheduled operation is accounted for, all required observations and recoveries were completed, inputs/sources remained pinned, files are valid and their hashes reconcile, and no infrastructure/execution failure or unexecuted required step occurred.
- **Expected behavior observed:** reason/state/payload-release/model-call expectations match. False means a reported finding; it must not make the data disappear or invite rerunning until a passing sample is obtained. A fully measured violation can have COMPLETE with `expected_behavior_observed=false`. Never interpret COMPLETE itself as “secure.”

Reconciliation must calculate and retain, rather than hardcode as true:

1. Each configured primary group has exactly 1,200 rows, controls exactly 1,200; every expected state scenario/step and parser case/subvariant count is present, including failures and not-submitted rows where incomplete.
2. Every trial/step/scenario ID and execution index obeys the plan; no duplicate rows, orphan recoveries, extra scored attempts, or warmup/setup leakage into rates. Sequence-variant/device/window coverage equals the planned allocation or explicitly records a discrepancy.
3. For every role/group, A+R=completed and A+R+F+U=scheduled; submitted failures reconcile separately. Raw committed authentication decisions in failed downstream calls reconcile with audit evidence.
4. Each submitted window has exactly one corresponding native window decision audit; accepted-result booleans, event IDs, authentication/identity/order/reason and native timing agree. Session setup and lifecycle rows join to their own events, not counted as window acceptances. Handshake refusals retain local reason and generic wire REFUSAL distinction.
5. For each rejected attack/parser/state step: replay-state/deadline/lifecycle/sender equality, no accepted Window, zero release/preprocessing/motion/anomaly entries, unchanged consumed set. Record every violation ID. Audit ordinal growth alone is not poisoning.
6. For accepted controls/setup/recoveries: exact-next increment/last update, same deadline, one consumed event, four call entries of one, matching real callback counts and selected model output identities. No model prediction/flag criterion is imposed. Rejected controls must instead have zero release/model calls and unchanged state.
7. All predeclared recovery steps, including S6 retry and handshake recovery, have separate rows with correct parent IDs, observed reasons/state/counters and retained packet identity. Retried S6 bytes match the initial future packet; exact replay bytes match the previously accepted source; stale-tag mutations leave tag bytes unchanged.
8. Expected/actual reason cross-tabs include mismatches verbatim; generated summaries/CSV can be reproduced exactly from persisted raw rows. State/parser coverage and simulated-clock vs real-clock timings are explicit.
9. No `internal_error`, evidence-incomplete endpoint, failed writer, source/artifact drift, missing timing or missing counter observation can be hidden by a successful summary. Schema/allowlist validation disallows provisioning secrets and nonfinite numbers.
10. All exact-byte hashes and manifest references verify; no historical file is an output target. Re-read written evidence before completion.

Create INCOMPLETE when the new output is allocated. Write data and reconciliation, close and flush all outputs, then `manifest.json` mapping each evidence file to exact-byte SHA-256 (excluding itself and the mutually exclusive status markers). `reconciliation.json` can verify all already-written evidence files and source/artifact inputs; it must not hash itself or a future manifest. Finally re-read/validate that manifest against disk and exclusively write COMPLETE containing the manifest hash, run ID, counts, and the separate expected-behavior verdict; then remove the temporary INCOMPLETE marker. If both markers exist after interruption, treat the run as incomplete until checked, never as automatically successful. This avoids recursive/self-hashing and false completeness on crashes. Persistent I/O errors remain incomplete even if marker writing also fails; report them out of band.

## 20. Predeclared interpretation rules

Use observed finite-population language: “In the evaluated Authentication-v2 software implementation, X/Y attacks of type Z were rejected under the specified trial population.” If A=0, report “0 accepted attacks out of N observed trials,” with the acceptance interval and dependence qualification. For controls, “0 valid-message rejections out of N controls” describes the evaluated control population, not universal FRR.

An unexpected accept is an attack-acceptance observation even if anomaly inference flags the motion. A rejection for an unexpected reason still contributes to rejection count but is a reason/coverage finding. A valid-control reject remains a failure in that denominator. No 100% security guarantee, proof of security, physical Quest inference, 256-bit credential claim, hardware latency generalization, or protection against attacker key possession follows. Signed future packets here represent reorder/withholding of legitimate traffic, not a demonstrated forgery.

Report state corruption, unexpected identity authentication, accepted payload authority on a rejection, and nonzero rejected-traffic calls even if acceptance rates are otherwise zero. Do not create a new tolerated-violation threshold, remove outliers, lower sample sizes, retry until passing, or tune mutation/source/model/threshold choices against outcomes. If the planned scale is impractical, preserve measured feasibility evidence and amend scope explicitly **before** a formal run; never silently return to 100/group.

## 21. Historical v1 versus current-v2 design

| Dimension | Preserved historical Tier 1 | New current-v2 plan |
|---|---|---|
| Profile | `puf-snn-l3-v1-wire2`; Wire 2.0 | `puf-snn-l3-credential-admission-v1-wire2`; Wire 2.0 with current admission/confirmation owners |
| Credential admission | Supplied-correct synthetic candidate | One controlled reference-condition read, real reconstruction, independent verification and live local admission |
| Independent verifier | Later pre-HKDF service absent from historical execution | Current record/store/key-provider/service and independent endpoint derivation |
| Primary/control size | 100 per group /100 controls | 1,200 per group /1,200 controls |
| Variation | Per-trial synthetic material/motion; fixed A/B IDs, sequence 0 replay and 0→1 metadata, position mantissa mutations | Six device profiles, two enrollments, fresh sessions, five positions, 600 reused test windows, six metadata fields, position/quaternion mutations, explicit pair/variant balance |
| Inference callback | Accepted-payload collector | Existing frozen SNN-32 seed 7 plus RF anomaly seed 6007, real preprocessing, counters |
| State poisoning/recovery | State snapshots for formal groups; advanced cases mostly unit/integration tests | Eight enumerated groups, 960 scenarios/1,080 negative steps and retained valid continuations |
| Parser | Separate unit/integration/cross-language tests | 28 ×60 formal boundary cases, raw bytes and exact reasons |
| Interval | Two-sided 95% Wilson | Two-sided 95% Clopper–Pearson for attack acceptance and control rejection; dependence disclosed |
| Timing | Layer-3 sender/verifier native timing, collector boundary | Native verifier plus shared composite receiver-path/nested CPU/GC instrumentation, real callbacks; expiry fixture identified |
| Identity | `results/week-4/will/authentication/tier1-20260923T205156Z-343cb4a2/` | New `results/week-6/will/authentication/tier1-v2-formal-001/` |

Historical authorities inspected: `docs/puf-tier1-attacks.md`, `docs/tier1-results-attacks.md`, `configs/tier1_attack_experiment_v1.json`, `src/python/scripts/run_tier1_attacks.py`, `schemas/tier1-attempt-v1.schema.json`, `tests/tier1/test_tier1.py`, and the preserved run's `trial-plan.json`/`reconciliation.json`. The preserved plan is a list of trial/mutation assignments; historical reconciliation records 700 formal and 800 setup rows. Its attempt schema does not support these new populations. There is no reason to edit it, the old runner, results, manifests or baseline identities. No historical experiment was rerun or rewritten for this plan.

## 22. Dependencies, source traceability and blockers

**No protocol ambiguity or protocol implementation blocker was found that prevents this experiment.** Two important implementation constraints are resolved in the design: fresh-only pipeline construction/additional handshakes (section 4), and public terminal counters being unavailable/pending enumeration requiring a narrow safe observer (section 11). First-failure precedence, key-ID semantics and expiry cleanup are specified by current executable source. No cryptographic/protocol redesign is needed.

### Frozen artifacts before formal execution

The pinned source dataset `data/generated/synthetic-windows.jsonl` is **absent locally** at design time. Its required SHA-256 is `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`. Model manifests and COMPLETE files exist, but the following binaries are also **absent locally**. Availability checks were read-only; models were not loaded, trained or regenerated.

- `results/week-4/keegan/snn-architecture-32/`: `seed-7/model-state.pt`, `seed-17/model-state.pt`, `seed-27/model-state.pt`; require existing `config.json` and `normalization.json` as well. Manifest pin: `ccf13e7d7c3b199676e8a847394cc1d5a1c4d70939fa2f94d8efd84ab0470779`.
- `results/week-5/keegan/model-evidence/`: `models/logistic_regression-seed-7-storage-refit.joblib`, `models/random_forest-seed-7-storage-refit.joblib`, with hashes from `local_model_artifacts`. Manifest pin: `456b21cf1c4ed74dbc52294857b2d9c607d9cdd6efeb753b2679b95b9df100ed`.
- `results/week-5/keegan/stream-evaluation/`: all six `models/anomaly_{logistic_regression,random_forest}_seed{6007,6017,6027}.joblib`; existing `frozen-validation-thresholds.json`, `anomaly-feature-names.json`, and input/feature metadata required. Manifest pin: `8c053eadacf67c97f4d886a8116df17f185afb818d2e25439090fb7d7275f13e`.

The next task can implement the planner, schemas, runner and unit tests with explicitly nonformal fixtures without these files. Formal execution must restore the exact trusted archived artifacts and satisfy the unchanged loader's complete-bundle checks, including binaries outside the selected inference pair. Do not re-fit storage models, retrain SNNs, regenerate the pinned dataset, loosen hash checks or substitute dummy callbacks to obtain COMPLETE. Compatible Python/galois (`0.4.11` reconstruction backend)/NumPy/PyTorch/scikit-learn/joblib/runtime dependencies and exact package versions must be recorded at preflight. Artifact existence is not claimed to be hash verification; full pinned hash verification belongs to that preflight.

No scale feasibility experiment was run. The design bounds primary/control sequence positions to 0–4 and state prefixes to E=2–6, and isolates scenarios to bound audit/result copies. The 34,920 planned accepted setup/control/recovery windows plus 20 warmups exercise actual models under the expected successful schedule; this is not a runtime estimate. The exact compiler operation count must be checked before formal execution. A small nonformal implementation validation can measure feasibility with restored artifacts without selecting outcomes or changing the planned population.

### Implementation/test anchors inspected

| Behavior | Executable authority | Relevant existing tests / assertions |
|---|---|---|
| Credential and local admission | `auth/credential_verifier.py`, `auth/session.py::Sender.begin_attempt` | `tests/auth/test_credential_verifier.py` full tag/binding/no key search; `test_credential_admission.py` real candidate, zero work on wrong candidate, swapped/replayed handles, existing session survival |
| Session framing/replacement/expiry | `auth/session.py::unframe`, `Verifier.begin_session/confirm_session`; audited lifecycle methods | `tests/auth/test_session.py` frame/version/proof length/deadline/replacement; `test_verifier.py` equality, explicit expiry, unchanged TTL, replacement |
| Representation and quality precedence | `auth/binary_window.py::parse_envelope/parse_window/validate_quality` | `test_binary_window.py` wrapper/bounds/float/structural offsets; `test_protocol_rejection.py`; `check_binary_v2_negative.py` raw C#-generated mutations; `test_quality.py` |
| Replay and atomic state | `auth/verifier.py::verify_window/session_status` | `test_verifier.py` duplicate/stale/gap/missing/retry, invalid high-sequence tag, key ID, device/session precedence, allocation failure and late expiry |
| Sender packet construction | `auth/sender.py::seal_window` | `test_lifecycle_audit.py`, `test_finalization.py`, `test_audit.py`; sender consumes sequence on sealing and may fail after consumption |
| Immutable release and counts | `integration.py::ExactlyOnceClassifierRelease`, `pipeline_v2.py` | `test_classifier_integration.py`; `tests/test_pipeline_v2.py` zero rejected calls, both consumers once, committed sequence before inference, copy/repeated-release refusal and callback-failure behavior |
| Shared timing and artifacts | `pipeline_timing.py`, `frozen_pipeline.py`, `scripts/benchmark_week6_v2.py` | `tests/test_pipeline_timing.py` restoring wrappers, no argument logging, separate warmup, I/O outside timers, no nested-percentile addition, preserved failed admissions; `test_frozen_pipeline.py` all-hashes-before-load, missing-artifact/no-refit, real boundary smoke |

These source/test inspections justify the plan; they are **not new test-pass or formal-run evidence**. This task did not invoke the formal runner, either historical study, inference callbacks, package installation, or model training. The [preparation audit](week6-v2-protocol-spec-prep.md) is supporting traceability only; its previous test counts are not claimed as newly executed here.

## 23. Exact implementation checklist for the next Codex task

1. Recheck branch/HEAD, working tree, applicable repository guidance and diffs since the design baseline. Read this plan and current specification; document any relevant behavior change before coding. Preserve existing user work and all historical evidence.
2. Implement the new config and versioned attempt/trial-plan/summary schemas with strict validation and unresolved formal-pin rejection. Add the new runner and isolated helper module. Do not modify authentication/session/cryptographic/inference behavior.
3. Implement deterministic plan compilation and safe provisioning/admission orchestration, including multi-sender/replacement use of one existing verifier/pipeline. Test exact 1,200/cell/variant/sequence/window balance, unique IDs and all setup/recovery counts without launching formal trials.
4. Implement all five public-byte attacks, eight state scenarios and 28 parser cases at their stated boundaries. Test exact first-failure reasons with compact synthetic fixtures, sender sealing/retained-packet behavior, expiry proxy restoration and no secret access in mutation helpers. Add no hidden re-signing or state writes.
5. Implement safe snapshots, pending-ID observer, result/audit joins, pass-through release and real callback entry counters, and shared timing integration. Test real object identity preservation, rejected zero work, accepted one-of-each, state snapshots for both devices and tombstones, and failures after acceptance.
6. Implement append-only evidence, traffic deduplication, exact Clopper–Pearson summaries, reason/latency/recovery outputs, source/artifact manifests, and separate completeness/expected-behavior verdicts. Test missing/duplicate rows, execution failure/not-submitted accounting, secret sentinel exclusion, exact U64 values, disk failures and nonrecursive hashes. Test that unexpected outcomes remain written and summarized.
7. Run relevant existing auth/integration/pipeline/timing/frozen-loader tests and new harness tests as implementation validation. Do not execute an existing historical experiment or use its source-baseline check as a v2 gate. Tests may use fixtures; mark them nonformal and keep outputs outside the formal directory.
8. Before any later formal run, restore and verify exact data/model artifacts, pin compatible environment and clean committed implementation/plan/config/schema sources, validate the full planned operation schedule and establish practical runtime without lowering counts. Record feasibility separately; do not promote test outputs to formal evidence.
9. Formal execution, when subsequently requested, uses the committed/pinned configuration, exclusive new result directory, actual frozen callbacks, exactly the planned schedule and recovery, and all completeness checks. This design task authorizes **no formal experiment execution**.

## READY TO IMPLEMENT

- [x] New current-v2 identity and unchanged protocol baseline established.
- [x] Five primary definitions frozen at 1,200/group; legitimate controls at 1,200.
- [x] Six-device/two-enrollment/five-position variation and separate nonsecret seed streams specified; OS session randomness and remaining dependence explicit.
- [x] Eight state groups (960 scenarios/1,080 negative steps), 28 parser cases (1,680 negatives), exact reasons and valid recovery traffic defined.
- [x] Controlled real reconstruction/admission fixture and frozen real inference condition selected without retraining.
- [x] Safe snapshots, release/preprocessing/motion/anomaly counters, timing boundaries and two-sided 95% Clopper–Pearson metrics decided.
- [x] Proposed config/schema/runner paths, evidence package, error accounting, manifests and completeness/interpretation rules specified.
- [x] No protocol ambiguity prevents implementation; historical evidence remains separate and untouched.

## NEEDS CONFIRMATION BEFORE FORMAL RUN

- Restore the exact pinned dataset and all model binaries required by the existing frozen loader, then verify hashes and compatible runtime. These artifacts are absent here; none is needed merely to implement the design with nonformal tests.
- Confirm practical execution of the declared scale using implementation-validation measurements. If resources cannot support it, retain that evidence and explicitly amend the predeclared scope before formal execution; no silent reduction below 1,000/group.

No additional faculty decision is requested for ordinary harness choices, current protocol semantics, interval selection or the already directed sample-size expansion. Clean execution-source pins and successful validation are routine preflight requirements, not unresolved experimental-design questions.
