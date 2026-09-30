# Pre-HKDF Credential Admission Integration

Phase 2, September 30, 2026. Implements mandatory local credential admission using the [Phase 1 primitive](credential-verifier-implementation-week5.md) and the [security design](credential-verifier-design-week5.md). This is a trusted co-located software research pilot, not a production deployment.

## Scope

Control flow and testing only. Supported sender and receiver constructors now require the same `CredentialAdmissionService`. The Phase 1 HMAC comparison remains the authority for candidate admission. No optional bypass, legacy unverified session mode, evaluator-truth check, or substitution of the receiver's credential for the candidate was added.

Exact files changed in this phase:

| File | Change |
| --- | --- |
| `src/python/puf_snn/auth/credential_verifier.py` | Local opaque authorization, issuance table, request/challenge binding, single-use receiver consumption/sender claim, expiry and local revocation |
| `src/python/puf_snn/auth/session.py` | Mandatory service dependency; sender verification before request; receiver authorization before derivation; candidate continuity and cleanup |
| `src/python/puf_snn/auth/sender.py` | Preserve schema-v1 generic refusal vocabulary for admission failures; update current behavior description |
| `src/python/puf_snn/auth/verifier.py` | Forward mandatory service and separate local admission argument; preserve generic audit-v1 refusal vocabulary |
| `src/python/puf_snn/auth/config.py` | Require explicitly versioned current admission profile/config |
| `src/python/puf_snn/auth/__init__.py` | Export `LocalAdmissionAuthorization` alongside the existing Phase 1 types |
| `src/python/scripts/run_layer3_demo.py` | Trusted HMAC enrollment with an OS-random verifier key, shared service, authorization handoff, new config/output defaults |
| `configs/authentication_v2.json` (new) | Current mandatory-admission configuration; no verifier key bytes |
| `tests/auth/test_credential_admission.py` (new) | 35 integration tests, including zero-HKDF instrumentation and two saved nominal regressions |
| `tests/auth/support.py` | Real synthetic HMAC provisioning and verified sender requests for shared auth fixtures |
| `tests/auth/test_session.py` | Shared service, local authorization arguments, earlier miscorrection rejection, and valid admission for RNG/collision tests |
| `tests/auth/test_layer3_integration.py` | Updated material/handshake setup and wrong-candidate rejection expectations |
| `tests/auth/test_finalization.py` | Provision service in sender/receiver fixtures and supply local authorization |
| `tests/auth/test_lifecycle_audit.py` | Use admitted requests for pending/active lifecycle fixtures |
| `tests/auth/test_verifier.py` | Use explicitly provisioned current receiver fixtures |
| `tests/auth/test_audit.py` | Test current config and explicit rejection of historical v1 config by current code |
| `docs/credential-verifier-session-integration-week5.md` (new) | This report |

The Phase 1 design, implementation report, and 48 primitive unit tests were not edited. Their descriptions of the standalone-only implementation are the historical Phase 1 state; this report documents the subsequent integration.

No dependency was installed/upgraded in this phase. No formal Layer 2 rerun, Tier 1 run, 430-case evaluation, formal latency benchmark, audit-v2 implementation, historical manifest update, commit, or push was performed. Existing auth tests exercise small synthetic enrollment/reconstruction fixtures and demos in temporary directories; they do not rerun formal research experiments.

## Previous Flow

`Sender.begin_attempt()` structurally checked a `ReconstructionResult` and emitted `P3RQ` for any coherent four-byte valid-format candidate. `Verifier.begin_session()` derived from `RegistryEntry.credential4` when building the challenge. `Sender.answer_challenge()` then derived from the candidate. A wrong credential reached both derivations before the receiver's client-confirmation comparison rejected it with `key_confirmation_failed`.

The original ordering was receiver HKDF, sender HKDF, then mutual confirmation. Checking only inside the sender's `answer_challenge()` could not establish zero HKDF on both endpoints.

## New Flow

