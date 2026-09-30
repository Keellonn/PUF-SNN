# Independent Pre-HKDF Credential Verification

Design proposal, September 30, 2026. Source inspected at commit `56d9535cf6dca71c0745874814e1471d4cf897cc`. This document is the only change made for this task. No verifier is implemented, no reconstruction is rerun, and no source, test, schema, configuration, or formal evidence is changed. Line references below describe the inspected source.

## Problem

The frozen Layer 2 construction uses one simulated 64-bit response, indices 0..62, BCH(63,36,t=5), and a 32-bit credential followed by four zero padding bits. It uses code-offset helper data, with no retry, voting, stable-bit selection, or independent credential verifier. Padding checks syntax; beyond the correction radius, a decoder can return a different message with valid padding.

The saved nominal experiment contains 12,000 attempts, 11,805 correct reconstructions, and 195 failures (1.625% reconstruction FRR): 186 decoder failures, seven invalid-padding outcomes, and two wrong but valid-format credentials. The sweep contains:

| Noise SD | Attempts | Wrong valid-format candidates |
| --- | ---: | ---: |
| 0.0 | 12,000 | 0 |
| 0.05 | 12,000 | 0 |
| 0.1 | 12,000 | 5 |
| 0.25 | 12,000 | 69 |
| 0.5 | 12,000 | 194 |
| 1.0 | 12,000 | 160 |

There are 428 sweep and two nominal miscorrections, totaling 430 among 84,000 saved attempts. These are reconstruction observations, not measured Layer 3 false accepts. The current confirmation mechanism rejects mismatching key material only after keys have been derived.

Evidence: [formal results](layer2-formal-results-week5-draft.md), [nominal summary](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/baseline_summary.csv), [sweep summary](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/noise_sweep_summary.csv). A read-only scan of saved JSONL confirmed the counts and nominal identifiers in this document.

Evidence integrity qualification: this Windows checkout has CRLF working-tree JSON/JSONL files but LF Git index versions. The raw working-tree manifest SHA-256 is `ef83a3862399741a500e5b24117ae3ca040342fb6532347f25d9459e7a139210`; replacing CRLF with LF **in memory** yields `082db862432da3d1b523f247035d2ae5d27be3a387317792f6eda8e72960a71b`, matching `COMPLETE`. All six manifest-listed JSON/JSONL files match after that in-memory conversion; all six CSV files match their raw-byte hashes. This is not a claim that every working-tree raw hash matches. No files were normalized or rewritten. Future regression loading must explicitly account for the verified artifact representation, rather than silently accepting arbitrary hash mismatches. Hash manifests establish consistency, not signed provenance.

## Current Pipeline

The repository does not currently have a production acquisition-to-session runner. There are distinct research and integration paths:

1. [`reconstruction/credential.py`](../src/python/puf_snn/reconstruction/credential.py), `reconstruct()` at line 117, selects the first 63 response bits, XORs helper bits, and calls the BCH decoder once. Lines 146–158 return decoder/format failures. Lines 159–165 convert the first 32 decoded message bits to four big-endian bytes and return `ReconstructionResult(outcome="candidate_valid_format", candidate_credential=...)`.
2. The formal caller is [`run_reconstruction.py`](../src/python/scripts/run_reconstruction.py), `run_evaluation()`, line 382. It receives `result`, separately evaluates it against enrolled research truth at line 393, and writes it at line 395. It **does not call Layer 3 or HKDF**. The historical `run_layer2.py` similarly receives results at line 199. The formal 430 cases were not observed passing through Layer 3 in that experiment.
3. Actual reconstructed-result-to-session integration is demonstrated by [`tests/auth/test_session.py`](../tests/auth/test_session.py), lines 75–80 and 94–110, and [`test_layer3_integration.py`](../tests/auth/test_layer3_integration.py), including its wrong-candidate test. The tests pass the returned result to `Sender.begin_attempt()`.
4. The operational `auth.sender.Sender.begin_attempt()` (line 67) calls the base `auth.session.Sender.begin_attempt()` through `_begin_attempt()` at line 89. The base function (line 213) validates result type, decoder metadata, padding, four-byte length, and agreement between message bits and credential bytes. At line 254 it retains `result.candidate_credential` as `self._candidate`, sets `PENDING`, and returns `P3RQ`. There is no authenticity check.
5. `auth.verifier.Verifier.begin_session()` wraps `auth.session.Verifier.begin_session()`. The latter parses `P3RQ`, looks up the device's `RegistryEntry`, constructs a transcript, and **already derives the server key at line 442**, using `entry.credential4`. It stores the key in `_Pending` and returns `P3CH`.
6. `auth.session.Sender.answer_challenge()` validates the transcript, then calls **`self._derive_key(self._candidate, transcript)` at line 285**. The base `_derive_key()` at line 265 calls `derive_session_key()`; the audited subclass override in `auth/sender.py`, lines 164–165, calls the same primitive with a timing sink. The receiver override in `auth/verifier.py`, lines 60–61, does likewise.
7. **The common HKDF entry is `auth/session.py:71`, `derive_session_key()`. The actual extract/expand expression is line 76:** `hkdf_expand(hkdf_extract(t.server_nonce, credential4), info, 32)`. Salt is the public server nonce; info includes the domain-separated transcript. Each normal handshake invokes this function once per endpoint.
8. Only then does `client_proof()` compute HMAC-SHA-256 over the client-confirm domain and transcript. `Verifier.confirm_session()` compares it with `hmac.compare_digest` at lines 466–469. On success the server returns `server_proof()` over its separate domain, transcript, and client proof, and publishes its active session. `Sender.finish_session()` verifies that server proof at lines 307–309 before becoming active. Server activation therefore precedes receipt/verification of `P3OK` by the sender; both endpoints do not activate atomically.
9. Authenticated window sealing, window verification, and accepted-window release follow. Their format and per-window HMAC need no redesign for the proposed gate.

