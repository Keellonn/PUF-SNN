# Independent Pre-HKDF Credential Verification

**Owner:** Will Wallace  
**Week:** 5  
**Status:** Completed

## Purpose

The purpose of the independent credential verifier is to prevent a reconstructed credential from reaching session-key derivation merely because BCH decoding succeeded and the returned message had valid padding.
The formal Layer 2 reconstruction experiment demonstrated that, once the number of response-bit errors exceeds the BCH correction radius, the decoder can occasionally return a syntactically valid but incorrect credential.
Before this Week 5 change, a valid-format reconstructed candidate could enter Layer 3 session establishment and reach HKDF. If the reconstructed credential was wrong, the mismatch would eventually be detected by mutual session-key confirmation, but only after key derivation had already occurred.
The new verifier adds an independent credential-authenticity decision between Layer 2 reconstruction and Layer 3 session-key derivation.
The required pipeline is now:

`PUF reconstruction -> candidate validation -> independent credential verification -> local admission authorization -> HKDF -> session confirmation -> authenticated windows`

A wrong valid-format candidate is therefore rejected before it can initiate session-key derivation.

## Motivation

### Layer 2 Miscorrection Problem
The frozen Layer 2 construction uses,
- BCH(63,36,t=5)
- 63 selected PUF response bits
- a 32-bit pilot credential
- four zero padding bits
- one noisy response and one BCH decode per attempt

The formal Layer 2 experiment evaluated 84,000 reconstruction attempts and identified 430 valid-format wrong credentials.
These were not decoder failures or padding failures. In each case, BCH returned a complete 36-bit message whose four padding bits were valid, but the resulting 32-bit credential did not match the enrolled credential.

The nominal experiment contained two such cases,
- seed 2222, device 3, attempt 88
- seed 6543, device 1, attempt 75

The remaining 428 occurred in the formal noise sweep.
These observations showed that successful decoding and correct message formatting are not sufficient to establish credential authenticity.

### Why Padding Validation Is Not Enough
The four zero padding bits provide a simple format check.
They can detect some incorrect decoded messages because a random incorrect message may produce nonzero padding.
However, padding does not authenticate the credential.
A wrong decoded message can still end in `0000`, allowing the first 32 bits to appear as a valid credential even though they differ from the enrolled value.
The credential verifier therefore performs a separate comparison against information created during trusted enrollment.
The roles are intentionally separated,
- BCH determines whether a candidate message can be reconstructed
- Padding checks whether that message has the expected format
- Credential verification determines whether the returned credential corresponds to the trusted enrollment
- Session confirmation later verifies that both endpoints derived the same session key

## Security Goal
A reconstructed credential may be supplied to HKDF only when all of the following are true,
- Reconstruction produced a coherent valid-format candidate
- The candidate passes the independent enrollment verifier
- The candidate is associated with the correct trusted device and enrollment context
- The same exact candidate that passed verification is the candidate later used for session-key derivation

A prior verification result from another device, enrollment, candidate, request, or session attempt is not sufficient.

For a rejected candidate, the intended behavior is,
- credential verification fails
- no P3RQ is emitted
- no receiver pending session is created
- sender HKDF is not executed
- receiver HKDF is not executed
- no confirmation proof is generated
- no new session becomes active
- no authenticated sensor window can be released from that attempt

A successful credential verification grants permission to attempt session establishment. It does not by itself establish an active session or authorize sensor-window release.

## Threat Model

The Week 5 implementation is a trusted, co-located software research pilot.
The design assumes that the credential-admission service, sender, receiver, and enrollment logic execute within the trusted local software environment.
The adversary may attempt to,
- submit a wrong but valid-format reconstructed credential
- substitute public helper or routing information
- use the wrong device or enrollment context
- reuse or swap an admission authorization
- corrupt or replace verifier records
- access the verifier-record database
- observe public protocol traffic
- attempt session establishment through exposed software APIs

The implementation is designed to fail closed when verifier records, keys, bindings, or authorization state are missing or inconsistent.
The design does not treat Python process boundaries as strong isolation. An attacker that fully controls the trusted process can bypass software checks or read process memory.
The implementation is therefore not remote attestation and is not intended to prove the physical origin of credential bytes.


## Design Alternatives