```text
valid-format coherent candidate
    -> Phase 1 HMAC credential verifier
    -> service issues opaque local admission
    -> sender creates and binds exact P3RQ bytes
    -> receiver checks and consumes local admission
    -> receiver binds its generated transcript
    -> receiver HKDF -> P3CH
    -> sender claims unchanged verified candidate for that transcript
    -> sender HKDF -> client confirmation
    -> server confirmation -> endpoint activation -> authenticated windows

wrong valid-format candidate
    -> credential verification failure
    -> no admission / P3RQ / receiver challenge
    -> ZERO sender HKDF and ZERO receiver HKDF
    -> no confirmation / new pending or active receiver session
```

The HMAC construction, four-byte candidate representation, full 32-byte tag, independent key, and constant-time tag comparison are unchanged from Phase 1. Verification uses trusted enrollment records rather than evaluator labels. No credential or public credential hash is added to the request.

## Admission Authorization

`LocalAdmissionAuthorization` is an opaque, fieldless object with a redacted representation. Ordinary construction raises `TypeError`; it has no `verified=True` constructor or mutable attributes, and pickling is rejected. A lookalike allocated with `object.__new__` has no authority: the configured service must find that exact object in its private live issuance table.

`CredentialAdmissionService.authorize()` calls the Phase 1 verifier and issues one identity only on success. The service-owned state binds:

- The exact immutable verified candidate, retained privately, never a public candidate hash.
- Device ID, enrollment ID, reconstruction profile and the exact enrollment-record snapshot (which includes key ID and tag).
- The local attempt ID and monotonic expiration deadline.
- The exact `P3RQ` byte string, bound once after verification, including its device ID and nonce.
- The receiver-generated transcript, bound once after receiver consumption, including boot/session IDs, server nonce, request nonce, device and limits.

The handle contains no verifier key or credential fields and is passed separately through `begin_session(..., admission=sender.admission)`. It is neither serialized into Wire 2 nor sent as an unauthenticated request field. Sender and receiver must use the same service instance; a service with even identical key/record contents cannot accept another service's handle.

The lifetime is the configured handshake timeout, checked against a monotonic deadline at every service operation. `consume()` is protected by the service lock and succeeds once. The sender's `claim_candidate()` requires prior receiver consumption, exact request/transcript/attempt/binding agreement, and unchanged candidate bytes. A claim removes the handle, even when a swap is detected. The claimed bytes come from the verifier's private candidate state, not from `RegistryEntry.credential4`.

Revocation removes the handle; `revoke_enrollment()` denies that device/enrollment generation and removes its outstanding handles. A changed, unsupported, disabled, or revoked store record invalidates the snapshot. The receiver separately checks its current enabled registry entry and supplies its current enrollment/profile to consumption. There is no persistent generation authority or rotation service in this phase.

Sender failure, request-construction failure, and audited sender failure revoke retained admission state. Receiver errors after successful consumption revoke that attempt; pending termination also revokes it. A denied duplicate/replay that did not itself consume authorization does not revoke the original valid pending attempt. This avoids letting a refused duplicate invalidate an already-issued challenge.

Expiration validity is immediate when checked; physical removal of abandoned entries is lazy on subsequent service operations/new authorization. This is not guaranteed wall-clock erasure. The pilot has no background cleanup service or remote resource-abuse protection. Python private attributes and locks do not isolate secrets from malicious code in the same process.

## Sender Changes

The insertion point is `auth/session.py`, `Sender.begin_attempt()`, at the `CredentialAdmissionService.authorize()` call (line 260 in this implementation). It is **after** all existing result type, decoder outcome, padding, candidate length, and message/credential coherence checks, and **before** client nonce allocation, `P3RQ` construction, and transition to `PENDING`.

Decoder failure and invalid padding still return `failed_reconstruction` before the credential verifier is invoked. For a well-formed candidate, the sender uses its trusted provisioned device/enrollment/helper configuration to authorize. A failure returns `Failure("credential_verification_failed")`, moves the attempt to `FAILED`, and clears candidate, request, authorization and key state. No retry or re-enrollment occurs.

On pass, the sender retains the unchanged candidate and opaque handle, creates the normal request bytes, binds them once in the service, and becomes pending. The audited wrapper commits its existing admission audit row before exposing the request; an audit failure revokes the unexposed handle and fails the attempt.