[`run_layer3_demo.py`](../src/python/scripts/run_layer3_demo.py), `initialize_material()` lines 33–42, creates a fixed synthetic candidate rather than calling `reconstruct()`. Its `establish()` lines 45–58 drives steps 4–8. `run_tier1_attacks.py` also provisions explicit synthetic correct candidates. Benchmark and stream-evaluation scripts reuse demo establishment. Synthetic setup success must not be described as reconstruction evidence.

**Current wrong-candidate failure:** provided the rest of the handshake is valid, the receiver records `key_confirmation_failed`, removes pending key state, creates a failed tombstone, and sends the generic `REFUSAL`. The sender receiving that frame reports `session_refused`. `key_confirmation_failed` on the sender itself instead describes a bad server proof. Decoder and padding failures are currently `Failure("failed_reconstruction", result.outcome)` before any request.

**Current sensitive data handling:** `ReconstructionResult` retains both message bits and credential bytes; its generated dataclass representation does not hide them. `Sender._candidate` retains the same bytes object until derivation or failure, then removes that reference; this is not guaranteed memory erasure. Local variables and caller-held results can remain. `RegistryEntry.credential4` stores the reference credential in plaintext process memory, although `repr=False` hides it from the ordinary registry representation. Pending and active sessions retain keys with `repr=False`; intermediate HKDF bytes exist transiently. No candidate credential is sent directly in the Wire 2 handshake, and audited sender/verifier paths do not intentionally log it. Handshake proofs are key-dependent public traffic, with the guessing implications discussed below.

The research exception is substantial: `run_reconstruction.enroll_runs()` lines 175–193 stores `evaluator_enrolled_credential_hex` and `evaluator_reference64` in `enrollments.json`; `evaluate_result()` lines 229–249 stores `candidate_credential_hex` and `candidate_message36` in `attempts.jsonl`. Historical runners/validation artifacts also contain research secrets. `credential_for()` lines 53–57 deterministically regenerates credentials from published stream identities using `random.Random`. These are intentionally reproducible synthetic data, not confidential operational enrollment. They remain unchanged and must never be copied into new operational audit output.

**Current audit timing:** `auth/sender.py:93` records a `reconstruction` decision after base admission but before any handshake HKDF. A valid-format acceptance has `identity_authenticated=false` and `authentication_result="not_checked"`. There is no independent-verification event or explicit derivation-start event. Successful server challenge creation stores provenance and KDF timing privately but emits no successful pre-HKDF audit row. On terminal confirmation success/failure, the audited receiver's `_before_activation_commit()` / `_before_pending_terminal()` records `session_establishment`, with KDF latency. The sender records terminal establishment or message failures through `_response()`. Base `auth.session` classes have state/reasons/tombstones, not full operational audits. [`auth/audit.py`](../src/python/puf_snn/auth/audit.py) and [`auth-audit-v1.schema.json`](../schemas/auth-audit-v1.schema.json) define the current allowlisted records. In-memory audit commit precedes active publication; file flushing is separate, with no crash-durability or tamper-evidence guarantee.

## Security Goal

For a particular trusted device/enrollment binding and attempt, a candidate may be supplied to HKDF **only if** it is a coherent valid-format reconstruction result **and** passes an independent credential verifier created during trusted enrollment. The same immutable candidate that passed verification must be the input subsequently supplied to HKDF. A prior pass for another candidate, device, enrollment generation, or attempt is insufficient.

The verifier must be independent of padding and session confirmation, reject mismatches without replacing the candidate, and fail closed on missing, invalid, disabled, unavailable, or inconsistent enrollment/key state. Runtime verification receives no evaluator truth or correctness labels. A verified credential is permission to attempt a handshake, not proof of a remote physical device's identity and not permission to release sensor windows.

For a rejected candidate attempt, the pilot target is stronger than merely protecting the sender's HKDF input: **zero sender and zero receiver HKDF calls, zero confirmation operations, no new pending/active session, and no window release for that attempt**. The admission gate therefore precedes `P3RQ`, and trusted receiver admission must also prevent an unchecked request from triggering derivation.

## Threat Model

The selected scope is a trusted, local software research harness with logically distinct enrollment, credential-admission, sender, and receiver components. The harness and admission code execute correctly. The adversary can supply a wrong valid-format candidate, substitute public helper material or routing labels, read the verifier-record database, observe public traffic, and attempt calls through exposed admission APIs. Separate tests cover database corruption and service failures. A malicious actor controlling the trusted Python process can bypass gates or read secrets; Python object privacy is not an isolation boundary.

The independent verifier key is held by a trusted admission service/key provider, outside helper data and verifier-record storage. The sender invokes that service locally without receiving the key. This is a custody model for the local pilot, not an already implemented isolated server, HSM, or network service. A remote sender cannot magically access a server-held key. Extending this design across machines requires a separately authenticated confidential admission channel and an authenticated, fresh authorization bound to the request, or protected local verification hardware. Neither is provided by current Wire 2. Sending a raw credential over the unprotected handshake or putting a fleet-wide key in each client is not an acceptable shortcut.

Attack distinctions:

- **Helper-only theft:** helper data supplies no HMAC check without the separate key/record, but this is not a proof that helper data leaks nothing. Guessing a credential determines a putative reference via helper XOR encoded credential. PUF bias, correlations, known responses, modeling, or published simulation seeds can provide extra information. No residual-entropy proof exists for this simulated construction.
- **Verifier-record database theft:** HMAC records alone do not provide an efficient credential-guess predicate without the key, assuming HMAC security and protected key custody. This claim excludes a simultaneous leak of raw reference credentials, research artifacts, or usable captured protocol traffic.
- **Key plus record compromise:** the attacker can enumerate at most `2^32` credentials per binding, recompute HMAC, and find the matching value. Key custody failure removes the new storage protection. A shared service key exposes all records in its scope; per-device keys would reduce that scope but add lifecycle work.
- **Database write access:** tag/identity substitution should fail, but deletion can cause denial of service. Old valid enrollment rows can be replayed unless the authoritative active generation is protected outside attacker-controlled rollback state. This proposal requires trusted enrollment integrity and monotonic active-generation policy; HMAC alone is not rollback protection.
- **Online access:** a pass/fail verification service is an online guessing oracle. Use authenticated callers, authorization for the intended binding, bounded attempts/rate limits, and generic external failures if exposed. Do not expose a general HMAC-computation API or let an untrusted caller enroll an arbitrary replacement credential.
- **Endpoint/process compromise:** reference credentials and session keys can be read or checks bypassed. Separating files in the same compromised process does not solve this.