### Public Hash
One considered design was to store a public value such as,
`SHA256(device_id || credential)`
and compare the reconstructed credential against that value.
This was rejected because the pilot credential contains only 32 bits.
A public verifier would provide an attacker with a direct offline test for every possible credential value. At most `2^32` candidate values would need to be checked.
Adding a public device identifier or salt would separate records but would not increase the entropy of the underlying credential.
A public unkeyed hash was therefore not used.

### Keyed HMAC
The selected design stores an HMAC tag generated using a secret key that is independent of the PUF credential, helper data, and Layer 3 session keys.
Without access to the verifier key, theft of the tag-only verifier database does not provide the same standalone public credential-checking predicate as an unkeyed hash.
This design also allows the verifier to bind the credential to trusted device, enrollment, reconstruction, and key-version context.
The keyed HMAC approach was selected for the software pilot.

### Encrypted Reference
Another considered design was to encrypt the enrolled credential using an independent server-side key and compare the reconstructed credential against the decrypted reference.
This could provide authenticated protection for the enrolled reference at rest.
However, it also gives the verifier direct recoverability of the credential and introduces encryption-key, nonce, decryption, storage, and rotation requirements that are unnecessary for demonstrating the pre-HKDF admission property.
Encrypted reference storage remains a possible future storage-protection improvement, but it was not required for this Week 5 implementation.

### Direct Credential Comparison
The existing Layer 3 receiver already maintains access to a reference credential for session-key derivation.
The reconstructed candidate could therefore have been compared directly against that stored credential before HKDF.
This would catch miscorrections, but it would require the admission mechanism itself to access the recoverable credential and would provide no separation between routine verification data and the raw enrolled secret.
The selected HMAC verifier instead uses a tag-only verification record and a separate verifier key.
The existing raw reference credential remains a pilot limitation because it is still required by the current receiver for HKDF.


## Selected Verifier Design

### HMAC Construction
The verifier uses full-length HMAC-SHA-256.
The input is constructed using length-prefixed fields:
`LP(x) = U16-big-endian(byte_length(x)) || x`

The authenticated verifier message is,
`LP("PUF-SNN/credential-verifier/v1")`  
`|| LP(canonical_device_id)`  
`|| LP(enrollment_id)`  
`|| LP(reconstruction_id)`  
`|| LP(verifier_key_id)`  
`|| credential4`

The enrollment verifier is,
`HMAC-SHA256(K_verify, message)`
The complete 32-byte HMAC tag is retained.
The credential is included as exactly four bytes, preserving leading zeros.
Identifiers are treated as exact case-sensitive values rather than being automatically trimmed, case-folded, or normalized.
Verification uses `hmac.compare_digest` rather than ordinary short-circuit byte equality.

### Verifier Key

`K_verify` is an independent 32-byte verifier key.
It is not derived from,
- the PUF response
- the reconstructed credential
- the enrolled credential
- helper data
- the simulation seed
- HKDF
- the session key

Production-like pilot execution generates the verifier key using operating-system randomness.
Deterministic keys are used only where necessary in unit-test fixtures.
The key is stored separately from verifier records. Verifier records contain only a nonsecret key identifier.
There is no default or fallback key when the requested key is unavailable.

### Enrollment Record
Trusted enrollment creates a verifier record containing the information required to reproduce the HMAC comparison.
The record contains,
- schema/version information
- HMAC algorithm identifier
- canonical device ID
- enrollment ID
- reconstruction-profile ID
- verifier key ID
- full 32-byte HMAC tag
- enabled/revoked lifecycle state

The verifier record does not contain,
- plaintext credential bytes
- PUF reference-response bits
- verifier-key bytes
- session keys

The same enrolled credential is used transiently during trusted provisioning to generate both the normal Layer 2 enrollment material and the verifier tag.
Runtime credential verification does not receive evaluator truth or the enrolled credential as an input.

### Device and Enrollment Binding
The HMAC is bound to more than the four credential bytes.
It also includes the trusted,
- device identity
- enrollment identity
- reconstruction profile
- verifier-key identity

This prevents a verifier record for one context from simply being relabeled as another context.
The runtime admission service also checks that the trusted sender binding, verifier record, enrollment generation, and session context agree.
One limitation remains: if two devices genuinely have the exact same 32-bit credential value and each is correctly provisioned with its own verifier tag, presenting those same credential bytes to the second device can match that device's own tag.
The verifier authenticates the enrolled credential value under a trusted device context. It cannot prove the physical origin of identical credential bytes.