`Sender.answer_challenge()` retains the existing transcript/device/nonce/limit checks and then calls `claim_candidate()` (line 313) before `_derive_key()`. It detects candidate replacement, attempt replacement, unconsumed authorization, revoked/stale authorization, or a different transcript. Only the exact admitted bytes reach the existing derivation function. There is no fallback to an enrolled reference credential.

## Receiver Changes

Both the base `auth.session.Verifier` and audited `auth.verifier.Verifier` require `admission_service` at construction. `begin_session()` retains its request/version/registry/resource checks but adds mandatory `consume()` at `auth/session.py:478`.

Consumption occurs **before** session-ID/server-nonce allocation, HKDF, challenge framing, or `_Pending` creation. It requires a live, unconsumed handle owned by this service and the exact authorized request/device/enrollment/reconstruction binding. After successful consumption, the generated transcript is bound to that handle before receiver HKDF. Existing registry/resource errors can still reject earlier without derivation; absence of authorization never enables a legacy path.

Receiver admission rejection returns the existing generic `REFUSAL` bytes with local `last_reason="credential_verification_failed"`. It creates no pending/active state for the rejected attempt and does not replace an already active session. Constructors without an admission service are unsupported; `admission=None` on a syntactically valid request is an explicit pre-HKDF rejection.

## Version/Profile Transition

Current behavior is identified as:

- Config version: `puf-snn-auth-config-v2`.
- Protocol profile: `puf-snn-l3-credential-admission-v1-wire2`.
- Configuration file: `configs/authentication_v2.json`.
- Sender provisioning carries that current profile.
- Demo default output root: `results/week-5/will/credential-admission-demo`, with an exclusive timestamped `admission-...` directory.

Wire version remains **2.0**. The profile distinguishes source/control-flow behavior rather than changing the wire transcript. `AuthConfig` rejects historical v1 config instead of silently interpreting it as the new profile. The demo provisions an OS-random independent verifier key and returns a fourth material item, the shared service; current test callers were updated accordingly.

This source is **not the historical frozen Layer 3 Authentication Baseline v1**. `docs/layer3-baseline-v1-manifest.json`, `configs/authentication_v1.json`, old audit schema and saved Tier 1 artifacts are unchanged. No historical baseline guard is bypassed. Historical execution requires its recorded source revision; these modified current sources must not be substituted under old baseline hashes.

The old benchmark/stream-evaluation runners still reference historical config and are not migrated or run in this phase. They require an explicit subsequent profile/reporting transition; current `AuthConfig` fails closed on those old config values. No compatibility claim is made for running the frozen Tier 1 workflow against current source.

## Failure Behavior

For a rejected valid-format candidate:

| Observable | Result |
| --- | --- |
| Session-facing sender result | `credential_verification_failed` |
| Sender state | `FAILED`; candidate/request/admission/key cleared |
| Request nonce or `P3RQ` | Not allocated/emitted |
| Sender derivation / HKDF extract / HKDF expand | 0 |
| Receiver derivation / HKDF extract / HKDF expand | 0 |
| Challenge / client proof / server proof | 0 |
| New receiver pending / active state | None |
| Previously active receiver session | Preserved |

Rejected receiver authorization similarly stops before receiver derivation/challenge/state creation. If rejection concerns a candidate/attempt/transcript swap **after a valid receiver challenge**, receiver HKDF has already legitimately run once for the original admitted attempt; the sender performs zero derivations with the swapped value. These tests do not falsely claim to undo earlier valid work. Both-endpoint zero-HKDF is the claim for initial candidate/admission rejection, including the two saved miscorrections.

Audit-v2 is deliberately deferred. Existing audited wrappers map the new admission failure to schema-v1 `session_refused`, with no credential/tag/handle dump. This preserves valid generic failure records without adding new schema fields/events or claiming fine-grained verification auditing. The returned failure/local reason remains `credential_verification_failed`. Credential verification is not marked as successful remote identity authentication; mutual confirmation remains required.

## Zero-HKDF Evidence

`test_credential_admission.py` adds **35 test methods**, including subtests for base and audited endpoints. The `zero_work()` context patches all three derivation lookup locations, each with a raising spy, and checks call counts after execution (so an implementation catching the spy exception cannot hide a call):