The retained raw Layer 3 reference registry is a distinct secret-bearing store. Theft of that store reveals credentials directly. The keyed-record claim must never be generalized to theft of the entire current pilot state.

## Candidate Designs

| Design | Enrollment state and verification secrets | Helper-only theft | Verifier database theft | Verifier-side key compromise | Device binding and operational cost | Pilot / production assessment |
| --- | --- | --- | --- | --- | --- | --- |
| A. Public `SHA256(device_id || credential)` | Store device ID and digest; no verification secret | Helper alone adds no hash predicate, but obtaining the public digest supplies one immediately | Enumerate `2^32` values and compare; public device ID/salt only separates records | No secret key to protect this predicate | Canonical framed identity avoids ambiguity; trivial storage/lifecycle | Reject for this pilot. A fast public digest does not protect a 32-bit secret. Not a production solution for low-entropy credentials |
| B. Separate-key HMAC-SHA-256 | Store full tag, bound identity/context, version and key ID; independent secret key required to recompute | No new standalone predicate from this verifier; construction leakage caveats remain | Tag-only theft does not enable efficient offline checks without key; raw-registry/traffic leaks remain separate | Key plus records enables the 32-bit search; key plus write authority permits replacement tags | Bind canonical device and enrollment context; manage generation, rotation, access, availability, revocation | Recommended admission mechanism for the trusted software pilot. Potential component with adequate entropy/custody in a different production design; this pilot is not production secure |
| C. AEAD-encrypted reference under independent server key | Store nonce, ciphertext, authentication tag, algorithm/key ID; bind device and generation as associated data; decrypt with secret server key, then constant-time compare | No new verifier predicate without key, subject to helper caveats | Proper authenticated ciphertext alone does not expose a guess predicate without key | Key plus ciphertext reveals credential directly, without a `2^32` search | AEAD nonce discipline, authenticated metadata, decryption lifecycle and key rotation; a separate encryption key if also using B | Viable if recoverable server reference storage is required; could protect the existing reference registry at rest. More secret recovery capability than B needs. Still not production-grade with a 32-bit underlying credential |
| D1. Existing raw `RegistryEntry.credential4` plus direct comparison | Retain enrolled credential; compare candidate with protected registry credential | No additional predicate from helper alone | Reference theft discloses credential immediately if store is plaintext | No separate verifier key today; custody compromise exposes reference | Device-indexed registry binding, constant-time compare possible; simplest operation but broad access to recoverable secrets | Could detect pilot miscorrections before HKDF if explicitly added as a gate, but adds no tag-only storage separation. Not chosen merely for convenience |
| D2. Existing derived-key confirmation | Keep raw enrolled credential; derive both session keys and compare proofs | Public traffic can supply a guessing predicate even without a new verifier | Raw registry theft immediately reveals credential | Reference/session compromise defeats the relevant checks | Existing transcript device binding, nonce/session state and mutual proofs | Retain as session confirmation, but it fails the required pre-HKDF ordering and is not an independent enrollment verifier |

B is preferred for its narrowly scoped comparison authority: routine credential verification needs a tag and controlled MAC service rather than decryption or access to the raw enrollment reference. This advantage is conditional on real separation of access to the reference registry. It is not stronger security for a process that already holds every secret. C remains a reasonable complementary at-rest protection decision; adding it is not necessary to test pre-HKDF rejection and is not silently included in this proposal.