### Security Limitations
The underlying credential remains only 32 bits.
A 256-bit HMAC key and 256-bit HMAC output do not turn the credential itself into a 256-bit secret.
If an attacker obtains both the verifier key and verifier records, the attacker can test the entire 32-bit credential space.
The existing protocol also still permits traffic-based offline credential guessing under the 32-bit pilot assumption. An observer with sufficient public handshake information can test guessed credentials against key-dependent protocol proofs.
The verifier therefore removes one specific problem — admission of an unverified reconstructed credential into HKDF — but does not solve the underlying low-entropy credential limitation.

## Standalone Implementation

### Credential Verifier Module

The verifier was implemented in,
`src/python/puf_snn/auth/credential_verifier.py`

The module contains the credential-verification and local-admission functionality separately from the existing authenticated-window verifier.
Its responsibilities include,
- verifier-record creation
- HMAC framing
- key-provider access
- tag comparison
- trusted binding validation
- structured verification results
- local admission authorization

### Key Provider
The verifier accesses `K_verify` through a separate key-provider abstraction.
The in-memory research implementation supports independently generated 32-byte keys and retrieval through a nonsecret key ID.
An unknown, missing, or unavailable key causes verification to fail closed.
The implementation does not silently replace missing key material or fall back to a default key.
Normal object representations are designed not to expose verifier-key material.

### Verifier Record Store
Verifier records are stored separately from verifier keys.
Records are retrieved using trusted enrollment context rather than by accepting arbitrary candidate-controlled identity information.
The store requires coherent device and enrollment bindings and rejects unsupported, disabled, or inconsistent records.
The runtime record does not store the raw enrolled credential.

### Verification Results
The standalone verifier uses structured outcomes rather than a simple public boolean.
Supported result categories include,
- `verified`
- `credential_mismatch`
- `record_missing`
- `record_disabled`
- `unsupported_record`
- `key_unavailable`
- `binding_mismatch`
- `invalid_input`
- `internal_error`
Only `verified` permits the candidate to continue into session admission.

### Failure Behavior
For a valid-format candidate that does not match the trusted enrollment verifier:
`credential_verification_failed`
is returned to the session layer.

The verifier does not,
- substitute the enrolled credential
- retry using alternate keys
- automatically create a verifier record
- modify the candidate
- fall back to direct comparison
- permit session establishment because padding was valid


## Pre-HKDF Session Integration

### Previous Session Flow
Before the Week 5 credential-admission change, the effective candidate-to-session path was:

`reconstruction -> valid-format candidate -> P3RQ/session setup -> HKDF -> mutual confirmation`

A wrong but valid-format credential could therefore reach session-key derivation.

Because the sender and receiver would derive different keys, mutual confirmation would eventually reject the session.

This protected the final session from becoming active, but the rejection occurred after HKDF.

### New Session Flow

The current supported flow is,
`PUF reconstruction`  
`-> candidate format/coherence checks`  
`-> independent credential verification`  
`-> local admission authorization`  
`-> P3RQ`  
`-> receiver authorization check`  
`-> receiver HKDF`  
`-> sender HKDF`  
`-> mutual session confirmation`  
`-> active session`  
`-> authenticated sensor windows`

The credential verifier therefore acts as a gate between Layer 2 reconstruction and Layer 3 key establishment.

### Sender Admission Gate
The sender performs credential verification after reconstruction-result coherence checks and before generating the session request.
A valid-format candidate must pass the configured credential-admission service before request creation.

If verification fails,
- the attempt becomes terminal
- no request is emitted
- no client session nonce/request is released into the session path
- no sender HKDF occurs

Only a verified candidate receives a local admission authorization.

### Local Admission Authorization
Successful verification produces an opaque local authorization handle.
The authorization is not placed into Wire 2 and is not serialized as part of the network/session request.
It is maintained by the trusted local credential-admission service and is bound to the specific,
- service instance
- device
- enrollment
- reconstruction profile
- candidate
- session attempt
- request
- receiver transcript context

The authorization is single-use.
Forged, swapped, stale, revoked, foreign-service, or replayed authorizations are rejected.
A public value such as `verified=True` is not sufficient to bypass the admission service.