- `puf_snn.auth.session.derive_session_key`
- `puf_snn.auth.sender.derive_session_key`
- `puf_snn.auth.verifier.derive_session_key`
- `puf_snn.auth.session.hkdf_extract` and `hkdf_expand`
- `client_proof`, `server_proof`, `_Pending`, and `_Active`

It also wraps `session.frame` and requires zero framing calls on rejection. Candidate-rejection helpers forbid `secrets.token_bytes` and assert cleared sender state and empty receiver pending/active state. Receiver-rejection helpers preserve before/after state snapshots.

Representative invariant tests:

| Test name | Evidence |
| --- | --- |
| `test_wrong_valid_format_zero_work_base_and_audited` | Both endpoint implementations reject before request, both derivations, proofs or state creation |
| `test_decoder_failure_never_invokes_verifier`, `test_padding_failure_never_invokes_verifier` | Phase 1 verification count 0, all protected operation counts 0 |
| `test_missing_record`, `test_disabled_record`, `test_revoked_record`, `test_wrong_verifier_key` | Provisioning/verifier denial is pre-request and pre-HKDF |
| `test_device_binding_mismatch`, `test_enrollment_binding_mismatch`, `test_reconstruction_binding_mismatch` | Binding failures cannot reach derivation |
| `test_receiver_missing_authorization_base_and_audited`, `test_forged_authorization_and_boolean`, `test_foreign_service_authorization` | Direct/forged/foreign-service admission is denied |
| `test_request_swap`, `test_authorization_device_swap_at_receiver`, `test_receiver_enrollment_generation_changed` | Exact request and current registry binding enforced |
| `test_authorization_replay_across_receivers` | Second receiver cannot consume; original handshake can still finish |
| `test_stale_authorization`, `test_revoked_authorization`, `test_revoked_enrollment_rejects_handle_and_future_candidates` | Expired/revoked authorization fails before receiver HKDF |
| `test_candidate_swap_detected_before_sender_hkdf`, `test_sender_attempt_identity_swap`, `test_challenge_session_context_swap` | No sender derivation after swapping an admitted value/context |
| `test_sender_cannot_derive_before_receiver_consumption` | Forged challenge cannot start sender HKDF before local receiver approval |
| `test_existing_active_session_survives_failed_new_candidate` | Failed new attempt does not mutate the prior receiver session |
| `test_sender_audit_failure_revokes_unemitted_authorization`, `test_request_construction_failure_clears_base_admission` | Failed setup cannot leave a usable exposed authorization |

The positive audited test `test_correct_reconstructed_candidate_one_derivation_each_and_window` measures one verifier invocation and one issued handle; one derivation through the sender alias and one through the receiver alias; two total extracts and two expands; one pending and one active allocation; and framing order `P3RQ`, `P3CH`, `P3CF`, `P3OK`. The original module's derivation name is not called in this audited path because the modules imported aliases. `test_correct_base_endpoints_use_common_derivation_twice` separately proves two calls through the base module name. The positive test also accepts and releases an authenticated window after the new handshake.

## Known Miscorrection Regressions

Both tests passed using immutable saved formal evidence:

| Regression | Saved location | Result |
| --- | --- | --- |
| Seed 2222 / device 3 / attempt 88 | `attempts.jsonl`, one-based line 2789; enrollment `layer2-experiment-v1:2222:device-3` | `credential_verification_failed`; no P3RQ; sender HKDF 0; receiver HKDF 0 |
| Seed 6543 / device 1 / attempt 75 | `attempts.jsonl`, one-based line 7976; enrollment `layer2-experiment-v1:6543:device-1` | Same pre-HKDF rejection and zero counts |

The test names are `test_nominal_seed_2222_device_3_attempt_88` and `test_nominal_seed_6543_device_1_attempt_75`. Both load from `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/`.