The separate-secret storage principle is consistent with [OWASP's pepper guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#peppering), which requires keeping the secret separate from the database. That analogy does not make this fast-HMAC pilot a recommended password-storage construction.

## Selected Pilot Design

Introduce `auth/credential_verifier.py`, distinct from `auth/verifier.py` (which verifies sessions and windows). It owns the versioned record, enrollment tag creation, key-provider interface, credential comparison, and local admission authority. Neither BCH nor an evaluator owns this decision.

Use an independently generated 32-byte OS-random `K_verify`, unrelated to PUF simulation randomness, reconstructed credentials, reference credentials, HKDF, or session keys. Production-like pilot execution must not derive this key from a published experiment seed. Explicit synthetic unit-test keys are allowed only as nonsecret test fixtures. Persist reusable operational keys through a protected key provider; an ephemeral run key requires ephemeral verifier records and fresh trusted enrollment on restart, never automatic fallback to an empty/default key.

Define the message precisely before implementation:

```text
LP(x) = U16-big-endian(byte_length(x)) || x
M = LP(ASCII("PUF-SNN/credential-verifier/v1"))
 || LP(ASCII(canonical_device_id))
 || LP(ASCII(enrollment_id))
 || LP(ASCII(reconstruction_id))
 || LP(ASCII(verifier_key_id))
 || credential4
enrollment_verifier = HMAC-SHA256(K_verify, M)  # all 32 tag bytes
```

This is a format specification, not code added to the repository. Reuse the existing identifier grammar `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}` and existing length-prefix convention. Treat identifiers as exact case-sensitive ASCII bytes; reject invalid input rather than trimming, case-folding, or Unicode-normalizing it. `credential4` is exactly four bytes in the representation already returned by reconstruction, preserving leading zeros. No hexadecimal/text credential conversion is part of the MAC input.

The extra enrollment, reconstruction, and key identifiers separate generations and construction/key contexts. They are looked up from trusted configuration, not accepted as authority from `HelperData.enrollment_id` or an unauthenticated request. Helper labels are routing metadata only. The local gate verifies that trusted sender binding, helper enrollment/configuration, verifier record, and receiver registry identify the same active enrollment. Formal fixtures reuse `device-0` through `device-5` across seeds, so records must be keyed by `(device_id, enrollment_id)` or provisioned in isolated seed cohorts, never by bare device name across all 120 devices.

Require same-type, fixed-length 32-byte tags and use `hmac.compare_digest` for comparison; this avoids content-dependent short-circuit equality. It does not guarantee the entire service runs in constant time or eliminate record-lookup leakage. See [Python's HMAC documentation](https://docs.python.org/3/library/hmac.html#hmac.compare_digest).

**Device-binding limit:** moving A's tag to B, changing the bound identity, or presenting A's different credential to B must fail. However, if A and B have exactly the same four-byte credential, recomputing B's HMAC using those bytes legitimately matches B's tag. Including `device_id` cannot recover the physical origin of identical bytes. All 120 saved enrolled credentials are distinct in the inspected evidence, so the planned cross-device fixtures can satisfy the different-value precondition. A strict universal requirement to reject A's credential at B even when values collide requires additional device-bound secret/attestation material or a controlled uniqueness policy with its own limitations. It cannot be promised by this formula alone.

## Enrollment Procedure

1. A trusted enrollment authority selects the canonical identity, unique enrollment generation, reconstruction profile, and intended receiver registry entry. Enrollment authorization is outside attacker-controlled authentication requests.
2. Obtain the trusted reference and four-byte credential already needed by `reconstruction.enroll()`. Create unchanged BCH helper data. Use the same credential transiently to create the HMAC verifier; no new PUF readings, retry, or reconstruction changes are needed.
3. Store a trusted verifier record containing schema/algorithm version, canonical device ID, enrollment ID, reconstruction ID, key ID, full 32-byte tag, and lifecycle metadata (enabled/revoked and creation metadata). Maintain the authoritative active generation and binding to the intended helper record. No plaintext credential or reference response belongs in this verifier record.
4. Store `K_verify` separately in the key provider; records contain only its nonsecret key ID. Keep the existing Layer 3 reference credential behind separate privileged access. It is still needed by the current receiver's HKDF; an HMAC tag cannot replace that reference as HKDF input.
5. Publish helper binding, verifier record, and receiver enrollment atomically from a coherent enrollment snapshot. Partial enrollment is disabled. Enrollment consistency may compare the provisioning inputs, but runtime candidate acceptance must not consult research truth or bypass the MAC check.
6. Limit transient secret retention. Redact object representations and exceptions; do not promise secure erasure of immutable Python bytes. Do not serialize key-provider state. Research import creates temporary fixtures from existing synthetic enrollment records only inside a privileged test setup.

Rotation uses a new key ID and trusted re-tagging of the original enrolled credential (or fresh trusted enrollment), with an explicit active-generation transition. A tag alone cannot be converted to a tag under a new key. Do not retry a mismatch under every key or generate a replacement record from the candidate. If the key is compromised, rotation alone does not undo recovered credentials; revoke affected material and decide whether re-enrollment with a new credential is required.

## Verification Procedure

1. Preserve the current result-shape/coherence checks. Decoder failure and invalid padding return before the credential-verification service is called. Invalid API/result shapes remain internal/format errors, not ordinary HMAC mismatches.
2. Resolve the intended binding from trusted sender enrollment. Require one enabled record of the supported version and exact active generation; enforce helper/config/registry consistency and key availability. No record synthesis, fallback key, identity alias, or replacement credential is allowed.
3. Compute the full HMAC over the unchanged candidate and trusted framed context. Constant-time compare with the enrolled tag. The runtime service has no enrolled-credential parameter, response reference, BER, or `evaluator_outcome` parameter.
4. On pass, retain an immutable admission context scoped to the exact candidate, device, enrollment generation, attempt, and service instance. Subsequent use of the context is bounded by attempt lifecycle/revocation. A caller-provided boolean such as `verified=True` is insufficient.
5. Commit `credential_verified` audit state before releasing admission. Only then allocate a client nonce/request, bind a single-use local receiver authorization to that exact `P3RQ`, and allow session setup. Use an opaque in-process handle recorded by the trusted service, not a public candidate hash or serialized credential-bearing token.
6. Receiver setup consumes that local authorization and checks request/device/nonce/enrollment agreement before its own HKDF. Sender derivation uses only the candidate retained in its admitted context. Clear the context on failure, completion, expiry, or generation change; reject stale, swapped, forged, or reused handles.

This local capability is an API/control-flow guard in a trusted process, not a security boundary against arbitrary code execution. Unchanged standalone HKDF primitives remain usable for primitive test vectors, but all supported candidate-to-session entry points must require admission. No optional runtime bypass flag or legacy unverified production path should remain.

## Failure Behavior

For a well-formed wrong candidate, return `Failure("credential_verification_failed")` and record that outcome with a safe mismatch detail. The attempt becomes `FAILED`, drops retained candidate/admission state, and terminates without retries or substitution.

Missing/corrupt/disabled records, wrong or unavailable key, binding/generation mismatch, and unknown version all deny admission. Classify storage/provider faults separately for operational reporting; do not hide them in reconstruction FRR. External callers receive a generic rejection, while restricted internal audit uses an enum detail, never exception contents or secret values. An audit failure also blocks request emission/derivation and marks evidence incomplete using the existing fail-closed approach.

For that attempt there is **no `P3RQ`, no server challenge, no HKDF on either endpoint, no derived session key, no client/server confirmation, no new pending or active session, and no authenticated window**. Tests assert this across both endpoints. A pre-existing independently authenticated session on the receiver is not silently replaced by a failed new attempt; “no active session” means no session created by the rejected attempt. Any policy to terminate an older session is a separate lifecycle decision.

## Pipeline Integration Point

```text
one PUF response -> unchanged BCH reconstruction -> candidate format/coherence check
    -> independent enrollment HMAC verification
       FAIL -> terminal rejection; zero HKDF / keys / confirmation / new sessions
       PASS -> audited local admission -> P3RQ / authorized receiver setup
            -> receiver HKDF -> sender HKDF -> mutual session confirmation
            -> authenticated sensor windows
```

The exact sender insertion point is in `auth.session.Sender.begin_attempt()`, **after the candidate/message consistency check through current line 247 and before `_start`, nonce generation, `_candidate` retention, `PENDING`, or the `P3RQ` return at lines 248–256**. The audited wrapper coordinates the corresponding audit commit before the request is exposed. This is earlier than `answer_challenge()` because checking only there would allow the receiver's line-442 HKDF first.

For the stronger zero-HKDF guarantee, `Verifier.begin_session()` also requires a trusted local admission authorization before line 442. Update local setup callers to convey the opaque handle separately from the unchanged request bytes; do not place it in Wire 2 or trust an unauthenticated request field. Both the base session classes and audited subclasses must enforce the rule, since tests and callers use both. The same service binds and validates authorization; the experiment runner cannot manufacture success from evaluator labels.

Responsibilities remain explicit:

| Component | Proposed responsibility |
| --- | --- |
| Enrollment authority | Provision coherent helper, tag, protected key reference, active identity/generation, and existing receiver reference |
| Reconstruction | Recover a syntactically valid candidate from one reading; no authenticity decision or evaluator truth |
| Credential verifier/admission service | Check enrolled HMAC and trusted context; authorize only the exact candidate/attempt; fail closed |
| Layer 3 sender/receiver | Require admission, then retain current transcript/HKDF/confirmation semantics and window protection |
| Audit layer | Commit secret-free ordered decisions and derivation instrumentation; distinguish credential verification from identity authentication |
| Research evaluator | Determine labels and metrics outside admission; never influence its answer |

If faculty requires remote enforcement without trusting the sender or a shared local admission service, this integration proposal is insufficient. That is a deployment/protocol decision to resolve before implementing a remote version, not an excuse to silently move verification after server derivation.

## Audit Behavior

Prefer a new `puf-snn-auth-audit-v2` schema rather than changing the meaning of saved v1 records. Keep Wire protocol version 2.0 separate from audit schema version. Existing window events remain semantically unchanged.

| New outcome/event | Meaning and order | HKDF count for this attempt |
| --- | --- | --- |
| `reconstruction_decoder_failure` | No candidate; verifier not invoked | 0 |
| `reconstruction_invalid_format` | Padding/format rejection; verifier not invoked | 0 |
| `credential_verification_failed` | Candidate denied; detail identifies mismatch or safe configuration/service fault | 0 |
| `credential_verified` | Independent check passed, prior to request release | 0 at this point |
| `session_derivation_started` | Per-endpoint event committed immediately before HKDF invocation; requires admission ID | Normally 1 per endpoint after this event |
| `session_established` | Endpoint confirmation succeeded; preserve sender/receiver activation distinction | Normally 1 per endpoint |

Retain terminal confirmation-failure and derivation/internal-error categories; passing the credential check does not guarantee later availability or confirmation success. Add `credential_verification_result` (`pass`, `fail`, `not_checked`, `error`) independently from current session `authentication_result`; `identity_authenticated` remains false at `credential_verified`. Derivation-start records express intended invocation order, while explicit call counters/trace instrumentation establish actual execution in tests and completed experiments. An absent latency measurement alone does not prove zero calls. A crash between event and invocation is an incomplete attempt, not evidence of either execution or nonexecution.

Allowlisted metadata: recorder/event/attempt IDs; canonical device/enrollment IDs; admission correlation ID; verifier algorithm/version and nonsecret key ID; active generation; outcome/detail enums; decoder status/correction count/padding status; reconstruction, verification, and per-endpoint derivation durations/call counts; timestamps; software/dependency/config versions; source commit; whole-input-artifact identity/hash and row locator. Seed, phase, sweep index, noise SD, device index, and attempt number are appropriate **only for explicitly synthetic research provenance**. Do not log any RNG seed used to generate an operational credential or verifier key.

Exclude credential bytes, candidate message bits, reference/noisy PUF bits, helper dumps, HMAC verifier/tag values, verifier key, PRK, session keys, confirmation proofs, secret-bearing representations, and raw exception messages. Also exclude public hashes of individual credentials/candidate messages: they recreate the forbidden guessing predicate. Whole-artifact hashes reference existing synthetic evidence; they are not a license to hash operational secrets into logs. Validate provenance inputs rather than allowing arbitrary strings to smuggle secrets into an otherwise safe schema. Document that existing research evidence is a separate intentionally revealing artifact class.

Add a verification latency slot and explicit per-role HKDF call accounting without conflating verifier MAC computation with HKDF's internal HMAC calls. Audit I/O is measured separately. Preserve fail-closed in-memory audit semantics; durable/tamper-evident logging is an additional future decision.

## Test Plan

These are future tests, not executed validation of an implemented verifier. Use synthetic trusted enrollment fixtures and patch the runtime admission inputs, never evaluator truth inside the verifier. Test base session classes as well as audited endpoints.

| Case | Required assertion |
| --- | --- |
| Correct four-byte candidate | Full tag matches; one verification; admission succeeds; candidate bytes remain unchanged |
| Incorrect coherent valid-format candidate | `credential_verification_failed`; no request/confirmation/key/session; both endpoint HKDF counters zero |
| Nominal seed 2222 / device 3 / attempt 88 | Saved row 2789 is denied before HKDF |
| Nominal seed 6543 / device 1 / attempt 75 | Saved row 7976 is denied before HKDF |
| Full saved miscorrection population | Exactly 2 nominal + 428 sweep = 430 cases loaded and all rejected before either endpoint HKDF |
| Wrong-device candidate | Use distinct A/B credentials; A's bytes under B's trusted binding fail |
| Device/tag substitution | A's tag/record cannot be relabeled B; changed case/invalid identifiers and ambiguous concatenation attempts fail validation or verification |
| Equal credentials on two devices | Explicit limitation test: B's own bound tag accepts the shared bytes; do not assert impossible physical-origin discrimination |
| Corrupt verifier tag | Bit flip, wrong length, wrong type, malformed encoding all fail closed |
| Missing record | No record synthesis or fallback; zero derivation |
| Key mismatch/unavailable key | Wrong key, unknown key ID, provider exception, and disabled key deny admission |
| Decoder failure | Credential-verifier call count 0; HKDF call count 0 |
| Invalid padding | Credential-verifier call count 0; HKDF call count 0 |
| Invalid candidate shape | Length/type/message disagreement or malformed result fails before HMAC verification |
| Correct complete handshake | One `derive_session_key`, one `hkdf_extract`, and one `hkdf_expand` per endpoint: two of each total; confirmation follows; window acceptance still works |
| Admission bypass and reuse | Direct `begin_session` without valid local authorization rejects before HKDF; swapped request/candidate/identity, stale generation, forged handle, and handle replay fail |
| Enrollment lifecycle | Partial/disabled/duplicate records, helper binding mismatch, revocation, generation change, and rotation races deny stale admission |
| Audit ordering/failure | Verified event precedes each derivation; mismatch has no derivation or establishment event; audit failure blocks progression |
| Secret-free logs | Inspect in-memory audit, JSONL, metrics, stdout/stderr, error paths, and object representations for credential, verifier key, PRK, and session key leakage |
| Existing active session | Rejected new attempt creates/replaces no session and releases no new-attempt windows |

For zero-call proof, patch `puf_snn.auth.session.hkdf_extract` and `hkdf_expand` with counting/raise-on-call wrappers and instrument both endpoint `_derive_key` methods. Also patch `derive_session_key` where used: it is imported into `auth.sender` and `auth.verifier`, so patching only its original module name can miss subclass calls. Instrument `client_proof`, `server_proof`, request/challenge emission, and pending/active state. Distinguish the new verifier's HMAC from the HKDF HMAC operations. Positive tests wrap the real derivation and assert exact counts rather than replacing it with a dummy success.

Secret tests use controlled sentinel bytes and check binary, hex, base64, list/message-bit representations and forbidden field names, plus hashes of individual secrets. Check the new verifier tag is absent too. Representation checks apply to new secret-bearing verifier/admission types; the unchanged `ReconstructionResult` already exposes candidate fields in its representation, so test that operational logging never serializes that object rather than claiming its existing representation is redacted. Schema validation and explicit serialization allowlists complement content checks. Failure exceptions must not interpolate inputs. Retain confirmation-tampering tests after a legitimately verified candidate to prove that confirmation remains necessary.

**Saved-case loading without reconstruction:** load the existing `attempts.jsonl` and `enrollments.json` as immutable fixtures, check provenance/representation, and select records with `evaluator_outcome == "evaluator_wrong_match"`. Reconstitute the saved `ReconstructionResult` from recorded fields, checking syntax/coherence only. Provision temporary HMAC records once from the enrolled synthetic credentials in privileged test setup; pass only candidate, trusted binding, and verifier service to admission. Evaluator truth is used to select/score the population, never to decide acceptance. Stub reconstruction/simulation entry points to raise if invoked. Use `(phase, sweep_index, simulation_seed, device_id, attempt_number)` plus source artifact/row identity to disambiguate cases. Do not regenerate responses, search for new miscorrections, or modify sealed evidence.

The two mandatory nominal fixtures are `baseline`, SD 0.1, enrollment IDs `layer2-experiment-v1:2222:device-3` and `layer2-experiment-v1:6543:device-1`, respectively. They remain individually named regression cases as well as members of the 430-case population; do not count them twice in reported totals.

## Experimental Evaluation Plan

Create a separate future verifier-evaluation artifact directory/version. Keep the formal Layer 2 artifacts and their original summaries unchanged. The first evaluation should use saved results as inputs without running reconstruction. It measures credential admission on saved candidates, not new PUF reliability.

Report by nominal/sweep condition and by device/run, with pooled counts as a secondary summary:

| Metric | Definition / denominator |
| --- | --- |
| Correct reconstructed candidates `C` | Saved valid-format candidates equal to trusted evaluator credential |
| Verifier true accepts `TA` | Correct candidates admitted; report `TA/C` |
| Verifier false rejects `FR` | Correct candidates denied; report `FR/C`, with mismatches versus operational/configuration errors separated |
| Miscorrected candidates `W` | Saved valid-format candidates unequal to evaluator credential |
| Verifier catches `R` | Wrong candidates denied before HKDF; split actual HMAC mismatches from other rejection faults |
| Wrong candidates passing `F` | Wrong candidates admitted; report `F/W`; incomplete/not-evaluated cases separately |
| Wrong-device attempts | Separate synthetic population with source/target binding, distinct-value/collision classification, admits/rejects, and denominator |
| HKDF execution | Per-attempt sender/receiver calls and stage order for every category, including failures and provider faults |

For complete, well-provisioned runs require `C = TA + FR` and `W = R + F`, with `R` explicitly meaning rejection before either HKDF. If a wrong candidate is rejected only after derivation, it is an admission invariant failure, not a catch. Provider errors and incomplete attempts must never be removed to improve the rate; show them and their effect on reconciliation. Report operational false rejects separately from cryptographic mismatch false rejects. Preserve decoder failures/invalid format as reconstruction outcomes with verification `not_checked`.

The saved nominal set supplies `C=11,805`, `W=2`, plus 186 decoder failures and seven invalid-format records. The conditional desired nominal outcome is 11,805 true accepts, zero added verifier false rejects, and two catches before HKDF. That would preserve 195 reconstruction-related unsuccessful attempts (1.625%), relocating miscorrection rejection earlier; it would not improve reconstruction accuracy. These are targets, not measurements. Across all saved miscorrections the primary target is 430/430 pre-HKDF catches and zero wrong-candidate admissions. Observing that target does **not** prove zero false-accept probability in general; conditions/devices are correlated and this population is selected, not a random adversarial trial distribution.

Measure verifier latency with a monotonic high-resolution clock from entry to the verification operation through result, including record lookup, context validation, key-provider access, MAC, and comparison. Separately report any isolated MAC timing and audit I/O; do not present it as end-to-end verification. For pass/mismatch/configuration-error groups report sample count, mean, median, p95, maximum, units, warm-up policy, machine/runtime, and provider/cache mode. Use linear p95 index `(n-1)*0.95`, retain outliers, and report null for empty groups. Verification-not-invoked records have null duration, not measured zero.

For the saved-input evaluation, pair each stored reconstruction duration with its newly measured verification duration. Report the distribution of those per-attempt sums as **archived reconstruction plus current verification, a composite estimate**, not freshly measured end-to-end latency. Do not sum separate percentiles. Decoder/format failures have zero verification work but a null verifier timing; their pre-admission path duration is the recorded reconstruction time. Future same-run reconstruction-plus-verification timing requires separate authorization to execute reconstruction, measures the combined interval directly, and records acquisition/audit inclusion explicitly. None is executed for this design task.

Future results must retain safe row locators, source/config versions, evidence hashes and their representation, algorithm/key IDs (never key bytes or secret-generating seeds), per-stage outcomes, counters, and completeness markers. Fixed synthetic fixture keys may support deterministic unit tests; experimental keys remain protected, with re-enrollment or securely retained keys for replay. Timing and success claims must identify which mode was used.

## Security Limitations

- The credential is a 32-bit proof-of-mechanism value, with at most 32 bits of entropy. Its actual entropy against someone holding the published research seeds/artifacts is effectively absent. HKDF output length does not create additional uncertainty about the input; [RFC 5869](https://www.rfc-editor.org/rfc/rfc5869.html) describes extraction/expansion, and this finite 32-bit input-space limitation follows directly for this pipeline.
- A public unkeyed credential hash exposes an offline predicate over at most 4,294,967,296 guesses. Public device binding or salt does not enlarge that per-device secret space. The selected keyed tag removes that particular standalone public-verifier predicate only while its key remains secret.
- This gate does not eliminate **existing traffic-based guessing**. From the inspected protocol, an observer with a transcript and client confirmation can try a credential, derive the corresponding key from public salt/info, and compare the predicted proof. A known authenticated window/tag plus enough handshake context can similarly check guesses. This is a deduction from the current code, not an executed attack. The new verifier neither fixes nor worsens the fundamental 32-bit traffic risk, and Wire 2 remains unchanged in this proposal.
- Verifier-key compromise together with tags enables exhaustive credential search. A server reference-store compromise is worse: it directly reveals credentials. A 256-bit HMAC output/key is not a claim of 256-bit device authentication strength.
- HMAC comparison has a negligible collision risk under its assumptions, not a mathematical guarantee of rejection for every distinct input. Passing all 430 saved cases is a regression result only. Credential-value collisions across devices are a separate 32-bit limitation.
- Simulated PUF noise/manufacturing assumptions do not establish physical unclonability, tamper resistance, side-channel resistance, or residual entropy after helper exposure. Deterministic fixtures validate control flow and measurement only.
- Production would require independently justified effective credential entropy after public/helper leakage (for example, a design target of at least 128 bits for a 128-bit security objective), suitable hardware/extraction analysis, protected enrollment/key custody, authenticated deployment channels, revocation and rollback controls, online-abuse controls, and independent protocol review. Simply increasing HKDF output or HMAC tag length cannot satisfy that requirement. Changing credential length requires a new reconstruction design and evidence, outside this task.
- The local admission capability depends on correct trusted execution and enrollment. It is not a remote proof of successful PUF reconstruction, nor does it prove where bytes originated. Python reference deletion does not promise zeroization. Existing audit storage is neither durable transactional storage nor tamper-evident logging.

## Proposed File Changes

The following is an implementation impact inventory, **not changes made now**. Paths are repository-relative. Prefer a new admission/audit profile while preserving frozen experiment identities and old evidence.

| Classification | File(s) | Proposed work / necessity |
| --- | --- | --- |
| New verifier module | `src/python/puf_snn/auth/credential_verifier.py` (new) | Versioned HMAC record, framing, enrollment API, separate key provider, constant-time verification, local admission authority and lifecycle |
| Enrollment integration | `src/python/puf_snn/auth/session.py` | Extend trusted provisioning/context association without embedding secrets into public helper data; require verifier dependency and coherent receiver binding |
| Enrollment integration | `src/python/scripts/run_layer3_demo.py` | Provision synthetic verifier records/key provider and admission context in `initialize_material()`; adapt `establish()` |
| Session admission integration | `src/python/puf_snn/auth/session.py` | Mandatory sender gate before request; receiver local-authorization check before derivation; preserve candidate identity and cleanup |
| Session admission integration / audit | `src/python/puf_snn/auth/sender.py`, `src/python/puf_snn/auth/verifier.py` | Coordinate verification/derivation audits, enforce dependency, pass/consume local authorization, record counters/timing and failure state |
| API export | `src/python/puf_snn/auth/__init__.py` | Export new public provisioning/admission types if the chosen API needs them; no mandatory export of secret internals |
| Audit/schema change | `src/python/puf_snn/auth/audit.py`; `schemas/auth-audit-v2.schema.json` (new) | New schema/profile selection, outcome fields, verification latency, correlation and call counters; preserve v1 schema for historical readers |
| Configuration/profile | `src/python/puf_snn/auth/config.py`; `configs/authentication_v2.json` (new) | Version the mandatory-admission profile while retaining Wire 2.0; accept key identifiers/provider configuration only, never key bytes; preserve old config evidence |
| Tests (new) | `tests/auth/test_credential_verifier.py`, `tests/auth/test_credential_admission.py`, `tests/experiments/test_credential_verifier_experiment.py` | Unit, negative/order/bypass, saved-case and reporting tests described above |
| Tests (existing fixtures/expectations) | `tests/auth/test_session.py`, `tests/auth/test_layer3_integration.py`, `tests/auth/test_finalization.py`, `tests/auth/support.py` | Provision verified fixtures; move wrong-candidate rejection earlier; remove unchecked fixture session admission; preserve primitive vector tests |
| Tests (audit/setup consumers) | `tests/auth/test_audit.py`, `tests/auth/test_lifecycle_audit.py`, `tests/auth/test_verifier.py`, `tests/auth/test_classifier_integration.py`, `tests/auth/test_protocol_rejection.py` | Update new-profile schema/setup consumers as required and check unchanged window/replay/release behavior; fixture helpers should minimize direct edits |
| Experiment/reporting | `src/python/scripts/evaluate_credential_verifier.py` (new); `schemas/credential-verifier-attempt-v1.schema.json` (new) | Read saved inputs without reconstructing; separate labels from admission; emit safe result categories, timings, counters, reconciliation, manifests |
| Experiment/reporting | `src/python/scripts/benchmark_classifier_pipeline.py` | Replace its currently null/unmeasured independent-verification slot and update setup scope/latency descriptions when measured |
| Experiment consumers | `src/python/scripts/evaluate_stream_attacks.py`, `src/python/puf_snn/attacks/evaluation.py`; `tests/test_stream_evaluation.py` | Adapt only if the shared establishment signature changes; update future report statements that independent verification is unmeasured; no classifier/attack logic redesign |
| Frozen Tier 1 dependency | `src/python/scripts/run_tier1_attacks.py`; `tests/tier1/test_tier1.py` | Its baseline hash guard and direct synthetic setup must be addressed for any new-profile experiment. Preserve the frozen v1 runner in its recorded revision; create a separately versioned runner/config/baseline if evaluating Tier 1 under the new admission profile. Do not bypass the guard or rewrite old manifests |
| Documentation | `docs/credential-verifier-design-week5.md` (this file); later `docs/puf-layer3-design.md`, `docs/authenticated-window-interface.md`, `docs/puf-layer2-design.md`, `README.md` | Document syntax/authenticity separation, custody, API/schema/profile changes and run instructions; add a separate future verifier results report |

Unchanged algorithms/artifacts: `reconstruction/credential.py`, `reconstruction/bch.py`, BCH tests, `run_reconstruction.py`, its configuration/auditor and all formal results, Wire 2 codec, authenticated-window schemas, per-window HMAC, classifier/inference behavior, and golden wire vectors. Keep `schemas/auth-audit-v1.schema.json` and `docs/layer3-baseline-v1-manifest.json` as historical contracts. Low-level HKDF-vector tests should remain valid without turning primitive functions into implicit session admission APIs.

The frozen Layer 3 manifest pins source/test/schema hashes; `run_tier1_attacks.check_baseline()` (around lines 125–137) rejects changed inputs. A future implementation will therefore require an explicitly versioned new baseline or isolated old revision for historical runs, not updated hashes pretending to be the original baseline. The manifest also names documentation paths absent from this checkout (`docs/authentication-v1.md` and `docs/layer3-final-status-and-tier1-handoff.md`); resolve historical baseline completeness separately before promising that old Tier 1 runs can execute here. No old manifest or evidence is repaired in this task.

## Open Faculty Decisions

1. **Trust and placement:** Is the first implementation explicitly a trusted co-located software pilot with a key-owning admission service and local authorization on both endpoints? Recommended: yes. A remote or hostile-client threat model needs a separate protected admission channel/attestation design before implementation.
2. **Key custody and recovery:** Choose ephemeral per-run versus persistent protected key storage, service-wide versus per-device scope, caller authorization/rate limits if exposed, rotation/revocation policy, and owner. The key must be independent and absent from verifier records, public helpers, source/config dumps, and reports.
3. **Reference registry:** Accept the existing raw reference in protected process memory as an explicit pilot limitation, or separately scope AEAD protection at rest. Do not claim database-leak protection for a database that also contains `credential4`.
4. **Identity guarantee:** Confirm that wrong-device tests mean distinct credential values with authoritative identity/generation binding. If identical-value cross-device rejection is required, choose additional device-bound secret/attestation material or a new credential design; HMAC context binding alone cannot provide it.
5. **Lifecycle integrity:** Specify trusted active-generation storage and behavior during rotation/revocation/races, including stale local authorization and pre-existing active sessions. No automatic re-enrollment on mismatch.
6. **Evidence/profile transition:** Approve a new admission/audit profile and baseline identity, preserving frozen Layer 2 and Layer 3 evidence. Agree how future regression tooling verifies the known CRLF/LF checkout representation, without editing sealed input files or disabling integrity checks.
7. **Claim and evaluation scope:** Keep the first evaluation limited to admission on saved candidates, target all 430 known catches before either HKDF, retain separate mismatch/service-failure metrics, and explicitly accept the remaining 32-bit, public-traffic, synthetic-PUF, and research-artifact limitations. Any fresh reconstruction or production security work requires separate scope.

Design recommendation: proceed to implementation only after these deployment/custody and claim boundaries are resolved. This document completes the requested design work; no verifier implementation or new experimental result is claimed.