### Receiver Authorization Gate
The receiver must consume the trusted local authorization before session derivation begins.
The receiver checks that the authorization corresponds to the exact request and trusted enrollment context.
Only after successful authorization may the receiver,
- allocate the new pending session
- derive session-key material
- construct the challenge

A direct receiver request without the required local admission authorization is rejected before HKDF.

### Candidate Continuity
The same candidate that passed independent verification must be the candidate used later by the sender for session-key derivation.
The implementation prevents the verified candidate from being replaced with,
- another reconstructed candidate
- the enrolled reference credential
- caller-provided replacement bytes

This preserves the meaning of the experiment,
the system is testing whether the actual reconstructed credential is correct enough to enter Layer 3, rather than silently correcting it using evaluator truth.

### Failure Path

For a wrong valid-format credential, the integrated path is,
`wrong candidate`  
`-> credential verification failure`  
`-> no admission authorization`  
`-> no P3RQ`  
`-> no receiver pending session`  
`-> sender HKDF = 0`  
`-> receiver HKDF = 0`  
`-> no client/server confirmation`  
`-> no new active session`

An already active unrelated session remains unchanged by the failed attempt.

## Authentication v2

### Configuration

The new supported authentication configuration is,
`configs/authentication_v2.json`
The configuration identifies the current credential-admission behavior separately from the historical Layer 3 v1 baseline.
The current profile is,
`puf-snn-l3-credential-admission-v1-wire2`

The configuration version is,
`puf-snn-auth-config-v2`

Historical Layer 3 v1 manifests and evidence were preserved rather than rewritten to describe the new implementation.

### What Changed
Week 5 added,
- independent enrollment credential verification
- separate verifier-key handling
- tag-only verifier records
- mandatory sender credential admission
- opaque local admission authorization
- mandatory receiver authorization before HKDF
- candidate continuity between verification and HKDF
- current authentication-v2 configuration
- fail-closed handling for missing or inconsistent verifier state


### What Stayed the Same
The following cryptographic and reconstruction components were intentionally left unchanged,
- BCH reconstruction
- helper-data construction
- 32-bit credential format
- HKDF extract/expand implementation
- session-key derivation formula
- client confirmation proof
- server confirmation proof
- Wire 2 format
- authenticated-window encoding
- per-window HMAC
- replay/order verification
- accepted-payload release logic

The new verifier changes when session-key derivation is permitted, not the HKDF or authenticated-window algorithms themselves.

## Testing

### Standalone Verifier Tests
The standalone credential-verifier implementation added 48 dedicated unit tests.
These tests covered areas including,
- correct credentials
- incorrect credentials
- fixed HMAC behavior
- record validation
- missing records
- disabled/revoked records
- key availability
- wrong keys
- device binding
- enrollment binding
- reconstruction-profile binding
- malformed inputs
- tag corruption
- tag length/type errors
- identifier validation
- constant-time comparison behavior
- credential leading-zero handling
- same-credential cross-device limitation behavior
- secret-safe object representations

Results,
- New verifier tests: 48 passed
- Full auth suite at the standalone phase: 202 passed
- Existing auth tests included in that run: 154
- Final failures: 0

The standalone phase deliberately did not change session/HKDF behavior.

### Session Integration Tests
The pre-HKDF integration added 35 dedicated admission/integration tests.
The tests explicitly instrumented both sender and receiver derivation paths.
Negative cases checked that rejected credentials produced zero calls to,
- sender session-key derivation
- receiver session-key derivation
- HKDF extract
- HKDF expand
- session confirmation
- new pending/active session creation

The integration tests also covered,
- missing admission
- forged authorization
- swapped request authorization
- wrong-device authorization
- wrong-enrollment authorization
- reconstruction-profile mismatch
- authorization replay
- stale/revoked authorization
- candidate swapping
- failed admission while another valid session remains active
- valid handshake after successful admission
- confirmation tampering after successful credential verification
- authenticated-window operation after the new handshake

Final test results,
- New integration tests: 35
- Focused auth tests: 104 passed
- Full auth suite: 237 passed
- Failures: 0
- Errors: 0
- Skips: 0