The fixture loader checks saved file hashes, accepting the already documented raw/LF-normalized-in-memory representation for this CRLF checkout without rewriting files. It loads only the selected candidate records for verification, restores their recorded decoder/message/padding fields, and uses the saved helper bits and enrollment IDs. Trusted fixture enrollment creates HMAC records from the enrolled synthetic credential. Evaluator labels select/assert the regression identity; they are not arguments to runtime admission and cannot influence the HMAC result. `reconstruct()` is forbidden by a spy during rejection. No failure was regenerated, and no new response was sampled. This is a two-case regression test, not the 430-case formal evaluation or a general zero-false-accept claim.

## Existing Confirmation

The existing client/server HMAC confirmation domains, transcript encoding, HKDF salt/info, and proof comparisons are unchanged. `test_client_confirmation_tamper_still_rejected` and `test_server_confirmation_tamper_still_rejected` prove tampering is still rejected after successful credential admission. Existing proof length/reflection/replay/deadline tests also remain.

Enrollment verification admits the candidate to a session attempt; confirmation proves matching session material in the fresh transcript. A pass does not authorize window release. As before, the receiver activates when accepting the client proof and sending the server proof; the sender activates only after validating that proof. Activation is not atomic across endpoints, and a tampered server proof can leave a receiver session active while the sender rejects it. This is the retained protocol behavior, not a new admission guarantee.

## Test Results

Commands were run from the repository root, using the existing Python 3.12.10 Windows ARM64 virtual environment and the previously established generic-CPU workaround. No additional dependency installation occurred.

Focused command:

```powershell
$env:PYTHONPATH = 'src/python'
$env:NUMBA_CPU_NAME = 'generic'
.\.venv\Scripts\python.exe -B -W default -m unittest tests.auth.test_credential_verifier tests.auth.test_credential_admission tests.auth.test_session tests.auth.test_layer3_integration
```

Full auth command:

```powershell
$env:PYTHONPATH = 'src/python'
$env:NUMBA_CPU_NAME = 'generic'
.\.venv\Scripts\python.exe -B -W default -m unittest discover -s tests/auth -p 'test_*.py'
```

All runs in this phase, in execution order (times are unittest-reported runtime, not shell/import wall time):

| Run | Test count | Runtime | Result | Warnings / skips |
| --- | ---: | ---: | --- | --- |
| First focused | 101 | 12.297 s | 4 failures, 0 errors | No warnings; 0 skipped |
| Corrected focused | 102 | 16.212 s | PASS | No warnings; 0 skipped |
| First full auth | 235 | 16.290 s | PASS | Existing warnings below; 0 skipped |
| Final focused after cleanup/fixture hardening | **104** | **14.840 s** | **PASS** | No warnings; 0 skipped |
| Final full auth | **237** | **16.642 s** | **PASS** | Existing warnings below; 0 skipped |

Final focused breakdown: 48 credential-verifier tests, 35 new credential-admission tests, 13 session tests, and eight Layer 3 integration tests. The final full suite contains the original 202 auth tests plus 35 new tests. No final failures, errors, or skipped tests remain.

The first focused failures were investigated and corrected:

1. The positive instrumentation test incorrectly expected calls through the original `session.derive_session_key` name for audited endpoints, which use imported aliases. Counts now distinguish aliases correctly, with an additional base-endpoint positive test.
2. The existing RNG-failure test supplied a credential that is now correctly rejected before RNG access. It now supplies the legitimately enrolled credential to continue testing RNG failure at the intended stage.
3. A duplicate busy request incorrectly revoked the original consumed authorization, causing later confirmation parsing to see a sender failure. Receiver cleanup now revokes only authorization consumed by the failing invocation; the original pending handshake survives a refused duplicate.
4. The existing session-ID-collision test reused a completed sender request/authorization. It now starts a new, independently verified attempt before injecting the receiver's collision sequence.

After the first all-green full run, an additional base sender request-framing-failure cleanup test and sender attempt-swap test were added. Request construction is now inside the existing failure-cleanup guard. The saved regressions were tightened to use their actual saved helpers. Final focused/full runs above validate those changes.

Full-suite warnings are unchanged matplotlib/pyparsing deprecations: `oneOf` to `one_of`, `parseString` to `parse_string`, `resetCache` to `reset_cache`, and `enablePackrat` to `enable_packrat`; matplotlib's classic style also prints the `parseString` and `resetCache` messages. They are not suppressed or treated as passes for failed tests. Git also warns that the checkout policy may replace LF with CRLF in modified source files when Git next touches them; protected evidence was not normalized.