### Saved Miscorrection Regressions
The integration suite includes the two nominal miscorrections identified by the formal Layer 2 experiment:
**Seed 2222 / device 3 / attempt 88**
and
**Seed 6543 / device 1 / attempt 75**
These cases use the saved formal reconstruction evidence rather than rerunning reconstruction.
Both candidates were rejected by the independent verifier before session-key derivation.
For each case,
- verifier rejection occurred
- no P3RQ was emitted
- sender HKDF count was 0
- receiver HKDF count was 0
- no confirmation occurred
- no new session became active

These saved regressions ensure that the specific failure mode that motivated the verifier remains covered by the authentication test suite.

## Security Interpretation
The Week 5 verifier changes the meaning of the boundary between reconstruction and session establishment.
A valid BCH result is now treated as a credential candidate rather than automatically being treated as authenticated credential material.
This produces three distinct decisions,
**Layer 2 reconstruction:**  
Can a candidate credential be recovered from the noisy PUF response?
**Credential admission:**  
Does that candidate match the credential information established during trusted enrollment?
**Layer 3 session confirmation:**  
Did both endpoints derive matching session-key material for the current handshake?
These checks are complementary.
The credential verifier does not replace BCH reconstruction or mutual session confirmation.
Instead, it prevents known-invalid reconstructed credentials from reaching the key-derivation stage while retaining confirmation as a separate defense for successfully admitted handshakes.
This gives the software prototype a clearer fail-closed security boundary,
`reconstruction success != credential authentication`
Only independently verified candidates can enter the supported session-establishment path.


## Limitations
- The credential remains a deterministic 32-bit proof-of-mechanism value
- A 256-bit HMAC tag does not provide 256 bits of effective credential security
- The verifier does not eliminate offline guessing made possible by the underlying 32-bit credential and observable protocol traffic
- Compromise of both verifier records and the verifier key allows exhaustive credential guessing
- Compromise of the existing Layer 3 raw reference-credential registry directly exposes the enrolled credential
- The implementation assumes a trusted co-located software process
- The local authorization handle is a control-flow mechanism, not remote attestation
- The verifier does not prove that credential bytes originated from a particular physical device
- Equal credential values on two devices cannot be distinguished by credential value alone
- Python memory management does not provide guaranteed secret zeroization
- The current verifier-key provider and enrollment lifecycle are research-pilot mechanisms rather than production key-management infrastructure
- Operational audit-v2 events have not been implemented; current wrappers retain the older coarse audit vocabulary
- No physical PUF or hardware-backed key storage was used
- No production-security claim is made
- A future production design would require substantially higher independently justified credential entropy, protected key custody, enrollment/revocation design, abuse controls, and separate security review

## Reproducibility

### Important Files
Primary verifier implementation,
`src/python/puf_snn/auth/credential_verifier.py`

Session integration,
`src/python/puf_snn/auth/session.py`

Sender wrapper,
`src/python/puf_snn/auth/sender.py`

Receiver/verifier wrapper,
`src/python/puf_snn/auth/verifier.py`

Authentication configuration support,
`src/python/puf_snn/auth/config.py`

Public authentication exports,
`src/python/puf_snn/auth/__init__.py`

Standalone verifier tests,
`tests/auth/test_credential_verifier.py`

Credential-admission integration tests,
`tests/auth/test_credential_admission.py`

Additional affected session/integration tests are maintained under,
`tests/auth/`

### Config
Current credential-admission authentication configuration:
`configs/authentication_v2.json`
The historical authentication-v1 configuration and Layer 3 baseline manifests remain preserved as historical contracts.
The Week 5 implementation intentionally introduced a new current profile instead of rewriting the frozen historical authentication baseline.

### Evidence References
The reconstruction behavior that motivated the verifier is recorded in:
`results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/`
The two nominal saved regression cases are present in the formal Layer 2 `attempts.jsonl`.
The population-level credential-verifier experiment is stored separately at:
`results/week-5/will/credential-verifier/credential-verifier-v1-formal-001/`
The formal verifier experiment reused saved Layer 2 candidates and did not rerun reconstruction.

## Formal Evaluation

Formal population-level credential-verifier results are maintained separately in:
`docs/credential-verifier-formal-results-week5.md`
That formal evaluation uses the saved 84,000-attempt Layer 2 population and evaluates credential admission separately from reconstruction.
The architecture and implementation described in this document should therefore be read together with the formal results report, while the formal results report and its sealed evidence should remain unchanged.