Old test semantics intentionally changed: valid-format wrong-credential tests (including the six-error synthetic miscorrection) now expect pre-HKDF admission failure rather than post-HKDF `key_confirmation_failed`; receiver tombstones are not expected when no request is sent. Valid fixture requests must carry real service-issued authorization. Low-level HKDF/transcript/proof-vector tests remain isolated primitive tests and do not manufacture an admission bypass. Historical config acceptance was replaced with current-config acceptance plus explicit historical-config rejection. No unverified legacy fixture path was retained in supported session APIs.

## Unchanged Components

Before/after raw-byte SHA-256 comparison covered **250 protected existing files**, including every one of the **243 saved result files** under `results/`. Every captured file remained byte-identical, and no saved result file was added or removed.

| Protected source | Unchanged SHA-256 |
| --- | --- |
| `src/python/puf_snn/reconstruction/bch.py` | `5bb11f2901a94c552c1b453eea092603d49cd749d476b07541a615487dffe1f8` |
| `src/python/puf_snn/reconstruction/credential.py` | `865ac1b9c26e439c872a7b7376ae393c79b324d389286c51f70be82e6d438193` |

Unchanged components/artifacts:

- BCH and reconstruction source, including the reconstruction runner.
- Wire 2 bytes, authenticated-window encoding and `binary_window.py`.
- Per-window HMAC and window verification/release behavior.
- HKDF, transcript, framing and client/server confirmation primitives.
- Formal Layer 2 evidence and historical reconstruction manifests.
- Historical Tier 1 evidence and `docs/layer3-baseline-v1-manifest.json`.
- Historical authentication-v1 config and auth-audit-v1 schema.

In addition to byte hashes and golden/vector tests, AST comparison against the existing Git revision confirmed unchanged `hkdf_extract`, `hkdf_expand`, `derive_session_key`, `client_proof`, `server_proof`, `frame`, `unframe`, `_parse_confirmation`, `Limits`, `Transcript`, `Sender.seal_window`, and `Verifier.verify_window`. Source syntax/whitespace and report links/sections were checked separately. These checks do not imply the modified session-control source still matches the frozen baseline manifest.

## Remaining Work

- Implement audit-v2 with explicit verification/derivation events and measurement fields. Current generic v1 refusals cannot distinguish all admission failure causes in persisted audits.
- Implement and run the separate **430-case formal verifier evaluation**, with sealed inputs, complete outcome reconciliation and both-endpoint HKDF counters. Only the two required saved nominal regressions were evaluated here.
- Measure verifier latency and reconstruction-plus-verification timing under a defined methodology; unittest runtimes are not verifier latency measurements.
- Update the pipeline benchmark and other dependent current runners to the new profile and material API, with clearly versioned reporting. Old benchmark/stream configs currently fail explicit version validation.
- Define a new Tier 1 profile/source baseline only if required for later evaluation; do not relabel or modify frozen artifacts.
- Strengthen deployment/lifecycle controls if expanding beyond this trusted local pilot: protected key/reference custody, persistent enrollment generations, rotation, remote transport/attestation, resource limits and background cleanup. Local revocation does not retroactively erase already-derived keys or close existing authenticated sessions. It must win before the relevant admission operation to deny that operation; arbitrary concurrent mutation of private state is not a supported lifecycle API.

The credential remains only 32 bits. Verifier-key-plus-record compromise permits exhaustive offline search; the unchanged reference registry and research fixtures expose credentials under their existing assumptions; captured Layer 3 confirmation traffic can still test guesses offline. Identical credential bytes do not prove a physical device of origin. No production security, malicious-process isolation, secure Python-byte erasure, or general zero-false-accept guarantee is claimed.

The supported local flow now enforces independent verification before request emission and receiver derivation, with tested rejection on both required saved miscorrections. It is ready for a separately authorized formal verifier evaluation, with the remaining reporting and lifecycle limitations above kept explicit.
